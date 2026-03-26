# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "zvec",
# ]
# ///

from pathlib import Path
from typing import Any

from indexer import embed_text, load_chunks, tokenize


def _rows_to_citations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for row in rows[:3]:
        citations.append(
            {
                "doc_id": row.get("doc_id") or row.get("note_id") or row.get("path"),
                "chunk_id": row.get("chunk_id"),
                "snippet": row.get("text", "")[:180],
            }
        )
    return citations


def _rows_to_related(rows: list[dict[str, Any]]) -> list[str]:
    related: list[str] = []
    for row in rows[:3]:
        if row.get("path") and row["path"] not in related:
            related.append(row["path"])
    return related


def _passes_filters(item: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    for key, wanted in filters.items():
        current = item.get(key)
        if isinstance(current, list) and isinstance(wanted, list):
            # list/list filters use overlap semantics (any shared value matches).
            if not set(current) & set(wanted):
                return False
            continue
        if isinstance(current, list):
            if wanted not in current:
                return False
            continue
        if isinstance(wanted, list):
            if current not in wanted:
                return False
            continue
        if current != wanted:
            return False
    return True


def _semantic_search_zvec(
    workspace_root: Path,
    query: str,
    limit: int,
    filters: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    import zvec  # type: ignore

    zvec_dir = workspace_root / "rag" / "index" / "zvec"
    if not zvec_dir.exists():
        raise FileNotFoundError(
            "zvec index not found. Run build_index() before semantic search."
        )

    rows = load_chunks(workspace_root)
    by_chunk_id = {str(row.get("chunk_id", "")): row for row in rows}

    collection = zvec.open(path=str(zvec_dir))
    raw_results = collection.query(
        zvec.VectorQuery("embedding", vector=embed_text(query)),
        topk=max(limit * 4, limit),
    )

    results: list[dict[str, Any]] = []
    for hit in raw_results:
        chunk_id = str(hit.get("id", "")) if isinstance(hit, dict) else ""
        if not chunk_id:
            continue
        item = by_chunk_id.get(chunk_id)
        if not item:
            continue
        if not _passes_filters(item, filters):
            continue
        score_raw = hit.get("score", 0.0) if isinstance(hit, dict) else 0.0
        score = float(score_raw)
        row = dict(item)
        row["semantic_score"] = score
        results.append(row)
        if len(results) >= limit:
            break
    return results


def _keyword_score(query_token_set: set[str], row: dict[str, Any]) -> float:
    tokens = row.get("tokens")
    if isinstance(tokens, list):
        doc_tokens = [str(token).lower() for token in tokens]
    else:
        doc_tokens = tokenize(str(row.get("text", "")))
    return float(sum(1 for token in doc_tokens if token in query_token_set))


def semantic_search(
    workspace_root: Path,
    query: str,
    limit: int = 8,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return _semantic_search_zvec(workspace_root, query, limit=limit, filters=filters)


def keyword_search(
    workspace_root: Path,
    query: str,
    limit: int = 8,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    q_tokens = tokenize(query)
    q_token_set = set(q_tokens)
    if not q_token_set:
        return []

    results: list[dict[str, Any]] = []
    for item in load_chunks(workspace_root):
        if not _passes_filters(item, filters):
            continue
        score = _keyword_score(q_token_set, item)
        if score <= 0:
            continue
        row = dict(item)
        row["keyword_score"] = float(score)
        results.append(row)
    return sorted(results, key=lambda x: x["keyword_score"], reverse=True)[:limit]


def hybrid_search(
    workspace_root: Path,
    query: str,
    limit: int = 8,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    query_token_set = set(tokenize(query))
    if not query_token_set:
        return []

    expanded_limit = max(limit * 4, limit)
    semantic_rows = semantic_search(
        workspace_root, query, limit=expanded_limit, filters=filters
    )
    keyword_rows = keyword_search(
        workspace_root, query, limit=expanded_limit, filters=filters
    )

    scored_by_chunk: dict[str, dict[str, Any]] = {}

    for row in semantic_rows:
        chunk_id = str(row.get("chunk_id", ""))
        if not chunk_id:
            continue
        out = dict(row)
        out["semantic_score"] = float(out.get("semantic_score", 0.0))
        out.setdefault("keyword_score", 0.0)
        scored_by_chunk[chunk_id] = out

    for row in keyword_rows:
        chunk_id = str(row.get("chunk_id", ""))
        if not chunk_id:
            continue
        out = scored_by_chunk.get(chunk_id, dict(row))
        out.setdefault("semantic_score", 0.0)
        out["keyword_score"] = float(row.get("keyword_score", 0.0))
        scored_by_chunk[chunk_id] = out

    scored: list[dict[str, Any]] = []
    for row in scored_by_chunk.values():
        semantic_score = float(row.get("semantic_score", 0.0))
        keyword_score = float(row.get("keyword_score", 0.0))
        if semantic_score <= 0 and keyword_score <= 0:
            continue
        row["hybrid_score"] = semantic_score + keyword_score * 0.1
        scored.append(row)

    ranked = sorted(scored, key=lambda x: x["hybrid_score"], reverse=True)
    return ranked[:limit]


def rerank_results(query: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    query_tokens = set(tokenize(query))
    q_len = len(query_tokens) or 1
    reranked = []
    for row in rows:
        coverage = len(set(tokenize(row.get("text", ""))) & query_tokens) / q_len
        out = dict(row)
        out["rerank_score"] = float(row.get("hybrid_score", 0.0)) + coverage * 0.2
        reranked.append(out)
    return sorted(reranked, key=lambda x: x["rerank_score"], reverse=True)


def answer_from_context(question: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "answer": "unknown",
            "citations": [],
            "related_notes": [],
            "confidence": "low",
            "question": question,
        }

    top = rows[0]
    if float(top.get("rerank_score", top.get("hybrid_score", 0.0))) < 0.15:
        return {
            "answer": "unknown",
            "citations": [],
            "related_notes": [],
            "confidence": "low",
            "question": question,
        }

    citations = _rows_to_citations(rows)
    related = _rows_to_related(rows)

    answer = top.get("text", "").strip()
    return {
        "answer": answer,
        "citations": citations,
        "related_notes": related,
        "confidence": "medium" if len(citations) > 1 else "low",
        "question": question,
    }


def ask_with_citations(
    workspace_root: Path,
    question: str,
    filters: dict[str, Any] | None = None,
    limit: int = 8,
    use_cloud_generation: bool = False,
    cloud_generator: Any | None = None,
) -> dict[str, Any]:
    rows = hybrid_search(workspace_root, question, limit=limit, filters=filters)
    rows = rerank_results(question, rows)
    local_result = answer_from_context(question, rows)

    if not use_cloud_generation:
        return local_result

    if not callable(cloud_generator):
        return local_result

    try:
        generated = cloud_generator(question, rows)
    except Exception as exc:
        fallback = dict(local_result)
        fallback["cloud_error"] = f"{exc.__class__.__name__}: {exc}"
        return fallback

    generated_answer = ""
    if isinstance(generated, dict):
        generated_answer = str(generated.get("answer", "")).strip()
    else:
        generated_answer = str(generated).strip()

    if not generated_answer or generated_answer == "unknown":
        fallback = dict(local_result)
        fallback["cloud_error"] = "invalid_cloud_output"
        return fallback

    cloud_result = dict(local_result)
    cloud_result["answer"] = generated_answer
    local_low_evidence = (
        local_result.get("answer") == "unknown"
        or str(local_result.get("confidence", "")).lower() == "low"
    )
    cloud_result["confidence"] = "low" if local_low_evidence else "medium"
    cloud_result["answer_source"] = "cloud_generated"

    if not cloud_result.get("citations"):
        cloud_result["citations"] = _rows_to_citations(rows)
    if not cloud_result.get("related_notes"):
        cloud_result["related_notes"] = _rows_to_related(rows)

    if not cloud_result.get("citations"):
        fallback = dict(local_result)
        fallback["cloud_error"] = "cloud_output_without_evidence"
        return fallback

    return cloud_result

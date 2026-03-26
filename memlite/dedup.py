import hashlib
import json
import uuid
from datetime import datetime
from difflib import SequenceMatcher
from math import sqrt
from pathlib import Path
from typing import Any

from frontmatter import parse_frontmatter
from indexer import build_index, load_chunks, tokenize
from knowledge_store import (
    get_document_by_id,
    list_documents,
    now_iso,
    update_document_meta,
)
from rag import keyword_search, semantic_search
from storage import init_db, with_db


def _db_path(workspace_root: Path) -> Path:
    return (workspace_root / "kb.db").resolve()


def _groups_cache_path(workspace_root: Path) -> Path:
    path = workspace_root / "rag" / "index" / "dedup_groups.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _dedup_eval_report_path(workspace_root: Path) -> Path:
    path = workspace_root / "rag" / "index" / "dedup_eval_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _normalized_text(text: str) -> str:
    return " ".join(tokenize(text))


def _group_id_for(doc_ids: list[str]) -> str:
    signature = "|".join(sorted(doc_ids))
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:12]
    return f"grp-{digest}"


def _similarity(text_a: str, text_b: str) -> float:
    normalized_a = _normalized_text(text_a)
    normalized_b = _normalized_text(text_b)
    if not normalized_a or not normalized_b:
        return 0.0
    set_a = set(normalized_a.split())
    set_b = set(normalized_b.split())
    union = set_a | set_b
    token_score = float(len(set_a & set_b)) / float(len(union)) if union else 0.0
    sequence_score = SequenceMatcher(None, normalized_a, normalized_b).ratio()
    return round(max(token_score, sequence_score), 4)


def _thresholds(profile: dict[str, float] | None) -> tuple[float, float]:
    profile = profile or {}
    auto_threshold = float(profile.get("auto", 0.93))
    review_threshold = float(profile.get("review", 0.85))
    if review_threshold > auto_threshold:
        review_threshold = auto_threshold
    return auto_threshold, review_threshold


def _load_dedup_eval_report(workspace_root: Path) -> dict[str, Any] | None:
    report_path = _dedup_eval_report_path(workspace_root)
    if not report_path.exists():
        return None
    try:
        parsed = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _label_is_duplicate(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) > 0.0
    normalized = str(value).strip().lower()
    return normalized in {"duplicate", "dup", "match", "positive", "true", "1"}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) != 0.0
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y", "t", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "f", "off", "", "none", "null"}:
        return False
    return False


def _wilson_lower_bound(
    successes: int, total: int, z: float = 1.959963984540054
) -> float:
    if total <= 0:
        return 0.0
    phat = float(successes) / float(total)
    z2 = z * z
    denominator = 1.0 + (z2 / float(total))
    center = phat + (z2 / (2.0 * float(total)))
    margin = z * sqrt(
        (phat * (1.0 - phat) / float(total)) + (z2 / (4.0 * total * total))
    )
    lower = (center - margin) / denominator
    return round(max(0.0, lower), 6)


def run_dedup_eval(workspace_root: Path, labeled_pairs_path: Path) -> dict[str, Any]:
    payload = json.loads(labeled_pairs_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        pairs = payload
        labeling_provenance: dict[str, Any] = {}
    elif isinstance(payload, dict):
        raw_pairs = payload.get("pairs", [])
        pairs = raw_pairs if isinstance(raw_pairs, list) else []
        raw_provenance = payload.get("labeling_provenance", {})
        labeling_provenance = (
            dict(raw_provenance) if isinstance(raw_provenance, dict) else {}
        )
    else:
        pairs = []
        labeling_provenance = {}

    normalized_pairs: list[dict[str, Any]] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        normalized_pairs.append(pair)

    pair_count = len(normalized_pairs)
    hard_negative_count = sum(
        1
        for pair in normalized_pairs
        if _parse_boolish(
            pair.get("hard_negative", pair.get("is_hard_negative", False))
        )
    )

    auto_candidates = [
        pair
        for pair in normalized_pairs
        if _to_float(pair.get("score", pair.get("similarity", 0.0))) >= 0.93
    ]
    auto_candidate_count = len(auto_candidates)
    auto_candidate_true_positive_count = sum(
        1
        for pair in auto_candidates
        if _label_is_duplicate(pair.get("label", pair.get("is_duplicate", False)))
    )

    precision = (
        float(auto_candidate_true_positive_count) / float(auto_candidate_count)
        if auto_candidate_count
        else 0.0
    )
    wilson_lower_bound = _wilson_lower_bound(
        auto_candidate_true_positive_count,
        auto_candidate_count,
    )

    reviewer_count = labeling_provenance.get("reviewer_count")
    reviewer_count_valid = (
        isinstance(reviewer_count, int)
        and not isinstance(reviewer_count, bool)
        and reviewer_count >= 2
    )
    adjudication = labeling_provenance.get("adjudication")
    adjudication_valid = _parse_boolish(adjudication)
    has_labeling_provenance = reviewer_count_valid and adjudication_valid

    protocol_checks = {
        "pair_count": pair_count >= 1000,
        "hard_negatives": hard_negative_count > 0,
        "labeling_provenance": has_labeling_provenance,
    }
    protocol_passed = all(protocol_checks.values())
    auto_merge_enabled = protocol_passed and wilson_lower_bound > 0.95

    report = {
        "pair_count": pair_count,
        "hard_negative_count": hard_negative_count,
        "labeling_provenance": {
            "reviewer_count": reviewer_count,
            "adjudication": adjudication,
        },
        "auto_candidate_count": auto_candidate_count,
        "auto_candidate_true_positive_count": auto_candidate_true_positive_count,
        "precision": round(precision, 6),
        "wilson_lower_bound": wilson_lower_bound,
        "protocol_checks": protocol_checks,
        "protocol_passed": protocol_passed,
        "auto_merge_enabled": auto_merge_enabled,
        "fallback_mode": "review_queue" if not auto_merge_enabled else "auto_merge",
    }

    _dedup_eval_report_path(workspace_root).write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    return report


def _persist_group_cache(workspace_root: Path, groups: dict[str, list[str]]) -> None:
    cache_path = _groups_cache_path(workspace_root)
    cache_path.write_text(json.dumps(groups, indent=2), encoding="utf-8")


def _load_group_cache(workspace_root: Path) -> dict[str, list[str]]:
    cache_path = _groups_cache_path(workspace_root)
    if not cache_path.exists():
        return {}
    raw = json.loads(cache_path.read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for key, value in raw.items():
        if isinstance(value, list):
            out[str(key)] = [str(item) for item in value]
    return out


def _persist_groups_sqlite(
    workspace_root: Path,
    auto_groups: list[dict[str, Any]],
    review_groups: list[dict[str, Any]],
) -> None:
    db_path = _db_path(workspace_root)
    init_db(db_path)
    now = now_iso()
    with with_db(db_path) as conn:
        for group in auto_groups:
            conn.execute(
                """
                INSERT INTO dedup_groups (
                    group_id, canonical_doc_id, state, confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                    state=excluded.state,
                    confidence=excluded.confidence,
                    updated_at=excluded.updated_at
                """,
                (
                    group["group_id"],
                    None,
                    "auto",
                    float(group["score"]),
                    now,
                    now,
                ),
            )
        for group in review_groups:
            conn.execute(
                """
                INSERT INTO dedup_groups (
                    group_id, canonical_doc_id, state, confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                    state=excluded.state,
                    confidence=excluded.confidence,
                    updated_at=excluded.updated_at
                """,
                (
                    group["group_id"],
                    None,
                    "review",
                    float(group["score"]),
                    now,
                    now,
                ),
            )


def dedup_scan(
    workspace_root: Path,
    threshold_profile: dict[str, float] | None = None,
) -> dict[str, Any]:
    auto_threshold, review_threshold = _thresholds(threshold_profile)
    documents = list_documents(workspace_root)

    docs_with_hash: list[dict[str, Any]] = []
    by_hash: dict[str, list[str]] = {}
    for document in documents:
        body = str(document["body"])
        content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        enriched = dict(document)
        enriched["content_hash"] = content_hash
        docs_with_hash.append(enriched)
        by_hash.setdefault(content_hash, []).append(str(document["doc_id"]))

    exact_duplicates: list[dict[str, Any]] = []
    auto_merge_candidates: list[dict[str, Any]] = []
    review_candidates: list[dict[str, Any]] = []
    keep_separate_evidence: list[dict[str, Any]] = []
    groups_cache: dict[str, list[str]] = {}

    for content_hash, doc_ids in sorted(by_hash.items()):
        if len(doc_ids) < 2:
            continue
        group = {
            "group_id": _group_id_for(doc_ids),
            "doc_ids": sorted(doc_ids),
            "match_type": "exact",
            "score": 1.0,
            "content_hash": content_hash,
            "route": "auto",
            "auto_threshold": auto_threshold,
            "review_threshold": review_threshold,
        }
        exact_duplicates.append(group)
        auto_merge_candidates.append(group)
        groups_cache[group["group_id"]] = group["doc_ids"]

    for idx, left in enumerate(docs_with_hash):
        for right in docs_with_hash[idx + 1 :]:
            if left["content_hash"] == right["content_hash"]:
                continue
            left_doc_id = str(left["doc_id"])
            right_doc_id = str(right["doc_id"])
            score = _similarity(str(left["body"]), str(right["body"]))
            candidate = {
                "group_id": _group_id_for([left_doc_id, right_doc_id]),
                "doc_ids": sorted([left_doc_id, right_doc_id]),
                "match_type": "near",
                "score": score,
                "auto_threshold": auto_threshold,
                "review_threshold": review_threshold,
            }
            if score >= auto_threshold:
                candidate["route"] = "auto"
                auto_merge_candidates.append(candidate)
                groups_cache[candidate["group_id"]] = candidate["doc_ids"]
            elif score >= review_threshold:
                candidate["route"] = "review"
                review_candidates.append(candidate)
                groups_cache[candidate["group_id"]] = candidate["doc_ids"]
            else:
                keep_separate_evidence.append(
                    {
                        **candidate,
                        "route": "keep_separate",
                        "reason": "below_review_threshold",
                    }
                )

    eval_report = _load_dedup_eval_report(workspace_root)
    auto_merge_enabled = bool(eval_report and eval_report.get("auto_merge_enabled"))
    if not auto_merge_enabled and auto_merge_candidates:
        downgraded_auto_candidates: list[dict[str, Any]] = []
        for candidate in auto_merge_candidates:
            downgraded_auto_candidates.append(
                {
                    **candidate,
                    "route": "review",
                    "review_reason": "auto_merge_disabled",
                }
            )
        review_candidates = review_candidates + downgraded_auto_candidates
        auto_merge_candidates = []

    _persist_group_cache(workspace_root, groups_cache)
    _persist_groups_sqlite(workspace_root, auto_merge_candidates, review_candidates)

    return {
        "thresholds": {
            "auto": auto_threshold,
            "review": review_threshold,
        },
        "exact_duplicates": exact_duplicates,
        "near_duplicates": auto_merge_candidates + review_candidates,
        "auto_merge_candidates": auto_merge_candidates,
        "review_candidates": review_candidates,
        "keep_separate_evidence": keep_separate_evidence,
        "auto_merge_enabled": auto_merge_enabled,
    }


def _snapshot_documents(workspace_root: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for document in list_documents(workspace_root):
        docs.append(
            {
                "doc_id": str(document["doc_id"]),
                "path": str(document["path"]),
                "raw_text": str(document["raw_text"]),
            }
        )
    return sorted(docs, key=lambda item: item["doc_id"])


def _snapshot_doc_edges(workspace_root: Path) -> list[dict[str, Any]]:
    db_path = _db_path(workspace_root)
    if not db_path.exists():
        return []
    init_db(db_path)
    with with_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT edge_id, src_doc_id, dst_doc_id, edge_type, weight, evidence, created_at
            FROM doc_edges
            ORDER BY edge_id
            """
        ).fetchall()
    return [
        {
            "edge_id": str(row[0]),
            "src_doc_id": str(row[1]),
            "dst_doc_id": str(row[2]),
            "edge_type": str(row[3]),
            "weight": float(row[4]),
            "evidence": str(row[5]),
            "created_at": str(row[6]),
        }
        for row in rows
    ]


def _snapshot_dedup_groups(workspace_root: Path) -> list[dict[str, Any]]:
    db_path = _db_path(workspace_root)
    if not db_path.exists():
        return []
    init_db(db_path)
    with with_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT group_id, canonical_doc_id, state, confidence, created_at, updated_at
            FROM dedup_groups
            ORDER BY group_id
            """
        ).fetchall()
    return [
        {
            "group_id": str(row[0]),
            "canonical_doc_id": row[1],
            "state": str(row[2]),
            "confidence": float(row[3]),
            "created_at": str(row[4]),
            "updated_at": str(row[5]),
        }
        for row in rows
    ]


def _collect_snapshot(workspace_root: Path) -> dict[str, Any]:
    build_index(workspace_root)
    return {
        "documents": _snapshot_documents(workspace_root),
        "chunks": sorted(
            load_chunks(workspace_root), key=lambda item: item.get("chunk_id", "")
        ),
        "doc_edges": _snapshot_doc_edges(workspace_root),
        "dedup_groups": _snapshot_dedup_groups(workspace_root),
    }


def _ensure_documents_in_db(
    workspace_root: Path,
    documents: list[dict[str, Any]],
) -> None:
    db_path = _db_path(workspace_root)
    init_db(db_path)
    with with_db(db_path) as conn:
        for document in documents:
            body = str(document["body"])
            meta = dict(document["meta"])
            created_at = str(meta.get("created_at") or now_iso())
            updated_at = str(meta.get("updated_at") or created_at)
            conn.execute(
                """
                INSERT INTO documents (
                    doc_id,
                    title,
                    source_type,
                    source_uri,
                    body,
                    content_hash,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    title=excluded.title,
                    body=excluded.body,
                    content_hash=excluded.content_hash,
                    updated_at=excluded.updated_at
                """,
                (
                    str(document["doc_id"]),
                    str(meta.get("title") or document["doc_id"]),
                    "note",
                    str(document.get("path", "")),
                    body,
                    hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    created_at,
                    updated_at,
                ),
            )


def _dedup_group_from_snapshot(
    snapshot: dict[str, Any], group_id: str
) -> dict[str, Any] | None:
    for row in snapshot.get("dedup_groups", []):
        if str(row.get("group_id", "")) == group_id:
            return dict(row)
    return None


def _restore_group_state_from_snapshot(
    workspace_root: Path,
    snapshot: dict[str, Any],
    group_id: str,
) -> None:
    db_path = _db_path(workspace_root)
    init_db(db_path)
    snapshot_group = _dedup_group_from_snapshot(snapshot, group_id)
    with with_db(db_path) as conn:
        if snapshot_group is None:
            conn.execute(
                """
                INSERT INTO dedup_groups (
                    group_id, canonical_doc_id, state, confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                    canonical_doc_id=excluded.canonical_doc_id,
                    state=excluded.state,
                    confidence=excluded.confidence,
                    updated_at=excluded.updated_at
                """,
                (group_id, None, "candidate", 0.0, now_iso(), now_iso()),
            )
            return
        conn.execute(
            """
            INSERT INTO dedup_groups (
                group_id, canonical_doc_id, state, confidence, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(group_id) DO UPDATE SET
                canonical_doc_id=excluded.canonical_doc_id,
                state=excluded.state,
                confidence=excluded.confidence,
                created_at=excluded.created_at,
                updated_at=excluded.updated_at
            """,
            (
                str(snapshot_group["group_id"]),
                snapshot_group.get("canonical_doc_id"),
                str(snapshot_group.get("state", "candidate")),
                float(snapshot_group.get("confidence", 0.0)),
                str(snapshot_group.get("created_at", now_iso())),
                str(snapshot_group.get("updated_at", now_iso())),
            ),
        )


def _insert_pending_merge_log(
    workspace_root: Path,
    merge_id: str,
    group_id: str,
    canonical_doc_id: str,
    merged_docs: list[dict[str, Any]],
    before_snapshot: dict[str, Any],
) -> None:
    db_path = _db_path(workspace_root)
    init_db(db_path)
    now = now_iso()
    with with_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO dedup_groups (
                group_id, canonical_doc_id, state, confidence, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(group_id) DO UPDATE SET
                updated_at=excluded.updated_at
            """,
            (group_id, None, "pending_merge", 1.0, now, now),
        )
        conn.execute(
            """
            INSERT INTO merge_logs (
                merge_id,
                group_id,
                canonical_doc_id,
                merged_doc_ids,
                snapshot_before,
                snapshot_after,
                diff_notes,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                merge_id,
                group_id,
                canonical_doc_id,
                json.dumps([str(doc["doc_id"]) for doc in merged_docs]),
                json.dumps(before_snapshot),
                None,
                "pending",
                now,
            ),
        )


def _persist_merge_success(
    workspace_root: Path,
    merge_id: str,
    group_id: str,
    canonical_doc_id: str,
    diff_notes_list: list[str],
    after_snapshot: dict[str, Any],
) -> None:
    db_path = _db_path(workspace_root)
    init_db(db_path)
    now = now_iso()
    with with_db(db_path) as conn:
        conn.execute(
            """
            UPDATE dedup_groups
            SET canonical_doc_id = ?, state = ?, updated_at = ?
            WHERE group_id = ?
            """,
            (canonical_doc_id, "merged", now, group_id),
        )
        conn.execute(
            """
            UPDATE merge_logs
            SET snapshot_after = ?, diff_notes = ?
            WHERE merge_id = ?
            """,
            (json.dumps(after_snapshot), "\n".join(diff_notes_list), merge_id),
        )


def _mark_merge_failed(workspace_root: Path, merge_id: str, error_text: str) -> None:
    db_path = _db_path(workspace_root)
    init_db(db_path)
    with with_db(db_path) as conn:
        conn.execute(
            """
            UPDATE merge_logs
            SET snapshot_after = NULL, diff_notes = ?
            WHERE merge_id = ?
            """,
            (f"failed:{error_text}", merge_id),
        )


def _resolve_doc_ids(
    workspace_root: Path, group_id_or_doc_ids: str | list[str]
) -> tuple[str, list[str]]:
    if isinstance(group_id_or_doc_ids, list):
        doc_ids = sorted({str(doc_id) for doc_id in group_id_or_doc_ids})
        if len(doc_ids) < 2:
            raise ValueError("At least two documents are required for dedup merge")
        return _group_id_for(doc_ids), doc_ids

    group_id = str(group_id_or_doc_ids)
    groups = _load_group_cache(workspace_root)
    doc_ids = groups.get(group_id)
    if not doc_ids or len(doc_ids) < 2:
        raise ValueError(f"Dedup group is unknown or too small: {group_id}")
    return group_id, sorted(doc_ids)


def _safe_created_at(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.max


def _select_canonical(documents: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        documents,
        key=lambda doc: (
            _safe_created_at(str(doc["meta"].get("created_at", ""))),
            -len(str(doc["body"])),
            str(doc["doc_id"]),
        ),
    )[0]


def _compressed_summary(
    canonical: dict[str, Any], merged_docs: list[dict[str, Any]]
) -> str:
    canonical_summary = str(canonical["meta"].get("summary") or "").strip()
    canonical_body = str(canonical["body"]).strip().split("\n")[0].strip()
    base = (
        canonical_summary or canonical_body or str(canonical["meta"].get("title", ""))
    )
    if not base:
        base = str(canonical["doc_id"])
    return f"{base[:160]} (merged {len(merged_docs)} duplicate documents)"


def _diff_notes(
    canonical: dict[str, Any], merged_docs: list[dict[str, Any]]
) -> list[str]:
    notes: list[str] = []
    canonical_tokens = set(tokenize(str(canonical["body"])))
    for document in merged_docs:
        current_tokens = set(tokenize(str(document["body"])))
        missing = sorted(current_tokens - canonical_tokens)
        if missing:
            notes.append(f"{document['doc_id']} adds tokens: {', '.join(missing[:8])}")
        else:
            notes.append(f"{document['doc_id']} fully overlaps canonical content")
    return notes


def dedup_merge(
    workspace_root: Path,
    group_id_or_doc_ids: str | list[str],
    mode: str = "auto",
) -> dict[str, Any]:
    if mode not in {"auto", "review"}:
        raise ValueError(f"Unsupported dedup merge mode: {mode}")

    group_id, doc_ids = _resolve_doc_ids(workspace_root, group_id_or_doc_ids)
    documents: list[dict[str, Any]] = []
    for doc_id in doc_ids:
        document = get_document_by_id(workspace_root, doc_id)
        if document is None:
            raise ValueError(f"Document not found for merge: {doc_id}")
        documents.append(document)

    canonical = _select_canonical(documents)
    canonical_doc_id = str(canonical["doc_id"])
    merged_docs = [doc for doc in documents if doc["doc_id"] != canonical_doc_id]
    merge_id = f"merge-{uuid.uuid4().hex[:12]}"
    merge_state = "auto_merged" if mode == "auto" else "manual_merged"

    before_snapshot = _collect_snapshot(workspace_root)
    _ensure_documents_in_db(workspace_root, list_documents(workspace_root))
    compressed_summary = _compressed_summary(canonical, merged_docs)
    diff_notes_list = _diff_notes(canonical, merged_docs)

    _insert_pending_merge_log(
        workspace_root=workspace_root,
        merge_id=merge_id,
        group_id=group_id,
        canonical_doc_id=canonical_doc_id,
        merged_docs=merged_docs,
        before_snapshot=before_snapshot,
    )

    try:
        update_document_meta(
            workspace_root,
            canonical_doc_id,
            {
                "status": "active",
                "merge_state": merge_state,
                "merge_id": merge_id,
                "compressed_summary": compressed_summary,
                "diff_notes": diff_notes_list,
                "merged_into": None,
            },
        )

        for document in merged_docs:
            update_document_meta(
                workspace_root,
                str(document["doc_id"]),
                {
                    "status": "merged",
                    "merged_into": canonical_doc_id,
                    "merge_state": merge_state,
                    "merge_id": merge_id,
                },
            )

        after_snapshot = _collect_snapshot(workspace_root)
        _ensure_documents_in_db(workspace_root, list_documents(workspace_root))
        _persist_merge_success(
            workspace_root=workspace_root,
            merge_id=merge_id,
            group_id=group_id,
            canonical_doc_id=canonical_doc_id,
            diff_notes_list=diff_notes_list,
            after_snapshot=after_snapshot,
        )
    except Exception as exc:
        _restore_documents(workspace_root, list(before_snapshot.get("documents", [])))
        _ensure_documents_in_db(workspace_root, list_documents(workspace_root))
        _restore_doc_edges(workspace_root, list(before_snapshot.get("doc_edges", [])))
        _restore_group_state_from_snapshot(workspace_root, before_snapshot, group_id)
        _mark_merge_failed(workspace_root, merge_id, f"{exc.__class__.__name__}:{exc}")
        build_index(workspace_root)
        raise

    return {
        "merge_id": merge_id,
        "group_id": group_id,
        "canonical_doc_id": canonical_doc_id,
        "compressed_summary": compressed_summary,
        "diff_notes": diff_notes_list,
        "mode": mode,
    }


def _restore_documents(
    workspace_root: Path, snapshot_documents: list[dict[str, Any]]
) -> None:
    for document in snapshot_documents:
        relative_path = str(document["path"])
        path = workspace_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(document["raw_text"]), encoding="utf-8")


def _restore_doc_edges(
    workspace_root: Path, snapshot_doc_edges: list[dict[str, Any]]
) -> None:
    db_path = _db_path(workspace_root)
    init_db(db_path)
    with with_db(db_path) as conn:
        conn.execute("DELETE FROM doc_edges")
        for edge in snapshot_doc_edges:
            conn.execute(
                """
                INSERT INTO doc_edges (
                    edge_id,
                    src_doc_id,
                    dst_doc_id,
                    edge_type,
                    weight,
                    evidence,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(edge["edge_id"]),
                    str(edge["src_doc_id"]),
                    str(edge["dst_doc_id"]),
                    str(edge["edge_type"]),
                    float(edge["weight"]),
                    str(edge["evidence"]),
                    str(edge["created_at"]),
                ),
            )


def _dangling_refs(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    doc_ids = {str(document["doc_id"]) for document in snapshot["documents"]}
    dangling: list[dict[str, str]] = []
    for chunk in snapshot["chunks"]:
        doc_id = str(chunk.get("doc_id", ""))
        if doc_id and doc_id not in doc_ids:
            dangling.append({"kind": "chunk", "id": str(chunk.get("chunk_id", ""))})
    for edge in snapshot["doc_edges"]:
        src = str(edge.get("src_doc_id", ""))
        dst = str(edge.get("dst_doc_id", ""))
        if src and src not in doc_ids:
            dangling.append(
                {"kind": "doc_edge_src", "id": str(edge.get("edge_id", ""))}
            )
        if dst and dst not in doc_ids:
            dangling.append(
                {"kind": "doc_edge_dst", "id": str(edge.get("edge_id", ""))}
            )
    return dangling


def _dangling_merged_into_refs(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    doc_ids = {str(document["doc_id"]) for document in snapshot["documents"]}
    dangling: list[dict[str, str]] = []
    for document in snapshot["documents"]:
        raw_text = str(document.get("raw_text", ""))
        meta, _ = parse_frontmatter(raw_text)
        merged_into = meta.get("merged_into")
        if merged_into is None:
            continue
        target = str(merged_into).strip()
        if not target or target == "null":
            continue
        if target not in doc_ids:
            dangling.append(
                {
                    "doc_id": str(document.get("doc_id", "")),
                    "merged_into": target,
                }
            )
    return dangling


def _verify_searchability(
    workspace_root: Path, snapshot: dict[str, Any]
) -> dict[str, bool]:
    if not snapshot["chunks"]:
        return {"keyword": True, "semantic": True}
    first = str(snapshot["chunks"][0].get("text", ""))
    query_tokens = tokenize(first)
    if not query_tokens:
        return {"keyword": True, "semantic": True}
    query = " ".join(query_tokens[:3])
    return {
        "keyword": bool(keyword_search(workspace_root, query, limit=3)),
        "semantic": bool(semantic_search(workspace_root, query, limit=3)),
    }


def dedup_rollback(workspace_root: Path, merge_id: str) -> dict[str, Any]:
    db_path = _db_path(workspace_root)
    init_db(db_path)
    with with_db(db_path) as conn:
        row = conn.execute(
            """
            SELECT group_id, snapshot_before
            FROM merge_logs
            WHERE merge_id = ?
            """,
            (merge_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"Merge log not found: {merge_id}")

    group_id = str(row[0])
    before_snapshot = json.loads(str(row[1]))
    _restore_documents(workspace_root, list(before_snapshot.get("documents", [])))
    _ensure_documents_in_db(workspace_root, list_documents(workspace_root))
    _restore_doc_edges(workspace_root, list(before_snapshot.get("doc_edges", [])))
    _restore_group_state_from_snapshot(workspace_root, before_snapshot, group_id)
    after_snapshot = _collect_snapshot(workspace_root)
    dangling = _dangling_refs(after_snapshot)
    dangling_merged_into_refs = _dangling_merged_into_refs(after_snapshot)
    searchability = _verify_searchability(workspace_root, after_snapshot)

    before_documents = {
        str(doc["doc_id"]): str(doc["raw_text"])
        for doc in before_snapshot.get("documents", [])
    }
    after_documents = {
        str(doc["doc_id"]): str(doc["raw_text"])
        for doc in after_snapshot.get("documents", [])
    }
    before_chunks = {
        str(chunk.get("chunk_id", "")): chunk
        for chunk in before_snapshot.get("chunks", [])
    }
    after_chunks = {
        str(chunk.get("chunk_id", "")): chunk
        for chunk in after_snapshot.get("chunks", [])
    }
    before_edges = {
        str(edge.get("edge_id", "")): edge
        for edge in before_snapshot.get("doc_edges", [])
    }
    after_edges = {
        str(edge.get("edge_id", "")): edge
        for edge in after_snapshot.get("doc_edges", [])
    }

    documents_restored = all(
        after_documents.get(doc_id) == raw_text
        for doc_id, raw_text in before_documents.items()
    )
    chunks_restored = all(
        after_chunks.get(chunk_id) == chunk for chunk_id, chunk in before_chunks.items()
    )
    edges_restored = all(
        after_edges.get(edge_id) == edge for edge_id, edge in before_edges.items()
    )

    restored = (
        documents_restored
        and chunks_restored
        and edges_restored
        and not dangling
        and not dangling_merged_into_refs
        and searchability["keyword"]
        and searchability["semantic"]
    )

    return {
        "merge_id": merge_id,
        "restored": restored,
        "before_snapshot": before_snapshot,
        "after_snapshot": after_snapshot,
        "dangling_refs": dangling,
        "dangling_merged_into_refs": dangling_merged_into_refs,
        "searchability": searchability,
    }

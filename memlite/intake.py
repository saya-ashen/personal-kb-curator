import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from knowledge_store import now_iso
from storage import init_db, with_db


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _db_path(workspace_root: Path, options: dict[str, Any] | None) -> Path:
    if options and options.get("db_path"):
        db_path = Path(str(options["db_path"]))
        if not db_path.is_absolute():
            db_path = workspace_root / db_path
        return db_path.resolve()
    return (workspace_root / "kb.db").resolve()


def _canonical_file_path(workspace_root: Path, path_or_url: str) -> Path:
    source_path = Path(path_or_url)
    if not source_path.is_absolute():
        source_path = workspace_root / source_path
    return source_path.resolve()


def _extract_entities(text: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []

    projects = {
        m.group(1)
        for m in re.finditer(
            r"(?:project|项目)\s+([A-Za-z0-9_-]+)", text, re.IGNORECASE
        )
    }
    people = {m.group(1) for m in re.finditer(r"@([A-Za-z][A-Za-z0-9_-]+)", text)}
    tags = {m.group(1).lower() for m in re.finditer(r"#([A-Za-z0-9_-]+)", text)}

    for name in sorted(projects):
        entities.append({"type": "project", "name": name})
    for name in sorted(people):
        entities.append({"type": "person", "name": name})
    for name in sorted(tags):
        entities.append({"type": "topic", "name": name})

    return entities


def _read_source(
    workspace_root: Path,
    path_or_url: str,
    options: dict[str, Any] | None,
) -> tuple[str, str, str, str, dict[str, Any]]:
    if _is_url(path_or_url):
        fetch_url = options.get("fetch_url") if options else None
        if callable(fetch_url):
            try:
                payload = fetch_url(path_or_url)
            except Exception as exc:
                quality = {
                    "degraded": True,
                    "reason": f"fetch_failed:{exc.__class__.__name__}",
                }
                return (
                    "url",
                    path_or_url,
                    path_or_url,
                    f"URL capture failed for {path_or_url}",
                    quality,
                )
            if isinstance(payload, dict):
                text = str(payload.get("text", "")).strip()
                title = str(payload.get("title", path_or_url))
                degraded = bool(payload.get("degraded", False))
                reason = str(payload.get("reason", ""))
            else:
                text = str(payload).strip()
                title = path_or_url
                degraded = False
                reason = ""
        else:
            text = f"URL capture placeholder for {path_or_url}"
            title = path_or_url
            degraded = True
            reason = "network_fetch_disabled"

        quality = {"degraded": degraded, "reason": reason}
        return "url", path_or_url, title, text, quality

    source_path = _canonical_file_path(workspace_root, path_or_url)
    if not source_path.exists():
        raise FileNotFoundError(f"Input source not found: {path_or_url}")

    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        text = source_path.read_bytes().decode("latin-1", errors="ignore").strip()
        quality = {"degraded": True, "reason": "pdf_extraction_fallback"}
    else:
        text = source_path.read_text(encoding="utf-8", errors="replace").strip()
        quality = {"degraded": False, "reason": ""}

    return "file", source_path.as_uri(), source_path.stem, text, quality


def _relation_edges(
    conn: Any,
    document_id: str,
    entities: list[dict[str, str]],
    captured_at: str,
) -> list[dict[str, Any]]:
    evidence_by_doc: dict[str, list[str]] = {}
    for entity in entities:
        rows = conn.execute(
            """
            SELECT DISTINCT doc_id
            FROM entities
            WHERE doc_id != ?
              AND entity_type = ?
              AND lower(name) = lower(?)
            """,
            (document_id, entity["type"], entity["name"]),
        ).fetchall()
        marker = f"{entity['type']}:{entity['name']}"
        for row in rows:
            other_doc_id = str(row[0])
            evidence_by_doc.setdefault(other_doc_id, []).append(marker)

    edges: list[dict[str, Any]] = []
    for other_doc_id in sorted(evidence_by_doc):
        matches = sorted(set(evidence_by_doc[other_doc_id]))
        edge_value = f"{document_id}:related:{other_doc_id}:{'|'.join(matches)}"
        edges.append(
            {
                "edge_id": _stable_id("edge", edge_value),
                "src_doc_id": document_id,
                "dst_doc_id": other_doc_id,
                "edge_type": "related",
                "weight": float(len(matches)),
                "evidence": ", ".join(matches),
                "created_at": captured_at,
            }
        )
    return edges


def import_document(
    workspace_root: Path,
    path_or_url: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_type, source_uri, title, body, extraction_quality = _read_source(
        workspace_root=workspace_root,
        path_or_url=path_or_url,
        options=options,
    )
    captured_at = now_iso()
    document_id = _stable_id("doc", f"{source_type}:{source_uri}")
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

    entities = _extract_entities(body)
    db_path = _db_path(workspace_root, options)
    init_db(db_path)
    with with_db(db_path) as conn:
        existing = conn.execute(
            "SELECT created_at FROM documents WHERE doc_id = ?",
            (document_id,),
        ).fetchone()
        created_at = str(existing[0]) if existing else captured_at

        conn.execute(
            """
            INSERT INTO documents (
                doc_id, title, source_type, source_uri, body,
                content_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                title=excluded.title,
                source_type=excluded.source_type,
                source_uri=excluded.source_uri,
                body=excluded.body,
                content_hash=excluded.content_hash,
                updated_at=excluded.updated_at
            """,
            (
                document_id,
                title,
                source_type,
                source_uri,
                body,
                content_hash,
                created_at,
                captured_at,
            ),
        )

        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (document_id,))
        conn.execute("DELETE FROM entities WHERE doc_id = ?", (document_id,))
        conn.execute("DELETE FROM doc_edges WHERE src_doc_id = ?", (document_id,))

        chunk_id = f"{document_id}#0"
        conn.execute(
            """
            INSERT INTO chunks (chunk_id, doc_id, ord, text, token_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (chunk_id, document_id, 0, body, len(body.split()), captured_at),
        )

        for entity in entities:
            entity_id = _stable_id(
                "ent",
                f"{document_id}:{entity['type']}:{entity['name'].lower()}",
            )
            conn.execute(
                """
                INSERT INTO entities (
                    entity_id, doc_id, chunk_id, name, entity_type, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_id,
                    document_id,
                    chunk_id,
                    entity["name"],
                    entity["type"],
                    1.0,
                    captured_at,
                ),
            )

        edges = _relation_edges(
            conn=conn,
            document_id=document_id,
            entities=entities,
            captured_at=captured_at,
        )

        for edge in edges:
            conn.execute(
                """
                INSERT INTO doc_edges (
                    edge_id, src_doc_id, dst_doc_id, edge_type, weight, evidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge["edge_id"],
                    edge["src_doc_id"],
                    edge["dst_doc_id"],
                    edge["edge_type"],
                    edge["weight"],
                    edge["evidence"],
                    edge["created_at"],
                ),
            )

    return {
        "document_id": document_id,
        "title": title,
        "source_type": source_type,
        "source_uri": source_uri,
        "captured_at": captured_at,
        "content_hash": content_hash,
        "extraction_quality": extraction_quality,
        "entities": entities,
        "edges": [
            {
                "edge_id": edge["edge_id"],
                "src_doc_id": edge["src_doc_id"],
                "dst_doc_id": edge["dst_doc_id"],
                "edge_type": edge["edge_type"],
                "weight": edge["weight"],
            }
            for edge in edges
        ],
    }

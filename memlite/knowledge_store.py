import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from frontmatter import dump_frontmatter, parse_frontmatter
from storage import init_db, with_db


def now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _slug(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:60] or "note"


def _note_path(workspace_root: Path, zone: str, title: str, note_id: str) -> Path:
    zone_dir = workspace_root / zone
    zone_dir.mkdir(parents=True, exist_ok=True)
    return zone_dir / f"{_slug(title)}-{note_id[-8:]}.md"


def create_note(
    workspace_root: Path, payload: dict[str, Any], zone: str = "notes"
) -> dict[str, Any]:
    created = now_iso()
    note_id = payload.get("id") or f"note-{uuid.uuid4().hex[:12]}"
    title = payload.get("title") or "Untitled note"
    meta = {
        "id": note_id,
        "title": title,
        "created_at": payload.get("created_at", created),
        "updated_at": payload.get("updated_at", created),
        "type": payload.get("type", "note"),
        "summary": payload.get("summary", ""),
        "tags": payload.get("tags", []),
        "topics": payload.get("topics", []),
        "projects": payload.get("projects", []),
        "people": payload.get("people", []),
        "source": payload.get("source", "manual"),
        "confidence": payload.get("confidence", "medium"),
        "related": payload.get("related", []),
    }
    for key, value in payload.items():
        if key in {"body"}:
            continue
        if key not in meta:
            meta[key] = value
    body = payload.get("body", "")

    path = _note_path(workspace_root, zone, title, note_id)
    content = f"{dump_frontmatter(meta)}\n\n{body.strip()}\n"
    path.write_text(content, encoding="utf-8")
    return {
        "note_id": note_id,
        "note_path": str(path.relative_to(workspace_root)),
        "title": title,
    }


def get_note(workspace_root: Path, note_path: str) -> dict[str, Any]:
    path = workspace_root / note_path
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    return {"path": note_path, "meta": meta, "body": body.strip()}


def update_note(
    workspace_root: Path, note_path: str, updates: dict[str, Any]
) -> dict[str, Any]:
    path = workspace_root / note_path
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    meta.update(updates.get("meta", {}))
    meta["updated_at"] = now_iso()
    new_body = updates.get("body", body).strip()
    path.write_text(f"{dump_frontmatter(meta)}\n\n{new_body}\n", encoding="utf-8")
    return {"updated": True, "note_path": note_path}


def search_notes(workspace_root: Path, query: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    tokens = [t.lower() for t in query.split() if t.strip()]
    for zone in ["notes", "meetings", "projects", "reviews"]:
        zone_dir = workspace_root / zone
        if not zone_dir.exists():
            continue
        for path in zone_dir.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            score = sum(text.lower().count(t) for t in tokens)
            if score <= 0:
                continue
            meta, body = parse_frontmatter(text)
            results.append(
                {
                    "path": str(path.relative_to(workspace_root)),
                    "note_id": meta.get("id", path.stem),
                    "title": meta.get("title", path.stem),
                    "score": score,
                    "snippet": body[:200],
                }
            )
    return sorted(results, key=lambda x: x["score"], reverse=True)


def link_notes(
    workspace_root: Path, source_path: str, target_path: str
) -> dict[str, Any]:
    source = get_note(workspace_root, source_path)
    target = get_note(workspace_root, target_path)
    related = list(source["meta"].get("related", []))
    target_id = target["meta"].get("id")
    if target_id and target_id not in related:
        related.append(target_id)
    update_note(workspace_root, source_path, {"meta": {"related": related}})
    return {"linked": True, "source": source_path, "target": target_path}


def list_related_notes(workspace_root: Path, note_path: str) -> list[str]:
    note = get_note(workspace_root, note_path)
    return list(note["meta"].get("related", []))


CONTENT_ZONES = ("notes", "meetings", "projects", "reviews")


def iter_note_paths(workspace_root: Path) -> list[Path]:
    paths: list[Path] = []
    for zone in CONTENT_ZONES:
        zone_dir = workspace_root / zone
        if not zone_dir.exists():
            continue
        for path in sorted(zone_dir.glob("*.md")):
            paths.append(path)
    return paths


def list_documents(workspace_root: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in iter_note_paths(workspace_root):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        doc_id = str(meta.get("id", path.stem))
        documents.append(
            {
                "doc_id": doc_id,
                "path": str(path.relative_to(workspace_root)),
                "meta": meta,
                "body": body.strip(),
                "raw_text": text,
            }
        )
    return documents


def get_document_by_id(workspace_root: Path, doc_id: str) -> dict[str, Any] | None:
    for document in list_documents(workspace_root):
        if document["doc_id"] == doc_id:
            return document
    return None


def update_document_meta(
    workspace_root: Path,
    doc_id: str,
    meta_updates: dict[str, Any],
) -> dict[str, Any]:
    document = get_document_by_id(workspace_root, doc_id)
    if document is None:
        raise ValueError(f"Document not found: {doc_id}")

    path = workspace_root / str(document["path"])
    meta = dict(document["meta"])
    meta.update(meta_updates)
    meta["updated_at"] = now_iso()
    body = str(document["body"]).strip()
    path.write_text(f"{dump_frontmatter(meta)}\n\n{body}\n", encoding="utf-8")
    return {"doc_id": doc_id, "path": str(document["path"]), "updated": True}


def _db_path(workspace_root: Path) -> Path:
    return (workspace_root / "kb.db").resolve()


def sync_documents_to_db(workspace_root: Path) -> dict[str, int]:
    documents = list_documents(workspace_root)
    db_path = _db_path(workspace_root)
    init_db(db_path)
    upserted = 0
    with with_db(db_path) as conn:
        for document in documents:
            body = str(document.get("body", ""))
            meta = dict(document.get("meta", {}))
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
            upserted += 1
    return {"documents": len(documents), "upserted": upserted}


def _stable_edge_id(src_doc_id: str, dst_doc_id: str, edge_type: str) -> str:
    signature = f"{src_doc_id}|{edge_type}|{dst_doc_id}"
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
    return f"edge-{digest}"


def persist_doc_edges(
    workspace_root: Path,
    edges: list[dict[str, Any]],
) -> dict[str, int]:
    db_path = _db_path(workspace_root)
    init_db(db_path)
    sync_documents_to_db(workspace_root)

    inserted = 0
    updated = 0
    skipped = 0
    now = now_iso()
    with with_db(db_path) as conn:
        for edge in edges:
            src_doc_id = str(edge.get("src_doc_id", "")).strip()
            dst_doc_id = str(edge.get("dst_doc_id", "")).strip()
            edge_type = str(edge.get("edge_type", "")).strip()
            if (
                not src_doc_id
                or not dst_doc_id
                or not edge_type
                or src_doc_id == dst_doc_id
            ):
                skipped += 1
                continue

            edge_id = str(
                edge.get("edge_id")
                or _stable_edge_id(src_doc_id, dst_doc_id, edge_type)
            )
            weight = float(edge.get("weight", 0.0))
            evidence = str(edge.get("evidence", ""))
            created_at = str(edge.get("created_at") or now)

            exists = conn.execute(
                "SELECT 1 FROM doc_edges WHERE edge_id = ?",
                (edge_id,),
            ).fetchone()
            if exists is None:
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
                        edge_id,
                        src_doc_id,
                        dst_doc_id,
                        edge_type,
                        weight,
                        evidence,
                        created_at,
                    ),
                )
                inserted += 1
            else:
                conn.execute(
                    """
                    UPDATE doc_edges
                    SET src_doc_id = ?,
                        dst_doc_id = ?,
                        edge_type = ?,
                        weight = ?,
                        evidence = ?
                    WHERE edge_id = ?
                    """,
                    (
                        src_doc_id,
                        dst_doc_id,
                        edge_type,
                        weight,
                        evidence,
                        edge_id,
                    ),
                )
                updated += 1

    return {
        "input_edges": len(edges),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
    }


def list_doc_edges(
    workspace_root: Path,
    doc_id: str | None = None,
    edge_type: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    db_path = _db_path(workspace_root)
    if not db_path.exists():
        return []
    init_db(db_path)

    clauses: list[str] = []
    params: list[Any] = []
    if doc_id:
        clauses.append("(src_doc_id = ? OR dst_doc_id = ?)")
        params.extend([doc_id, doc_id])
    if edge_type:
        clauses.append("edge_type = ?")
        params.append(edge_type)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, int(limit)))
    query = (
        "SELECT edge_id, src_doc_id, dst_doc_id, edge_type, weight, evidence, created_at "
        "FROM doc_edges "
        f"{where_sql} "
        "ORDER BY src_doc_id, dst_doc_id, edge_type, edge_id "
        "LIMIT ?"
    )

    with with_db(db_path) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()

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

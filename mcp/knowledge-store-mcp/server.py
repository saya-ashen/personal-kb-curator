import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from memlite.indexer import build_index
from memlite.knowledge_store import (
    create_note,
    get_note,
    link_notes,
    list_documents,
    list_related_notes,
    update_note,
)
from memlite.rag import hybrid_search
from memlite.workflows import dedup_merge, dedup_rollback, dedup_scan

ALIAS_OPS = {
    "create_note": "upsert_document",
    "update_note": "upsert_document",
    "search_notes": "hybrid_search",
    "link_notes": "link_documents",
}

SUPPORTED_OPERATIONS = {
    "create_note",
    "update_note",
    "get_note",
    "search_notes",
    "link_notes",
    "list_related_notes",
    "upsert_document",
    "build_index",
    "hybrid_search",
    "dedup_scan",
    "dedup_merge",
    "dedup_rollback",
    "link_documents",
}

DEFAULT_OPERATION = "upsert_document"
ALLOWED_ZONES = {"notes", "meetings", "projects", "reviews"}


def _resolve_note_path_from_doc_id(workspace_root: Path, doc_id: str) -> str:
    for document in list_documents(workspace_root):
        if str(document.get("doc_id", "")) == doc_id:
            return str(document.get("path", ""))
    return ""


def _require_non_empty_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required and must be a non-empty string")
    return value.strip()


def _parse_limit(payload: dict[str, Any], default: int = 8) -> int:
    raw = payload.get("limit", default)
    if isinstance(raw, bool):
        raise ValueError("limit must be an integer")
    try:
        limit = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc
    if limit <= 0:
        raise ValueError("limit must be greater than 0")
    return limit


def _validate_zone(payload: dict[str, Any]) -> str:
    raw = payload.get("zone", "notes")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("zone must be a non-empty string")
    zone = raw.strip()
    if zone not in ALLOWED_ZONES:
        raise ValueError(f"zone must be one of: {', '.join(sorted(ALLOWED_ZONES))}")
    return zone


def _safe_workspace_relative_path(
    workspace_root: Path,
    raw_path: str,
    *,
    field_name: str,
) -> str:
    path = Path(raw_path)
    if path.is_absolute():
        raise ValueError(f"{field_name} path traversal is not allowed")
    candidate = (workspace_root.resolve() / path).resolve()
    try:
        relative = candidate.relative_to(workspace_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{field_name} path traversal is not allowed") from exc
    return str(relative)


def _require_safe_note_path(
    workspace_root: Path, payload: dict[str, Any], field_name: str = "note_path"
) -> str:
    note_path = _require_non_empty_string(payload, field_name)
    return _safe_workspace_relative_path(
        workspace_root,
        note_path,
        field_name=field_name,
    )


def _upsert_document(workspace_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    has_update_markers = any(
        key in payload
        for key in ("note_path", "updates", "document_id", "meta", "body")
    )
    if has_update_markers and (
        "note_path" in payload or "updates" in payload or "document_id" in payload
    ):
        note_path = str(payload.get("note_path", "")).strip()
        if not note_path:
            note_path = _resolve_note_path_from_doc_id(
                workspace_root, str(payload.get("document_id", ""))
            )
        if not note_path:
            raise ValueError("note_path or document_id is required for update")
        note_path = _safe_workspace_relative_path(
            workspace_root,
            note_path,
            field_name="note_path",
        )

        updates_raw = payload.get("updates", {})
        if updates_raw is not None and not isinstance(updates_raw, dict):
            raise ValueError("updates must be a dict when provided")
        updates = cast(dict[str, Any], updates_raw or {})
        if not updates:
            updates = {}
            if isinstance(payload.get("meta"), dict):
                updates["meta"] = cast(dict[str, Any], payload["meta"])
            if "body" in payload:
                updates["body"] = payload.get("body", "")

        out = update_note(workspace_root, note_path, updates)
        note = get_note(workspace_root, note_path)
        document_id = str(note["meta"].get("id", ""))
        return {
            **out,
            "document_id": document_id,
            "note_id": document_id,
            "operation": "update",
        }

    raw_document = payload.get("document")
    if not isinstance(raw_document, dict):
        raw_document = payload.get("note", payload)
    document = cast(dict[str, Any], raw_document)
    zone = _validate_zone(payload)
    created = create_note(workspace_root, document, zone=zone)
    document_id = str(created.get("note_id", ""))
    return {
        **created,
        "document_id": document_id,
        "note_id": document_id,
        "operation": "create",
    }


def _link_documents(workspace_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    source_raw = payload.get("source_path") or payload.get("from_path")
    target_raw = payload.get("target_path") or payload.get("to_path")

    if source_raw is not None and not isinstance(source_raw, str):
        raise ValueError("source_path must be a string")
    if target_raw is not None and not isinstance(target_raw, str):
        raise ValueError("target_path must be a string")

    source_path = source_raw.strip() if isinstance(source_raw, str) else ""
    target_path = target_raw.strip() if isinstance(target_raw, str) else ""

    if not source_path and payload.get("from_id"):
        source_path = _resolve_note_path_from_doc_id(
            workspace_root, str(payload["from_id"])
        )
    if not target_path and payload.get("to_id"):
        target_path = _resolve_note_path_from_doc_id(
            workspace_root, str(payload["to_id"])
        )

    if not source_path or not target_path:
        raise ValueError(
            "source/target paths or from_id/to_id are required for link_documents"
        )

    source_path = _safe_workspace_relative_path(
        workspace_root,
        source_path,
        field_name="source_path",
    )
    target_path = _safe_workspace_relative_path(
        workspace_root,
        target_path,
        field_name="target_path",
    )

    linked = link_notes(workspace_root, source_path, target_path)
    source_note = get_note(workspace_root, source_path)
    target_note = get_note(workspace_root, target_path)
    return {
        **linked,
        "from_id": source_note["meta"].get("id"),
        "to_id": target_note["meta"].get("id"),
    }


def _resolve_operation(
    operation: str | None, payload: dict[str, Any]
) -> tuple[str, str, list[dict[str, str]]]:
    requested = operation or str(
        payload.get("operation")
        or payload.get("command")
        or payload.get("dispatch")
        or ""
    )
    requested = requested.strip() or DEFAULT_OPERATION
    resolved = ALIAS_OPS.get(requested, requested)
    if resolved not in SUPPORTED_OPERATIONS:
        raise ValueError(f"unsupported operation: {requested}")

    warnings: list[dict[str, str]] = []
    if requested != resolved and requested in ALIAS_OPS:
        warnings.append(
            {
                "type": "deprecation",
                "phase": "M4",
                "message": f"'{requested}' is deprecated; use '{resolved}'",
                "alias_from": requested,
                "alias_to": resolved,
            }
        )
    return requested, resolved, warnings


def execute_operation(
    workspace_root: Path,
    operation: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    requested_operation, resolved_operation, warnings = _resolve_operation(
        operation, payload
    )

    if resolved_operation == "upsert_document":
        result = _upsert_document(workspace_root, payload)
        result["index"] = build_index(workspace_root)
    elif resolved_operation == "get_note":
        note_path = _require_safe_note_path(workspace_root, payload)
        result = get_note(workspace_root, note_path)
    elif resolved_operation == "hybrid_search":
        query = _require_non_empty_string(payload, "query")
        result = {
            "results": hybrid_search(
                workspace_root,
                query,
                limit=_parse_limit(payload, default=8),
                filters=cast(dict[str, Any] | None, payload.get("filters")),
            )
        }
    elif resolved_operation == "build_index":
        result = build_index(workspace_root)
    elif resolved_operation == "link_documents":
        result = _link_documents(workspace_root, payload)
    elif resolved_operation == "list_related_notes":
        note_path = _require_safe_note_path(workspace_root, payload)
        result = {"related": list_related_notes(workspace_root, note_path)}
    elif resolved_operation == "dedup_scan":
        result = dedup_scan(
            workspace_root,
            threshold_profile=cast(
                dict[str, float] | None, payload.get("threshold_profile")
            ),
        )
    elif resolved_operation == "dedup_merge":
        group_id_or_doc_ids: str | list[str] = str(payload.get("group_id", ""))
        if isinstance(payload.get("doc_ids"), list):
            group_id_or_doc_ids = [str(item) for item in payload["doc_ids"]]
        result = dedup_merge(
            workspace_root,
            group_id_or_doc_ids=group_id_or_doc_ids,
            mode=str(payload.get("mode", "auto")),
        )
    elif resolved_operation == "dedup_rollback":
        merge_id = _require_non_empty_string(payload, "merge_id")
        result = dedup_rollback(workspace_root, merge_id=merge_id)
    else:
        raise ValueError(f"unsupported operation: {resolved_operation}")

    result["_meta"] = {
        "requested_operation": requested_operation,
        "resolved_operation": resolved_operation,
    }
    if warnings:
        result["warnings"] = warnings
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="knowledge-store-mcp MVP server")
    _ = parser.add_argument("--workspace-root", default=".", help="Workspace root")
    _ = parser.add_argument(
        "operation",
        nargs="?",
        default=None,
        help="Operation name",
    )
    _ = parser.add_argument("--payload", default="{}", help="JSON payload")
    args = parser.parse_args()

    root = Path(cast(str, args.workspace_root)).resolve()
    operation = cast(str | None, args.operation)
    raw_payload = cast(str, args.payload)
    parsed_payload = json.loads(raw_payload)
    if not isinstance(parsed_payload, dict):
        raise ValueError("payload must be a JSON object")
    payload: dict[str, Any] = parsed_payload

    result = execute_operation(root, operation=operation, payload=payload)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

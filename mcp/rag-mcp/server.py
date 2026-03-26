import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from memlite.rag import (
    ask_with_citations,
    hybrid_search,
    rerank_results,
    semantic_search,
)

ALIAS_OPS = {
    "search_notes": "hybrid_search",
    "answer_from_context": "ask_with_citations",
}

SUPPORTED_OPERATIONS = {
    "semantic_search",
    "hybrid_search",
    "rerank_results",
    "answer_from_context",
    "ask_with_citations",
    "search_notes",
}

DEFAULT_OPERATION = "ask_with_citations"


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


def _parse_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    raise ValueError(f"{field_name} must be a boolean or boolean-like string")


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

    if resolved_operation == "semantic_search":
        query = _require_non_empty_string(payload, "query")
        result = {
            "results": semantic_search(
                workspace_root,
                query,
                limit=_parse_limit(payload, default=8),
                filters=cast(dict[str, Any] | None, payload.get("filters")),
            )
        }
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
    elif resolved_operation == "rerank_results":
        query = _require_non_empty_string(payload, "query")
        rows_raw = payload.get("results", [])
        if not isinstance(rows_raw, list):
            raise ValueError("results must be a list")
        rows = cast(list[dict[str, Any]], rows_raw)
        result = {"results": rerank_results(query, rows)}
    elif resolved_operation == "ask_with_citations":
        question_raw = payload.get("question") or payload.get("query")
        if not isinstance(question_raw, str) or not question_raw.strip():
            raise ValueError("question is required and must be a non-empty string")
        question = question_raw.strip()
        result = ask_with_citations(
            workspace_root,
            question,
            filters=cast(dict[str, Any] | None, payload.get("filters")),
            limit=_parse_limit(payload, default=8),
            use_cloud_generation=_parse_bool(
                payload.get("use_cloud_generation", False),
                field_name="use_cloud_generation",
            ),
            cloud_generator=None,
        )
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
    parser = argparse.ArgumentParser(description="rag-mcp MVP server")
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

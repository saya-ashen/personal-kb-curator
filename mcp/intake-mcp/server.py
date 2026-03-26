import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from memlite.indexer import build_index
from memlite.workflows import import_document

SUPPORTED_OPERATIONS = {"import_document"}
DEFAULT_OPERATION = "import_document"


def _resolve_operation(
    operation: str | None, payload: dict[str, Any]
) -> tuple[str, str]:
    requested = operation or str(
        payload.get("operation")
        or payload.get("command")
        or payload.get("dispatch")
        or ""
    )
    requested = requested.strip() or DEFAULT_OPERATION
    resolved = requested
    if resolved not in SUPPORTED_OPERATIONS:
        raise ValueError(f"unsupported operation: {resolved}")
    return requested, resolved


def _require_non_empty_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required and must be a non-empty string")
    return value.strip()


def execute_operation(
    workspace_root: Path,
    operation: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    requested_operation, resolved_operation = _resolve_operation(operation, payload)
    if resolved_operation != "import_document":
        raise ValueError(f"unsupported operation: {resolved_operation}")

    result = import_document(
        workspace_root=workspace_root,
        path_or_url=_require_non_empty_string(payload, "path_or_url"),
        options=cast(dict[str, Any] | None, payload.get("options")),
    )
    if "index" not in result:
        result["index"] = build_index(workspace_root)
    result["_meta"] = {
        "requested_operation": requested_operation,
        "resolved_operation": resolved_operation,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="intake-mcp server")
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

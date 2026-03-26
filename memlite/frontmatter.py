import json
from typing import Any


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    escaped = str(value).replace('"', '\\"')
    return f'"{escaped}"'


def dump_frontmatter(meta: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text

    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text

    raw_head = parts[0].splitlines()[1:]
    body = parts[1]
    meta: dict[str, Any] = {}
    for line in raw_head:
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value.startswith("[") and value.endswith("]"):
            try:
                meta[key] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        if value.startswith('"') and value.endswith('"'):
            meta[key] = value[1:-1].replace('\\"', '"')
            continue
        if value in {"true", "false"}:
            meta[key] = value == "true"
            continue
        if value == "null":
            meta[key] = None
            continue
        meta[key] = value
    return meta, body

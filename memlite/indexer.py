# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "zvec",
# ]
# ///

import json
import re
import shutil
from pathlib import Path
from typing import Any

from frontmatter import parse_frontmatter


CONTENT_ZONES = ["notes", "meetings", "projects", "reviews"]
TOKEN_RE = re.compile(r"[A-Za-z0-9_\u4e00-\u9fff]+")
VECTOR_DIM = 256


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def embed_text(text: str, dim: int = VECTOR_DIM) -> list[float]:
    tokens = tokenize(text)
    if not tokens:
        return [0.0] * dim
    vector = [0.0] * dim
    for token in tokens:
        slot = hash(token) % dim
        vector[slot] += 1.0
    norm = sum(value * value for value in vector) ** 0.5
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


def _rebuild_zvec_index(
    index_dir: Path, chunks: list[dict[str, Any]]
) -> dict[str, Any]:
    import zvec  # type: ignore

    zvec_dir = index_dir / "zvec"
    if zvec_dir.exists():
        shutil.rmtree(zvec_dir)

    schema = zvec.CollectionSchema(
        name="chunks",
        vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, VECTOR_DIM),
    )
    collection = zvec.create_and_open(path=str(zvec_dir), schema=schema)
    docs = [
        zvec.Doc(
            id=str(chunk["chunk_id"]),
            vectors={"embedding": embed_text(str(chunk.get("text", "")))},
        )
        for chunk in chunks
    ]
    if docs:
        collection.insert(docs)
    return {"enabled": True, "path": str(zvec_dir), "count": len(docs)}


def _load_markdown(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_text(encoding="utf-8")
    return parse_frontmatter(content)


def build_index(workspace_root: Path) -> dict[str, Any]:
    index_dir = workspace_root / "rag" / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = index_dir / "chunks.jsonl"

    chunks: list[dict[str, Any]] = []
    for zone in CONTENT_ZONES:
        zone_dir = workspace_root / zone
        if not zone_dir.exists():
            continue
        for path in sorted(zone_dir.glob("*.md")):
            meta, body = _load_markdown(path)
            paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
            if not paragraphs:
                paragraphs = [body.strip()]
            for idx, paragraph in enumerate(paragraphs):
                if not paragraph:
                    continue
                chunk = {
                    "chunk_id": f"{meta.get('id', path.stem)}#{idx}",
                    "doc_id": meta.get("id", path.stem),
                    "note_id": meta.get("id", path.stem),
                    "title": meta.get("title", path.stem),
                    "path": str(path.relative_to(workspace_root)),
                    "zone": zone,
                    "topics": meta.get("topics", []),
                    "projects": meta.get("projects", []),
                    "people": meta.get("people", []),
                    "text": paragraph,
                    "tokens": tokenize(paragraph),
                }
                chunks.append(chunk)

    with chunks_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    vector_status = _rebuild_zvec_index(index_dir=index_dir, chunks=chunks)

    return {
        "chunk_count": len(chunks),
        "index_path": str(chunks_path),
        "vector_backend": "zvec",
        "vector_index": vector_status,
    }


def load_chunks(workspace_root: Path) -> list[dict[str, Any]]:
    chunks_path = workspace_root / "rag" / "index" / "chunks.jsonl"
    if not chunks_path.exists():
        return []
    chunks: list[dict[str, Any]] = []
    for line in chunks_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "doc_id" not in row:
            row["doc_id"] = row.get("note_id")
        chunks.append(row)
    return chunks

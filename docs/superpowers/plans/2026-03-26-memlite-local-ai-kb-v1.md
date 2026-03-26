# Mem-lite Local AI KB V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first Mem-like knowledge system with file+URL ingestion, hybrid retrieval (local retrieval + optional cloud generation), and high-confidence dedup auto-merge with rollback.

**Architecture:** Keep existing `memlite` orchestration contracts and evolve internals to a SQLite-backed metadata/index layer with pluggable vector search. Expose new MCP operations while preserving old aliases for compatibility. Implement dedup and rollback as first-class state transitions with snapshot integrity checks.

**Tech Stack:** Python 3.13, SQLite (FTS5), pytest, local file storage, optional cloud LLM API for generation fallback path.

---

## File Structure and Responsibilities

- `memlite/storage.py` (create): SQLite connection, schema migration bootstrap, transaction helpers.
- `memlite/models.py` (create): typed row mappers and constants for document/chunk/entity/edge/merge states.
- `memlite/intake.py` (create): file and URL ingestion adapters, normalization, extraction quality flags.
- `memlite/dedup.py` (create): duplicate candidate generation, confidence scoring, merge and rollback orchestration.
- `memlite/indexer.py` (modify): move from JSONL-only chunks to SQLite-backed chunk persistence + incremental index.
- `memlite/rag.py` (modify): hybrid scoring backed by DB/vector store, citation-safe answer synthesis and cloud fallback policy.
- `memlite/knowledge_store.py` (modify): persist `merged_into`, `merge_id`, `merge_state`, dedup groups, merge logs.
- `memlite/workflows.py` (modify): add import/dedup/rollback workflows and keep existing command compatibility.
- `mcp/intake-mcp/server.py` (create): MCP-facing ingestion entrypoint.
- `mcp/knowledge-store-mcp/server.py` (modify): add `upsert_document`, `dedup_scan`, `dedup_merge`, `dedup_rollback`, alias old ops.
- `mcp/rag-mcp/server.py` (modify): add `ask_with_citations`, keep old operation aliases.
- `commands/dedup.md` (create): operator-facing dedup command contract.
- `skills/dedup-curation/SKILL.md` (create): merge/review/rollback flow guidance.
- `tests/test_storage_schema.py` (create): schema and migration invariants.
- `tests/test_intake_pipeline.py` (create): md/txt/pdf/url import and idempotency tests.
- `tests/test_hybrid_retrieval.py` (create): lexical+semantic fusion and unknown fallback tests.
- `tests/test_dedup_merge_rollback.py` (create): merge invariants and rollback integrity tests.
- `tests/test_mcp_compatibility.py` (create): old/new MCP API behavior parity tests.
- `tests/test_command_contracts.py` (create): command/agent contract checks for operation names and required outputs.
- `tests/test_dedup_eval_gate.py` (create): precision gate and Wilson CI enforcement for auto-merge enablement.
- `scripts/benchmark_kb.py` (create): repeatable local benchmark for ingest/index/query metrics.
- `docs/superpowers/specs/2026-03-26-memlite-local-ai-kb-design.md` (reference): source spec, do not drift.

### Task 1: Storage and Schema Foundation

**Files:**
- Create: `memlite/storage.py`
- Create: `memlite/models.py`
- Modify: `memlite/__init__.py`
- Test: `tests/test_storage_schema.py`

- [ ] **Step 1: Write the failing schema tests**

```python
from pathlib import Path

from memlite.storage import init_db, with_db


def test_init_db_creates_required_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "kb.db"
    init_db(db_path)
    with with_db(db_path) as conn:
        names = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type='table'"
            ).fetchall()
        }
    assert {"documents", "chunks", "entities", "doc_edges", "dedup_groups", "merge_logs"}.issubset(names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage_schema.py::test_init_db_creates_required_tables -v`
Expected: FAIL with import or missing table errors.

- [ ] **Step 3: Implement minimal DB bootstrap and helpers**

```python
def init_db(db_path: Path) -> None:
    ...

@contextmanager
def with_db(db_path: Path) -> Iterator[sqlite3.Connection]:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

Run:
```bash
git add memlite/storage.py memlite/models.py memlite/__init__.py tests/test_storage_schema.py
git commit -m "feat(storage): add sqlite schema bootstrap for kb entities"
```

### Task 2: Intake Pipeline for File and URL

**Files:**
- Create: `memlite/intake.py`
- Modify: `memlite/workflows.py`
- Modify: `memlite/cli.py`
- Test: `tests/test_intake_pipeline.py`

- [ ] **Step 1: Write failing intake tests (file/url/idempotency)**

```python
def test_import_url_sets_source_fields(...):
    result = import_document(...)
    assert result["source_type"] == "url"
    assert result["source_uri"].startswith("https://")
    assert result["captured_at"]


def test_degraded_extraction_sets_quality_flags(...):
    result = import_document(...)
    assert result["extraction_quality"]["degraded"] is True
    assert result["extraction_quality"]["reason"]


def test_reimport_same_source_is_idempotent(...):
    first = import_document(...)
    second = import_document(...)
    assert first["document_id"] == second["document_id"]


def test_import_persists_entities(...):
    result = import_document(...)
    assert result["entities"]
    assert any(e["type"] == "project" for e in result["entities"])


def test_import_persists_queryable_relation_edges(...):
    result = import_document(...)
    assert result["edges"]
    assert any(edge["edge_type"] == "related" for edge in result["edges"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_intake_pipeline.py -v`
Expected: FAIL with missing `import_document` workflow and schema fields.

- [ ] **Step 3: Implement minimal intake adapters**

```python
def import_document(workspace_root: Path, path_or_url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    ...
```

- [ ] **Step 4: Wire CLI command and workflow call**

Run: `python -m memlite.cli --workspace-root . capture "hello #kb"`
Expected: JSON output includes note/document metadata and index refresh result.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_intake_pipeline.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

Run:
```bash
git add memlite/intake.py memlite/workflows.py memlite/cli.py tests/test_intake_pipeline.py
git commit -m "feat(intake): add file and url ingestion with idempotent upsert"
```

### Task 3: Hybrid Retrieval and RAG Guardrails

**Files:**
- Modify: `memlite/indexer.py`
- Modify: `memlite/rag.py`
- Modify: `memlite/workflows.py`
- Test: `tests/test_hybrid_retrieval.py`

- [ ] **Step 1: Write failing hybrid retrieval tests**

```python
def test_hybrid_search_combines_lexical_and_semantic_scores(...):
    rows = hybrid_search(...)
    assert rows
    assert "hybrid_score" in rows[0]


def test_answer_returns_unknown_on_low_evidence(...):
    out = answer_from_context("unrelated question", [])
    assert out["answer"] == "unknown"


def test_non_unknown_answers_always_include_citations(...):
    out = ask_with_citations(...)
    if out["answer"] != "unknown":
        assert out["citations"]
        assert {"doc_id", "chunk_id", "snippet"}.issubset(out["citations"][0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_hybrid_retrieval.py -v`
Expected: FAIL with missing DB-backed scoring/citation behavior.

- [ ] **Step 3: Implement minimal index and retrieval updates**

```python
def build_index(workspace_root: Path, incremental: bool = True) -> dict[str, Any]:
    ...


def ask_with_citations(workspace_root: Path, question: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    ...
```

- [ ] **Step 4: Add cloud-generation opt-in and fallback**

Run: `pytest tests/test_hybrid_retrieval.py::test_answer_returns_unknown_on_low_evidence -v`
Expected: PASS with default local-only behavior when cloud mode disabled.

- [ ] **Step 5: Run full retrieval tests**

Run: `pytest tests/test_hybrid_retrieval.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

Run:
```bash
git add memlite/indexer.py memlite/rag.py memlite/workflows.py tests/test_hybrid_retrieval.py
git commit -m "feat(rag): implement hybrid retrieval with citation-safe answering"
```

### Task 4: Dedup Scan, Auto-Merge, and Rollback

**Files:**
- Create: `memlite/dedup.py`
- Modify: `memlite/knowledge_store.py`
- Modify: `memlite/workflows.py`
- Test: `tests/test_dedup_merge_rollback.py`

- [ ] **Step 1: Write failing dedup tests**

```python
def test_auto_merge_sets_merged_fields_and_group(...):
    result = dedup_merge(..., group_id_or_doc_ids=["doc-1", "doc-2"])
    assert result["merge_id"]
    assert result["canonical_doc_id"]
    assert result["compressed_summary"]
    assert result["diff_notes"]


def test_rollback_restores_premerge_state(...):
    rollback = dedup_rollback(...)
    assert rollback["restored"] is True
    assert rollback["before_snapshot"]["documents"] == rollback["after_snapshot"]["documents"]
    assert rollback["before_snapshot"]["chunks"] == rollback["after_snapshot"]["chunks"]
    assert rollback["before_snapshot"]["doc_edges"] == rollback["after_snapshot"]["doc_edges"]
    assert rollback["dangling_refs"] == []


def test_post_rollback_documents_are_searchable(...):
    dedup_rollback(...)
    lexical = keyword_search(...)
    semantic = semantic_search(...)
    assert lexical
    assert semantic
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dedup_merge_rollback.py -v`
Expected: FAIL with missing dedup APIs and merge state fields.

- [ ] **Step 3: Implement dedup scan and threshold routing**

```python
def dedup_scan(workspace_root: Path, threshold_profile: dict[str, float] | None = None) -> dict[str, Any]:
    ...
```

- [ ] **Step 4: Implement merge + snapshot logging + rollback**

```python
def dedup_merge(
    workspace_root: Path,
    group_id_or_doc_ids: str | list[str],
    mode: str = "auto",
) -> dict[str, Any]:
    ...


def dedup_rollback(workspace_root: Path, merge_id: str) -> dict[str, Any]:
    ...
```

Implementation checkpoint:
- emit `compressed_summary` for the canonical record
- persist merge `diff_notes` describing member-to-canonical deltas

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dedup_merge_rollback.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

Run:
```bash
git add memlite/dedup.py memlite/knowledge_store.py memlite/workflows.py tests/test_dedup_merge_rollback.py
git commit -m "feat(dedup): add auto-merge pipeline with snapshot rollback"
```

### Task 5: MCP API Expansion and Compatibility Aliases

**Files:**
- Create: `mcp/intake-mcp/server.py`
- Modify: `mcp/knowledge-store-mcp/server.py`
- Modify: `mcp/rag-mcp/server.py`
- Test: `tests/test_mcp_compatibility.py`

- [ ] **Step 1: Write failing MCP compatibility tests**

```python
def test_old_and_new_knowledge_ops_both_work(...):
    assert call("create_note", payload)["note_id"]
    assert call("upsert_document", payload)["document_id"]


def test_alias_parity_for_update_answer_and_links(...):
    assert call("update_note", payload)["updated"] is True
    assert call("answer_from_context", payload)["answer"]
    assert call("link_notes", payload)["linked"] is True
    assert call("link_documents", payload)["linked"] is True


def test_semantic_search_operation_available(...):
    result = call("semantic_search", {"query": "project alpha", "limit": 3})
    assert "results" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mcp_compatibility.py -v`
Expected: FAIL with missing new operations and aliases.

- [ ] **Step 3: Implement new MCP operations and alias mapping**

```python
ALIAS_OPS = {
    "create_note": "upsert_document",
    "update_note": "upsert_document",
    "search_notes": "hybrid_search",
    "answer_from_context": "ask_with_citations",
    "link_notes": "link_documents",
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_mcp_compatibility.py -v`
Expected: PASS, including checks for:
- M1-M2 dual availability (old and new operations callable)
- M3 default routing to new operation names in command payloads
- M4 deprecation warning emission while old operations still execute

- [ ] **Step 5: Commit**

Run:
```bash
git add mcp/intake-mcp/server.py mcp/knowledge-store-mcp/server.py mcp/rag-mcp/server.py tests/test_mcp_compatibility.py
git commit -m "feat(mcp): add intake service and backward-compatible api aliases"
```

### Task 6: Command and Skill Wiring for New Flows

**Files:**
- Create: `commands/dedup.md`
- Create: `skills/dedup-curation/SKILL.md`
- Modify: `commands/capture.md`
- Modify: `commands/ask.md`
- Modify: `agents/capture-agent.md`
- Modify: `agents/knowledge-agent.md`
- Test: `tests/test_command_contracts.py`

- [ ] **Step 1: Write failing command contract tests**

```python
from pathlib import Path


def test_capture_command_uses_import_document_contract() -> None:
    text = Path("commands/capture.md").read_text(encoding="utf-8")
    assert "import_document" in text


def test_dedup_command_exposes_scan_merge_rollback() -> None:
    text = Path("commands/dedup.md").read_text(encoding="utf-8")
    assert "dedup_scan" in text
    assert "dedup_merge" in text
    assert "dedup_rollback" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_command_contracts.py -v`
Expected: FAIL with missing `commands/dedup.md` and missing `import_document` references.

- [ ] **Step 3: Update commands/skills/agents to new operation names with alias-safe behavior**

Run: `pytest tests/test_command_contracts.py -v`
Expected: PASS with updated command contracts.

- [ ] **Step 4: Commit**

Run:
```bash
git add commands/dedup.md skills/dedup-curation/SKILL.md commands/capture.md commands/ask.md agents/capture-agent.md agents/knowledge-agent.md
git commit -m "chore(workflows): wire commands and skills to v1 kb operations"
```

### Task 7: Dedup Precision Gate and Release Toggle

**Files:**
- Create: `tests/test_dedup_eval_gate.py`
- Modify: `memlite/dedup.py`
- Modify: `memlite/workflows.py`

- [ ] **Step 1: Write failing dedup gate tests**

```python
def test_auto_merge_disabled_when_precision_gate_fails(...):
    report = run_dedup_eval(...)
    assert report["auto_merge_enabled"] is False
    assert report["pair_count"] >= 1000
    assert report["hard_negative_count"] > 0
    assert report["labeling_provenance"]["adjudication"] is True


def test_auto_merge_enabled_when_wilson_lower_bound_passes(...):
    report = run_dedup_eval(...)
    assert report["wilson_lower_bound"] > 0.95
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dedup_eval_gate.py -v`
Expected: FAIL with missing evaluation gate implementation.

- [ ] **Step 3: Implement evaluation gate and workflow toggles**

```python
def run_dedup_eval(workspace_root: Path, labeled_pairs_path: Path) -> dict[str, Any]:
    ...
```

Implementation checkpoint:
- validate labeled set has at least 1,000 pairs and includes hard negatives
- include labeling provenance metadata (reviewer count, adjudication flag)
- deny auto-merge if protocol requirements are not met

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dedup_eval_gate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

Run:
```bash
git add tests/test_dedup_eval_gate.py memlite/dedup.py memlite/workflows.py
git commit -m "feat(dedup): enforce precision gate before enabling auto-merge"
```

### Task 8: Full Verification, Benchmarks, and Documentation Sync

**Files:**
- Modify: `docs/superpowers/specs/2026-03-26-memlite-local-ai-kb-design.md` (only if measured numbers need annotation)
- Create: `docs/superpowers/plans/2026-03-26-memlite-local-ai-kb-v1-verification.md`
- Create: `scripts/benchmark_kb.py`
- Modify: `mcp/knowledge-store-mcp/README.md`
- Modify: `mcp/rag-mcp/README.md`

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: PASS.

- [ ] **Step 2: Run smoke scenarios for required acceptance criteria**

Run:
```bash
python -m memlite.cli --workspace-root . capture "project alpha decision"
python -m memlite.cli --workspace-root . ask "what did we decide for project alpha"
python mcp/knowledge-store-mcp/server.py --workspace-root . dedup_scan --payload '{}'
```
Expected: successful JSON responses with citations for ask and actionable dedup output.

- [ ] **Step 3: Record benchmark results and gaps**

Run: `python scripts/benchmark_kb.py --workspace-root . --target-size 10000`
Expected: metrics file with index duration, ingest throughput, retrieval p95/p99 and explicit pass/fail gates for:
- full index build for 10k corpus <= 45 minutes
- incremental ingest throughput >= 20 docs/minute at 10k corpus size
- retrieval latency at 10k corpus: p95 < 1.5s, p99 < 2.5s
- baseline machine metadata (8 CPU cores, 32 GB RAM, NVMe SSD) recorded

Run: `python scripts/benchmark_kb.py --workspace-root . --target-size 100000 --soak`
Expected: 100k soak metrics recorded as non-blocking evidence.

- [ ] **Step 4: Document verification evidence**

Add measured outcomes and known deltas to `docs/superpowers/plans/2026-03-26-memlite-local-ai-kb-v1-verification.md`.
Include dedup protocol evidence: sample size, hard negatives, and labeling/adjudication provenance.
Include ingestion parse-success evidence (`>=95%`) for clean `md`, `txt`, `pdf`, and `url` samples.

- [ ] **Step 5: Commit**

Run:
```bash
git add docs/superpowers/plans/2026-03-26-memlite-local-ai-kb-v1-verification.md scripts/benchmark_kb.py mcp/knowledge-store-mcp/README.md mcp/rag-mcp/README.md
git commit -m "docs: add v1 verification evidence and benchmark procedure"
```

### Task 9: Graph Enrichment and Discovery (M4)

**Files:**
- Modify: `memlite/knowledge_store.py`
- Modify: `memlite/workflows.py`
- Modify: `memlite/dedup.py`
- Test: `tests/test_graph_enrichment.py`

- [ ] **Step 1: Write failing graph enrichment tests**

```python
def test_edge_discovery_adds_same_topic_and_follow_up_links(...):
    result = run_graph_enrichment(...)
    assert result["new_edges"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_graph_enrichment.py -v`
Expected: FAIL with missing discovery/enrichment workflow.

- [ ] **Step 3: Implement relation-edge enrichment workflow**

```python
def run_graph_enrichment(workspace_root: Path, limit: int = 500) -> dict[str, Any]:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_graph_enrichment.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

Run:
```bash
git add memlite/knowledge_store.py memlite/workflows.py memlite/dedup.py tests/test_graph_enrichment.py
git commit -m "feat(graph): add relation edge discovery and enrichment workflow"
```

## Execution Notes

- Keep tasks in order; do not start dedup before storage and intake are stable.
- If a task exceeds one focused session, split it into two commits but preserve TDD order.
- Do not remove old MCP operations until M4 deprecation phase.
- Validate migration phases explicitly:
  - M1-M2: old and new MCP operations both callable
  - M3: commands/skills default to new operation names
  - M4: old names emit deprecation warnings but still execute
- Prefer feature flags for cloud generation and auto-merge enablement.

# Mem-lite Local AI KB Design (V1)

## 1. Scope and Decisions

This design defines a local-first knowledge tool similar to Mem, aligned to the current repository (`memlite`, MCP servers, commands, skills).

Confirmed constraints:

- Import scope: local files + webpage URL ingestion
- Retrieval mode: local retrieval + optional cloud generation (hybrid)
- Dedup mode: high-confidence auto-merge with rollback logs
- Target scale: 10k-100k items (single-user or small team)

Non-goals for V1:

- Multi-tenant SaaS architecture
- Heavy distributed search stack in first release
- Fully autonomous destructive merge without rollback trail

## 2. Candidate Approaches

### Approach A (Recommended): SQLite + FTS5 + local vector backend

- Pros: lightest local deployment, fast MVP iteration, low ops overhead
- Cons: limited headroom for high concurrency and very large corpora

### Approach B: PostgreSQL + pgvector

- Pros: better long-term scaling, clearer migration path for team usage
- Cons: higher local setup complexity, slower initial delivery

### Approach C: Dedicated search/vector platform first

- Pros: strongest retrieval flexibility and feature depth
- Cons: over-engineered for V1, heavy operations burden

Decision: implement Approach A for V1 while keeping interfaces portable for migration to Approach B.

## 3. High-Level Architecture

### 3.1 Ingestion and Normalization

Input adapters:

- Local files: `md`, `txt`, `pdf`
- Web pages: URL fetch and text extraction

All inputs normalize into a canonical document model (`NormalizedDocument`) with:

- source metadata (`source_type`, `source_uri`, `captured_at`)
- normalized text (`content_markdown`, `content_text`)
- content fingerprints (`content_hash`, optional simhash/minhash)

### 3.2 Auto-Organization and Linking

Use rules + model-assisted extraction to build structured metadata:

- entities: topic, project, person, org, keyword
- relation edges: `related`, `same_topic`, `follow_up`, `duplicate_of`

Relations are persisted and queryable, not implicit only.

### 3.3 Indexing and Retrieval

- Lexical index: FTS5/BM25 over title/summary/body/tags
- Semantic index: chunk embeddings in local vector backend
- Hybrid retrieval: lexical + semantic recall, then rerank

### 3.4 RAG Answering

- Retrieve TopK chunks from hybrid pipeline
- Rerank and produce grounded answer
- Always include citations (`doc_id`, `chunk_id`, snippet)
- If evidence insufficient, return `unknown`

Generation policy:

- default `cloud_generation=false`
- retrieval path is always local-only and no-egress
- cloud generation is explicit opt-in (`cloud_generation=true`)
- on cloud timeout/failure, fallback to local extractive answer mode

### 3.5 Dedup and Compression

- Candidate generation: exact hash + near-duplicate heuristics
- Verification: embedding similarity + metadata consistency
- High-confidence auto-merge; medium confidence to review queue
- Persistent merge logs and snapshot-based rollback

## 4. Data Model

## 4.1 `documents`

- `id`
- `source_type` (`file` | `url`)
- `source_uri`
- `title`
- `summary`
- `content_markdown`
- `content_text`
- `language`
- `created_at`
- `updated_at`
- `content_hash`
- `status` (`active`, `merged`, `archived`)
- `merged_into` (nullable `document_id`)
- `merge_id` (nullable)
- `merge_state` (`none`, `auto_merged`, `manual_merged`, `rolled_back`)

## 4.2 `chunks`

- `chunk_id`
- `document_id`
- `seq`
- `text`
- `token_count`
- `embedding`
- `chunk_hash`

## 4.3 `entities`

- `entity_id`
- `type` (`topic`, `project`, `person`, `org`, `keyword`)
- `name`
- `aliases`

## 4.4 `doc_edges`

- `from_doc`
- `to_doc`
- `edge_type` (`related`, `duplicate_of`, `same_topic`, `follow_up`)
- `score`
- `evidence`

## 4.5 `dedup_groups`

- `group_id`
- `canonical_doc_id`
- `member_doc_ids`
- `confidence`
- `created_at`

## 4.6 `merge_logs`

- `merge_id`
- `group_id`
- `operation` (`auto_merge`, `split`, `rollback`)
- `before_snapshot`
- `after_snapshot`
- `operator`
- `ts`

## 5. Retrieval and RAG Pipeline

1. Query preprocessing and filters
2. Lexical recall (FTS/BM25)
3. Semantic recall (vector similarity)
4. Candidate merge and score fusion
5. Optional rerank (local or cloud reranker)
6. Answer synthesis from TopK context
7. Citation emission and confidence calculation

Fusion score baseline:

- `score = a * bm25 + b * vector + c * recency + d * edge_boost`

Confidence guardrail:

- low evidence or low final score => `unknown`

## 6. Dedup and Compression Strategy

Candidate stages:

1. exact duplicate by `content_hash`
2. near duplicate by simhash/minhash + title similarity

Verification features:

- embedding cosine similarity
- title/body edit distance
- source and timestamp consistency

Threshold profile (initial):

- `>= 0.93`: auto-merge
- `0.85 - 0.93`: review queue
- `< 0.85`: keep separate, store candidate evidence only

Merge behavior:

- choose canonical document by completeness + references + freshness
- mark members as merged (`merged_into`), do not hard-delete
- generate compressed summary and store diff notes
- invariants:
  - exactly one active canonical document per dedup group
  - all non-canonical members must carry `status=merged` and non-null `merged_into`
  - `merged_into` must point to an active canonical in the same group

Rollback behavior:

- restore from `before_snapshot` by `merge_id`
- rebuild affected relation edges and chunk references

### 6.1 Dedup evaluation protocol

- labeled dataset:
  - minimum 1,000 candidate pairs sampled from real corpus
  - include hard negatives (same topic but non-duplicates)
- labeling process:
  - two-pass human labeling; conflicts resolved by adjudication
- metric:
  - auto-merge precision on pairs scored `>= 0.93`
  - Wilson 95% confidence interval lower bound must stay above 0.95
- release gate:
  - auto-merge remains disabled if precision gate fails
  - failed gate falls back to review queue for all candidates

## 7. MCP API Surface (V1)

Planned tool APIs:

- `import_document(path_or_url, options)`
- `upsert_document(doc)`
- `build_index(scope)`
- `semantic_search(query, filters, top_k)`
- `hybrid_search(query, filters, top_k)`
- `ask_with_citations(question, filters)`
- `dedup_scan(scope, threshold_profile)`
- `dedup_merge(group_id_or_doc_ids, mode)`
- `dedup_rollback(merge_id)`
- `link_documents(from_id, to_id, edge_type, score)`

### 7.1 Compatibility matrix and migration

To avoid breaking existing commands/skills, V1 keeps backward-compatible aliases:

- `create_note` -> `upsert_document`
- `update_note` -> `upsert_document`
- `search_notes` -> `hybrid_search`
- `answer_from_context` -> `ask_with_citations`
- `link_notes` -> `link_documents`

Migration policy:

- milestone M1-M2: old + new APIs both available
- milestone M3: commands/skills switch to new API names
- milestone M4: old APIs marked deprecated but still callable

## 8. Repository Mapping and Evolution Plan

Current repository already contains a strong MVP skeleton:

- `memlite/workflows.py`: orchestration entry points
- `memlite/indexer.py`: index build over markdown zones
- `memlite/rag.py`: semantic/keyword/hybrid/re-rank/answer contracts
- `memlite/knowledge_store.py`: note CRUD and linking
- `mcp/knowledge-store-mcp`, `mcp/rag-mcp`: MCP modules
- `commands/*.md`, `skills/*`: behavior-level orchestration

Evolution path:

1. Keep workflow interfaces stable; improve internals first
2. Upgrade `indexer` from JSONL-only chunks to pluggable backends
3. Extend `knowledge_store` with dedup groups, merge logs, rollback
4. Keep `rag.py` function signatures but swap in stronger retrieval/rerank backends
5. Add intake MCP module for URL/file parsing and normalization

## 9. Milestones

### M1 (Week 1): Intake + schema + incremental index

- File and URL ingestion adapters
- Canonical document/chunk schema persistence
- Incremental index refresh

### M2 (Week 2): Hybrid retrieval + grounded answering

- FTS + vector recall fusion
- Citation formatting and confidence gating
- strict `unknown` fallback

### M3 (Week 3): Dedup/merge/rollback

- Candidate scan and confidence scoring
- Auto-merge execution for high-confidence duplicates
- Snapshot-based rollback tooling

### M4 (Week 4): Graph enrichment + performance hardening

- Relation edge improvements and discovery
- Batch compression summaries
- performance tuning for 10k-100k item target

## 10. Acceptance Criteria (V1)

- Ingestion support is validated for `md`, `txt`, `pdf`, and `url`:
  - parse success >= 95% for clean inputs
  - each imported document stores `source_type`, `source_uri`, `captured_at`
  - re-importing identical source is idempotent (no duplicate active documents)
  - degraded extractions emit extraction-quality flags
- Scale validation under a defined baseline machine (8 CPU cores, 32 GB RAM, NVMe SSD):
  - corpus size target: 10k documents mandatory, 100k soak target
  - full index build for 10k corpus <= 45 minutes
  - incremental ingest throughput >= 20 docs/minute at 10k corpus size
  - retrieval latency at 10k corpus: p95 < 1.5s, p99 < 2.5s (no cloud generation)
- High-confidence auto-merge precision gate passes per §6.1 protocol
- Every merge operation is rollback-verifiable by `merge_id`:
  - `documents/chunks/doc_edges` identity and counts restore to `before_snapshot`
  - no dangling `duplicate_of` or `merged_into` references after rollback
  - restored documents are searchable in both lexical and semantic retrieval
- Answer outputs always include citations; low evidence returns `unknown`

## 11. Risks and Mitigations

- False-positive merges: mitigate with conservative thresholds + rollback logs
- Retrieval drift across mixed content: mitigate with periodic eval set and rerank tuning
- URL extraction variability: mitigate with adapter fallback and extraction quality flags
- Local resource limits: mitigate with incremental indexing and configurable chunking limits

## 12. Testing Strategy

- Unit tests:
  - normalization, chunking, tokenization, scoring, merge thresholding
- Integration tests:
  - end-to-end `import -> index -> ask -> cite`
  - dedup merge and rollback recovery
- Regression tests:
  - fixed query set with expected citation coverage

## 13. Open Questions for Planning Stage

- exact local vector backend choice for V1 (SQLite extension vs lightweight embedded store)
- default cloud generation provider and fallback policy
- PDF extraction library choice and OCR fallback behavior

These open items will be closed in the implementation planning phase.

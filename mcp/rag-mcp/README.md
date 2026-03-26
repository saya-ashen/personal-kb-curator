# rag-mcp

Retrieval MCP server for semantic/hybrid search, reranking, and answer generation with citations.

Primary operations:

- `semantic_search`
- `hybrid_search`
- `rerank_results`
- `ask_with_citations`

Default operation behavior:

- if no operation is provided, the server defaults to `ask_with_citations`
- operation can also be routed from payload fields (`operation`, `command`, `dispatch`)

Compatibility aliases (deprecated, still callable):

- `search_notes` -> `hybrid_search`
- `answer_from_context` -> `ask_with_citations`

Operation responses include `_meta.requested_operation` and `_meta.resolved_operation`, plus a deprecation warning payload when an alias is used.

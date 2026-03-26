# knowledge-store-mcp

MCP server for document upsert, retrieval, linking, and dedup lifecycle actions.

Primary operations:

- `upsert_document`
- `get_note`
- `build_index`
- `hybrid_search`
- `link_documents`
- `list_related_notes`
- `dedup_scan`
- `dedup_merge`
- `dedup_rollback`

Default operation behavior:

- if no operation is provided, the server defaults to `upsert_document`
- operation can also be routed from payload fields (`operation`, `command`, `dispatch`)

`upsert_document` side effects:

- executes a synchronous `build_index` after create or update
- response includes the fresh index payload under `index`

Compatibility aliases (deprecated, still callable):

- `create_note` -> `upsert_document`
- `update_note` -> `upsert_document`
- `search_notes` -> `hybrid_search`
- `link_notes` -> `link_documents`

The server returns `_meta.requested_operation` and `_meta.resolved_operation` for routing visibility, and emits deprecation warnings for aliased operations.

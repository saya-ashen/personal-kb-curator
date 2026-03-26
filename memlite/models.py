"""Shared schema constants for memlite storage."""

from typing import Final


REQUIRED_TABLES: Final[frozenset[str]] = frozenset(
    {
        "documents",
        "chunks",
        "entities",
        "doc_edges",
        "dedup_groups",
        "merge_logs",
    }
)


SCHEMA_STATEMENTS: Final[tuple[str, ...]] = (
    """
    CREATE TABLE IF NOT EXISTS documents (
        doc_id TEXT PRIMARY KEY,
        title TEXT NOT NULL DEFAULT '',
        source_type TEXT NOT NULL DEFAULT 'file',
        source_uri TEXT,
        body TEXT NOT NULL DEFAULT '',
        content_hash TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
        chunk_id TEXT PRIMARY KEY,
        doc_id TEXT NOT NULL,
        ord INTEGER NOT NULL,
        text TEXT NOT NULL,
        token_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (doc_id) REFERENCES documents (doc_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entities (
        entity_id TEXT PRIMARY KEY,
        doc_id TEXT NOT NULL,
        chunk_id TEXT,
        name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (doc_id) REFERENCES documents (doc_id) ON DELETE CASCADE,
        FOREIGN KEY (chunk_id) REFERENCES chunks (chunk_id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS doc_edges (
        edge_id TEXT PRIMARY KEY,
        src_doc_id TEXT NOT NULL,
        dst_doc_id TEXT NOT NULL,
        edge_type TEXT NOT NULL,
        weight REAL NOT NULL DEFAULT 0,
        evidence TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY (src_doc_id) REFERENCES documents (doc_id) ON DELETE CASCADE,
        FOREIGN KEY (dst_doc_id) REFERENCES documents (doc_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dedup_groups (
        group_id TEXT PRIMARY KEY,
        canonical_doc_id TEXT,
        state TEXT NOT NULL DEFAULT 'candidate',
        confidence REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (canonical_doc_id) REFERENCES documents (doc_id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS merge_logs (
        merge_id TEXT PRIMARY KEY,
        group_id TEXT NOT NULL,
        canonical_doc_id TEXT NOT NULL,
        merged_doc_ids TEXT NOT NULL,
        snapshot_before TEXT NOT NULL,
        snapshot_after TEXT,
        diff_notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY (group_id) REFERENCES dedup_groups (group_id) ON DELETE CASCADE,
        FOREIGN KEY (canonical_doc_id) REFERENCES documents (doc_id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_chunks_doc_ord ON chunks (doc_id, ord)",
    "CREATE INDEX IF NOT EXISTS idx_entities_doc ON entities (doc_id)",
    "CREATE INDEX IF NOT EXISTS idx_doc_edges_src ON doc_edges (src_doc_id)",
    "CREATE INDEX IF NOT EXISTS idx_doc_edges_dst ON doc_edges (dst_doc_id)",
    "CREATE INDEX IF NOT EXISTS idx_dedup_groups_state ON dedup_groups (state)",
    "CREATE INDEX IF NOT EXISTS idx_merge_logs_group ON merge_logs (group_id)",
)

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from memlite.models import REQUIRED_TABLES
from memlite.storage import init_db, with_db


class StorageSchemaTests(unittest.TestCase):
    def _table_names(self, db_path: Path) -> set[str]:
        with with_db(db_path) as conn:
            return {
                row[0]
                for row in conn.execute(
                    "select name from sqlite_master where type='table'"
                ).fetchall()
            }

    def test_init_db_creates_required_tables(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "kb.db"
            init_db(db_path)
            names = self._table_names(db_path)

        self.assertTrue(REQUIRED_TABLES.issubset(names))

    def test_init_db_is_idempotent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "kb.db"
            init_db(db_path)
            init_db(db_path)
            names = self._table_names(db_path)

        self.assertTrue(REQUIRED_TABLES.issubset(names))

    def test_with_db_commits_on_success(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "kb.db"
            init_db(db_path)

            with with_db(db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO documents (
                        doc_id, title, source_type, source_uri, body,
                        content_hash, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "doc-commit",
                        "Commit Test",
                        "file",
                        "file:///tmp/doc-commit.md",
                        "body",
                        "hash-commit",
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:00:00Z",
                    ),
                )

            with with_db(db_path) as conn:
                row = conn.execute(
                    "SELECT doc_id FROM documents WHERE doc_id = ?",
                    ("doc-commit",),
                ).fetchone()

        self.assertEqual(("doc-commit",), row)

    def test_with_db_rolls_back_on_exception(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "kb.db"
            init_db(db_path)

            with self.assertRaises(RuntimeError):
                with with_db(db_path) as conn:
                    conn.execute(
                        """
                        INSERT INTO documents (
                            doc_id, title, source_type, source_uri, body,
                            content_hash, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "doc-rollback",
                            "Rollback Test",
                            "file",
                            "file:///tmp/doc-rollback.md",
                            "body",
                            "hash-rollback",
                            "2026-01-01T00:00:00Z",
                            "2026-01-01T00:00:00Z",
                        ),
                    )
                    raise RuntimeError("force rollback")

            with with_db(db_path) as conn:
                row = conn.execute(
                    "SELECT doc_id FROM documents WHERE doc_id = ?",
                    ("doc-rollback",),
                ).fetchone()

        self.assertIsNone(row)

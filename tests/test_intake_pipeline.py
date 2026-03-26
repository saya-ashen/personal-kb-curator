from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from memlite.intake import import_document
from memlite.storage import with_db


class IntakePipelineTests(unittest.TestCase):
    def _table_count(self, workspace_root: Path, table: str) -> int:
        with with_db(workspace_root / "kb.db") as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0])

    def test_import_url_sets_source_fields(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)

            def fake_fetch(url: str) -> dict[str, str]:
                return {
                    "title": "Example URL",
                    "text": f"Captured from {url} for project Atlas",
                }

            result = import_document(
                workspace_root=workspace_root,
                path_or_url="https://example.test/memlite",
                options={"fetch_url": fake_fetch},
            )

        self.assertEqual("url", result["source_type"])
        self.assertEqual("https://example.test/memlite", result["source_uri"])
        self.assertTrue(result["captured_at"])

    def test_url_fetch_failure_sets_degraded_extraction_flags(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)

            def failing_fetch(_: str) -> dict[str, str]:
                raise RuntimeError("timeout")

            result = import_document(
                workspace_root=workspace_root,
                path_or_url="https://example.test/fail",
                options={"fetch_url": failing_fetch},
            )

        self.assertEqual("url", result["source_type"])
        self.assertTrue(result["extraction_quality"]["degraded"])
        self.assertIn("fetch_failed", result["extraction_quality"]["reason"])

    def test_degraded_extraction_sets_quality_flags(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            pdf_path = workspace_root / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\n")

            result = import_document(
                workspace_root=workspace_root, path_or_url=str(pdf_path)
            )

        self.assertTrue(result["extraction_quality"]["degraded"])
        self.assertTrue(result["extraction_quality"]["reason"])

    def test_reimport_same_source_is_idempotent_and_counts_stable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            note_path = workspace_root / "source.txt"
            note_path.write_text("project Atlas decision note", encoding="utf-8")

            first = import_document(
                workspace_root=workspace_root, path_or_url=str(note_path)
            )
            counts_before = {
                table: self._table_count(workspace_root, table)
                for table in ["documents", "chunks", "entities", "doc_edges"]
            }

            second = import_document(
                workspace_root=workspace_root, path_or_url=str(note_path)
            )
            counts_after = {
                table: self._table_count(workspace_root, table)
                for table in ["documents", "chunks", "entities", "doc_edges"]
            }

        self.assertEqual(first["document_id"], second["document_id"])
        self.assertEqual(counts_before, counts_after)

    def test_canonical_file_path_keeps_same_document_id(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            docs_dir = workspace_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            note_path = docs_dir / "canon.txt"
            note_path.write_text("project Atlas", encoding="utf-8")

            first = import_document(
                workspace_root=workspace_root, path_or_url="docs/canon.txt"
            )
            second = import_document(
                workspace_root=workspace_root, path_or_url=str(note_path.resolve())
            )

            symlink_path = workspace_root / "alias.txt"
            try:
                symlink_path.symlink_to(note_path)
            except (OSError, NotImplementedError):
                symlink_result = second
            else:
                symlink_result = import_document(
                    workspace_root=workspace_root,
                    path_or_url=str(symlink_path),
                )

        self.assertEqual(first["document_id"], second["document_id"])
        self.assertEqual(first["document_id"], symlink_result["document_id"])

    def test_import_persists_entities(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            note_path = workspace_root / "entities.txt"
            note_path.write_text("Project Atlas with @saya", encoding="utf-8")

            result = import_document(
                workspace_root=workspace_root, path_or_url=str(note_path)
            )

            with with_db(workspace_root / "kb.db") as conn:
                rows = conn.execute(
                    "SELECT entity_type, name FROM entities WHERE doc_id = ?",
                    (result["document_id"],),
                ).fetchall()

        self.assertTrue(result["entities"])
        self.assertTrue(
            any(entity["type"] == "project" for entity in result["entities"])
        )
        self.assertTrue(any(row[0] == "project" for row in rows))

    def test_import_persists_queryable_relation_edges_across_documents(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            first_path = workspace_root / "first.txt"
            first_path.write_text("Project Atlas with @saya", encoding="utf-8")
            second_path = workspace_root / "second.txt"
            second_path.write_text("Project Atlas status update", encoding="utf-8")

            first = import_document(
                workspace_root=workspace_root, path_or_url=str(first_path)
            )
            result = import_document(
                workspace_root=workspace_root, path_or_url=str(second_path)
            )

            with with_db(workspace_root / "kb.db") as conn:
                rows = conn.execute(
                    "SELECT edge_type, dst_doc_id FROM doc_edges WHERE src_doc_id = ?",
                    (result["document_id"],),
                ).fetchall()

        self.assertTrue(result["edges"])
        self.assertFalse(
            any(edge["src_doc_id"] == edge["dst_doc_id"] for edge in result["edges"])
        )
        self.assertTrue(any(edge["edge_type"] == "related" for edge in result["edges"]))
        self.assertTrue(
            any(edge["dst_doc_id"] == first["document_id"] for edge in result["edges"])
        )
        self.assertTrue(any(row[0] == "related" for row in rows))
        self.assertTrue(any(row[1] == first["document_id"] for row in rows))

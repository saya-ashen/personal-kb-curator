from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import sys
from unittest.mock import patch

MEMLITE_DIR = Path(__file__).resolve().parents[1] / "memlite"
if str(MEMLITE_DIR) not in sys.path:
    sys.path.insert(0, str(MEMLITE_DIR))

from dedup import dedup_merge, dedup_rollback, dedup_scan
from frontmatter import parse_frontmatter
from indexer import build_index
from indexer import load_chunks
from rag import keyword_search, semantic_search
from storage import with_db


class DedupMergeRollbackTests(unittest.TestCase):
    def _semantic_stub(
        self,
        workspace_root: Path,
        query: str,
        limit: int,
        filters: dict[str, object] | None,
    ) -> list[dict[str, object]]:
        wanted = {token.lower() for token in query.split() if token.strip()}
        rows: list[dict[str, object]] = []
        for row in load_chunks(workspace_root):
            text = str(row.get("text", "")).lower()
            overlap = sum(1 for token in wanted if token in text)
            if overlap <= 0:
                continue
            out = dict(row)
            out["semantic_score"] = float(overlap)
            rows.append(out)
        rows.sort(key=lambda item: float(item.get("semantic_score", 0.0)), reverse=True)
        return rows[:limit]

    def _write_note(
        self,
        workspace_root: Path,
        doc_id: str,
        body: str,
        created_at: str,
    ) -> None:
        notes_dir = workspace_root / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        (notes_dir / f"{doc_id}.md").write_text(
            "---\n"
            f'id: "{doc_id}"\n'
            f'title: "{doc_id}"\n'
            f'created_at: "{created_at}"\n'
            f'updated_at: "{created_at}"\n'
            'type: "note"\n'
            "---\n\n"
            f"{body}\n",
            encoding="utf-8",
        )

    def _read_meta(self, workspace_root: Path, doc_id: str) -> dict[str, object]:
        text = (workspace_root / "notes" / f"{doc_id}.md").read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(text)
        return meta

    def _db_path(self, workspace_root: Path) -> Path:
        return workspace_root / "kb.db"

    def test_dedup_scan_routes_by_thresholds(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "doc-1",
                "Project Atlas launch decision approved for staged rollout.",
                "2026-03-01T10:00:00Z",
            )
            self._write_note(
                workspace_root,
                "doc-2",
                "Project Atlas launch decision approved for staged rollout.",
                "2026-03-01T11:00:00Z",
            )
            self._write_note(
                workspace_root,
                "doc-3",
                "Project Atlas launch decision approved for staged rollout with owners listed.",
                "2026-03-01T12:00:00Z",
            )
            self._write_note(
                workspace_root,
                "doc-4",
                "Weekly grocery list with apples, milk, and bread.",
                "2026-03-01T13:00:00Z",
            )

            out = dedup_scan(workspace_root)

        self.assertEqual(0.93, out["thresholds"]["auto"])
        self.assertEqual(0.85, out["thresholds"]["review"])
        self.assertTrue(out["exact_duplicates"])
        self.assertTrue(out["auto_merge_candidates"])
        self.assertTrue(out["review_candidates"])
        self.assertTrue(out["keep_separate_evidence"])

        self.assertTrue(
            all(item.get("route") == "auto" for item in out["auto_merge_candidates"])
        )
        self.assertTrue(
            all(item.get("route") == "review" for item in out["review_candidates"])
        )
        self.assertTrue(
            all(
                item.get("route") == "keep_separate"
                and item.get("auto_threshold") == 0.93
                and item.get("review_threshold") == 0.85
                and item.get("reason") == "below_review_threshold"
                for item in out["keep_separate_evidence"]
            )
        )

    def test_auto_merge_sets_merged_fields_and_group(self) -> None:
        with (
            TemporaryDirectory() as temp_dir,
            patch(
                "indexer._rebuild_zvec_index",
                return_value={"enabled": False, "path": "", "count": 0},
            ),
            patch("rag._semantic_search_zvec", side_effect=self._semantic_stub),
        ):
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "doc-1",
                "Project Atlas launch decision approved.",
                "2026-03-01T10:00:00Z",
            )
            self._write_note(
                workspace_root,
                "doc-2",
                "Project Atlas launch decision approved.",
                "2026-03-01T11:00:00Z",
            )
            build_index(workspace_root)

            result = dedup_merge(workspace_root, group_id_or_doc_ids=["doc-1", "doc-2"])

            self.assertTrue(result["merge_id"])
            self.assertTrue(result["canonical_doc_id"])
            self.assertTrue(result["compressed_summary"])
            self.assertTrue(result["diff_notes"])

            non_canonical = (
                "doc-2" if result["canonical_doc_id"] == "doc-1" else "doc-1"
            )
            meta = self._read_meta(workspace_root, non_canonical)
            self.assertEqual("merged", meta.get("status"))
            self.assertEqual(result["canonical_doc_id"], meta.get("merged_into"))
            self.assertEqual("auto_merged", meta.get("merge_state"))
            self.assertEqual(result["merge_id"], meta.get("merge_id"))

    def test_rollback_restores_premerge_state(self) -> None:
        with (
            TemporaryDirectory() as temp_dir,
            patch(
                "indexer._rebuild_zvec_index",
                return_value={"enabled": False, "path": "", "count": 0},
            ),
            patch("rag._semantic_search_zvec", side_effect=self._semantic_stub),
        ):
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "doc-1",
                "Project Atlas launch decision approved.",
                "2026-03-01T10:00:00Z",
            )
            self._write_note(
                workspace_root,
                "doc-2",
                "Project Atlas launch decision approved.",
                "2026-03-01T11:00:00Z",
            )
            build_index(workspace_root)

            merged = dedup_merge(workspace_root, group_id_or_doc_ids=["doc-1", "doc-2"])
            rollback = dedup_rollback(workspace_root, merged["merge_id"])

        self.assertTrue(rollback["restored"])
        self.assertEqual(
            rollback["before_snapshot"]["documents"],
            rollback["after_snapshot"]["documents"],
        )
        self.assertEqual(
            rollback["before_snapshot"]["chunks"],
            rollback["after_snapshot"]["chunks"],
        )
        self.assertEqual(
            rollback["before_snapshot"]["doc_edges"],
            rollback["after_snapshot"]["doc_edges"],
        )
        self.assertEqual([], rollback["dangling_refs"])
        self.assertEqual([], rollback["dangling_merged_into_refs"])

    def test_post_rollback_documents_are_searchable(self) -> None:
        with (
            TemporaryDirectory() as temp_dir,
            patch(
                "indexer._rebuild_zvec_index",
                return_value={"enabled": False, "path": "", "count": 0},
            ),
            patch("rag._semantic_search_zvec", side_effect=self._semantic_stub),
        ):
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "doc-1",
                "Project Atlas launch decision approved with staged rollout.",
                "2026-03-01T10:00:00Z",
            )
            self._write_note(
                workspace_root,
                "doc-2",
                "Project Atlas launch decision approved with staged rollout.",
                "2026-03-01T11:00:00Z",
            )
            build_index(workspace_root)

            merged = dedup_merge(workspace_root, group_id_or_doc_ids=["doc-1", "doc-2"])
            dedup_rollback(workspace_root, merged["merge_id"])

            lexical = keyword_search(workspace_root, "atlas launch decision", limit=5)
            semantic = semantic_search(workspace_root, "atlas launch decision", limit=5)

        self.assertTrue(lexical)
        self.assertTrue(semantic)

    def test_rollback_preserves_documents_created_after_merge(self) -> None:
        with (
            TemporaryDirectory() as temp_dir,
            patch(
                "indexer._rebuild_zvec_index",
                return_value={"enabled": False, "path": "", "count": 0},
            ),
            patch("rag._semantic_search_zvec", side_effect=self._semantic_stub),
        ):
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "doc-1",
                "Project Atlas launch decision approved with staged rollout.",
                "2026-03-01T10:00:00Z",
            )
            self._write_note(
                workspace_root,
                "doc-2",
                "Project Atlas launch decision approved with staged rollout.",
                "2026-03-01T11:00:00Z",
            )
            build_index(workspace_root)

            merged = dedup_merge(workspace_root, group_id_or_doc_ids=["doc-1", "doc-2"])
            self._write_note(
                workspace_root,
                "doc-3",
                "Post merge note that must survive rollback.",
                "2026-03-01T12:00:00Z",
            )
            rollback = dedup_rollback(workspace_root, merged["merge_id"])
            self.assertTrue((workspace_root / "notes" / "doc-3.md").exists())

        self.assertTrue(rollback["restored"])

    def test_rollback_restores_dedup_group_state(self) -> None:
        with (
            TemporaryDirectory() as temp_dir,
            patch(
                "indexer._rebuild_zvec_index",
                return_value={"enabled": False, "path": "", "count": 0},
            ),
            patch("rag._semantic_search_zvec", side_effect=self._semantic_stub),
        ):
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "doc-1",
                "Project Atlas launch decision approved.",
                "2026-03-01T10:00:00Z",
            )
            self._write_note(
                workspace_root,
                "doc-2",
                "Project Atlas launch decision approved.",
                "2026-03-01T11:00:00Z",
            )
            scan = dedup_scan(workspace_root)
            group_id = scan["auto_merge_candidates"][0]["group_id"]
            with with_db(self._db_path(workspace_root)) as conn:
                before = conn.execute(
                    "SELECT canonical_doc_id, state FROM dedup_groups WHERE group_id = ?",
                    (group_id,),
                ).fetchone()
            merged = dedup_merge(workspace_root, group_id_or_doc_ids=group_id)
            with with_db(self._db_path(workspace_root)) as conn:
                during = conn.execute(
                    "SELECT canonical_doc_id, state FROM dedup_groups WHERE group_id = ?",
                    (group_id,),
                ).fetchone()

            dedup_rollback(workspace_root, merged["merge_id"])
            with with_db(self._db_path(workspace_root)) as conn:
                after = conn.execute(
                    "SELECT canonical_doc_id, state FROM dedup_groups WHERE group_id = ?",
                    (group_id,),
                ).fetchone()

        self.assertEqual((None, "auto"), before)
        self.assertEqual("merged", during[1])
        self.assertEqual(before, after)

    def test_merge_failure_is_atomic_and_self_healing(self) -> None:
        with (
            TemporaryDirectory() as temp_dir,
            patch(
                "indexer._rebuild_zvec_index",
                return_value={"enabled": False, "path": "", "count": 0},
            ),
            patch("rag._semantic_search_zvec", side_effect=self._semantic_stub),
            patch(
                "dedup._persist_merge_success",
                side_effect=RuntimeError("db write failed"),
            ),
        ):
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "doc-1",
                "Project Atlas launch decision approved.",
                "2026-03-01T10:00:00Z",
            )
            self._write_note(
                workspace_root,
                "doc-2",
                "Project Atlas launch decision approved.",
                "2026-03-01T11:00:00Z",
            )
            build_index(workspace_root)

            with self.assertRaises(RuntimeError):
                dedup_merge(workspace_root, group_id_or_doc_ids=["doc-1", "doc-2"])

            doc_1_meta = self._read_meta(workspace_root, "doc-1")
            doc_2_meta = self._read_meta(workspace_root, "doc-2")
            with with_db(self._db_path(workspace_root)) as conn:
                failed_log = conn.execute(
                    "SELECT snapshot_after, diff_notes FROM merge_logs ORDER BY created_at DESC LIMIT 1"
                ).fetchone()

        self.assertNotEqual("merged", doc_1_meta.get("status"))
        self.assertNotEqual("merged", doc_2_meta.get("status"))
        self.assertIsNotNone(failed_log)
        self.assertIsNone(failed_log[0])
        self.assertIn("failed", str(failed_log[1]).lower())


if __name__ == "__main__":
    unittest.main()

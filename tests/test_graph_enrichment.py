from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

MEMLITE_DIR = Path(__file__).resolve().parents[1] / "memlite"
if str(MEMLITE_DIR) not in sys.path:
    sys.path.insert(0, str(MEMLITE_DIR))

from knowledge_store import list_doc_edges
from workflows import run_graph_enrichment


class GraphEnrichmentTests(unittest.TestCase):
    def _write_note(
        self,
        workspace_root: Path,
        doc_id: str,
        created_at: str,
        topics: list[str],
        projects: list[str],
        body: str,
    ) -> None:
        notes_dir = workspace_root / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        topic_list = ", ".join(f'"{topic}"' for topic in topics)
        project_list = ", ".join(f'"{project}"' for project in projects)
        (notes_dir / f"{doc_id}.md").write_text(
            "---\n"
            f'id: "{doc_id}"\n'
            f'title: "{doc_id}"\n'
            f'created_at: "{created_at}"\n'
            f'updated_at: "{created_at}"\n'
            'type: "note"\n'
            f"topics: [{topic_list}]\n"
            f"projects: [{project_list}]\n"
            "---\n\n"
            f"{body}\n",
            encoding="utf-8",
        )

    def _seed_workspace(self, workspace_root: Path) -> dict[str, str]:
        created_at = {
            "doc-1": "2026-03-01T09:00:00Z",
            "doc-2": "2026-03-03T12:00:00Z",
            "doc-3": "2026-03-05T10:30:00Z",
        }
        self._write_note(
            workspace_root=workspace_root,
            doc_id="doc-1",
            created_at=created_at["doc-1"],
            topics=["atlas", "launch"],
            projects=["Atlas"],
            body="Kickoff decisions for Atlas launch.",
        )
        self._write_note(
            workspace_root=workspace_root,
            doc_id="doc-2",
            created_at=created_at["doc-2"],
            topics=["atlas", "retrospective"],
            projects=["Atlas"],
            body="Follow-up actions and owner updates for Atlas.",
        )
        self._write_note(
            workspace_root=workspace_root,
            doc_id="doc-3",
            created_at=created_at["doc-3"],
            topics=["finance"],
            projects=["Budget"],
            body="Budget planning notes for next quarter.",
        )
        return created_at

    def test_edge_discovery_adds_same_topic_and_follow_up_links(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._seed_workspace(workspace_root)

            result = run_graph_enrichment(workspace_root, limit=500)
            all_edges = list_doc_edges(workspace_root)

        self.assertGreater(result["new_edges"], 0)
        self.assertTrue(any(edge["edge_type"] == "same_topic" for edge in all_edges))
        self.assertTrue(any(edge["edge_type"] == "follow_up" for edge in all_edges))

    def test_list_doc_edges_supports_doc_id_and_edge_type_filters(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._seed_workspace(workspace_root)
            run_graph_enrichment(workspace_root, limit=500)

            filtered = list_doc_edges(
                workspace_root,
                doc_id="doc-1",
                edge_type="same_topic",
                limit=500,
            )

        self.assertTrue(filtered)
        self.assertTrue(all(edge["edge_type"] == "same_topic" for edge in filtered))
        self.assertTrue(
            all(
                edge["src_doc_id"] == "doc-1" or edge["dst_doc_id"] == "doc-1"
                for edge in filtered
            )
        )

    def test_run_graph_enrichment_is_idempotent_and_does_not_duplicate_edge_ids(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._seed_workspace(workspace_root)

            first = run_graph_enrichment(workspace_root, limit=500)
            edges_after_first = list_doc_edges(workspace_root, limit=500)
            second = run_graph_enrichment(workspace_root, limit=500)
            edges_after_second = list_doc_edges(workspace_root, limit=500)

        ids_after_first = [edge["edge_id"] for edge in edges_after_first]
        ids_after_second = [edge["edge_id"] for edge in edges_after_second]

        self.assertGreater(first["new_edges"], 0)
        self.assertEqual(0, second["new_edges"])
        self.assertEqual(len(ids_after_first), len(set(ids_after_first)))
        self.assertEqual(len(ids_after_second), len(set(ids_after_second)))
        self.assertEqual(set(ids_after_first), set(ids_after_second))
        self.assertEqual(len(edges_after_first), len(edges_after_second))

    def test_follow_up_edges_are_directional_from_older_to_newer(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            created_at = self._seed_workspace(workspace_root)
            run_graph_enrichment(workspace_root, limit=500)
            follow_up_edges = list_doc_edges(
                workspace_root,
                edge_type="follow_up",
                limit=500,
            )

        self.assertTrue(follow_up_edges)
        self.assertTrue(
            all(
                created_at[edge["src_doc_id"]] < created_at[edge["dst_doc_id"]]
                for edge in follow_up_edges
            )
        )

    def test_same_topic_and_follow_up_edges_have_expected_evidence_and_weight(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._seed_workspace(workspace_root)
            run_graph_enrichment(workspace_root, limit=500)

            same_topic_edges = list_doc_edges(
                workspace_root,
                edge_type="same_topic",
                limit=500,
            )
            follow_up_edges = list_doc_edges(
                workspace_root,
                edge_type="follow_up",
                limit=500,
            )

        same_topic = next(
            edge
            for edge in same_topic_edges
            if edge["src_doc_id"] == "doc-1" and edge["dst_doc_id"] == "doc-2"
        )
        follow_up = next(
            edge
            for edge in follow_up_edges
            if edge["src_doc_id"] == "doc-1" and edge["dst_doc_id"] == "doc-2"
        )

        self.assertEqual(1.0, same_topic["weight"])
        self.assertEqual("topics:atlas", same_topic["evidence"])
        self.assertEqual(2.0, follow_up["weight"])
        self.assertIn("topics:atlas", follow_up["evidence"])
        self.assertIn("projects:atlas", follow_up["evidence"])


if __name__ == "__main__":
    unittest.main()

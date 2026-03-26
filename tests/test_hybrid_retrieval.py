import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from memlite.indexer import build_index
from memlite.rag import (
    answer_from_context,
    ask_with_citations,
    hybrid_search,
    keyword_search,
    semantic_search,
)


class HybridRetrievalTests(unittest.TestCase):
    def _write_note(
        self,
        workspace_root: Path,
        name: str,
        body: str,
        projects: list[str] | None = None,
    ) -> None:
        project_values = projects or []
        notes_dir = workspace_root / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        projects_json = json.dumps(project_values)
        (notes_dir / f"{name}.md").write_text(
            f'---\nid: "doc-{name}"\ntitle: "{name}"\nprojects: {projects_json}\n---\n\n{body}\n',
            encoding="utf-8",
        )

    def test_hybrid_search_combines_lexical_and_semantic_scores(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "atlas",
                "Project Atlas decision and rollout plan for search quality.",
            )
            build_index(workspace_root)

            rows = hybrid_search(workspace_root, "atlas search plan", limit=3)

        self.assertTrue(rows)
        self.assertIn("hybrid_score", rows[0])
        self.assertIn("semantic_score", rows[0])
        self.assertIn("keyword_score", rows[0])

    def test_answer_returns_unknown_on_low_evidence(self) -> None:
        question = "unrelated question"
        out = answer_from_context(
            question,
            [{"chunk_id": "doc-a#0", "text": "noise", "hybrid_score": 0.0}],
        )
        self.assertEqual("unknown", out["answer"])
        self.assertEqual(question, out["question"])

    def test_non_unknown_answers_always_include_citations(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "release",
                "Project Atlas launch decision approved staged rollout release.",
            )
            build_index(workspace_root)

            out = ask_with_citations(
                workspace_root,
                "atlas launch decision approved",
                use_cloud_generation=False,
            )

        self.assertNotEqual("unknown", out["answer"])
        self.assertTrue(out["citations"])
        self.assertTrue({"doc_id", "chunk_id", "snippet"}.issubset(out["citations"][0]))

    def test_keyword_search_uses_exact_token_matching(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root, "sub", "The concatenate utility is documented."
            )
            self._write_note(workspace_root, "exact", "The cat is sleeping.")
            build_index(workspace_root)

            rows = keyword_search(workspace_root, "cat", limit=5)

        ids = [row["doc_id"] for row in rows]
        self.assertIn("doc-exact", ids)
        self.assertNotIn("doc-sub", ids)

    def test_keyword_search_prefers_precomputed_tokens(self) -> None:
        rows = [
            {
                "chunk_id": "doc-1#0",
                "doc_id": "doc-1",
                "text": "cat cat cat",
                "tokens": ["dog"],
            }
        ]
        with patch("memlite.rag.load_chunks", return_value=rows):
            out = keyword_search(Path("."), "cat", limit=5)

        self.assertEqual([], out)

    def test_hybrid_search_filter_scalar_matches_list_membership(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "atlas",
                "Atlas launch decision approved.",
                projects=["atlas"],
            )
            self._write_note(
                workspace_root,
                "zeus",
                "Zeus launch decision approved.",
                projects=["zeus"],
            )
            build_index(workspace_root)

            rows = hybrid_search(
                workspace_root,
                "launch decision",
                limit=5,
                filters={"projects": "atlas"},
            )

        ids = [row["doc_id"] for row in rows]
        self.assertIn("doc-atlas", ids)
        self.assertNotIn("doc-zeus", ids)

    def test_hybrid_search_filter_list_overlaps_list_membership(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "atlas",
                "Atlas launch decision approved.",
                projects=["atlas"],
            )
            self._write_note(
                workspace_root,
                "zeus",
                "Zeus launch decision approved.",
                projects=["zeus"],
            )
            build_index(workspace_root)

            rows = hybrid_search(
                workspace_root,
                "launch decision",
                limit=5,
                filters={"projects": ["atlas", "apollo"]},
            )

        ids = [row["doc_id"] for row in rows]
        self.assertIn("doc-atlas", ids)
        self.assertNotIn("doc-zeus", ids)

    def test_cloud_generation_can_answer_when_local_is_unknown(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "sparse",
                "Atlas roadmap includes migration milestones and ownership details.",
            )
            build_index(workspace_root)

            question = (
                "atlas alpha beta gamma delta epsilon zeta eta theta iota kappa "
                "lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega"
            )

            local_out = ask_with_citations(
                workspace_root,
                question,
                use_cloud_generation=False,
            )

            def cloud_generator(_: str, __: list[dict[str, object]]) -> str:
                return "Cloud synthesized answer"

            out = ask_with_citations(
                workspace_root,
                question,
                use_cloud_generation=True,
                cloud_generator=cloud_generator,
            )

        self.assertEqual("unknown", local_out["answer"])
        self.assertEqual("Cloud synthesized answer", out["answer"])
        self.assertEqual("low", out["confidence"])
        self.assertEqual("cloud_generated", out["answer_source"])
        self.assertTrue(out["citations"])
        self.assertTrue({"doc_id", "chunk_id", "snippet"}.issubset(out["citations"][0]))

    def test_cloud_generation_flag_falls_back_to_local_on_failure(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "fallback",
                "Project Atlas final decision is to keep retrieval local by default.",
            )
            build_index(workspace_root)

            local_out = ask_with_citations(
                workspace_root,
                "What is the Atlas final decision?",
                use_cloud_generation=False,
            )

            def failing_generator(_: str, __: list[dict[str, object]]) -> str:
                raise RuntimeError("cloud unavailable")

            fallback_out = ask_with_citations(
                workspace_root,
                "What is the Atlas final decision?",
                use_cloud_generation=True,
                cloud_generator=failing_generator,
            )

        self.assertEqual(local_out["answer"], fallback_out["answer"])
        self.assertIn("cloud_error", fallback_out)
        self.assertIn("RuntimeError", fallback_out["cloud_error"])
        if local_out["answer"] != "unknown":
            self.assertTrue(fallback_out["citations"])

    def test_cloud_invalid_output_falls_back_with_diagnostics(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._write_note(
                workspace_root,
                "invalid",
                "Project Atlas keeps local retrieval active by default.",
            )
            build_index(workspace_root)

            local_out = ask_with_citations(
                workspace_root,
                "atlas local retrieval",
                use_cloud_generation=False,
            )

            def invalid_generator(_: str, __: list[dict[str, object]]) -> str:
                return ""

            out = ask_with_citations(
                workspace_root,
                "atlas local retrieval",
                use_cloud_generation=True,
                cloud_generator=invalid_generator,
            )

        self.assertEqual(local_out["answer"], out["answer"])
        self.assertIn("cloud_error", out)
        self.assertIn("invalid", out["cloud_error"].lower())

    def test_semantic_search_prefers_zvec_backend_when_available(self) -> None:
        expected_rows = [
            {
                "chunk_id": "doc-z#0",
                "doc_id": "doc-z",
                "text": "zvec-ranked row",
                "semantic_score": 0.91,
            }
        ]
        with patch("memlite.rag._semantic_search_zvec", return_value=expected_rows):
            rows = semantic_search(Path("."), "atlas", limit=3)

        self.assertEqual(expected_rows, rows)

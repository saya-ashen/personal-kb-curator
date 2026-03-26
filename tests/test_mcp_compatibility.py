import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
MEMLITE_DIR = ROOT_DIR / "memlite"
if str(MEMLITE_DIR) not in sys.path:
    sys.path.insert(0, str(MEMLITE_DIR))


def _load_module(module_name: str, relative_path: str):
    module_path = ROOT_DIR / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class McpCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.intake_server = _load_module(
            "mcp_intake_server",
            "mcp/intake-mcp/server.py",
        )
        cls.knowledge_server = _load_module(
            "mcp_knowledge_server",
            "mcp/knowledge-store-mcp/server.py",
        )
        cls.rag_server = _load_module(
            "mcp_rag_server",
            "mcp/rag-mcp/server.py",
        )

    def test_new_operations_are_available(self) -> None:
        self.assertEqual(
            {"import_document"},
            set(self.intake_server.SUPPORTED_OPERATIONS),
        )
        self.assertTrue(
            {
                "upsert_document",
                "build_index",
                "semantic_search",
                "hybrid_search",
                "ask_with_citations",
                "dedup_scan",
                "dedup_merge",
                "dedup_rollback",
                "link_documents",
            }.issubset(
                set(self.knowledge_server.SUPPORTED_OPERATIONS)
                | set(self.rag_server.SUPPORTED_OPERATIONS)
            )
        )

    def test_m1_m2_dual_availability_old_and_new_ops(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            payload = {
                "note": {
                    "title": "Project Alpha",
                    "body": "Alpha sync note",
                },
                "zone": "notes",
            }
            with patch.object(
                self.knowledge_server,
                "build_index",
                return_value={"enabled": False, "count": 0},
            ):
                old_out = self.knowledge_server.execute_operation(
                    workspace_root,
                    operation="create_note",
                    payload=payload,
                )
                new_out = self.knowledge_server.execute_operation(
                    workspace_root,
                    operation="upsert_document",
                    payload=payload,
                )

        self.assertTrue(old_out["note_id"])
        self.assertTrue(new_out["document_id"])
        self.assertEqual("upsert_document", old_out["_meta"]["resolved_operation"])
        self.assertEqual("upsert_document", new_out["_meta"]["resolved_operation"])

    def test_alias_parity_update_answer_and_links(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            with patch.object(
                self.knowledge_server,
                "build_index",
                return_value={"enabled": False, "count": 0},
            ):
                first = self.knowledge_server.execute_operation(
                    workspace_root,
                    operation="upsert_document",
                    payload={
                        "note": {"title": "Alpha", "body": "alpha body"},
                        "zone": "notes",
                    },
                )
                second = self.knowledge_server.execute_operation(
                    workspace_root,
                    operation="upsert_document",
                    payload={
                        "note": {"title": "Beta", "body": "beta body"},
                        "zone": "notes",
                    },
                )

                update_old = self.knowledge_server.execute_operation(
                    workspace_root,
                    operation="update_note",
                    payload={
                        "note_path": first["note_path"],
                        "updates": {"body": "alpha body updated"},
                    },
                )

            with patch.object(
                self.rag_server,
                "ask_with_citations",
                return_value={"answer": "Alpha answer", "citations": []},
            ):
                answer_old = self.rag_server.execute_operation(
                    workspace_root,
                    operation="answer_from_context",
                    payload={"question": "What changed?"},
                )

            link_old = self.knowledge_server.execute_operation(
                workspace_root,
                operation="link_notes",
                payload={
                    "source_path": first["note_path"],
                    "target_path": second["note_path"],
                },
            )
            link_new = self.knowledge_server.execute_operation(
                workspace_root,
                operation="link_documents",
                payload={
                    "from_id": first["document_id"],
                    "to_id": second["document_id"],
                },
            )

        self.assertTrue(update_old["updated"])
        self.assertEqual("Alpha answer", answer_old["answer"])
        self.assertTrue(link_old["linked"])
        self.assertTrue(link_new["linked"])

    def test_m3_default_command_routing_uses_new_names(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)

            with patch.object(self.knowledge_server, "hybrid_search", return_value=[]):
                routed = self.knowledge_server.execute_operation(
                    workspace_root,
                    operation=None,
                    payload={"command": "search_notes", "query": "alpha"},
                )

            with patch.object(
                self.rag_server,
                "ask_with_citations",
                return_value={"answer": "default route", "citations": []},
            ):
                default_rag = self.rag_server.execute_operation(
                    workspace_root,
                    operation=None,
                    payload={"question": "default question"},
                )

        self.assertEqual("hybrid_search", routed["_meta"]["resolved_operation"])
        self.assertEqual(
            "ask_with_citations", default_rag["_meta"]["resolved_operation"]
        )

    def test_m4_old_ops_emit_deprecation_warnings_but_execute(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            with patch.object(
                self.knowledge_server,
                "build_index",
                return_value={"enabled": False, "count": 0},
            ):
                old_create = self.knowledge_server.execute_operation(
                    workspace_root,
                    operation="create_note",
                    payload={"note": {"title": "Deprecation", "body": "still works"}},
                )
            with patch.object(
                self.rag_server,
                "ask_with_citations",
                return_value={"answer": "still works", "citations": []},
            ):
                old_answer = self.rag_server.execute_operation(
                    workspace_root,
                    operation="answer_from_context",
                    payload={"question": "old op"},
                )

        self.assertTrue(old_create["document_id"])
        self.assertEqual("still works", old_answer["answer"])
        self.assertTrue(old_create.get("warnings"))
        self.assertTrue(old_answer.get("warnings"))
        self.assertEqual("deprecation", old_create["warnings"][0]["type"])
        self.assertEqual("deprecation", old_answer["warnings"][0]["type"])

    def test_semantic_search_operation_available(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            mocked_rows = [
                {
                    "chunk_id": "doc-alpha#0",
                    "doc_id": "doc-alpha",
                    "text": "project alpha delivery plan",
                    "semantic_score": 0.92,
                }
            ]
            with patch.object(
                self.rag_server,
                "semantic_search",
                return_value=mocked_rows,
            ):
                result = self.rag_server.execute_operation(
                    workspace_root,
                    operation="semantic_search",
                    payload={"query": "project alpha", "limit": 3},
                )

        self.assertIn("results", result)
        self.assertEqual("doc-alpha", result["results"][0]["doc_id"])

    def test_intake_routing_meta_uses_payload_fallback_operation(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            sample = workspace_root / "sample.txt"
            sample.write_text("alpha", encoding="utf-8")

            with (
                patch.object(
                    self.intake_server,
                    "import_document",
                    return_value={"document_id": "doc-alpha"},
                ),
                patch.object(
                    self.intake_server,
                    "build_index",
                    return_value={"enabled": False, "count": 0},
                ),
            ):
                result = self.intake_server.execute_operation(
                    workspace_root,
                    operation=None,
                    payload={
                        "command": "import_document",
                        "path_or_url": str(sample),
                    },
                )

        self.assertEqual("import_document", result["_meta"]["requested_operation"])
        self.assertEqual("import_document", result["_meta"]["resolved_operation"])

    def test_invalid_or_missing_required_params_raise_clear_errors(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)

            with self.assertRaisesRegex(ValueError, "note_path"):
                self.knowledge_server.execute_operation(
                    workspace_root,
                    operation="get_note",
                    payload={},
                )

            with self.assertRaisesRegex(ValueError, "path_or_url"):
                self.intake_server.execute_operation(
                    workspace_root,
                    operation="import_document",
                    payload={},
                )

            with self.assertRaisesRegex(ValueError, "query"):
                self.rag_server.execute_operation(
                    workspace_root,
                    operation="semantic_search",
                    payload={"limit": 3},
                )

            with self.assertRaisesRegex(ValueError, "limit"):
                self.rag_server.execute_operation(
                    workspace_root,
                    operation="semantic_search",
                    payload={"query": "alpha", "limit": "not-a-number"},
                )

    def test_path_traversal_rejected_for_note_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)

            with self.assertRaisesRegex(ValueError, "path traversal"):
                self.knowledge_server.execute_operation(
                    workspace_root,
                    operation="get_note",
                    payload={"note_path": "../etc/passwd"},
                )

            with self.assertRaisesRegex(ValueError, "path traversal"):
                self.knowledge_server.execute_operation(
                    workspace_root,
                    operation="link_documents",
                    payload={
                        "source_path": "notes/a.md",
                        "target_path": "../../tmp/b.md",
                    },
                )

    def test_use_cloud_generation_string_false_is_false(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            with patch.object(
                self.rag_server,
                "ask_with_citations",
                return_value={"answer": "ok", "citations": []},
            ) as mocked:
                self.rag_server.execute_operation(
                    workspace_root,
                    operation="ask_with_citations",
                    payload={
                        "question": "alpha",
                        "use_cloud_generation": "false",
                    },
                )

        call_kwargs = mocked.call_args.kwargs
        self.assertIs(call_kwargs["use_cloud_generation"], False)

    def test_invalid_zone_rejected_for_upsert_create(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            with self.assertRaisesRegex(ValueError, "zone"):
                self.knowledge_server.execute_operation(
                    workspace_root,
                    operation="upsert_document",
                    payload={
                        "note": {"title": "Alpha", "body": "x"},
                        "zone": "../notes",
                    },
                )

    def test_invalid_updates_type_rejected_for_upsert_update(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            with self.assertRaisesRegex(ValueError, "updates"):
                self.knowledge_server.execute_operation(
                    workspace_root,
                    operation="upsert_document",
                    payload={
                        "note_path": "notes/a.md",
                        "updates": "not-a-dict",
                    },
                )


if __name__ == "__main__":
    unittest.main()

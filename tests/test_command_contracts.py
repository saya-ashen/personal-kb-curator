from pathlib import Path
import re
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]


def _read_doc(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text(encoding="utf-8")


def _extract_backticked_set(text: str, line_pattern: str) -> set[str]:
    match = re.search(line_pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if match is None:
        return set()
    return set(re.findall(r"`([^`]+)`", match.group(0)))


class CommandContractTests(unittest.TestCase):
    def _assert_contract_structure(self, text: str) -> None:
        self.assertRegex(text, r"(?im)^\s*operation contract:\s*$")
        self.assertRegex(text, r"(?im)^\s*-\s*(primary|preferred) operations?:")
        self.assertRegex(text, r"(?im)^\s*-\s*.*aliases?:")
        alias_line = re.search(
            r"(?im)^\s*-\s*.*aliases?:.*$",
            text,
        )
        self.assertIsNotNone(alias_line)
        self.assertRegex(alias_line.group(0), r"(?i)(compatibility|legacy|deprecated)")

    def _assert_primary_is_default_or_preferred(
        self, text: str, operation: str
    ) -> None:
        self.assertRegex(
            text,
            rf"(?is)((prefer|preferred|default|recommended).{{0,80}}`{operation}`|`{operation}`.{{0,80}}(prefer|preferred|default|recommended|first))",
        )

    def test_contract_sections_exist_and_aliases_marked_secondary(self) -> None:
        docs = [
            "commands/capture.md",
            "commands/ask.md",
            "agents/capture-agent.md",
            "agents/knowledge-agent.md",
        ]
        for relative_path in docs:
            with self.subTest(relative_path=relative_path):
                self._assert_contract_structure(_read_doc(relative_path))

    def test_capture_primary_and_alias_sets_are_consistent_between_command_and_agent(
        self,
    ) -> None:
        command_text = _read_doc("commands/capture.md")
        capture_text = _read_doc("agents/capture-agent.md")

        command_primary = _extract_backticked_set(
            command_text,
            r"^\s*-\s*Primary operations?:.*$",
        )
        agent_primary = _extract_backticked_set(
            capture_text,
            r"^\s*-\s*Preferred operations?:.*$",
        )
        command_aliases = _extract_backticked_set(
            command_text,
            r"^\s*-\s*Compatibility aliases?:.*$",
        )
        agent_aliases = _extract_backticked_set(
            capture_text,
            r"^\s*-\s*Compatibility aliases?:.*$",
        )

        self.assertEqual({"import_document"}, command_primary)
        self.assertEqual(command_primary, agent_primary)
        self.assertEqual(
            {"upsert_document", "create_note", "update_note"}, command_aliases
        )
        self.assertEqual(command_aliases, agent_aliases)
        self._assert_primary_is_default_or_preferred(command_text, "import_document")
        self._assert_primary_is_default_or_preferred(capture_text, "import_document")

    def test_ask_primary_and_alias_sets_are_consistent_between_command_and_agent(
        self,
    ) -> None:
        command_text = _read_doc("commands/ask.md")
        knowledge_text = _read_doc("agents/knowledge-agent.md")

        command_primary = _extract_backticked_set(
            command_text,
            r"^\s*-\s*Primary operations?:.*$",
        )
        agent_primary = _extract_backticked_set(
            knowledge_text,
            r"^\s*-\s*Preferred operations?:.*$",
        )
        command_aliases = _extract_backticked_set(
            command_text,
            r"^\s*-\s*Compatibility aliases?:.*$",
        )
        agent_aliases = _extract_backticked_set(
            knowledge_text,
            r"^\s*-\s*Compatibility aliases?:.*$",
        )

        self.assertEqual({"hybrid_search", "ask_with_citations"}, command_primary)
        self.assertEqual(command_primary, agent_primary)
        self.assertEqual({"search_notes", "answer_from_context"}, command_aliases)
        self.assertEqual(command_aliases, agent_aliases)

        self._assert_primary_is_default_or_preferred(command_text, "hybrid_search")
        self._assert_primary_is_default_or_preferred(command_text, "ask_with_citations")
        self._assert_primary_is_default_or_preferred(knowledge_text, "hybrid_search")
        self._assert_primary_is_default_or_preferred(
            knowledge_text, "ask_with_citations"
        )

    def test_ask_contract_requires_citations_and_unknown_fallback(self) -> None:
        command_text = _read_doc("commands/ask.md")
        knowledge_text = _read_doc("agents/knowledge-agent.md")
        self.assertIn("citations", command_text)
        self.assertIn("unknown", command_text)
        self.assertIn("citations", knowledge_text)
        self.assertIn("unknown", knowledge_text)

    def test_dedup_skill_references_dedup_operations(self) -> None:
        text = _read_doc("skills/dedup-curation/SKILL.md")
        self.assertIn("dedup_scan", text)
        self.assertIn("dedup_merge", text)
        self.assertIn("dedup_rollback", text)
        self.assertIn("merge_id", text)
        self.assertIn("canonical_doc_id", text)
        self.assertIn("compressed_summary", text)
        self.assertIn("diff_notes", text)

    def test_dedup_command_outputs_and_skill_flow_reference(self) -> None:
        text = _read_doc("commands/dedup.md")
        self.assertIn("dedup_scan", text)
        self.assertIn("dedup_merge", text)
        self.assertIn("dedup_rollback", text)
        self.assertIn("merge_id", text)
        self.assertIn("canonical_doc_id", text)
        self.assertIn("compressed_summary", text)
        self.assertIn("diff_notes", text)
        self.assertIn("skills/dedup-curation/SKILL.md", text)


if __name__ == "__main__":
    unittest.main()

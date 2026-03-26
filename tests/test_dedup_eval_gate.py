import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

MEMLITE_DIR = Path(__file__).resolve().parents[1] / "memlite"
if str(MEMLITE_DIR) not in sys.path:
    sys.path.insert(0, str(MEMLITE_DIR))

from workflows import dedup_scan, run_dedup_eval


class DedupEvalGateTests(unittest.TestCase):
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

    def _write_labeled_pairs(
        self,
        labeled_pairs_path: Path,
        auto_true_positive_count: int,
        auto_false_positive_count: int,
        reviewer_count: int | None = 2,
        adjudication: object | None = True,
        false_positive_hard_negative: object = True,
        target_pair_count: int = 1000,
    ) -> None:
        pairs: list[dict[str, object]] = []

        for index in range(auto_true_positive_count):
            pairs.append(
                {
                    "pair_id": f"tp-{index}",
                    "score": 0.96,
                    "label": "duplicate",
                    "hard_negative": False,
                }
            )
        for index in range(auto_false_positive_count):
            pairs.append(
                {
                    "pair_id": f"fp-{index}",
                    "score": 0.96,
                    "label": "not_duplicate",
                    "hard_negative": false_positive_hard_negative,
                }
            )

        while len(pairs) < target_pair_count:
            index = len(pairs)
            pairs.append(
                {
                    "pair_id": f"n-{index}",
                    "score": 0.72,
                    "label": "not_duplicate",
                    "hard_negative": False,
                }
            )

        payload: dict[str, object] = {"pairs": pairs}
        if reviewer_count is not None or adjudication is not None:
            payload["labeling_provenance"] = {}
            if reviewer_count is not None:
                payload["labeling_provenance"]["reviewer_count"] = reviewer_count
            if adjudication is not None:
                payload["labeling_provenance"]["adjudication"] = adjudication

        labeled_pairs_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_auto_merge_disabled_when_protocol_metadata_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            labeled_pairs_path = workspace_root / "labeled_pairs.json"
            self._write_labeled_pairs(
                labeled_pairs_path,
                auto_true_positive_count=995,
                auto_false_positive_count=5,
                reviewer_count=None,
                adjudication=None,
            )

            report = run_dedup_eval(workspace_root, labeled_pairs_path)

            self.assertFalse(report["auto_merge_enabled"])
            self.assertGreaterEqual(report["pair_count"], 1000)
            self.assertGreater(report["hard_negative_count"], 0)
            self.assertIn("labeling_provenance", report["protocol_checks"])
            self.assertFalse(report["protocol_checks"]["labeling_provenance"])

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

            scan = dedup_scan(workspace_root)
            self.assertEqual([], scan["auto_merge_candidates"])
            self.assertTrue(scan["review_candidates"])
            self.assertTrue(
                all(item.get("route") == "review" for item in scan["review_candidates"])
            )

    def test_auto_merge_enabled_when_wilson_lower_bound_passes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            labeled_pairs_path = workspace_root / "labeled_pairs.json"
            self._write_labeled_pairs(
                labeled_pairs_path,
                auto_true_positive_count=990,
                auto_false_positive_count=10,
            )

            report = run_dedup_eval(workspace_root, labeled_pairs_path)

            self.assertTrue(report["auto_merge_enabled"])
            self.assertGreater(report["wilson_lower_bound"], 0.95)
            self.assertEqual(1000, report["pair_count"])
            self.assertGreater(report["hard_negative_count"], 0)
            self.assertEqual(2, report["labeling_provenance"]["reviewer_count"])
            self.assertTrue(report["labeling_provenance"]["adjudication"])

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

            scan = dedup_scan(workspace_root)
            self.assertTrue(scan["auto_merge_candidates"])

    def test_auto_merge_disabled_when_wilson_lower_bound_not_above_threshold(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            labeled_pairs_path = workspace_root / "labeled_pairs.json"
            self._write_labeled_pairs(
                labeled_pairs_path,
                auto_true_positive_count=950,
                auto_false_positive_count=50,
            )

            report = run_dedup_eval(workspace_root, labeled_pairs_path)

            self.assertFalse(report["auto_merge_enabled"])
            self.assertLessEqual(report["wilson_lower_bound"], 0.95)
            self.assertTrue(report["protocol_passed"])

    def test_auto_merge_disabled_when_no_hard_negatives(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            labeled_pairs_path = workspace_root / "labeled_pairs.json"
            self._write_labeled_pairs(
                labeled_pairs_path,
                auto_true_positive_count=990,
                auto_false_positive_count=10,
                false_positive_hard_negative="false",
            )

            report = run_dedup_eval(workspace_root, labeled_pairs_path)

            self.assertFalse(report["auto_merge_enabled"])
            self.assertEqual(0, report["hard_negative_count"])
            self.assertFalse(report["protocol_checks"]["hard_negatives"])

    def test_auto_merge_disabled_when_pair_count_below_minimum(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            labeled_pairs_path = workspace_root / "labeled_pairs.json"
            self._write_labeled_pairs(
                labeled_pairs_path,
                auto_true_positive_count=891,
                auto_false_positive_count=9,
                target_pair_count=900,
            )

            report = run_dedup_eval(workspace_root, labeled_pairs_path)

            self.assertFalse(report["auto_merge_enabled"])
            self.assertLess(report["pair_count"], 1000)
            self.assertFalse(report["protocol_checks"]["pair_count"])

    def test_auto_merge_disabled_when_adjudication_is_false(self) -> None:
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            labeled_pairs_path = workspace_root / "labeled_pairs.json"
            self._write_labeled_pairs(
                labeled_pairs_path,
                auto_true_positive_count=990,
                auto_false_positive_count=10,
                adjudication=False,
            )

            report = run_dedup_eval(workspace_root, labeled_pairs_path)

            self.assertFalse(report["auto_merge_enabled"])
            self.assertFalse(report["protocol_checks"]["labeling_provenance"])


if __name__ == "__main__":
    unittest.main()

"""Source identity and denominator checks for the offline disputed-review export."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_disputed_reviews_v1 as builder  # noqa: E402


class DisputedReviewTests(unittest.TestCase):
    def copy_sources(self, temporary_root: Path) -> None:
        for relative in set(builder.EXPECTED_SHA256) | {str(builder.FEED)}:
            target = temporary_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)

    def test_all_reviews_and_exact_models_reconcile(self) -> None:
        result = builder.build()
        self.assertEqual(
            (ROOT / builder.PUBLIC_OUTPUT).read_bytes(),
            (ROOT / builder.OUTPUT / "findings.json").read_bytes(),
        )
        self.assertEqual((result["review_denominator"], result["model_denominator"]), (60, 7))
        self.assertEqual(len(result["reviews"]), 60)
        self.assertEqual(len({row["id"] for row in result["reviews"]}), 60)
        self.assertEqual([row["id"] for row in result["reviews"][:4]], ["DEV-029", "DEV-030", "DEV-006", "DEV-013"])
        self.assertEqual(sum(result["mismatch_count_histogram"].values()), 60)
        self.assertEqual(result["testimonial_reference_positive"]["count"], 9)
        self.assertEqual(result["off_topic_review_ids"], ["DEV-029"])
        self.assertEqual([model["all_four_matches"] for model in result["models"]], [43, 45, 55, 54, 45, 49, 54])
        self.assertTrue(all(len(row["answers"]) == 7 for row in result["reviews"]))
        self.assertTrue(all(row["eligible_model_count"] == 7 for row in result["reviews"]))
        self.assertTrue(all(model["repeat_pass"] == "fresh1" and model["condition"] == "P0" for model in result["models"]))
        self.assertEqual([model["id_kind"] for model in result["models"]], ["normalized_run_id"] * 7)
        self.assertEqual(result["models"][-1]["id"], "perplexity-decider-native-fresh1-p0")

    def test_pinned_projection_drift_fails_under_optimized_python(self) -> None:
        with TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            self.copy_sources(temporary_root)
            relative = "results/solar-decide-native-full-v1/execution-adapter-v2/first-pass.public-projection.json"
            projection = temporary_root / relative
            projection.write_bytes(projection.read_bytes() + b" ")
            code = (
                "import sys; from pathlib import Path; "
                "sys.path.insert(0, sys.argv[1]); "
                "import build_disputed_reviews_v1 as builder; "
                "builder.build(Path(sys.argv[2]))"
            )
            completed = subprocess.run(
                [sys.executable, "-O", "-c", code, str(ROOT / "scripts"), directory],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(f"Pinned source SHA-256 mismatch: {relative}", completed.stderr)

    def test_input_drift_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            self.copy_sources(temporary_root)
            path = temporary_root / builder.INPUTS
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "Pinned source SHA-256 mismatch: data/pilot/inputs.jsonl"):
                builder.build(temporary_root)

    def test_changed_published_score_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            self.copy_sources(temporary_root)
            path = temporary_root / builder.FEED
            feed = json.loads(path.read_text())
            run = next(item for item in feed["runs"] if item["id"] == "solar-decide-native-fresh1-p0")
            run["metrics"]["all_four"] += 1
            path.write_text(json.dumps(feed))
            with self.assertRaisesRegex(ValueError, "Published score differs from projection: solar-decide-native-fresh1-p0"):
                builder.build(temporary_root)

    def test_duplicate_review_id_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "duplicated.jsonl"
            records = [json.loads(line) for line in (ROOT / builder.INPUTS).read_text().splitlines()]
            records[-1]["id"] = records[0]["id"]
            path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
            with self.assertRaisesRegex(ValueError, "Duplicate or missing review ID"):
                builder.load_jsonl(path, {f"DEV-{index:03d}" for index in range(1, 61)})


if __name__ == "__main__":
    unittest.main()

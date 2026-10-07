from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_native_agreement_policy_v1 as policy


class NativeAgreementPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = policy.analysis()
        cls.feed = json.loads((ROOT / policy.FEED).read_text())

    def test_all_21_pairs_have_fixed_denominators_and_retained_errors(self):
        pairs = self.data["pairs"]
        ids = [model["id"] for model in self.data["components"]]
        self.assertEqual([(pair["left"], pair["right"]) for pair in pairs],
                         list(combinations(ids, 2)))
        for pair in pairs:
            self.assertEqual(pair["accepted_count"] + pair["deferred_count"], 60)
            self.assertEqual(pair["accepted_all_four_correct"] +
                             pair["accepted_all_four_error_count"], pair["accepted_count"])
            self.assertEqual(set(pair["accepted_ids"]) & set(pair["deferred_ids"]), set())
            self.assertEqual(set(pair["accepted_ids"]) | set(pair["deferred_ids"]),
                             {f"DEV-{index:03d}" for index in range(1, 61)})
            self.assertIsNotNone(pair["known_two_run_development_cost_usd"])
            for field in policy.FIELDS:
                confusion = pair["accepted_field_confusion_reference_rows"][field]
                self.assertEqual(sum(sum(row.values()) for row in confusion.values()),
                                 pair["accepted_count"])
                self.assertTrue(set(pair["accepted_field_error_ids"][field]) <=
                                set(pair["accepted_all_four_error_ids"]))
        solar_perplexity = next(pair for pair in pairs if pair["left"] ==
            "solar-decide-native-fresh1-p0" and pair["right"] ==
            "perplexity-decider-native-fresh1-p0")
        self.assertEqual((solar_perplexity["accepted_count"],
                          solar_perplexity["accepted_all_four_error_count"],
                          solar_perplexity["deferred_count"]), (53, 0, 7))

    def test_acceptance_does_not_use_reference(self):
        original = policy.evaluate_pair(self.feed["reviews"],
            "clef-openrouter-native-fresh1-p0", "perplexity-decider-native-fresh1-p0")
        changed = deepcopy(self.feed["reviews"])
        for review in changed:
            review["reference"]["sentiment"] = "deliberately_changed_reference"
        rescored = policy.evaluate_pair(changed,
            "clef-openrouter-native-fresh1-p0", "perplexity-decider-native-fresh1-p0")
        self.assertEqual(original["accepted_ids"], rescored["accepted_ids"])
        self.assertEqual(original["deferred_ids"], rescored["deferred_ids"])
        self.assertNotEqual(original["accepted_all_four_correct"],
                            rescored["accepted_all_four_correct"])

    def test_changed_disputed_feed_is_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "changed.json"
            changed = deepcopy(self.feed)
            changed["reviews"][0]["answers"][0]["prediction"]["sentiment"] = "changed"
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "differs from pinned source rebuild"):
                policy.analysis(feed_path=path)

    def test_unknown_or_unreconciled_cost_is_not_summed(self):
        runs = json.loads((ROOT / policy.RUNS).read_text())
        changed = deepcopy(runs)
        target = next(run for run in changed["runs"] if run["id"] ==
                      "perplexity-decider-native-fresh1-p0")
        target["cost"]["unknownUpperBoundUsd"] = 0.001
        costs = policy.model_costs(ROOT, self.feed["models"], changed)
        self.assertIsNone(costs[target["id"]])
        target["cost"]["unknownUpperBoundUsd"] = 0
        target["cost"]["knownUsd"] = 0.01
        with self.assertRaisesRegex(ValueError, "charges do not reconcile"):
            policy.model_costs(ROOT, self.feed["models"], changed)


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "public-site/deep-insights-v1.json"


def resolve(feed, path):
    node = feed
    for part in path.replace("]", "").replace("[", ".").split("."):
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


class DeepInsightsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.check = subprocess.run([sys.executable, "scripts/build_deep_insights_v1.py", "--check"], cwd=ROOT,
                                   capture_output=True, text=True, timeout=600)
        cls.feed = json.loads(FEED.read_text())

    def test_committed_feed_matches_a_fresh_build(self):
        self.assertEqual(self.check.returncode, 0, self.check.stdout + self.check.stderr)
        self.assertIn("Verified public-site/deep-insights-v1.json", self.check.stdout)

    def test_every_bound_source_hash_is_current(self):
        sources = self.feed["source_sha256"]
        self.assertIn("docs/talk/scripts/common.py", sources)
        self.assertIn("public-site/native-agreement-policy-v1.json", sources)
        for rel, digest in sources.items():
            self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), digest, rel)

    def test_every_displayed_number_path_resolves(self):
        for name, block in self.feed.items():
            for item in block.get("key_numbers", []) if isinstance(block, dict) else []:
                for key in ("value", "of", "share"):
                    if item[key]:
                        resolve(self.feed, item[key])
        for part in self.feed["what_changed"]["segments"] + [s for i in self.feed["corrections"]["items"] for s in i["correct"]]:
            if not isinstance(part, str):
                self.assertIsNotNone(resolve(self.feed, part["path"]), part)

    def test_full_policy_routing_for_solar_and_perplexity(self):
        rows = {row["step"].split(":")[0].split(" (")[0]: row["count"] for row in self.feed["agreement_rule"]["full_policy_routing"]["rows"]}
        self.assertEqual(list(rows.values()), [7, 24, 4, 35, 25])
        sp = self.feed["agreement_rule"]["solar_perplexity"]
        self.assertEqual((sp["accepted"], sp["accepted_errors"], sp["deferred"], sp["two_run_charge_usd"]), (53, 0, 7, 0.03749436))

    def test_agreement_pass_sensitivity_keeps_unknown_cost_unknown(self):
        rule = self.feed["agreement_rule"]
        self.assertEqual((rule["qwen_gemma"]["accepted"], rule["qwen_gemma"]["accepted_errors"]), (58, 0))
        by_pass = {row["run_b"]["pass"]: row for row in rule["qwen_gemma_pass_sensitivity"]}
        self.assertEqual((by_pass["fresh2"]["accepted"], by_pass["fresh2"]["accepted_errors"]), (57, 1))
        self.assertEqual((by_pass["fresh3"]["accepted"], by_pass["fresh3"]["accepted_errors"]), (59, 1))
        self.assertIsNone(by_pass["fresh2"]["two_run_charge_usd"])
        self.assertEqual((rule["pairs_beating_solar_perplexity"], rule["charged_cross_pairs"]), (35, 853))

    def test_corrections_dated_8_october(self):
        values = {item["id"]: item["values"] for item in self.feed["corrections"]["items"]}
        self.assertEqual(self.feed["corrections"]["date"], "2026-10-08")
        self.assertEqual(values["dev029-mixed"]["mixed"], 4)
        self.assertEqual(values["zero-error-pairs"]["pairs"], 5)
        self.assertEqual(round(values["seven-model-cost"]["total_usd"], 4), 1.2013)
        self.assertEqual(round(values["seven-model-cost"]["unknown_upper_bound_usd"], 2), 0.13)
        self.assertEqual(values["seven-model-cost"]["clef_known_usd"], 0.31128624)
        jev_item = next(i for i in self.feed["corrections"]["items"] if i["id"] == "jev-calibration")
        self.assertEqual(jev_item["confidence_tag"], "descriptive-only")
        self.assertEqual(values["opus-passes"]["scores"], [59, 58, 58])
        self.assertEqual(values["jev-calibration"]["ece"], 0.011)
        self.assertEqual([(a["id"], a["confidence"], a["prediction"]) for a in values["jev-calibration"]["confident_wrong"]],
                         [("DEV-027", 0.96, "no"), ("DEV-029", 0.91, "no")])

    def test_headline_counts(self):
        f = self.feed
        self.assertEqual((f["determinism"]["zero_change"], f["determinism"]["configurations"]),
                         ({"decision": 31, "general": 11}, {"decision": 50, "general": 202}))
        self.assertEqual((f["frontier_convergence"]["largest_set"]["run_passes"], f["frontier_convergence"]["largest_set"]["family_count"]), (44, 7))
        self.assertEqual(f["hardest_reviews"]["reviews"][0]["id"], "DEV-030")
        self.assertEqual(f["prompt_direction"]["steps"]["P1->P2"]["worse"], 127)
        self.assertEqual(f["cost_frontier"]["gate"]["passes"][0]["usd"], 0.00268114)


if __name__ == "__main__":
    unittest.main()

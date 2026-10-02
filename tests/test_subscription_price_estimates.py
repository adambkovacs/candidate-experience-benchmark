import importlib.util
import unittest
from decimal import Decimal
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "scripts/build_subscription_price_estimates.py"
SPEC = importlib.util.spec_from_file_location("subscription_prices", PATH)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class SubscriptionPriceTests(unittest.TestCase):
    def test_claude_uses_both_cache_write_durations_and_does_not_add_thinking(self):
        tokens = dict(input=100, cacheRead=200, cacheWrite=300, cacheWrite5m=100,
                      cacheWrite1h=200, output=400, reasoningOutput=250)
        amount, status, parts = MOD.estimate("claude-fable-5-1", tokens, True)
        self.assertEqual(status, "complete")
        self.assertEqual(Decimal(amount), Decimal("0.0263"))
        self.assertEqual(Decimal(parts["output"]), Decimal("0.0200"))

    def test_codex_cached_tokens_are_within_input_total(self):
        tokens = dict(input=1000, cacheRead=300, cacheWrite=100,
                      output=200, reasoningOutput=150)
        amount, status, _ = MOD.estimate("gpt-6-sol", tokens, True)
        self.assertEqual(status, "complete")
        self.assertEqual(Decimal(amount), Decimal("0.00351"))

    def test_missing_components_and_unknown_model_do_not_gain_prices(self):
        tokens = dict(input=1000, cacheRead=0, cacheWrite=None, output=200)
        self.assertEqual(MOD.estimate("gpt-6-sol", tokens, True)[1],
                         "cache_write_tokens_unreported")
        self.assertEqual(MOD.estimate("gpt-6-sol-unknown", tokens, True)[1],
                         "unpriced_exact_model")

    def test_saved_fable_high_usage_resolves_one_hour_cache(self):
        data = MOD.build()
        entry = data["runs"]["fable51-high-phase2-batch10-p0"]
        self.assertEqual(entry["tokens"]["input"], 12)
        self.assertEqual(entry["tokens"]["cacheWrite1h"], 6451)
        self.assertEqual(entry["tokens"]["reasoningOutput"], 5705)
        self.assertEqual(entry["estimateUsd"], "0.60676")
        self.assertIsNone(entry["actualSubscriptionChargeUsd"])
        repeated = data["repeatPhases"]["fable51-high-phase2-batch10-p0:original:P0"]
        self.assertEqual(entry["estimateUsd"], repeated["estimateUsd"])

    def test_historical_codex_repeat_matrix_is_included(self):
        data = MOD.build()
        key = "codex-gpt-6-sol-high-batch10:repeat3:P2"
        phase = data["repeatPhases"][key]
        self.assertEqual(phase["estimateStatus"], "complete")
        self.assertEqual(phase["tokens"]["input"], 70155)
        self.assertEqual(phase["tokens"]["cacheRead"], 21504)
        self.assertEqual(phase["tokens"]["reasoningOutput"], 1590)
        self.assertEqual(phase["estimateUsd"], "0.1379228")
        self.assertEqual(data["repeatSeries"]["codex-gpt-6-sol-high-batch10"]["totalPhases"], 9)
        self.assertIsNotNone(data["repeatSeries"]["codex-gpt-6-sol-high-batch10"]["fullSeriesEstimateUsd"])


if __name__ == "__main__":
    unittest.main()

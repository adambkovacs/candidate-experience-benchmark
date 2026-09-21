#!/usr/bin/env python3
"""Offline checks only: these are not model quality results."""
import importlib.util, io, json, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bench", ROOT / "scripts/development_benchmark.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

class DevelopmentChecks(unittest.TestCase):
    def setUp(self):
        self.refs = bench.read_rows(ROOT / "data/pilot/proposed_labels.jsonl")
        self.pairs = json.loads((ROOT / "data/pilot/pairs.json").read_text())
        self.predictions = [{"id":r["id"],"status":"ok","prediction":dict(r["proposed_labels"])} for r in self.refs]

    def test_data_and_perfect_fixture(self):
        self.assertEqual(bench.validate()["records"],60)
        report = bench.score(self.refs,self.predictions,self.pairs)
        self.assertTrue(all(m["accuracy"]==1 for m in report["metrics"].values()))
        self.assertTrue(all(p["both_fully_correct"] for p in report["pair_checks"]))

    def test_failures_and_pair_inconsistency(self):
        self.predictions[8]["prediction"]["serious_concern_reported"]="no"
        self.predictions[0]["prediction"]["unexpected"]="extra"
        self.predictions[33]["prediction"]["serious_concern_reported"]="yes"
        self.predictions.pop()
        report=bench.score(self.refs,self.predictions,self.pairs)
        self.assertIn("DEV-009",report["serious_concerns"]["predicted_no"])
        self.assertEqual(set(report["missing_or_failed"]),{"DEV-001","DEV-060"})
        self.assertFalse(next(p for p in report["pair_checks"] if p["id"]=="irrelevant_religion")["invariants_preserved"])
        with self.assertRaises(ValueError):
            bench.score(self.refs,[{"id":"UNKNOWN"}],self.pairs)

    def test_runner_payload_and_failure_logging(self):
        replies=[
            {"model":"fixture-model","choices":[{"finish_reason":"stop","message":{"content":json.dumps(self.refs[0]["proposed_labels"])}}]},
            {"model":"fixture-model","choices":[{"finish_reason":"stop","message":{"content":"I refuse","refusal":"refusal"}}]},
            {"model":"fixture-model","choices":[{"finish_reason":"length","message":{"content":"{"}}]}
        ]
        calls=[]
        def fake_open(request,timeout):
            payload=json.loads(request.data)
            self.assertEqual(len(payload["messages"]),2)
            self.assertEqual(set(json.loads(payload["messages"][1]["content"])),{"feedback"})
            self.assertNotIn("proposed_labels",payload["messages"][0]["content"])
            calls.append(payload)
            if len(calls)==4:
                raise TimeoutError()
            return io.BytesIO(json.dumps(replies[len(calls)-1]).encode())
        with tempfile.TemporaryDirectory() as folder:
            args=SimpleNamespace(base_url="http://localhost:1234/v1",model="fixture-model",limit=4,
                output=str(Path(folder)/"run.jsonl"),config_note="offline mock",timeout=1)
            with patch.object(bench.urllib.request,"urlopen",side_effect=fake_open):
                bench.run(args)
            rows=bench.read_rows(args.output)
            self.assertEqual([r["status"] for r in rows],["ok","invalid_output","invalid_output","service_error"])
            self.assertEqual(len(calls),4)
            with self.assertRaises(FileExistsError):
                bench.run(args)

if __name__=="__main__":
    unittest.main()

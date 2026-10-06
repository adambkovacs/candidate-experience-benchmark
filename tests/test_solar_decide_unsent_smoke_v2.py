import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import solar_decide_unsent_smoke_v2 as successor
import solar_decide_risk_hold_v1 as risk


class SolarUnsentSmokeTests(unittest.TestCase):
    def test_exact_unsent_requests_and_four_context_reserve(self):
        value = successor.manifest_value()
        old = json.loads((successor.OLD / 'manifest.json').read_text())
        self.assertEqual(value['request_ids'], ['DEV-002','DEV-003'])
        self.assertEqual(value['requests'], old['requests'][1:3])
        self.assertEqual(value['per_request_four_question_reserve_usd'], '0.10485760')
        self.assertEqual(value['two_request_reserve_usd'], '0.20971520')
        self.assertFalse(value['full_phase_score_authorized'])
        self.assertNotIn('DEV-001', [row['id'] for row in value['requests']])

    def test_refuses_underreserve_or_changed_old_terminal(self):
        with mock.patch.object(successor, 'BOUND', successor.BOUND / 4):
            with self.assertRaises(ValueError):
                successor.manifest_value()
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in ('manifest.json','terminal-public.json','budget-reconciliation.json',
                         'budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl'):
                shutil.copyfile(successor.OLD / name, folder / name)
            terminal = json.loads((folder / 'terminal-public.json').read_text())
            terminal['smoke_never_sent'] = ['DEV-003']
            (folder / 'terminal-public.json').write_text(json.dumps(terminal))
            with mock.patch.object(successor, 'OLD', folder), mock.patch.object(risk, 'OLD', folder):
                with self.assertRaises(ValueError):
                    successor.manifest_value()

    def test_verify_and_duplicate_prepare_do_not_send(self):
        self.assertEqual(successor.verify(), successor.sha(successor.PLAN))
        with self.assertRaises(FileExistsError):
            successor.prepare()


if __name__ == '__main__':
    unittest.main()

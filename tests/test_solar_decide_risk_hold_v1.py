import json
from decimal import Decimal
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import contextmanager
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import solar_decide_risk_hold_v1 as risk


class SolarRiskHoldTests(unittest.TestCase):
    def test_four_question_gap_is_not_historical_charge(self):
        value = risk.proposal_value()
        self.assertEqual(Decimal(value['additional_risk_hold_usd']),
                         Decimal(value['conservative_four_question_bound_usd']) -
                         Decimal(value['historical_unknown_upper_bound_usd']))
        self.assertEqual(value['old_attempt_id'], 'DEV-001')
        self.assertEqual(value['old_unsent_ids'], ['DEV-002', 'DEV-003'])
        self.assertFalse(value['new_requests_authorized'])
        self.assertFalse(value['new_cost_event_authorized'])

    def test_preparation_and_verify_do_not_change_original_child(self):
        old = risk.OLD / 'budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl'
        before = risk.sha(old)
        self.assertEqual(risk.verify(), risk.sha(risk.PLAN))
        with self.assertRaises(FileExistsError):
            risk.prepare()
        self.assertEqual(risk.sha(old), before)

    def test_historical_tamper_and_unapproved_review_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in ('terminal-public.json', 'budget-reconciliation.json',
                         'budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl'):
                shutil.copyfile(risk.OLD / name, folder / name)
            terminal = json.loads((folder / 'terminal-public.json').read_text())
            terminal['smoke_never_sent'] = ['DEV-003']
            (folder / 'terminal-public.json').write_text(json.dumps(terminal))
            with mock.patch.object(risk, 'OLD', folder):
                with self.assertRaises(ValueError):
                    risk.historical()
            review = folder / 'review.json'
            review.write_text(json.dumps(risk.review_template()))
            with mock.patch.object(risk, 'REVIEW', review):
                with self.assertRaises(ValueError):
                    risk.require_review()

    def test_reviewed_risk_hold_flow_is_risk_only_and_duplicate_safe(self):
        original = risk.OLD / 'budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl'
        before = risk.sha(original)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            plan, review = base / 'proposal.json', base / 'root-review.json'
            budget, child, claim = base / 'budget.json', base / 'budget-test.jsonl', base / 'claim.json'
            plan.write_bytes(risk.PLAN.read_bytes())
            review.write_bytes(risk.REVIEW.read_bytes())
            calls = []

            def allocate(master, budget_path, entries):
                calls.append(('allocate', entries))
                budget_path.write_text(json.dumps({'partitions': entries}))
                child.write_text('{"event":"budget"}\n')

            @contextmanager
            def locked(_):
                yield SimpleNamespace(read=lambda: b'authority')

            def hold(*args, **kwargs):
                calls.append(('hold', args, kwargs))

            with (mock.patch.object(risk, 'BASE', base),
                  mock.patch.object(risk, 'PLAN', plan),
                  mock.patch.object(risk, 'REVIEW', review),
                  mock.patch.object(risk, 'BUDGET', budget),
                  mock.patch.object(risk, 'CHILD', child),
                  mock.patch.object(risk, 'CLAIM', claim),
                  mock.patch.object(risk, 'verify', return_value='checked'),
                  mock.patch.object(risk, 'require_review'),
                  mock.patch.object(risk, 'budget_entry', return_value={}),
                  mock.patch.object(risk.partitions, 'allocate', side_effect=allocate),
                  mock.patch.object(risk.authority, 'read_authority',
                                    return_value=SimpleNamespace(openrouter_available_usd=Decimal('1'))),
                  mock.patch.object(risk.authority.old, '_locked', side_effect=locked),
                  mock.patch.object(risk.authority, '_scan',
                                    return_value=(SimpleNamespace(head_sha256='head'), {}, set())),
                  mock.patch.object(risk.authority, 'hold_authority', side_effect=hold)):
                result = risk.admit()
                self.assertEqual(result['status'], 'active_risk_hold_no_inference')
                self.assertEqual(result['known_charge_usd'], '0')
                self.assertEqual(result['new_requests'], 0)
                self.assertEqual(calls[0][1][0]['cap_usd'], str(risk.CAP))
                self.assertEqual(calls[1][0], 'hold')
                with self.assertRaises(FileExistsError):
                    risk.admit()
            self.assertEqual(risk.sha(original), before)


if __name__ == '__main__':
    unittest.main()

import json
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import jev_kev_unknown_risk_hold_v1 as risk


class JevKevHistoricalRiskTests(unittest.TestCase):
    def test_three_distinct_attempts_and_only_the_missing_difference(self):
        items = risk.historical()
        self.assertEqual([item['record_id'] for item in items], ['DEV-026', 'DEV-018', 'DEV-060'])
        self.assertEqual(len({item['attempt_id'] for item in items}), 3)
        self.assertEqual(sum((Decimal(item['old_unknown_usd']) for item in items), Decimal(0)),
                         Decimal('0.003032064'))
        self.assertEqual(sum((Decimal(item['four_context_usd']) for item in items), Decimal(0)),
                         Decimal('0.012128256'))
        self.assertEqual(sum((Decimal(item['additional_risk_usd']) for item in items), Decimal(0)),
                         risk.CAP)
        proposal = risk.proposal_value()
        self.assertFalse(proposal['new_requests_authorized'])
        self.assertFalse(proposal['new_cost_event_authorized'])
        self.assertEqual(proposal['funding_pool'], 'openrouter_additional')

    def test_old_evidence_tamper_and_missing_master_hold_refused(self):
        original = risk.ITEMS[0]
        with tempfile.TemporaryDirectory() as temp:
            altered = Path(temp) / 'attempts.jsonl'
            altered.write_bytes((risk.ROOT / original['attempts']).read_bytes())
            contents = altered.read_text().replace('DEV-026', 'DEV-025')
            altered.write_text(contents)
            items = (dict(original, attempts=str(altered)),) + risk.ITEMS[1:]
            with mock.patch.object(risk, 'ITEMS', items):
                with self.assertRaises(ValueError):
                    risk.historical()
            master = Path(temp) / 'master.jsonl'
            master.write_text('{"event":"budget","cap_usd":"10"}\n')
            with mock.patch.object(risk, 'MASTER', master):
                with self.assertRaises(ValueError):
                    risk.current_master_retention()

    def test_jev_unknown_ledger_change_refused(self):
        original = risk.ITEMS[1]
        with tempfile.TemporaryDirectory() as temp:
            changed = Path(temp) / 'jev-child.jsonl'
            lines = (risk.ROOT / original['child']).read_text().splitlines()
            lines = [line for line in lines if not (
                json.loads(line).get('event') == 'unknown_cost_accounted_as_upper_bound' and
                json.loads(line).get('attempt_id') == original['attempt_id'])]
            changed.write_text('\n'.join(lines) + '\n')
            items = (risk.ITEMS[0], dict(original, child=str(changed)), risk.ITEMS[2])
            with mock.patch.object(risk, 'ITEMS', items):
                with self.assertRaises(ValueError):
                    risk.historical()

    def test_prepare_verify_and_unapproved_review_are_offline(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'proposal'
            with (mock.patch.object(risk, 'BASE', base),
                  mock.patch.object(risk, 'PLAN', base / 'proposal.json'),
                  mock.patch.object(risk, 'REVIEW', base / 'root-review.json')):
                plan_sha = risk.prepare()
                self.assertEqual(plan_sha, risk.verify())
                self.assertFalse(json.loads(risk.REVIEW.read_text())['approved'])
                with self.assertRaises(ValueError):
                    risk.require_review()
                with self.assertRaises(FileExistsError):
                    risk.prepare()
                plan = json.loads(risk.PLAN.read_text())
                plan['additional_risk_hold_usd'] = '0.012128256'
                risk.PLAN.write_text(json.dumps(plan))
                with self.assertRaises(ValueError):
                    risk.verify()

    def test_source_change_refused_before_money_action(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            plan = base / 'proposal.json'
            plan.write_text(json.dumps(risk.proposal_value()))
            with mock.patch.object(risk, 'PLAN', plan):
                with mock.patch.object(risk, 'SOURCES', risk.SOURCES + (str(base / 'changed.py'),)):
                    (base / 'changed.py').write_text('changed')
                    with self.assertRaises(ValueError):
                        risk.verify()

    def test_reviewed_admission_uses_real_temp_child_and_refuses_duplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            master = base / 'master.jsonl'
            master.write_text('{"event":"budget","cap_usd":"10"}\n')
            plan, review = base / 'proposal.json', base / 'root-review.json'
            budget = base / 'budget.json'
            child = base / ('budget-' + risk.PARTITION_ID + '.jsonl')
            claim = base / 'claim.json'
            plan.write_text(json.dumps(risk.proposal_value()))
            calls = []

            @contextmanager
            def locked(_):
                yield SimpleNamespace(read=lambda: b'authority')

            with (mock.patch.object(risk, 'BASE', base), mock.patch.object(risk, 'MASTER', master),
                  mock.patch.object(risk, 'PLAN', plan), mock.patch.object(risk, 'REVIEW', review),
                  mock.patch.object(risk, 'BUDGET', budget), mock.patch.object(risk, 'CHILD', child),
                  mock.patch.object(risk, 'CLAIM', claim),
                  mock.patch.object(risk, 'current_master_retention'),
                  mock.patch.object(risk.authority, 'read_authority',
                                    return_value=SimpleNamespace(openrouter_available_usd=Decimal('1'))),
                  mock.patch.object(risk.authority.old, '_locked', side_effect=locked),
                  mock.patch.object(risk.authority, '_scan',
                                    return_value=(SimpleNamespace(head_sha256='head'), {}, set())),
                  mock.patch.object(risk.authority, 'hold_authority',
                                    side_effect=lambda *args, **kwargs: calls.append((args, kwargs)))):
                approved = risk.review_template()
                approved.update(approved=True, independent_review=True,
                                authorized_by_root=True, reviewer='root')
                review.write_text(json.dumps(approved))
                result = risk.admit()
                self.assertEqual(result['status'], 'active_risk_hold_no_inference')
                self.assertEqual(result['new_requests'], 0)
                self.assertEqual(result['known_charge_usd'], '0')
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][1]['funding_pool'], 'openrouter_additional')
                ledger = risk.rows(master)
                self.assertEqual([e['event'] for e in ledger], ['budget', 'budget_partition'])
                self.assertEqual(ledger[1]['allocated_usd'], str(risk.CAP))
                self.assertEqual(risk.rows(child), [{'event': 'budget', 'cap_usd': str(risk.CAP)}])
                with self.assertRaises(FileExistsError):
                    risk.admit()
                self.assertEqual(len(risk.rows(master)), 2)


if __name__ == '__main__':
    unittest.main()

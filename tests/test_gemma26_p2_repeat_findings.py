import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_gemma26_p2_repeat_findings as report


def inputs():
    root = report.ROOT
    first = report.json_rows(root / report.PREFIX) + report.json_rows(root / report.FIRST_SUFFIX)
    second = report.json_rows(root / report.SECOND_ATTEMPTS)
    third = json.loads((root / report.THIRD_PROJECTION).read_text())['responses']
    rows = {'fresh1': first, 'fresh2': second, 'fresh3': third}
    records = {}
    for name, source in rows.items():
        plan = json.loads((root / report.BASE / name / 'manifest.json').read_text())
        records[name] = report.normalized(source, plan['conditions']['P2']['development'],
                                          allow_projection=name == 'fresh3')
    labels = {row['id']: row['proposed_labels'] for row in report.json_rows(root / report.LABELS)}
    published = json.loads((root / report.OUTPUT).read_text())['fixed60Scores']
    return records, labels, published


class GemmaP2RepeatFindingsTests(unittest.TestCase):
    def test_published_report_rebuilds_with_only_public_bindings(self):
        saved = json.loads((report.ROOT / report.OUTPUT).read_text())
        self.assertEqual(report.build(), saved)
        self.assertEqual(saved['completedP2Passes'], 3)
        self.assertEqual(saved['scoredSeriesConditions'], 7)
        self.assertFalse(saved['cleanMatchedThreeEligible'])
        self.assertEqual([saved['fixed60Scores'][name]['allFour'] for name in report.PASSES],
                         [57, 56, 56])
        self.assertEqual(saved['fixed60Ranges']['allFour'],
                         {'min': 56, 'max': 57, 'spread': 1})
        self.assertEqual(saved['failureIdsByPass'],
                         {'fresh1': ['DEV-007'], 'fresh2': [],
                          'fresh3': ['DEV-005', 'DEV-006']})
        for item in saved['sourceBindings']:
            self.assertEqual(report.digest(report.ROOT / item['path']), item['sha256'])
            self.assertNotRegex(item['path'], r'private|ledger|account|secret')
        self.assertNotRegex(json.dumps(saved),
                            r'raw_response|body_base64|api_key|provider_headers|feedback')

    def test_shared_valid_flips_and_match_gains_losses_are_evidence_bound(self):
        saved = json.loads((report.ROOT / report.OUTPUT).read_text())
        shared = saved['allThreeSharedValid']
        self.assertEqual(shared['denominator'], 57)
        self.assertEqual(shared['excludedIds'], ['DEV-005', 'DEV-006', 'DEV-007'])
        self.assertEqual(shared['allFourMatches'],
                         {'fresh1': 56, 'fresh2': 55, 'fresh3': 55})
        self.assertEqual([row['id'] for row in shared['changedRecords']],
                         ['DEV-013', 'DEV-059'])
        pairs = shared['pairwise']
        self.assertEqual([(p['from'], p['to'], p['changedFourFieldVectorIds'])
                          for p in pairs],
                         [('fresh1', 'fresh2', ['DEV-013']),
                          ('fresh2', 'fresh3', ['DEV-059']),
                          ('fresh1', 'fresh3', ['DEV-013', 'DEV-059'])])
        self.assertEqual([p['lostAllFourMatchIds'] for p in pairs],
                         [['DEV-013'], [], ['DEV-013']])
        self.assertEqual([p['gainedAllFourMatchIds'] for p in pairs], [[], [], []])
        self.assertEqual([(p['denominator'], p['changedFourFieldVectorIds'])
                          for p in saved['pairwiseAvailableValid']],
                         [(59, ['DEV-006', 'DEV-013']), (58, ['DEV-059']),
                          (57, ['DEV-013', 'DEV-059'])])

    def test_equal_aggregate_scores_do_not_hide_moved_per_record_error(self):
        records, labels, scores = inputs()
        original = report.analyze(records, labels, scores)
        other = next(rid for rid in report.IDS if rid != 'DEV-013' and
                     labels[rid]['sentiment'] == 'neutral' and
                     records['fresh2'][rid]['prediction']['sentiment'] == 'neutral' and
                     report.all_match(records['fresh2'][rid]['prediction'], labels[rid]) and
                     all(records[name][rid]['status'] == 'ok' for name in report.PASSES))
        changed = copy.deepcopy(records)
        a = changed['fresh2']['DEV-013']['prediction']
        b = changed['fresh2'][other]['prediction']
        a['sentiment'], b['sentiment'] = b['sentiment'], a['sentiment']
        modified = report.analyze(changed, labels, scores)
        self.assertEqual(modified['fixed60Scores'], original['fixed60Scores'])
        self.assertNotEqual(modified['allThreeSharedValid']['pairwise'],
                            original['allThreeSharedValid']['pairwise'])
        self.assertIn(other,
                      modified['allThreeSharedValid']['pairwise'][0]['lostAllFourMatchIds'])

    def test_source_hash_and_missing_failure_cannot_pass(self):
        records, labels, scores = inputs()
        changed = copy.deepcopy(records)
        changed['fresh3']['DEV-005'] = {'status': 'ok',
                                        'prediction': labels['DEV-005']}
        with self.assertRaisesRegex(ValueError, 'score differs|failures differ'):
            report.analyze(changed, labels, scores)
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            target = temp / report.SECOND_ATTEMPTS
            target.parent.mkdir(parents=True)
            shutil.copy2(report.ROOT / report.SECOND_ATTEMPTS, target)
            target.write_bytes(target.read_bytes() + b'\n')
            upstream = json.loads((report.ROOT / report.FIRST_FEED).read_text())['sourceBindings']
            with self.assertRaisesRegex(ValueError, 'binding differs'):
                report.bound(temp, report.SECOND_ATTEMPTS, [], upstream)

    def test_confusion_preserves_unavailable_and_class_balances(self):
        saved = json.loads((report.ROOT / report.OUTPUT).read_text())
        for field in report.FIELDS:
            reference = None
            for name in report.PASSES:
                view = saved['classBalanceAndConfusion'][name][field]
                if reference is None:
                    reference = view['referenceClassBalance']
                self.assertEqual(view['referenceClassBalance'], reference)
                self.assertEqual(sum(reference.values()), 60)
                self.assertEqual(sum(view['predictedClassBalanceValidOnly'].values()),
                                 saved['fixed60Scores'][name]['valid'])
                self.assertEqual(view['unavailable'],
                                 60 - saved['fixed60Scores'][name]['valid'])
                for truth, predictions in view['confusion'].items():
                    self.assertEqual(sum(predictions.values()), reference[truth])


if __name__ == '__main__':
    unittest.main()

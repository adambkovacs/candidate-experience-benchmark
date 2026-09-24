"""Offline protocol checks. These tests never fit a temperature scaler."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]/'scripts/anyjev_cached_l1.py'
spec = importlib.util.spec_from_file_location('anyjev_cached_l1', MODULE)
l1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(l1)


class CachedL1ProtocolTests(unittest.TestCase):
    def test_freeze_does_not_touch_labels(self):
        original = l1.rows
        seen = []
        def guarded(path):
            seen.append(Path(path))
            if Path(path) == l1.LABELS_FILE:
                raise AssertionError('Reference labels read during freeze')
            return original(path)
        with patch.object(l1,'rows',side_effect=guarded):
            payload = l1.fold_payload()
        self.assertNotIn(l1.LABELS_FILE,seen)
        self.assertEqual([len(f['test_ids']) for f in payload['folds']],[12]*5)
        self.assertEqual([len(f['train_ids']) for f in payload['folds']],[48]*5)
        self.assertEqual(len({i for f in payload['folds'] for i in f['test_ids']}),60)
        for pair in payload['pair_memberships']:
            self.assertEqual(sum(all(i in f['test_ids'] for i in pair['record_ids'])
                                 for f in payload['folds']),1)

    def test_frozen_map_hash_and_reconstruction(self):
        path = l1.REPO/'results/anyjev-cached-l1-cv5-2026-09-24/folds-v1.json'
        actual = l1.sha(path)
        self.assertEqual(actual,'7be25f9bcd9dfbde383bccefe4ad9e4c5a8d6a664b4964789c532dac299dff0c')
        self.assertEqual(l1.verify_fold_file(path,actual),l1.fold_payload())
        with self.assertRaisesRegex(ValueError,'reviewed hash'):
            l1.verify_fold_file(path,'0'*64)

    def test_saved_scores_and_policy_options_are_valid(self):
        saved,priors = l1.verify_scores()
        self.assertEqual(len(saved),60)
        self.assertEqual(set(priors),set(l1.KEYS))

    def test_training_label_access_excludes_heldout_ids(self):
        fold=l1.fold_payload()['folds'][0]
        class GuardedLabels(dict):
            def __getitem__(self,key):
                if key in fold['test_ids']:
                    raise AssertionError('Held-out label accessed for fitting')
                return {q:l1.VALUES[q][0] for q in l1.KEYS}
        indices=l1.training_label_indices(fold['train_ids'],fold['test_ids'],GuardedLabels(),'sentiment')
        self.assertEqual(indices,[0]*48)
        with self.assertRaisesRegex(ValueError,'Held-out ID'):
            l1.training_label_indices(fold['train_ids']+fold['test_ids'][:1],fold['test_ids'],GuardedLabels(),'sentiment')

    def test_evaluate_passes_only_training_labels_to_fit(self):
        import numpy as np
        sys.path.insert(0,str(l1.SOURCE))
        from anyjev.calibrate.posthoc import TemperatureScaler
        fold_map=l1.fold_payload()
        saved,_=l1.verify_scores()
        expected=[(f,q) for f in fold_map['folds'] for q in l1.KEYS]
        accesses=[]
        calls=[]
        class GuardedLabels(dict):
            def __getitem__(self,key):
                if len(calls)<len(expected):
                    fold,_=expected[len(calls)]
                    if key in fold['test_ids']:
                        raise AssertionError('Held-out label reached fit caller')
                    accesses.append(key)
                return {q:l1.VALUES[q][0] for q in l1.KEYS}
        class FakeScaler:
            temperature=1.0
            def apply(self,probs):
                return np.asarray(probs)
        def fake_fit(probs,train_labels):
            fold,q=expected[len(calls)]
            self.assertEqual(accesses,fold['train_ids'])
            self.assertEqual(len(train_labels),48)
            self.assertEqual(train_labels,[0]*48)
            accesses.clear()
            calls.append((fold['fold'],q))
            return FakeScaler()
        with patch.object(TemperatureScaler,'fit',side_effect=fake_fit):
            result=l1.evaluate(fold_map,saved,GuardedLabels())
        self.assertEqual(len(calls),20)
        self.assertEqual(len(result['temperatures']),20)
        for entry in result['temperatures']:
            self.assertEqual(sum(entry['train_class_support'].values()),48)
        self.assertEqual(result['reference_file_sha256'],l1.REFERENCE_SHA256)
        self.assertEqual(result['upstream_posthoc_sha256'],l1.POSTHOC_SHA256)

    def test_upstream_apply_preserves_all_saved_ranks_without_fit(self):
        import numpy as np
        sys.path.insert(0,str(l1.SOURCE))
        from anyjev.calibrate.posthoc import TemperatureScaler
        saved,_=l1.verify_scores()
        for temperature in (np.exp(-3),1.0,np.exp(3)):
            scaler=TemperatureScaler(temperature=float(temperature))
            for q in l1.KEYS:
                base=np.asarray([r['diagnostics'][q]['l0_probs'] for r in saved])
                scaled=scaler.apply(base)
                np.testing.assert_array_equal(np.argsort(base,axis=1),np.argsort(scaled,axis=1))

    def test_fixed_multiclass_metrics(self):
        out = l1.metrics([[.8,.2],[.3,.7]],[0,0])
        self.assertAlmostEqual(out['accuracy'],.5)
        self.assertAlmostEqual(out['brier'],(.08+.98)/2)
        self.assertAlmostEqual(out['ece'],(.2+.7)/2)
        self.assertEqual(sum(b['count'] for b in out['bins']),2)


if __name__=='__main__':
    unittest.main()

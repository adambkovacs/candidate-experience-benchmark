import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import specialist_benchmark as s

class SpecialistTests(unittest.TestCase):
    def test_equivalent_option_sets_and_no_metadata(self):
        rows=s.decision_rows('a feedback','the rubric')
        self.assertEqual([r['id'] for r in rows],list(s.KEYS))
        for row in rows:
            self.assertEqual([o['id'] for o in row['options']],s.VALUES[row['id']])
            self.assertEqual(set(row['state']),{'feedback','policy'})
        self.assertNotIn('proposed_labels',json.dumps(rows))
    def test_nli_explicit_semantic_uncertainty_hypothesis(self):
        pairs=s.nli_pairs('feedback','rubric')
        self.assertEqual(len(pairs),14)
        self.assertEqual(sum(' is insufficient_information.' in h for p,h in pairs),4)
        self.assertTrue(all(json.loads(p)=={'feedback':'feedback','policy':'rubric'} for p,h in pairs))

if __name__=='__main__':unittest.main()

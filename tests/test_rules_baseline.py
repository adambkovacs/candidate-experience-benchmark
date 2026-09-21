import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from rules_baseline import classify
from development_benchmark import valid

class RulesTests(unittest.TestCase):
    def test_off_topic(self):
        self.assertEqual(set(classify('The soup needs more pepper.').values()), {'insufficient_information'})
    def test_contact_and_escalation_are_separate(self):
        result=classify('The interviewer made unwanted sexual comments. Do not contact me.')
        self.assertEqual(result['serious_concern_reported'],'yes')
        self.assertEqual(result['follow_up_needed'],'no')
        self.assertEqual(result['testimonial_potential'],'no')
    def test_unanswered_process_request(self):
        result=classify('I emailed twice about rearranging the interview. Nobody has replied.')
        self.assertEqual(result['follow_up_needed'],'yes')
        self.assertTrue(valid(result))
    def test_negated_allegation(self):
        self.assertEqual(classify('There was no harassment in my interview.')['serious_concern_reported'],'no')

if __name__=='__main__':unittest.main()

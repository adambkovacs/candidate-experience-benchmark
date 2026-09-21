import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from specialist_benchmark import CoverageError, check_laya_coverage


class Tokenizer:
    mask_token = '[MASK]'
    mask_token_id = 1
    cls_token_id = 2
    sep_token_id = 3
    def __call__(self, text, **kwargs):
        return {'input_ids': text.split()}


def native_sequence(tok, state, q, max_len, head_max_len):
    # Upstream laya/common.py build_sequence's exact budget branches.
    head = tok(q['t'] + ' question: ' + q['ins'])['input_ids']
    options = [[1] + tok(' ' + option)['input_ids'][:48] for option in q['options']]
    budget = head_max_len - sum(map(len, options))
    if budget < 16:
        per = max(4, (head_max_len - 16) // max(1, len(options)))
        options = [option[:per] for option in options]
        budget = head_max_len - sum(map(len, options))
    sequence = [2] + head[:max(8, budget)] + [3]
    markers = []
    for option in options:
        markers.append(len(sequence))
        sequence += option
    sequence += [3]
    room = max(0, max_len - len(sequence) - 1)
    sequence += tok(state)['input_ids'][:room] + [3]
    return sequence[:max_len], [mark for mark in markers if mark < max_len]


class LayaCoverageTests(unittest.TestCase):
    def setUp(self):
        common = types.ModuleType('laya.common')
        common.render_options = lambda q: q['options']
        common.serialize_state = lambda s: s
        common.build_sequence = native_sequence
        self.patch = patch.dict(sys.modules, {'laya.common': common})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.agent = types.SimpleNamespace(tok=Tokenizer(), cfg={'max_len': 512, 'head_max_len': 192},
            _to_internal=lambda q: q)
        self.question = {'t': 'choice', 'ins': 'choose', 'options': ['yes', 'no']}

    def check(self, state='some feedback', question=None):
        return check_laya_coverage(self.agent, state, {'decision': question or self.question})

    def test_complete_sequence_accepted(self):
        self.assertEqual(self.check(), {'decision': 13})

    def test_state_truncation_rejected(self):
        with self.assertRaises(CoverageError): self.check('word ' * 512)

    def test_option_48_token_cap(self):
        question = {**self.question, 'options': ['word ' * 49, 'no']}
        self.agent.cfg.update(max_len=4096, head_max_len=512)
        with self.assertRaises(CoverageError): self.check(question=question)

    def test_instruction_truncation_rejected(self):
        with self.assertRaises(CoverageError): self.check(question={**self.question, 'ins': 'word ' * 192})

    def test_reserve16_branch_not_just_combined_head(self):
        # Full head+options=13<=20 but upstream still shortens each option.
        self.agent.cfg['head_max_len'] = 20
        with self.assertRaises(CoverageError):
            self.check(question={**self.question, 'options': ['one two three four', 'five six seven eight']})

    def test_expanded_context_preserves_long_state(self):
        self.agent.cfg.update(max_len=4096, head_max_len=512)
        self.assertGreater(self.check('word ' * 1000)['decision'], 1000)

if __name__ == '__main__': unittest.main()

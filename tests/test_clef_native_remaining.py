import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import clef_native_preparation as prep
import clef_native_remaining as remaining
import clef_connected_app_bridge as bridge

ACCOUNT = 'a' * 32
TOKEN = 'offline-only-token'
ENV = {prep.ACCOUNT_ENV: ACCOUNT, prep.TOKEN_ENV: TOKEN}
PRICE = {model: (ROOT / f'results/clef-native-v1/{model}-billing-source.md').read_bytes()
         for model in prep.MODELS}


def envelope(model):
    answers = {}
    for field in prep.KEYS:
        values = {label: 0.0 for label in prep.VALUES[field]}
        values[prep.VALUES[field][0]] = 1.0
        answers[field] = {'type': 'choice', 'choice': prep.VALUES[field][0],
                          'probabilities': values, 'confidence': 0.8}
    return {'success': True, 'status': 200, 'errors': [], 'messages': [],
            'result': {'model': model, 'answers': answers,
                       'usage': {'input_tokens': 100, 'output_tokens': 0}}}


class RemainingStagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.base = self.folder / 'clef'
        self.authority = self.folder / 'authority.jsonl'
        self.authority.write_bytes(remaining.AUTHORITY_SNAPSHOT.read_bytes())
        self.manifest = self.folder / 'manifest.json'
        self.manifest.write_bytes(prep.canonical(remaining.manifest_value()) + b'\n')

    def grant(self, model='clef', repeat='fresh1', condition='P1',
              phase='smoke', review_hash=None, prior_hash=None):
        path = self.folder / f'{model}-{repeat}-{condition}-{phase}-grant.json'
        value = {
            'kind': remaining.GRANT_KIND, 'approved': True,
            'authorized_by_user': True, 'reviewer': 'independent-offline-fixture',
            'model': model, 'stage': remaining.stage_name(model, repeat, condition, phase),
            'pass': repeat, 'condition': condition, 'phase': phase,
            'manifest_sha256': prep.sha(self.manifest.read_bytes()),
            'controller_sha256': prep.sha(Path(remaining.__file__).read_bytes()),
            'bridge_sha256': prep.sha(Path(bridge.__file__).read_bytes()),
            'account_id_sha256': prep.sha(ACCOUNT.encode()),
            'transport': 'mcp__codex_apps__cloudflare_execute',
            'full_context_hold_usd': str(prep.reservation_usd(model, 3 if phase == 'smoke' else 60)),
            'global_authority_cap_usd': '10.00',
            'global_authority_approval_sha256': remaining.APPROVAL_SHA256,
            'global_authority_ledger_sha256_at_admission': prep.sha(self.authority.read_bytes()),
            'billing_source_sha256': prep.sha(PRICE[model]),
            'smoke_review_sha256': review_hash,
            'prior_completion_sha256': prior_hash,
            'exhaustion_policy': 'pause', 'wait_seconds': 1}
        path.write_bytes(prep.canonical(value) + b'\n')
        return path

    def run_stage(self, grant, model='clef', repeat='fresh1', condition='P1',
                  phase='smoke', transport=None, review=None):
        return remaining.run_stage(model, repeat, condition, phase,
            self.manifest, grant, base=self.base, authority_path=self.authority,
            environment=ENV, wait_seconds=1, transport=transport,
            billing_source=lambda _: PRICE[model], smoke_review_path=review)

    def review(self, model='clef', repeat='fresh1', condition='P1'):
        directory = remaining.stage_dir(self.base, model, repeat, condition, 'smoke')
        completion = json.loads((directory / 'completion.json').read_bytes())
        value = {'kind': remaining.INSPECTION_KIND, 'approved': True,
            'reviewer': 'separate-offline-fixture', 'model': model,
            'stage': remaining.stage_name(model, repeat, condition, 'smoke'),
            'manifest_sha256': prep.sha(self.manifest.read_bytes()),
            'completion_sha256': prep.sha((directory / 'completion.json').read_bytes()),
            'records_sha256': completion['records_sha256'],
            'raw_sha256': completion['raw_sha256'],
            'decision': 'admit_unchanged_full_stage'}
        path = self.folder / f'{model}-{repeat}-{condition}-smoke-review.json'
        path.write_bytes(prep.canonical(value) + b'\n')
        return path

    def test_manifest_binds_exact_remaining_matrix_and_p_variants(self):
        manifest, _ = remaining.checked_manifest(self.manifest)
        self.assertEqual(len(manifest['stages']), 14)
        self.assertNotIn('clef/fresh2/P0', manifest['stages'])
        for model in prep.MODELS:
            self.assertIn(model, manifest['closed_fresh2_p0_completion_sha256'])
            for condition in ('P1', 'P2'):
                stage = manifest['stages'][f'{model}/fresh1/{condition}']
                self.assertEqual(stage['requests'],
                    prep.build_plan()['models'][model]['requests'][condition])
        with self.assertRaisesRegex(ValueError, 'Unpinned'):
            remaining.stage_name('clef', 'fresh2', 'P0', 'smoke')

    def test_p1_smoke_full_review_and_no_replay(self):
        seen = []
        def transport(url, headers, body):
            seen.append(prep.sha(body))
            self.assertIn('/@cf/cloudflare/clef', url)
            self.assertEqual(headers['Authorization'], 'Bearer ' + TOKEN)
            return 200, prep.canonical(envelope('clef'))
        smoke_grant = self.grant()
        smoke_result = self.run_stage(smoke_grant, transport=transport)
        self.assertEqual((smoke_result['attempted'], smoke_result['counts']['valid']), (3, 3))
        review = self.review()
        full_grant = self.grant(phase='development',
                                review_hash=prep.sha(review.read_bytes()))
        full_result = self.run_stage(full_grant, phase='development',
                                     transport=transport, review=review)
        self.assertEqual((full_result['attempted'], full_result['counts']['valid']), (60, 60))
        self.assertEqual(len(seen), 63)
        self.assertEqual(len(set(seen)), 60)
        actual = [r['request_sha256'] for r in
                  (json.loads(line) for line in
                   (remaining.stage_dir(self.base, 'clef', 'fresh1', 'P1', 'development')
                    / 'records.jsonl').read_bytes().splitlines())]
        expected = [r['payload_sha256'] for r in
                    remaining.manifest_value()['stages']['clef/fresh1/P1']['requests']]
        self.assertEqual(actual, expected)
        with self.assertRaisesRegex(ValueError, 'already claimed'):
            self.run_stage(full_grant, phase='development',
                           transport=transport, review=review)
        prior = prep.sha((remaining.stage_dir(self.base, 'clef', 'fresh1', 'P1',
                                               'development') / 'completion.json').read_bytes())
        successor_grant = self.grant(repeat='fresh2', condition='P1',
                                     prior_hash=prior)
        successor = self.run_stage(successor_grant, repeat='fresh2',
                                   condition='P1', transport=transport)
        self.assertEqual((successor['attempted'], successor['counts']['valid']), (3, 3))
        self.assertEqual(successor['stage'], 'clef/fresh2/P1/smoke')

    def test_changed_grant_fails_before_hold(self):
        grant = self.grant()
        value = json.loads(grant.read_bytes())
        value['condition'] = 'P2'
        grant.write_bytes(prep.canonical(value) + b'\n')
        head = self.authority.read_bytes()
        with self.assertRaisesRegex(ValueError, 'single-stage grant'):
            self.run_stage(grant, transport=lambda *_: self.fail('dispatch'))
        self.assertEqual(self.authority.read_bytes(), head)

    def test_successor_requires_terminal_prior_pass(self):
        grant = self.grant(repeat='fresh2', condition='P1')
        head = self.authority.read_bytes()
        with self.assertRaises(FileNotFoundError):
            self.run_stage(grant, repeat='fresh2', condition='P1',
                           transport=lambda *_: self.fail('dispatch'))
        self.assertEqual(self.authority.read_bytes(), head)
        self.assertEqual(
            remaining.predecessor_hash('clef', 'fresh3', 'P0',
                                       prep.sha(self.manifest.read_bytes())),
            remaining.manifest_value()['closed_fresh2_p0_completion_sha256']['clef'])

    def test_changed_billing_page_or_input_manifest_blocks_before_hold(self):
        grant = self.grant()
        head = self.authority.read_bytes()
        with self.assertRaisesRegex(ValueError, 'billing page changed'):
            remaining.run_stage('clef', 'fresh1', 'P1', 'smoke',
                self.manifest, grant, base=self.base, authority_path=self.authority,
                environment=ENV, wait_seconds=1,
                transport=lambda *_: self.fail('dispatch'),
                billing_source=lambda _: b'changed price')
        self.assertEqual(self.authority.read_bytes(), head)
        manifest = json.loads(self.manifest.read_bytes())
        manifest['stages']['clef/fresh1/P1']['requests'][0]['payload_sha256'] = '0' * 64
        self.manifest.write_bytes(prep.canonical(manifest) + b'\n')
        with self.assertRaisesRegex(ValueError, 'manifest differs'):
            self.run_stage(grant, transport=lambda *_: self.fail('dispatch'))
        self.assertEqual(self.authority.read_bytes(), head)

    def test_service_error_stops_with_unknown_hold_and_unsent(self):
        grant = self.grant(model='clef-flash', condition='P2')
        seen = []
        def transport(*_):
            seen.append(1)
            return 429, prep.canonical({'success': False, 'status': 429,
                                         'errors': [{'code': 1000, 'message': 'fixture'}],
                                         'messages': [], 'result': None})
        result = self.run_stage(grant, model='clef-flash', condition='P2',
                                transport=transport)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result['counts']['service_error'], 1)
        self.assertEqual(result['never_sent'], list(prep.SMOKE_IDS[1:]))
        self.assertEqual(result['unknown_cost_reserved_usd'], '0.005899')


if __name__ == '__main__':
    unittest.main()

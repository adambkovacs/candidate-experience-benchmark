import base64
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
PREP_SPEC = importlib.util.spec_from_file_location('clef_native_preparation',
    ROOT / 'scripts/clef_native_preparation.py')
prep = importlib.util.module_from_spec(PREP_SPEC)
PREP_SPEC.loader.exec_module(prep)
RUN_SPEC = importlib.util.spec_from_file_location('clef_native_smoke_runner',
    ROOT / 'scripts/clef_native_smoke_runner.py')
runner = importlib.util.module_from_spec(RUN_SPEC)
RUN_SPEC.loader.exec_module(runner)

ACCOUNT = 'a' * 32
TOKEN = 'offline-test-token'
ENV = {prep.ACCOUNT_ENV: ACCOUNT, prep.TOKEN_ENV: TOKEN}
SOURCES = {name: (name + '-reviewed-source').encode() for name in prep.MODELS}


def envelope(model):
    answers = {}
    for field in prep.KEYS:
        scores = {label: 0.0 for label in prep.VALUES[field]}
        scores[prep.VALUES[field][0]] = 1.0
        answers[field] = {'type': 'choice', 'choice': prep.VALUES[field][0],
                          'probabilities': scores, 'confidence': 0.8}
    return {'success': True, 'errors': [], 'messages': [],
            'result': {'model': model, 'answers': answers, 'usage': {'input_tokens': 500}}}


class ClefNativeSmokeRunnerTests(unittest.TestCase):
    def test_env_file_loads_exact_names_and_process_values_win(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / '.env'
            env_file.write_text('OTHER_KEY=ignored\nexport CLOUDFLARE_ACCOUNT_ID="' + ACCOUNT +
                                '"\nCLOUDFLARE_API_TOKEN=\'' + TOKEN + '\'\n')
            self.assertEqual(runner.credentials({}, env_file), (ACCOUNT, TOKEN))
            self.assertEqual(runner.credentials({prep.TOKEN_ENV: 'process-token'}, env_file),
                             (ACCOUNT, 'process-token'))
            self.assertEqual(runner.credentials({prep.ACCOUNT_ENV: ACCOUNT,
                                                 prep.TOKEN_ENV: TOKEN}, Path(directory) / 'absent'),
                             (ACCOUNT, TOKEN))

    def test_cf_aliases_load_from_parent_style_file_and_process_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / '.env'
            env_file.write_text('CF_ACCOUNT_ID=' + ACCOUNT + '\nCF_API_TOKEN=' + TOKEN + '\n')
            self.assertEqual(runner.credentials({}, env_file), (ACCOUNT, TOKEN))
            self.assertEqual(runner.credentials({'CF_API_TOKEN': 'process-alias'}, env_file),
                             (ACCOUNT, 'process-alias'))
            self.assertEqual(runner.credentials({prep.TOKEN_ENV: 'process-canonical',
                                                 'CF_API_TOKEN': 'process-alias'}, env_file),
                             (ACCOUNT, 'process-canonical'))

    def test_env_file_missing_key_fails_before_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, _ = self.files(folder)
            env_file = folder / '.env'
            env_file.write_text('CLOUDFLARE_ACCOUNT_ID=' + ACCOUNT + '\nOTHER_KEY=ignored\n')
            sent = []
            def transport(*_):
                sent.append(True)
                raise AssertionError('Must not send')
            with self.assertRaisesRegex(ValueError, 'token unavailable'):
                runner.run_smoke('clef', manifest, grant, output_root=folder / 'results',
                                 environment={}, env_file=env_file, transport=transport,
                                 billing_source=self.billing)
            self.assertEqual(sent, [])

    def files(self, folder):
        manifest = folder / 'manifest.json'
        plan = prep.build_plan()
        manifest.write_bytes(prep.canonical(plan) + b'\n')
        grant = {'kind': 'clef-native-initial-smoke-grant-v1',
                 'approved': True, 'authorized_by_user': True, 'reviewer': 'offline-fixture',
                 'plan_sha256': prep.sha(prep.canonical(plan)),
                 'runner_sha256': prep.sha(Path(runner.__file__).read_bytes()),
                 'account_id_sha256': prep.sha(ACCOUNT.encode()),
                 'models': list(prep.MODELS), 'stage': runner.STAGE,
                 'cap_usd': '0.10', 'exhaustion_policy': 'pause',
                 'billing_source_sha256': {name: prep.sha(raw) for name, raw in SOURCES.items()},
                 'input_usd_per_million': {name: str(spec['input_usd_per_million'])
                                           for name, spec in prep.MODELS.items()}}
        grant_path = folder / 'grant.json'
        grant_path.write_bytes(prep.canonical(grant) + b'\n')
        return manifest, grant_path, grant

    def billing(self, url):
        model = next(name for name, spec in prep.MODELS.items() if spec['source'] == url)
        return SOURCES[model]

    def test_six_injected_requests_hold_unknown_cost_and_do_not_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, _ = self.files(folder)
            output = folder / 'results'
            seen = []

            def transport(url, headers, body):
                request = json.loads(body)
                model = request['model']
                self.assertTrue(url.endswith('/@cf/cloudflare/' + model))
                self.assertEqual(headers['Authorization'], 'Bearer ' + TOKEN)
                self.assertEqual(set(request['questions']), set(prep.KEYS))
                seen.append(model)
                return 200, prep.canonical(envelope(model))

            for model in prep.MODELS:
                completion = runner.run_smoke(model, manifest, grant, output_root=output,
                                               environment=ENV, transport=transport,
                                               billing_source=self.billing)
                self.assertEqual(completion['status'], 'complete')
                self.assertEqual(completion['counts']['valid'], 3)
                records = [json.loads(line) for line in (output / model / 'fresh1/P0/smoke/records.jsonl').read_text().splitlines()]
                self.assertEqual([row['id'] for row in records], list(prep.SMOKE_IDS))
                self.assertTrue(all(row['charge_status'] == 'unknown_reserved' and
                                    row['parsed']['actual_charge_usd'] is None and
                                    row['reference_labels_read'] is False for row in records))
            self.assertEqual(seen, ['clef'] * 3 + ['clef-flash'] * 3)
            ledger = [json.loads(line) for line in (output / 'budget.jsonl').read_text().splitlines()]
            self.assertEqual(len(ledger), 7)
            self.assertEqual(sum(float(row['usd']) for row in ledger[1:]), 0.064884)
            self.assertEqual(len({row['attempt_id'] for row in ledger[1:]}), 6)
            with self.assertRaises((FileExistsError, ValueError)):
                runner.run_smoke('clef', manifest, grant, output_root=output,
                                 environment=ENV, transport=transport, billing_source=self.billing)
            self.assertEqual(len(seen), 6)
            self.assertNotIn(TOKEN, '\n'.join(path.read_text() for path in output.rglob('*') if path.is_file()))

    def test_missing_or_changed_grant_blocks_before_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant_path, grant = self.files(folder)
            sent = []
            def transport(*_):
                sent.append(True)
                raise AssertionError('Must not send')
            with self.assertRaisesRegex(ValueError, 'token unavailable'):
                runner.run_smoke('clef', manifest, grant_path, output_root=folder / 'none',
                                 environment={prep.ACCOUNT_ENV: ACCOUNT}, transport=transport,
                                 billing_source=self.billing)
            changed = copy.deepcopy(grant)
            changed['cap_usd'] = '1.00'
            grant_path.write_bytes(prep.canonical(changed) + b'\n')
            with self.assertRaisesRegex(ValueError, 'Explicit reviewed'):
                runner.run_smoke('clef', manifest, grant_path, output_root=folder / 'none',
                                 environment=ENV, transport=transport, billing_source=self.billing)
            self.assertEqual(sent, [])

    def test_transport_failure_preserves_reservation_and_unsent_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, _ = self.files(folder)
            output = folder / 'results'
            def transport(*_):
                raise TimeoutError('secret text must never be logged')
            completion = runner.run_smoke('clef', manifest, grant, output_root=output,
                                           environment=ENV, transport=transport,
                                           billing_source=self.billing)
            self.assertEqual(completion['status'], 'stopped')
            self.assertEqual(completion['attempted'], 1)
            self.assertEqual(completion['counts']['unknown_outcome'], 1)
            self.assertEqual(completion['never_sent'], list(prep.SMOKE_IDS[1:]))
            self.assertEqual(completion['unknown_cost_reserved_usd'], '0.015729')
            saved = '\n'.join(path.read_text() for path in output.rglob('*') if path.is_file())
            self.assertNotIn('secret text', saved)
            self.assertNotIn(TOKEN, saved)

    def test_http_200_provider_error_stops_without_extra_paid_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, _ = self.files(folder)
            output = folder / 'results'
            sent = []
            def transport(*_):
                sent.append(True)
                return 200, prep.canonical({'success': False, 'errors': [{'code': 9001}],
                                            'messages': [], 'result': None})
            completion = runner.run_smoke('clef', manifest, grant, output_root=output,
                                           environment=ENV, transport=transport,
                                           billing_source=self.billing)
            self.assertEqual(len(sent), 1)
            self.assertEqual(completion['counts']['service_error'], 1)
            self.assertEqual(completion['never_sent'], list(prep.SMOKE_IDS[1:]))
            record = json.loads((output / 'clef/fresh1/P0/smoke/records.jsonl').read_text())
            self.assertEqual(record['reason'], 'provider_envelope_error')

    def test_http_200_malformed_envelope_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, _ = self.files(folder)
            sent = []
            def transport(*_):
                sent.append(True)
                return 200, b'not json'
            completion = runner.run_smoke('clef-flash', manifest, grant,
                                           output_root=folder / 'results', environment=ENV,
                                           transport=transport, billing_source=self.billing)
            self.assertEqual(len(sent), 1)
            self.assertEqual(completion['counts']['service_error'], 1)
            self.assertEqual(completion['never_sent'], list(prep.SMOKE_IDS[1:]))

    def test_credential_echo_is_redacted_and_smoke_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, _ = self.files(folder)
            output = folder / 'results'
            def transport(_url, _headers, body):
                model = json.loads(body)['model']
                response = envelope(model)
                response['result']['echo'] = TOKEN
                return 200, prep.canonical(response)
            completion = runner.run_smoke('clef', manifest, grant, output_root=output,
                                           environment=ENV, transport=transport,
                                           billing_source=self.billing)
            self.assertEqual(completion['status'], 'stopped')
            self.assertEqual(completion['counts']['service_error'], 1)
            self.assertEqual(completion['attempted'], 1)
            saved = '\n'.join(path.read_text() for path in output.rglob('*') if path.is_file())
            self.assertNotIn(TOKEN, saved)
            raw = [json.loads(line) for line in
                   (output / 'clef/fresh1/P0/smoke/raw.jsonl').read_text().splitlines()]
            self.assertTrue(all(row['redacted'] and
                                b'[REDACTED]' in base64.b64decode(row['raw_response_base64'])
                                for row in raw))


if __name__ == '__main__':
    unittest.main()

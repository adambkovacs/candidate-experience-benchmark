"""Offline regression for the versioned OpenJev generated wire-body fix."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
spec = importlib.util.spec_from_file_location('openjev_generated_repeat_admission_v2_candidate',
    str(REPO / 'scripts/openjev_generated_repeat_admission_v2.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
V1 = json.loads((REPO / 'results/repeatability-v1/openjev-generated-fresh-v1/manifest.json').read_text())
V2 = json.loads((REPO / 'results/repeatability-v1/openjev-generated-fresh-v2/manifest.json').read_text())


class WireBodyTests(unittest.TestCase):
    def test_all_360_roundtrip_exact_intended_wire(self):
        count = 0
        for mode in runner.MODES:
            for condition in runner.CONDITIONS:
                for old, new in zip(V1['requests'][mode][condition], V2['requests'][mode][condition]):
                    body = runner.wire_item(new)
                    self.assertEqual(hashlib.sha256(body).hexdigest(), old['wire_body_sha256'])
                    self.assertEqual(new['request_sha256'], old['request_sha256'])
                    self.assertEqual(new['payload'], old['payload'])
                    self.assertEqual(json.loads(body), old['payload'])
                    count += 1
        self.assertEqual(count, 360)
        self.assertEqual(V2['schema'], 'openjev-generated-fresh-three-v2')
        self.assertEqual(V1['schema'], 'openjev-generated-fresh-three-v1')

    def test_persisted_manifest_passes_stage_wire_guard(self):
        saved = json.loads((REPO / 'results/repeatability-v1/openjev-generated-fresh-v2/manifest.json').read_text())
        for mode in runner.MODES:
            for condition in runner.CONDITIONS:
                runner.check_stage_wire(saved['requests'][mode][condition])

    def test_guard_rejects_tamper_before_claim_or_server(self):
        plan = json.loads((REPO / 'results/repeatability-v1/openjev-generated-fresh-v2/manifest.json').read_text())
        bad = plan['requests']['generated-off']['P0'][0]
        bad['wire_body'] += ' '
        phase = 'generated-off/fresh1/P0'
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            lock = base / 'host.lock'
            folder = base / 'phase'
            with patch.object(runner.native, 'HOST_LOCK', lock), \
                 patch.object(runner, 'phase_folder', return_value=folder), \
                 patch.object(runner, 'predecessor', side_effect=AssertionError('predecessor reached')), \
                 patch.object(runner, 'transport', side_effect=AssertionError('network reached')), \
                 patch.object(runner.native, 'start_server', side_effect=AssertionError('server reached')):
                with self.assertRaisesRegex(ValueError, 'before dispatch'):
                    runner.execute(plan, 'x'*64, phase, 'smoke', base / 'receipt.json')
            self.assertFalse((folder / 'smoke.claim.json').exists())
            self.assertFalse((folder / 'smoke.server.log').exists())

    def test_transport_sends_exact_preserved_bytes(self):
        expected = runner.wire_item(V2['requests']['generated-off']['P0'][0])
        sent = {}
        class Response:
            status = 200
            def getheaders(self): return [('Content-Type', 'application/json')]
            def read(self, limit): return b'{}'
        class Connection:
            def __init__(self, *args, **kwargs): pass
            def request(self, method, path, body, headers):
                sent.update(method=method, path=path, body=body, headers=headers)
            def getresponse(self): return Response()
            def close(self): pass
        with patch.object(runner.http.client, 'HTTPConnection', Connection):
            runner.transport(expected)
        self.assertEqual(sent['body'], expected)
        self.assertEqual((sent['method'], sent['path']), ('POST', '/v1/chat/completions'))


if __name__ == '__main__': unittest.main()

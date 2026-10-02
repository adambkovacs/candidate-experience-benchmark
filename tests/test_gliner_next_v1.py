import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gliner_next_v1 as next_v1


class GlinerNextOfflineTests(unittest.TestCase):
    def test_saved_manifest_is_source_bound_and_input_only(self):
        value = next_v1.build()
        self.assertEqual(value, json.loads(next_v1.OUTPUT.read_text()))
        self.assertFalse(value['reference_labels_read'])
        self.assertFalse(value['inference_performed'])
        self.assertEqual(value['token_fit']['status'], 'unverified')
        self.assertEqual(set(value['phases']), {'P0', 'P1', 'P2'})
        for phase in ('P0', 'P1', 'P2'):
            rows = value['phases'][phase]['requests']
            self.assertEqual([row['id'] for row in rows],
                             [f'DEV-{i:03d}' for i in range(1, 61)])
            self.assertEqual(len({row['payload_sha256'] for row in rows}), 60)
            self.assertGreater(min(row['message_utf8_bytes'] for row in rows), 8192)
        self.assertTrue(all('proposed_labels' not in path for path in value['source_sha256']))
        for name, digest in value['source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest)

    def test_price_drift_refused_even_when_capture_hash_is_updated(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for name in ('models.json', 'base-models.json', 'openapi.json', 'capture.json'):
                shutil.copyfile(next_v1.BASE / name, base / name)
            models = json.loads((base / 'models.json').read_text())
            target = next(item for item in models['data'] if item.get('id') == next_v1.MODEL)
            target['input_price_per_million'] = 0.15
            raw = json.dumps(models).encode()
            (base / 'models.json').write_bytes(raw)
            capture = json.loads((base / 'capture.json').read_text())
            capture['items']['models.json']['sha256'] = hashlib.sha256(raw).hexdigest()
            capture['items']['models.json']['bytes'] = len(raw)
            (base / 'capture.json').write_text(json.dumps(capture))
            with patch.object(next_v1, 'BASE', base):
                with self.assertRaisesRegex(ValueError, 'context or price differs'):
                    next_v1.read_catalog()

    def test_wrong_input_shape_refused(self):
        with patch.object(next_v1, 'read_rows', return_value=[{'id': 'DEV-001',
                                                               'feedback': 'text',
                                                               'reference': 'yes'}]):
            with self.assertRaisesRegex(ValueError, 'input-only'):
                next_v1.requests()


if __name__ == '__main__':
    unittest.main()

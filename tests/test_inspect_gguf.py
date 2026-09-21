import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from inspect_gguf import inspect,metadata


def string(value):
    value=value.encode();return struct.pack('<Q',len(value))+value


class GGUFInspectionTests(unittest.TestCase):
    def test_template_after_token_array_is_bound_to_weight_hash(self):
        template='{{ messages[0].content }}'
        content=b'GGUF'+struct.pack('<IQQ',3,0,2)
        content+=string('tokenizer.ggml.tokens')+struct.pack('<IIQ',9,8,2)+string('a')+string('b')
        content+=string('tokenizer.chat_template')+struct.pack('<I',8)+string(template)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'model.gguf';p.write_bytes(content)
            result=inspect(p,hashlib.sha256(content).hexdigest(),'publisher/repo/model.gguf')
            self.assertEqual(result['metadata']['tokenizer.chat_template'],template)
            self.assertEqual(result['template_sha256'],hashlib.sha256(template.encode()).hexdigest())
            self.assertEqual(result['metadata']['tokenizer.ggml.tokens']['count'],2)

    def test_split_artifacts_are_rejected(self):
        content=b'GGUF'+struct.pack('<IQQ',3,0,2)
        content+=string('split.count')+struct.pack('<IH',2,2)
        content+=string('tokenizer.chat_template')+struct.pack('<I',8)+string('template')
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'model.gguf';p.write_bytes(content)
            with self.assertRaisesRegex(ValueError,'Split GGUF'):
                inspect(p,hashlib.sha256(content).hexdigest(),'model.gguf')

    def test_unverified_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'model.gguf';p.write_bytes(b'wrong artifact')
            with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
                inspect(p,'0'*64,'publisher/repo/model.gguf')

    def test_unknown_format_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'model.gguf';p.write_bytes(b'GGUF'+struct.pack('<I',1))
            with self.assertRaisesRegex(ValueError,'version'):metadata(p)

if __name__=='__main__':unittest.main()

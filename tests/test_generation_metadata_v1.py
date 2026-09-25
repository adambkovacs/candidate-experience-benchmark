import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from enrich_openrouter_generation_v1 import inventory, retrieve
from build_public_explorer import generation_metadata

class GenerationMetadataTests(unittest.TestCase):
    def test_inventory_deduplicates_only_openrouter_generation_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'results').mkdir()
            rows=[{'raw_response':{'id':'gen-a'}, 'surface':'openrouter'},
                  {'raw_response':{'id':'gen-a'}, 'provider_endpoint':'test'},
                  {'raw_response':{'id':'secret'}, 'surface':'openrouter'},
                  {'raw_response':{'id':'gen-other'}}]
            (root/'results/attempts.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            result=inventory(root)
            self.assertEqual(result['ids'],['gen-a'])
            self.assertFalse(result['inference_submitted'])

    def test_identity_mismatch_is_unavailable_and_only_get_is_used(self):
        with patch('enrich_openrouter_generation_v1.fetch',return_value={'data':{'id':'gen-wrong'}}) as call:
            self.assertEqual(retrieve('gen-a','key')['status'],'unavailable')
            call.assert_called_once_with('/generation?id=gen-a','key',timeout=30)

    def test_hash_bound_median_deduplicates_and_preserves_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); folder=root/'results/generation-metadata-v1';folder.mkdir(parents=True)
            source=root/'results/attempts.jsonl';source.write_text(json.dumps({'raw_response':{'id':'gen-a'}})+'\n'+json.dumps({'raw_response':{'id':'gen-b'}})+'\n'+json.dumps({'attempt_id':'failed','status':'service_error'})+'\n')
            binding={'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'generation_ids':['gen-a','gen-b','gen-a']}
            (folder/'manifest.json').write_text(json.dumps({'sources':{'results/attempts.jsonl':binding}}))
            (folder/'metadata.jsonl').write_text(json.dumps({'id':'gen-a','status':'ok','data':{'generation_time':1200}})+'\n'+json.dumps({'id':'gen-b','status':'unavailable'})+'\n')
            result=generation_metadata(['results/attempts.jsonl'],root)
            self.assertEqual(result['providerGenerationSeconds'],1.2)
            self.assertEqual(result['providerGenerationReportedRequests'],1)
            self.assertEqual(result['providerGenerationTotalRequests'],3)
            source.write_text('changed\n')
            with self.assertRaises(ValueError):generation_metadata(['results/attempts.jsonl'],root)

if __name__=='__main__':unittest.main()

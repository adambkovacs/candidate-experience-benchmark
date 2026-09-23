import json
import sys
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import codex_batch_benchmark as batch
from development_benchmark import KEYS

class BatchTests(unittest.TestCase):
    def setUp(self):
        self.rows=[{'id':'A','feedback':'good'},{'id':'B','feedback':'bad'}]
        self.answers=[{'id':r['id'],**{k:'insufficient_information' for k in KEYS}} for r in self.rows]
    def test_no_reference_metadata(self):
        prompt=batch.batch_prompt('policy',[{**self.rows[0],'proposed_labels':'SECRET'}])
        self.assertNotIn('SECRET',prompt)
        self.assertNotIn('proposed_labels',prompt)
    def test_out_of_order_ids_allowed(self):
        self.assertEqual(set(batch.parse_batch(json.dumps({'records':self.answers[::-1]}),self.rows)),{'A','B'})
    def test_duplicate_unknown_missing_invalid(self):
        variants=[[self.answers[0],{**self.answers[1],'id':[]}],self.answers[:1],[self.answers[0],self.answers[0]],[self.answers[0],{**self.answers[1],'id':'C'}],[self.answers[0],{**self.answers[1],'sentiment':'wrong'}]]
        for records in variants:
            with self.assertRaises(ValueError):batch.parse_batch(json.dumps({'records':records}),self.rows)
    def test_run_splits_batches_and_preserves_timing(self):
        contexts=[]
        def fake_run(cmd, **kw):
            if cmd[1:]==['login','status']:return SimpleNamespace(returncode=0,stdout='Logged in using ChatGPT',stderr='')
            if cmd[1:]==['--version']:return SimpleNamespace(returncode=0,stdout='fixture',stderr='')
            journal=Path(args.attempts+'.journal.jsonl')
            started=json.loads(journal.read_text().splitlines()[-1])
            self.assertEqual(started['event'],'request_started')
            self.assertEqual(started['request']['prompt'],kw['input'])
            self.assertEqual(started['request']['output_schema'],json.loads((kw['cwd']/'schema.json').read_text()))
            contexts.append(kw['cwd'])
            supplied=json.loads(kw['input'].rsplit(chr(10),1)[-1])
            answers=[{'id':r['id'],**{k:'insufficient_information' for k in KEYS}} for r in supplied['records']]
            (kw['cwd']/'response.json').write_text(json.dumps({'records':answers}))
            return SimpleNamespace(returncode=0,stdout='{"type":"turn.completed","usage":{"input_tokens":10}}',stderr='')
        with tempfile.TemporaryDirectory() as temp, patch.object(batch.subprocess,'run',side_effect=fake_run):
            args=SimpleNamespace(codex='codex',model='gpt-6-sol',effort='low',limit=3,batch_size=2,phase='smoke',timeout=1,output=str(Path(temp)/'rows'),attempts=str(Path(temp)/'attempts'))
            batch.run(args)
            rows=[json.loads(x) for x in Path(args.output).read_text().splitlines()]
            attempts=[json.loads(x) for x in Path(args.attempts).read_text().splitlines()]
            self.assertEqual([a['batch_size'] for a in attempts],[2,1])
            self.assertEqual(len(set(contexts)),2)
            self.assertAlmostEqual(sum(r['elapsed_seconds'] for r in rows),sum(a['elapsed_seconds'] for a in attempts))
            self.assertTrue(all(r['status']=='ok' and 'usage' not in r for r in rows))

    def test_input_selection_rejects_overflow_empty_and_duplicate(self):
        rows=[{'id':str(i),'feedback':'text'} for i in range(60)]
        for offset,limit in [(0,0),(59,2),(60,1),(-1,1)]:
            with self.assertRaises(ValueError):batch.select_inputs(rows,offset,limit)
        self.assertEqual(len(batch.select_inputs(rows,20,40)),40)
        with self.assertRaises(ValueError):batch.select_inputs(rows[:-1],0,1)
        with self.assertRaises(ValueError):batch.select_inputs([rows[0]]*60,0,3)

    def test_schema_exact_batch_count(self):
        schema=batch.batch_schema(self.rows)['properties']['records']
        self.assertEqual((schema['minItems'],schema['maxItems']),(2,2))
        self.assertEqual(schema['items']['properties']['id']['enum'],['A','B'])
if __name__=='__main__':unittest.main()

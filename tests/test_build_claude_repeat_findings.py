"""Offline evidence checks for the single Claude subscription repeat report."""
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
import build_claude_repeat_findings as report
import claude_repeat_study as study
from claude_batch_benchmark import parse_batch_result
from claude_benchmark import safe_diagnostic
from development_benchmark import digest


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, ensure_ascii=False) + '\n' for value in values))


class ClaudeRepeatReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        plans = {repeat: study.plan_data(repeat) for repeat in ('repeat2', 'repeat3')}
        sources = {report.LABELS}
        for plan in plans.values():
            sources.update(Path(item['path']) for item in plan['source_bindings'])
        pair = json.loads((ROOT / study.PAIR).read_text())
        for condition in report.CONDITIONS:
            sources.add(Path(pair['conditions'][condition]['predictions']['file']))
        for relative in sources:
            dest = self.root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, dest)
        for repeat, plan in plans.items():
            write_json(self.root / report.BASE / repeat / 'manifest.json', plan)
        self.root_patch = patch.object(study, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def _attempt(self, plan, condition, phase, item, *, failure=False):
        ids = item['record_ids']
        if failure:
            body = '{malformed'
            status = 'service_error'
            parsed = {}
            exit_code = 1
        else:
            historical = json.loads((self.root / plan['conditions'][condition]['historical_attempts']['path']).read_text().splitlines()[item['batch_index']-1 if phase=='development' else 0])
            events = historical['raw_events']
            if phase == 'smoke':
                events = json.loads(json.dumps(events))
                result = next(event for event in reversed(events) if event.get('type') == 'result')
                result['structured_output']['records'] = result['structured_output']['records'][:3]
            body = json.dumps(events)
            parsed = parse_batch_result(events, 0, ids)
            self.assertEqual(parsed['status'], 'ok')
            status = 'ok'
            exit_code = 0
        attempt = {'repeat':plan['repeat'],'condition':condition,'phase':phase,
                   'batch_index':item['batch_index'],'ids':ids,'batch_size':len(ids),
                   'workflow':'batch10','requested_model':study.MODEL,'effort':study.EFFORT,
                   'cli_version':study.RUNTIME,'request':item['request'],
                   'policy_sha256':digest(item['request']['system']),
                   'input_sha256':digest(item['input_text']),
                   'schema_sha256':digest(json.dumps(item['request']['schema'],sort_keys=True)),
                   'auth_method':'claude.ai','controller_retries':0,'exit_code':exit_code,
                   'status':status,'elapsed_seconds':2.5}
        attempt.update(parsed)
        if not failure:
            attempt['raw_events'] = safe_diagnostic(json.loads(body))
        raw = {'schema':'claude-repeat-raw-capture-v1','repeat':plan['repeat'],
               'condition':condition,'phase':phase,'batch_index':item['batch_index'],
               'record_ids':ids,'input_sha256':attempt['input_sha256'],
               'exit_code':exit_code,'timed_out':False,'stdout':body,'stderr':''}
        folder = self.root / report.BASE / plan['repeat'] / condition
        raw_name = f"{phase}.batch-{item['batch_index']:03d}.raw.jsonl"
        raw_path = folder / raw_name
        write_rows(raw_path, [raw])
        attempt['raw_capture_file'] = raw_name
        attempt['raw_capture_sha256'] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        predictions = {row['id']:{k:v for k,v in row.items() if k!='id'} for row in parsed.get('prediction',{}).get('records',[])}
        records = [{'id':rid,'status':status,'prediction':predictions.get(rid),
                    'repeat':plan['repeat'],'condition':condition,'phase':phase,
                    'batch_index':item['batch_index'],'batch_position':i+1,
                    'batch_record_ids':ids,'requested_model':study.MODEL,'effort':study.EFFORT}
                   for i,rid in enumerate(ids)]
        return attempt,records

    def _phase(self, repeat='repeat2', condition='P2', phase='smoke', *, failed=False):
        plan=json.loads((self.root/report.BASE/repeat/'manifest.json').read_text())
        folder=self.root/report.BASE/repeat/condition
        claim={'repeat':repeat,'condition':condition,'phase':phase,
               'manifest_sha256':report._sha(self.root/report.BASE/repeat/'manifest.json'),
               'preflight_admitted':True,'usage_credits_off':True,'cli_version':study.RUNTIME}
        write_json(folder/f'{phase}.claim.json',claim)
        requests=[plan['conditions'][condition]['smoke']] if phase=='smoke' else plan['conditions'][condition]['development']
        requests=requests[:1] if failed else requests
        events=[{'event':'phase_started','repeat':repeat,'condition':condition,'phase':phase}]
        attempts=[];records=[]
        for item in requests:
            fail=failed and item is requests[-1]
            attempt,new_records=self._attempt(plan,condition,phase,item,failure=fail)
            attempts.append(attempt);records.extend(new_records)
            events.append({'event':'dispatch_intent','batch_index':item['batch_index'],
                           'record_ids':item['record_ids']})
            events.append({'event':'request_completed','batch_index':item['batch_index'],
                           'status':attempt['status']})
        events.append({'event':'phase_stopped','batch_index':requests[-1]['batch_index']} if failed else
                      {'event':'phase_completed','request_count':len(requests),
                       'record_count':3 if phase=='smoke' else 60})
        write_rows(folder/f'{phase}.journal.jsonl',events)
        write_rows(folder/f'{phase}.attempts.jsonl',attempts)
        write_rows(folder/f'{phase}.records.jsonl',records)
        if phase=='smoke' and not failed:
            write_json(folder/'smoke-inspection.json',{
                'inspection':'accepted_unchanged',
                'attempts_sha256':report._sha(folder/'smoke.attempts.jsonl'),
                'records_sha256':report._sha(folder/'smoke.records.jsonl'),
                'journal_sha256':report._sha(folder/'smoke.journal.jsonl')})
        return folder

    def test_historical_three_passes_and_open_repeats_excluded(self):
        value=report.build(self.root)
        self.assertEqual(value['completedConditions'],3)
        self.assertEqual(len(value['missingPasses']),6)
        self.assertEqual(value['passes']['original']['P2']['score']['denominator'],60)
        self.assertIsNone(value['passes']['original']['P2']['usage']['actualCostUsd'])
        self.assertIsNotNone(value['passes']['original']['P2']['usage']['cliListPriceEstimateUsd'])
        self.assertIsNone(value['passes']['original']['P2']['usage']['inferenceSeconds'])
        self.assertEqual(value['pairwiseFlips'],[])
        folder=self.root/report.BASE/'repeat2'/'P2'
        write_rows(folder/'development.journal.jsonl',[{'event':'phase_started'}])
        self.assertEqual(report.build(self.root)['completedConditions'],3)

    def test_closed_full_repeat_scores_and_source_hashes(self):
        self._phase()
        self._phase(phase='development')
        value=report.build(self.root)
        self.assertEqual(value['completedConditions'],4)
        result=value['passes']['repeat2']['P2']
        self.assertEqual(result['completionStatus'],'complete')
        self.assertEqual(result['score']['denominator'],60)
        self.assertEqual(result['score']['valid'],60)
        self.assertEqual(len(result['evidence']['rawCaptures']),6)
        self.assertEqual([f['from'] for f in value['pairwiseFlips']],['original'])
        self.assertEqual(value['pairwiseFlips'][0]['fourFieldVector']['changed'],0)
        self.assertEqual(result['score']['allFour'],value['passes']['original']['P2']['score']['allFour'])
        self.assertIsNone(value['threePassSummary']['P2']['allFour']['mean'])

    def test_stopped_phase_keeps_failures_and_never_sent(self):
        self._phase()
        self._phase(phase='development',failed=True)
        value=report.build(self.root)
        self.assertEqual(value['completedConditions'],3)
        self.assertEqual(len(value['partialPasses']),1)
        result=value['passes']['repeat2']['P2']
        self.assertEqual(result['score']['denominator'],60)
        self.assertEqual(result['score']['outcomes']['service_error'],10)
        self.assertEqual(result['score']['outcomes']['never_sent'],50)
        self.assertIsNone(result['usage']['tokens']['input_tokens'])
        self.assertIsNone(result['usage']['cliListPriceEstimateUsd'])

    def test_completed_smoke_pending_inspection_is_missing(self):
        folder=self._phase()
        (folder/'smoke-inspection.json').unlink()
        value=report.build(self.root)
        self.assertEqual(value['completedConditions'],3)
        self.assertIn({'pass':'repeat2','condition':'P2','status':'smoke_uninspected'},value['missingPasses'])

    def test_terminal_timeout_preserves_unknown_usage(self):
        self._phase()
        folder=self._phase(phase='development',failed=True)
        raw_path=folder/'development.batch-001.raw.jsonl'
        raw=json.loads(raw_path.read_text())
        raw['timed_out']=True
        raw['exit_code']=None
        write_rows(raw_path,[raw])
        attempts_path=folder/'development.attempts.jsonl'
        attempt=json.loads(attempts_path.read_text())
        attempt['error_type']='TimeoutExpired'
        attempt.pop('exit_code')
        attempt['raw_capture_sha256']=report._sha(raw_path)
        write_rows(attempts_path,[attempt])
        value=report.build(self.root)
        entry=value['passes']['repeat2']['P2']
        self.assertEqual(entry['score']['outcomes']['service_error'],10)
        self.assertIsNone(entry['usage']['tokens']['input_tokens'])

    def test_raw_capture_hash_or_prediction_mismatch_rejected(self):
        folder=self._phase()
        self._phase(phase='development')
        raw=folder/'development.batch-001.raw.jsonl'
        raw.write_text(raw.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'Source hash changed'):
            report.build(self.root)
        raw.write_text(raw.read_text()[:-1])
        records=folder/'development.records.jsonl'
        values=[json.loads(line) for line in records.read_text().splitlines()]
        values[0]['prediction']['sentiment']='negative'
        write_rows(records,values)
        with self.assertRaisesRegex(ValueError,'record differs'):
            report.build(self.root)

    def test_historical_hash_change_and_check_mode(self):
        destination=self.root/'report.json'
        with patch.object(report,'ROOT',self.root):
            report.main(['--output',str(destination)])
            before=destination.read_bytes()
            report.main(['--output',str(destination),'--check'])
            destination.write_text('{}\n')
            with self.assertRaisesRegex(ValueError,'Stale report'):
                report.main(['--output',str(destination),'--check'])
            self.assertEqual(destination.read_text(),'{}\n')
            destination.write_bytes(before)
        historical=self.root/json.loads((self.root/study.PAIR).read_text())['conditions']['P0']['predictions']['file']
        historical.write_text(historical.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'Source hash changed'):
            report.build(self.root)


if __name__=='__main__':
    unittest.main()

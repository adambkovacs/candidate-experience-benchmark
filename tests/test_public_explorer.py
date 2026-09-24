import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_public_explorer import tokens,export,surface
class PublicExportTests(unittest.TestCase):
 def test_batch_usage_is_counted_once_not_per_member_or_nested_iteration(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'batch.jsonl';p.write_text(json.dumps({'batch_size':10,'usage':{'input_tokens':2,'output_tokens':100,'cache_read_input_tokens':80,'iterations':[{'input_tokens':999,'output_tokens':999}]}})+'\n')
   t=tokens({'raw_batch_attempt_files':['batch.jsonl'],'attempt_files':['missing.jsonl']},Path(d));self.assertEqual(t['input'],2);self.assertEqual(t['output'],100);self.assertEqual(t['totalRequests'],1);self.assertEqual(t['cachedInput'],80)
 def test_missing_usage_is_not_zero_or_complete(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.jsonl';p.write_text('{}\n'+json.dumps({'usage':{'prompt_tokens':0,'completion_tokens':3}})+'\n')
   t=tokens({'attempt_files':['a.jsonl']},Path(d));self.assertEqual(t['input'],0);self.assertIsNone(t['reasoning']);self.assertFalse(t['complete']);self.assertEqual(t['reportedRequests'],1)
 def test_public_payload_has_only_allowed_top_level_fields_and_no_private_paths(self):
  x=export();self.assertEqual(x['denominator'],60);self.assertEqual(set(x),{'generatedAt','denominator','referenceNote','runs','cases','promptComparisons','nativeComparisons','roster'})
  text=json.dumps(x);self.assertNotIn('/Users/',text);self.assertNotIn('api_key',text);self.assertNotIn('raw_response',text);self.assertNotIn('execution-journal',text)
  ids={r['id'] for r in x['runs']};self.assertEqual(len(ids),len(x['runs']))
  for r in x['runs']:
   self.assertTrue(0<=r['valid']<=60)
   for v in r['metrics'].values():self.assertTrue(0<=v<=r['valid'])
  for c in x['cases']:self.assertIn(c['configuration'],ids)
  self.assertTrue(all(r['condition'] in ('P0','P1','P2') for r in x['runs']))
  self.assertTrue(all(r['experimentId']==(r['parentBaselineId'] or r['id']) for r in x['runs']))
  self.assertEqual(len(ids),len(x['runs']))
  self.assertTrue(all(r['protocolId'] for r in x['runs']))
  self.assertTrue(all(r['parentBaselineId'] for r in x['runs'] if r['condition'] != 'P0'))
  self.assertTrue(all(r['disposition'] in ('scheduled','blocked','excluded') for r in x['roster']))
  self.assertGreaterEqual(sum(r['condition']=='P1' for r in x['runs']),55)
  self.assertGreaterEqual(sum(r['condition']=='P2' for r in x['runs']),54)
  self.assertTrue(all(p['eligible'] for p in x['promptComparisons']))
  self.assertTrue(all(p['comparisons'] for p in x['promptComparisons']))
  self.assertTrue(all(p['sourceStatus']=='hash-verified saved report' for p in x['promptComparisons']))
  self.assertTrue(all('/' not in r['reason'] and 'budget' not in r['reason'].lower() for r in x['roster']))
 def test_subscription_costs_are_not_invented(self):
  x=export()
  for r in x['runs']:
   if 'subscription' in r['surface']:self.assertIsNone(r['cost']['actualUsd'])
 def test_jev_cost_and_timing_are_separated_from_smoke(self):
  x=export();r=next(r for r in x['runs'] if r['id']=='typesafe-jev113-v2')
  self.assertIsNone(r['cost']['actualUsd'])
  self.assertAlmostEqual(r['cost']['estimatedUsd'],0.005890920)
  self.assertAlmostEqual(r['smokeEstimatedUsd'],0.000294294)
  self.assertEqual(r['timing']['requests'],61)
  self.assertAlmostEqual(r['timing']['totalSeconds'],131.88291757926345)
  self.assertAlmostEqual(r['timing']['medianSeconds'],1.316025041975081)
  self.assertAlmostEqual(r['timing']['medianReconciledRecordSeconds'],1.4338928749784827)
  self.assertEqual(r['tokens']['reportedRequests'],60)
  self.assertEqual(r['tokens']['totalRequests'],61)
 def test_closed_hosted_recovery_only_and_no_fabricated_pairing(self):
  x=export();q36=[r for r in x['runs'] if r['id'].startswith('openrouter-paid-qwen36-35b-a3b-') and r['condition'] in ('P1','P2')]
  q8=[r for r in x['runs'] if r['protocolId']=='qwen8-hosted-recovery-v1']
  self.assertEqual(len(q36),4)
  self.assertEqual(len(q8),3)
  self.assertTrue(all(not r['pairedEligible'] for r in q36+q8))
  self.assertTrue(any(r['condition']=='P2' and r['valid']<60 for r in q36))
  self.assertFalse(any(r['id']=='openrouter-qwen3-8b-on-json-object-p0--p2' for r in q8))
 def test_report_p0_and_local_offline_results_are_present(self):
  x=export();ids={r['id'] for r in x['runs']}
  self.assertTrue(all(p['id'] in ids for p in x['promptComparisons']))
  local=[r for r in x['runs'] if r['protocolId']=='local-prompt-exact-v1']
  self.assertEqual(len(local),6)
  self.assertTrue(all(r['complete'] for r in local))
  self.assertTrue(any(r['valid']<60 for r in local))
  self.assertTrue(all(not r['pairedEligible'] for r in local))
 def test_closed_reconciliations_replace_partial_views_without_pairing(self):
  x=export();runs={r['id']:r for r in x['runs']}
  self.assertEqual(len(runs),len(x['runs']))
  final=[r for r in x['runs'] if r['protocolId']=='hosted-final-ten-v1']
  self.assertEqual(len(final),10)
  self.assertEqual(sum(r['valid'] for r in final),580)
  self.assertTrue(all(r['complete'] and not r['pairedEligible'] for r in final))
  stopped=[r for r in x['runs'] if r['protocolId'] in ('subscription-suffix-v1','subscription-stopped-original-v1')]
  self.assertEqual(len(stopped),7)
  self.assertEqual(sum(r['valid'] for r in stopped),350)
  self.assertTrue(all(r['complete'] and not r['pairedEligible'] for r in stopped))
  self.assertEqual(runs['codex-gpt-5.6-terra-low--p2']['valid'],50)
  self.assertIn('ambiguous',runs['codex-gpt-5.6-terra-low--p2']['resultStatus'])
  self.assertTrue(all(r['experimentId']==(r['parentBaselineId'] or r['id']) for r in x['runs']))
  self.assertEqual(runs['haiku45-not_applicable-phase2-batch10-p0']['condition'],'P0')
  self.assertEqual(runs['haiku45-not_applicable-phase2-batch10-p0']['valid'],60)
  self.assertEqual(runs['haiku45-not_applicable-phase2-batch10-p0']['model'],'claude-haiku-4-5-20251001')
  for condition in ('p1','p2'):
   ident='openrouter-qwen27-low-darkbloom-fp4--'+condition
   self.assertEqual(runs[ident]['parentBaselineId'],'openrouter-qwen27-low-darkbloom-fp4')
   self.assertEqual(runs[ident]['sourceConfigurationId'],'qwen27-low-hosted-addendum-v1')
   self.assertNotIn('qwen27-low-hosted-addendum-v1--'+condition,runs)
  self.assertEqual(runs['openrouter-qwen27-low-darkbloom-fp4']['condition'],'P0')
 def test_sealed_qwen36_suffix_reports_preserve_failures_and_never_sent(self):
  x=export();runs={r['id']:r for r in x['runs']}
  off=runs['openrouter-paid-qwen36-35b-a3b-off--p2']
  on=runs['openrouter-paid-qwen36-35b-a3b-on--p2']
  self.assertEqual((off['records'],off['valid'],off['neverSent']),(60,59,0))
  self.assertEqual((on['records'],on['valid'],on['neverSent']),(39,37,21))
  self.assertEqual(on['statusCounts']['service_error'],2)
  self.assertFalse(on['complete'])
  self.assertTrue(off['complete'])
  self.assertFalse(on['pairedEligible'])
  self.assertAlmostEqual(on['cost']['knownUsd'],0.0417374)
  self.assertEqual(on['cost']['unknownUpperBoundUsd'],'0.0598016')
  self.assertTrue(all(r['sourceViews'] for r in (off,on)))
 def test_qwen8_on_p2_requires_sealed_reconciliation_and_keeps_dev027_ambiguous(self):
  x=export();runs={r['id']:r for r in x['runs']}
  ident='openrouter-qwen3-8b-on-json-object-p0--p2'
  report_path=Path(__file__).resolve().parents[1]/'results/hosted-final-suffix-reconciled-v1/qwen8-on-p2.json'
  if not report_path.is_file():
   self.assertNotIn(ident,runs)
   return
  report=json.loads(report_path.read_text())
  run=runs[ident]
  self.assertEqual(run['protocolId'],'hosted-final-suffix-v1')
  self.assertEqual((run['records'],run['valid'],run['neverSent']),
                   (report['attempted'],report['valid_outputs'],report['never_sent_count']))
  self.assertEqual(run['statusCounts'],report['status_counts'])
  self.assertEqual(run['statusCounts']['interrupted_no_provider_result'],1)
  self.assertEqual(run['complete'],report['coverage_complete'])
  self.assertFalse(run['pairedEligible'])
  self.assertEqual(run['cost']['knownUsd'],float(report['cost']['known_observed_usd']))
  self.assertEqual(run['cost']['unknownUpperBoundUsd'],report['cost']['unknown_reserved_upper_bound_usd'])
  self.assertIsNone(run['cost']['actualUsd'])
  dev027=next(c for c in x['cases'] if c['configuration']==ident and c['id']=='DEV-027')
  self.assertEqual(dev027['status'],'interrupted_no_provider_result')
  self.assertIsNone(dev027['prediction'])
 def test_local_timing_is_diagnostic_and_batch_is_explicit(self):
  x=export()
  self.assertTrue(all(not r['timing']['comparableHosted'] for r in x['runs'] if r['surface']=='Local / specialist'))
  self.assertTrue(all(not r['timing']['comparableHosted'] for r in x['runs'] if r['timing']['kind']=='batch'))
if __name__=='__main__':unittest.main()

import importlib.util
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('legacy_qwen_findings',
    ROOT / 'scripts/build_legacy_qwen_repeat_findings.py')
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
findings = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(findings)


class LegacyQwenFindingsTests(unittest.TestCase):
    def _qwen35_successor_fixture(self, root, condition='P2'):
        successor = (Path('results/repeatability-v1/legacy-qwen-fresh3-v1') /
                     'qwen35-remaining-phases-v1')
        phase = successor / 'fresh1' / condition
        manifest = json.loads((ROOT / successor / 'manifest.json').read_text())
        plan = json.loads((ROOT / findings.MANIFEST).read_text())
        scheduled = next(row for row in manifest['scope']['phases']
                         if row['pass'] == 'fresh1' and row['condition'] == condition)

        source_paths = [successor / 'manifest.json',
                        Path('scripts/qwen35_remaining_phases_v1.cjs'),
                        Path(manifest['composite']['file']), findings.LABELS]
        source_paths.extend(Path(item['file']) for item in manifest['frozen'].values())
        smoke_names = ('claim.json', 'journal.jsonl', 'raw.jsonl', 'records.jsonl',
                       'completion.json', 'root-review.json', 'host-audit.json')
        source_paths.extend(phase / f'smoke.{name}' for name in smoke_names)
        source_paths.append(phase / 'smoke-inspection.json')
        smoke_review = json.loads((ROOT / phase / 'smoke.root-review.json').read_text())
        source_paths.append(Path(smoke_review['candidate_file']))
        for relative in dict.fromkeys(source_paths):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)

        template = json.loads((ROOT / phase / 'smoke.raw.jsonl').read_text().splitlines()[0])
        config = plan['configurations']['qwen3.5-4b-sdk-thinking-on']
        # Synthetic development receipts derive only from committed smoke evidence.
        # Never depend on the live development folder being present in a checkout.
        development_review = copy.deepcopy(smoke_review)
        candidate_path = phase / 'fixture-development-candidate.json'
        development_review.update(stage='development', ids=list(findings.IDS),
            request_sha256=[r['sha256'] for r in config['conditions'][condition]['requests']],
            candidate_file=str(candidate_path))
        development_review.pop('candidate_sha256', None)
        candidate = copy.deepcopy(development_review)
        candidate.update(approved=False, authorized_by_root=False, reviewer=None, reviewed_utc=None)
        (root / candidate_path).write_text(json.dumps(candidate) + '\n')
        development_review['candidate_sha256'] = findings.sha(root / candidate_path)
        review_path = root / phase / 'development.root-review.json'
        review_path.write_text(json.dumps(development_review) + '\n')
        claim = json.loads((ROOT / phase / 'smoke.claim.json').read_text())
        claim.update(stage='development', receipt_sha256=findings.sha(review_path))
        (root / phase / 'development.claim.json').write_text(json.dumps(claim) + '\n')
        raw, records, journal = [], [], []
        for index, rid in enumerate(findings.IDS):
            request = config['conditions'][condition]['requests'][index]
            wire = copy.deepcopy(template)
            wire.update({'id': rid, 'attempt_id': f'fixture-{rid}', 'elapsed_seconds': 1.0})
            wire['result']['stats']['promptTokensCount'] = request['prompt_tokens']
            wire['result']['stats']['totalTokensCount'] = (
                request['prompt_tokens'] + wire['result']['stats']['predictedTokensCount'])
            decision = findings.classify_sdk(wire, config, request)
            self.assertEqual(decision['status'], 'ok')
            raw.append(wire)
            records.append({'id': rid, 'attempt_id': wire['attempt_id'],
                            'request_sha256': request['sha256'],
                            'reference_labels_read': False, 'decision': decision})
            journal.extend(({'event': 'started', 'id': rid, 'attempt_id': wire['attempt_id'],
                             'request_sha256': request['sha256']},
                            {'event': 'finished', 'id': rid, 'attempt_id': wire['attempt_id'],
                             'status': 'ok'}))

        def write_rows(name, rows):
            target = root / phase / name
            target.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
            return findings.sha(target)

        raw_hash = write_rows('development.raw.jsonl', raw)
        records_hash = write_rows('development.records.jsonl', records)
        journal_hash = write_rows('development.journal.jsonl', journal)
        completion = {'phase': f'qwen3.5-4b-sdk-thinking-on/fresh1/{condition}',
                      'stage': 'development', 'status': 'completed', 'reason': None,
                      'attempted': 60, 'saved': 60, 'invalid': 0,
                      'journal_sha256': journal_hash, 'raw_sha256': raw_hash,
                      'records_sha256': records_hash, 'finished_utc': '2026-10-06T10:00:00Z'}
        completion_path = root / phase / 'development.completion.json'
        completion_path.write_text(json.dumps(completion) + '\n')
        review_hash = findings.sha(root / phase / 'development.root-review.json')
        audit = {'schema': 'qwen35-remaining-phases-v1-host-audit', 'status': 'passed',
                 'phase': completion['phase'], 'stage': 'development',
                 'before': {'boot': 'fixture', 'sleep_wakes': 1, 'ac_power': True},
                 'after': {'boot': 'fixture', 'sleep_wakes': 1, 'ac_power': True},
                 'host_check': {'host_unchanged': True, 'power_source_changed': False,
                                'power_source_before': 'ac', 'power_source_after': 'ac'},
                 'error': None, 'completion_sha256': findings.sha(completion_path),
                 'reviewed_receipt_sha256': review_hash,
                 'finished_utc': '2026-10-06T10:00:01Z'}
        (root / phase / 'development.host-audit.json').write_text(json.dumps(audit) + '\n')
        return plan, manifest, phase, scheduled

    def _qwen35_continuation_fixture(self, root, condition='P1'):
        plan, _, old_phase, _ = self._qwen35_successor_fixture(root, condition)
        proposal = json.loads((ROOT / findings.QWEN35_CONTINUATION_PROPOSAL).read_text())

        def copy_file(relative):
            relative = Path(relative)
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

        for relative in (findings.MANIFEST, findings.QWEN35_CONTINUATION_PROPOSAL,
                         findings.QWEN35_CONTINUATION_REVIEW,
                         findings.QWEN35_CONTINUATION_CONTROLLER):
            copy_file(relative)
        for name, item in proposal['frozen'].items():
            values = item.values() if name == 'completed_predecessors' else (item,)
            for binding in values:
                copy_file(binding['file'])
        for binding in proposal['scope']['blocked_phase']['bindings'].values():
            copy_file(binding['file'])

        phase = findings.QWEN35_CONTINUATION / 'fresh2' / condition
        (root / phase).mkdir(parents=True, exist_ok=True)
        for source in (root / old_phase).iterdir():
            if source.is_file() and (source.name.startswith('smoke.') or
                                     source.name.startswith('development.') or
                                     source.name == 'smoke-inspection.json'):
                shutil.copyfile(source, root / phase / source.name)
        config_id = 'qwen3.5-4b-sdk-thinking-on'
        phase_id = f'{config_id}/fresh2/{condition}'
        blocked_hash = proposal['scope']['blocked_phase']['bindings']['completion']['sha256']
        for stage in ('smoke', 'development'):
            review_path = root / phase / f'{stage}.root-review.json'
            review = json.loads(review_path.read_text())
            candidate_path = phase / f'fixture-{stage}-candidate.json'
            review.update(kind='qwen35-after-smoke-failure-v1-stage-root-review',
                          phase=phase_id, proposal_sha256=findings.QWEN35_CONTINUATION_PROPOSAL_SHA,
                          controller_sha256=findings.QWEN35_CONTINUATION_CONTROLLER_SHA,
                          prior_manifest_sha256=findings.QWEN35_SUCCESSOR_MANIFEST_SHA,
                          blocked_completion_sha256=blocked_hash,
                          blocked_phase_clean_credit=False, individually_clean_phase=True,
                          candidate_file=str(candidate_path))
            for key in ('manifest_sha256', 'composite_sha256', 'clean_repeat_credit',
                        'candidate_sha256'):
                review.pop(key, None)
            candidate = copy.deepcopy(review)
            candidate.update(approved=False, authorized_by_root=False,
                             reviewer=None, reviewed_utc=None)
            (root / candidate_path).write_text(json.dumps(candidate) + '\n')
            review['candidate_sha256'] = findings.sha(root / candidate_path)
            review_path.write_text(json.dumps(review) + '\n')
            claim_path = root / phase / f'{stage}.claim.json'
            claim = json.loads(claim_path.read_text())
            claim.update(phase=phase_id, receipt_sha256=findings.sha(review_path))
            claim_path.write_text(json.dumps(claim) + '\n')
            completion_path = root / phase / f'{stage}.completion.json'
            completion = json.loads(completion_path.read_text())
            completion['phase'] = phase_id
            completion_path.write_text(json.dumps(completion) + '\n')
            audit_path = root / phase / f'{stage}.host-audit.json'
            audit = json.loads(audit_path.read_text())
            audit.update(schema='qwen35-after-smoke-failure-v1-host-audit', phase=phase_id,
                         completion_sha256=findings.sha(completion_path),
                         reviewed_receipt_sha256=findings.sha(review_path))
            audit_path.write_text(json.dumps(audit) + '\n')
        inspection_path = root / phase / 'smoke-inspection.json'
        inspection = json.loads(inspection_path.read_text())
        inspection['completion_sha256'] = findings.sha(root / phase / 'smoke.completion.json')
        inspection_path.write_text(json.dumps(inspection) + '\n')
        return plan, proposal, phase

    def _qwen35_host_fixture(self, root, *, repeat='fresh2', condition='P0'):
        import hashlib
        plan, _, old_phase = self._qwen35_continuation_fixture(root)
        proposal = json.loads((ROOT / findings.QWEN35_HOST_PROPOSAL).read_text())
        phase = findings.QWEN35_HOST_CONTINUATION / repeat / condition
        (root / phase).mkdir(parents=True)
        template = json.loads((root / old_phase / 'smoke.raw.jsonl').read_text().splitlines()[0])
        # Copy only immutable authority/prefix evidence. Never copy the live successor folder.
        sources = [findings.QWEN35_HOST_PROPOSAL, findings.QWEN35_HOST_CANDIDATE,
                   findings.QWEN35_HOST_CONTROLLER]
        for key, item in proposal['frozen'].items():
            sources.extend(Path(x['file']) for x in (item.values() if key == 'completed_predecessors' else (item,)))
        for blocked in ('blocked_phase', 'prior_blocked_phase'):
            sources.extend(Path(x['file']) for x in proposal['scope'][blocked]['bindings'].values())
        for relative in dict.fromkeys(sources):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        config_id = 'qwen3.5-4b-sdk-thinking-on'
        config, phase_id = plan['configurations'][config_id], f'{config_id}/{repeat}/{condition}'
        original_review = json.loads((ROOT / findings.QWEN35_CONTINUATION / 'fresh2/P1/smoke.root-review.json').read_text())
        instance = original_review['runtime_token_preflight']['observed_instance_reference']
        host = {'boot': 'fixture', 'sleep_wakes': 1, 'ac_power': False,
                'power_source': 'battery', 'lid_open': True,
                'operational_policy': {'schema': 'local-execution-policy-v1', 'allow_battery_power': True}}
        def write(relative, value):
            target = root / relative; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value, separators=(',', ':')) + '\n')
            return findings.sha(target)
        def write_rows(relative, rows):
            target = root / relative
            target.write_text(''.join(json.dumps(x, separators=(',', ':')) + '\n' for x in rows))
            return findings.sha(target)
        for stage, count in (('smoke', 3), ('development', 60)):
            planned = config['conditions'][condition]['requests']
            measured = [{'id': rid, 'request_sha256': r['sha256'], 'rendered_sha256': r['rendered_sha256'],
                'prompt_tokens': r['prompt_tokens'], 'artifact_sha256': config['artifact_sha256'],
                'instance_reference': instance} for rid, r in zip(findings.IDS, planned)]
            review = copy.deepcopy(original_review)
            review.update(kind='qwen35-after-host-failure-v1-stage-root-review', phase=phase_id, stage=stage,
                proposal_sha256=findings.QWEN35_HOST_PROPOSAL_SHA,
                controller_sha256=findings.QWEN35_HOST_CONTROLLER_SHA,
                blocked_completion_sha256=proposal['scope']['blocked_phase']['bindings']['completion']['sha256'],
                prior_blocked_completion_sha256=proposal['scope']['prior_blocked_phase']['bindings']['completion']['sha256'],
                previous_proposal_sha256=findings.QWEN35_CONTINUATION_PROPOSAL_SHA,
                ids=list(findings.IDS[:count]), request_sha256=[r['sha256'] for r in planned[:count]],
                host_baseline=host,
                runtime_token_preflight={'request_count': 60,
                    'requests_sha256': hashlib.sha256(json.dumps(planned, separators=(',', ':')).encode()).hexdigest(),
                    'observed_preflight_sha256': hashlib.sha256(json.dumps(measured, separators=(',', ':')).encode()).hexdigest(),
                    'observed_instance_reference': instance})
            review.pop('candidate_sha256')
            attestation = {'artifact_sha256': config['artifact_sha256'], 'load_evidence': {
                'cache': plan['policy']['cache_policy'], 'instance_reference': instance}}
            saved_preflight = {'phase': phase_id, 'stage': stage, 'measurements': measured, 'runtime': attestation}
            route = {'source': 'https://openrouter.ai/api/v1/models', 'retrieved_utc': '2026-10-06T13:31:00Z',
                'catalog_matches': [], 'exact_family_decisions': {'Qwen3.5-4B': {'catalog_id_found': False}}}
            review['route_checked_utc'] = route['retrieved_utc']
            for key, value in (('host_baseline_file', host), ('runtime_preflight_file', saved_preflight),
                               ('route_catalog_file', route), ('route_raw_file', {'data': []})):
                relative = phase / f'fixture-{stage}-{key}.json'
                review[key] = str(relative)
                review[key.replace('_file', '_sha256')] = write(relative, value)
            candidate_path = phase / f'fixture-{stage}-candidate.json'; review['candidate_file'] = str(candidate_path)
            candidate = copy.deepcopy(review)
            candidate.update(approved=False, authorized_by_root=False, reviewer=None, reviewed_utc=None)
            review['candidate_sha256'] = write(candidate_path, candidate)
            review_hash = write(phase / f'{stage}.root-review.json', review)
            dispatch_measurements = [{k: v for k, v in m.items() if k != 'id'} for m in measured[:count]]
            claim = {'phase': phase_id, 'stage': stage, 'plan_sha256': findings.MANIFEST_SHA,
                'controller_sha256': plan['controller_sha256'], 'receipt_sha256': review_hash,
                'runtime_attestation': attestation, 'runtime_preflight_sha256':
                    hashlib.sha256(json.dumps(dispatch_measurements, separators=(',', ':')).encode()).hexdigest()}
            write(phase / f'{stage}.claim.json', claim)
            raw, records, journal = [], [], []
            for index, (rid, request) in enumerate(zip(findings.IDS[:count], planned[:count])):
                wire = copy.deepcopy(template)
                wire.update(id=rid, attempt_id=f'fixture-{stage}-{rid}', elapsed_seconds=1.0)
                wire['result']['stats']['promptTokensCount'] = request['prompt_tokens']
                wire['result']['stats']['totalTokensCount'] = request['prompt_tokens'] + wire['result']['stats']['predictedTokensCount']
                if stage == 'development' and index == 59:
                    wire['result']['nonReasoningContent'] = 'invalid synthetic output'
                decision = findings.classify_sdk(wire, config, request)
                raw.append(wire); records.append({'id': rid, 'attempt_id': wire['attempt_id'],
                    'request_sha256': request['sha256'], 'reference_labels_read': False, 'decision': decision})
                journal.extend(({'event': 'started', 'id': rid, 'attempt_id': wire['attempt_id'], 'request_sha256': request['sha256']},
                    {'event': 'finished', 'id': rid, 'attempt_id': wire['attempt_id'], 'status': decision['status']}))
            completion = {'phase': phase_id, 'stage': stage, 'status': 'completed', 'reason': None,
                'attempted': count, 'saved': count, 'invalid': int(stage == 'development')}
            for key, value in (('raw', raw), ('records', records), ('journal', journal)):
                completion[key + '_sha256'] = write_rows(phase / f'{stage}.{key}.jsonl', value)
            completion_hash = write(phase / f'{stage}.completion.json', completion)
            write(phase / f'{stage}.host-audit.json', {'schema': 'qwen35-after-host-failure-v1-host-audit',
                'status': 'passed', 'phase': phase_id, 'stage': stage, 'before': host, 'after': host,
                'host_check': {'host_unchanged': True}, 'error': None,
                'completion_sha256': completion_hash, 'reviewed_receipt_sha256': review_hash})
            if stage == 'smoke':
                write(phase / 'smoke-inspection.json', {'kind': 'legacy-qwen-three-record-smoke-inspection-v1',
                    'approved': True, 'reviewer': 'root', 'reference_labels_sent': False, 'ids': list(findings.IDS[:3]),
                    'completion_sha256': completion_hash, 'raw_sha256': completion['raw_sha256'],
                    'records_sha256': completion['records_sha256']})
        return plan, proposal, phase

    def test_qwen35_host_successor_uses_existing_metrics_and_preserves_both_blocked_smokes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plan, _, phase = self._qwen35_host_fixture(root)
            closed = findings.qwen35_host_continuation_phase(root, plan, 'fresh2', 'P0', findings.binder(root)[0])
            entry = closed['entry']
            self.assertEqual((closed['source'], entry['score']['denominator'], entry['score']['valid']),
                             ('qwen35_after_host_failure_v1', 60, 59))
            self.assertEqual(entry['score']['invalidReasonIds'], {'non_json': ['DEV-060']})
            self.assertEqual(entry['blockedPredecessor']['unknown_ids'], ['DEV-003'])
            self.assertEqual(entry['priorBlockedPredecessor']['invalid_reason_ids'], {'non_json': ['DEV-001']})
            self.assertEqual(entry['powerObservation'], {'source': 'battery', 'basis': 'matching_pre_post_checks'})
            self.assertTrue(entry['cleanRepeatCredit'])
            self.assertFalse(entry['predecessorP0CleanRepeatCredit'])
            self.assertIn('designCandidate', entry['evidence']['successor'])

    def test_qwen35_host_successor_ignores_partial_live_files_without_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); phase = findings.QWEN35_HOST_CONTINUATION / 'fresh2/P0'
            (root / phase).mkdir(parents=True)
            (root / phase / 'development.records.jsonl').write_text('partial not JSON')
            with mock.patch.object(findings, 'qwen35_host_continuation_context', side_effect=AssertionError('Must not read partial')):
                self.assertIsNone(findings.qwen35_host_continuation_phase(root, {}, 'fresh2', 'P0', findings.binder(root)[0]))

    def test_qwen35_host_successor_does_not_score_stopped_development(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); phase = findings.QWEN35_HOST_CONTINUATION / 'fresh2/P0'
            (root / phase).mkdir(parents=True)
            (root / phase / 'development.completion.json').write_text('{"status":"stopped"}')
            (root / phase / 'development.host-audit.json').write_text('{}')
            with mock.patch.object(findings, 'qwen35_host_continuation_context', side_effect=AssertionError('Must not score stopped')):
                self.assertIsNone(findings.qwen35_host_continuation_phase(root, {}, 'fresh2', 'P0', findings.binder(root)[0]))

    def test_qwen35_host_successor_requires_terminal_host_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plan, _, phase = self._qwen35_host_fixture(root)
            (root / phase / 'development.host-audit.json').unlink()
            self.assertIsNone(findings.qwen35_host_continuation_phase(root, plan, 'fresh2', 'P0', findings.binder(root)[0]))

    def test_qwen35_host_successor_accepts_scheduled_third_pass_without_live_host(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plan, _, phase = self._qwen35_host_fixture(root, repeat='fresh3', condition='P1')
            closed = findings.qwen35_host_continuation_phase(root, plan, 'fresh3', 'P1', findings.binder(root)[0])
            self.assertEqual(closed['entry']['sourcePath'], str(phase))
            self.assertEqual(closed['entry']['score']['valid'], 59)

    def test_qwen35_host_successor_rejects_rehashed_raw_control_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plan, _, phase = self._qwen35_host_fixture(root)
            raw_path = root / phase / 'development.raw.jsonl'
            rows = [json.loads(x) for x in raw_path.read_text().splitlines()]
            rows[0]['result']['stats']['promptTokensCount'] += 1
            raw_path.write_text(''.join(json.dumps(x) + '\n' for x in rows))
            completion_path = root / phase / 'development.completion.json'
            completion = json.loads(completion_path.read_text()); completion['raw_sha256'] = findings.sha(raw_path)
            completion_path.write_text(json.dumps(completion) + '\n')
            audit_path = root / phase / 'development.host-audit.json'
            audit = json.loads(audit_path.read_text()); audit['completion_sha256'] = findings.sha(completion_path)
            audit_path.write_text(json.dumps(audit) + '\n')
            with self.assertRaisesRegex(ValueError, 'classifier'):
                findings.qwen35_host_continuation_phase(root, plan, 'fresh2', 'P0', findings.binder(root)[0])

    def test_qwen35_host_successor_rejects_false_passed_host_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plan, _, phase = self._qwen35_host_fixture(root)
            path = root / phase / 'development.host-audit.json'
            audit = json.loads(path.read_text()); audit['after'] = {**audit['after'], 'sleep_wakes': 2}
            path.write_text(json.dumps(audit) + '\n')
            with self.assertRaisesRegex(ValueError, 'recorded preflight'):
                findings.qwen35_host_continuation_phase(root, plan, 'fresh2', 'P0', findings.binder(root)[0])

    def test_qwen35_host_successor_enters_report_condition_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plan, _, phase = self._qwen35_host_fixture(root)
            config_id = 'qwen3.5-4b-sdk-thinking-on'
            bind, bindings = findings.binder(root)
            closed = findings.qwen35_host_continuation_phase(root, plan, 'fresh2', 'P0', bind)
            labels = {x['id']: x['proposed_labels'] for x in findings.read_rows(root, findings.LABELS)}
            plan['configurations'][config_id]['schedule'] = [{'name': 'fresh2', 'conditions': ['P0']}]
            with mock.patch.object(findings, 'load_context', return_value=(plan, labels, bind, bindings)), \
                 mock.patch.object(findings, 'CONFIGS', (config_id,)), \
                 mock.patch.object(findings, 'qwen35_successor_phase', return_value=None), \
                 mock.patch.object(findings, 'qwen35_continuation_phase', return_value=None), \
                 mock.patch.object(findings, 'qwen35_host_continuation_phase', return_value=closed):
                report = findings.build(root)
            series = report['series'][0]
            self.assertEqual(series['completedConditions'], 1)
            self.assertEqual(series['passes']['fresh2']['P0']['score']['valid'], 59)
            self.assertEqual(series['threePassSummary']['P0']['allFour']['completedPasses'], 1)

    def test_qwen35_host_successor_rejects_changed_approved_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plan, _, phase = self._qwen35_host_fixture(root)
            path = root / findings.QWEN35_HOST_PROPOSAL
            proposal = json.loads(path.read_text()); proposal['policy']['controls_unchanged'] = False
            path.write_text(json.dumps(proposal) + '\n')
            with self.assertRaisesRegex(ValueError, 'Source hash differs'):
                findings.qwen35_host_continuation_phase(root, plan, 'fresh2', 'P0', findings.binder(root)[0])

    def test_qwen35_successor_requires_a_terminal_host_audited_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, manifest, phase, _ = self._qwen35_successor_fixture(root)
            (root / phase / 'development.host-audit.json').unlink()
            result = findings.qwen35_successor_phase(
                root, plan, 'fresh1', 'P2', findings.binder(root)[0])
            self.assertIsNone(result)

    def test_qwen35_successor_reports_individually_closed_phase_from_successor_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, manifest, phase, _ = self._qwen35_successor_fixture(root)
            closed = findings.qwen35_successor_phase(
                root, plan, 'fresh1', 'P2', findings.binder(root)[0])
            self.assertEqual((closed['pass'], closed['condition'], closed['source'],
                              closed['entry']['score']['denominator'],
                              closed['entry']['score']['valid']),
                             ('fresh1', 'P2', 'qwen35_remaining_phases_v1', 60, 60))
            self.assertTrue(closed['entry']['cleanRepeatCredit'])
            self.assertFalse(closed['entry']['predecessorP0CleanRepeatCredit'])
            self.assertEqual(closed['entry']['evidence']['development']['completion']['path'],
                             str(phase / 'development.completion.json'))
            self.assertEqual(closed['entry']['evidence']['successor']['manifest']['sha256'],
                             findings.sha(root / phase.parents[1] / 'manifest.json'))

    def test_qwen35_successor_accepts_each_scheduled_condition_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, _, phase, _ = self._qwen35_successor_fixture(root, condition='P1')
            closed = findings.qwen35_successor_phase(
                root, plan, 'fresh1', 'P1', findings.binder(root)[0])
            self.assertEqual(closed['entry']['sourcePath'], str(phase))
            self.assertEqual(closed['entry']['score']['invalidReasonIds'], {})

    def test_qwen35_successor_rejects_source_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, _, phase, _ = self._qwen35_successor_fixture(root)
            raw_path = root / phase / 'development.raw.jsonl'
            rows = raw_path.read_text().splitlines()
            changed = json.loads(rows[0])
            changed['result']['stats']['promptTokensCount'] += 1
            rows[0] = json.dumps(changed, separators=(',', ':'))
            raw_path.write_text('\n'.join(rows) + '\n')
            with self.assertRaisesRegex(ValueError, 'Source hash differs|receipt|classifier'):
                findings.qwen35_successor_phase(
                    root, plan, 'fresh1', 'P2', findings.binder(root)[0])

    def test_qwen35_continuation_accepts_approved_proposal_and_closed_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, proposal, phase = self._qwen35_continuation_fixture(root)
            closed = findings.qwen35_continuation_phase(
                root, plan, 'fresh2', 'P1', findings.binder(root)[0])
            self.assertEqual((proposal['status'], closed['source'],
                              closed['entry']['sourcePath'], closed['entry']['score']['denominator'],
                              closed['entry']['score']['valid']),
                             ('approved', 'qwen35_after_smoke_failure_v1', str(phase), 60, 51))
            self.assertTrue(closed['entry']['cleanRepeatCredit'])
            self.assertEqual(closed['entry']['blockedPredecessor']['status'], 'smoke_blocked')
            self.assertFalse(closed['entry']['blockedPredecessor']['development_admitted'])
            self.assertEqual(closed['entry']['blockedPredecessor']['invalid_reason_ids'],
                             {'non_json': ['DEV-001']})

    def test_qwen35_continuation_excludes_incomplete_development(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, _, phase = self._qwen35_continuation_fixture(root)
            (root / phase / 'development.host-audit.json').unlink()
            self.assertIsNone(findings.qwen35_continuation_phase(
                root, plan, 'fresh2', 'P1', findings.binder(root)[0]))

    def test_qwen35_continuation_rejects_proposal_or_raw_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, _, phase = self._qwen35_continuation_fixture(root)
            raw_path = root / phase / 'development.raw.jsonl'
            raw_path.write_text(raw_path.read_text().replace('"promptTokensCount":',
                                                              '"promptTokensCount":999999,"x":', 1))
            with self.assertRaisesRegex(ValueError, 'Source hash differs|receipt|classifier'):
                findings.qwen35_continuation_phase(
                    root, plan, 'fresh2', 'P1', findings.binder(root)[0])

    def test_current_continuation_stopped_smoke_is_host_failure_not_intrinsic(self):
        plan = json.loads((ROOT / findings.MANIFEST).read_text())
        bind, bindings = findings.binder(ROOT)
        stopped = findings.qwen35_continuation_stopped_smoke(ROOT, plan, bind)
        self.assertEqual((stopped['status'], stopped['attempted'], stopped['saved'],
                          stopped['valid'], stopped['invalid'], stopped['unknownStartedIds']),
                         ('stopped_unknown', 3, 2, 2, 0, ['DEV-003']))
        self.assertEqual(stopped['failureClass'], 'host_sleep_during_timeout')
        self.assertFalse(stopped['intrinsicModelFailure'])
        self.assertFalse(stopped['developmentAdmitted'])
        for group in stopped['evidence'].values():
            values = group.values() if isinstance(group, dict) else ()
            for item in values:
                if isinstance(item, dict) and 'path' in item:
                    self.assertEqual(bindings[item['path']], item['sha256'])

    def test_qwen35_stopped_p0_is_source_bound_and_unscored(self):
        with mock.patch.object(findings, 'qwen35_successor_phase', return_value=None):
            report = findings.build(ROOT)
        series = next(row for row in report['series']
                      if row['configuration'] == 'qwen3.5-4b-sdk-thinking-on')
        self.assertEqual(series['completedConditions'], 0)
        self.assertNotIn('P0', series['passes']['fresh1'])
        self.assertEqual(series['threePassSummary']['P0']['allFour']['completedPasses'], 0)
        partial = series['partialPasses'][0]
        self.assertEqual((partial['status'], partial['attempted'], partial['saved'],
                          partial['valid'], partial['invalid']),
                         ('stopped_unknown', 52, 51, 44, 7))
        self.assertEqual(partial['unknownStartedIds'], ['DEV-052'])
        self.assertEqual(partial['neverSentIds'], list(findings.IDS[52:]))
        self.assertFalse(partial['cleanRepeatEligible'])
        bound = {item['path']: item['sha256'] for item in series['sourceBindings']}
        for item in partial['evidence'].values():
            self.assertEqual(bound[item['path']], item['sha256'])
        composite = series.get('descriptiveComposites', [])
        if (ROOT / findings.QWEN35_COMPOSITE_REVIEW).exists():
            self.assertEqual(len(composite), 1)
            self.assertEqual(composite[0], series['missingPasses'][0])
            self.assertEqual(composite[0]['score']['denominator'], 60)
            self.assertEqual(composite[0]['score']['outcomes']['unknown_started'], 1)
            self.assertEqual(composite[0]['score']['outcomes']['never_sent'], 0)
            self.assertFalse(composite[0]['cleanRepeatEligible'])
        else:
            self.assertEqual(composite, [])
            self.assertEqual(partial, series['missingPasses'][0])

    def test_power_observation_requires_matching_checks_and_binds_post_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = Path('phase')
            (root / folder).mkdir()
            review_path = folder / 'development.root-review.json'
            completion_path = folder / 'development.completion.json'
            completion_path_at_root = root / completion_path
            completion_path_at_root.write_text('{}')
            completion_hash = findings.sha(completion_path_at_root)
            before = {'boot': 'boot-1', 'sleep_wakes': 4, 'ac_power': True}
            review = {'phase': 'test/fresh1/P0', 'capacity_evidence': before}
            (root / review_path).write_text(json.dumps(review))
            evidence = {'review': {'path': str(review_path)},
                        'completion': {'sha256': completion_hash}}
            bind, bindings = findings.binder(root)
            self.assertEqual(findings.power_observation(root, evidence, bind),
                             {'source': 'ac', 'basis': 'pre_stage_only'})
            self.assertNotIn('postStageVerification', evidence)

            post_path = folder / 'development.post-stage-verification.json'
            post = {'kind': 'root-closed-phase-verification-v1',
                    'phase': review['phase'], 'completion_sha256': completion_hash,
                    'host_unchanged': True,
                    'host': {'boot': 'boot-1', 'sleep_wakes': 4, 'ac_power': True}}
            (root / post_path).write_text(json.dumps(post))
            self.assertEqual(findings.power_observation(root, evidence, bind),
                             {'source': 'ac', 'basis': 'matching_pre_post_checks'})
            self.assertEqual(evidence['postStageVerification']['sha256'], bindings[str(post_path)])

            review['capacity_evidence'] = {'boot': 'boot-1', 'sleep_wakes': 4,
                                           'ac_power': False, 'power_source': 'battery'}
            post['host'] = review['capacity_evidence'].copy()
            (root / review_path).write_text(json.dumps(review))
            (root / post_path).write_text(json.dumps(post))
            self.assertEqual(findings.power_observation(root, evidence, bind),
                             {'source': 'battery', 'basis': 'matching_pre_post_checks'})

            post['host']['ac_power'] = True
            post['host']['power_source'] = 'ac'
            (root / post_path).write_text(json.dumps(post))
            self.assertEqual(findings.power_observation(root, evidence, bind),
                             {'source': None, 'basis': 'unverified_or_conflicting_checks'})
            review['capacity_evidence'] = 'unavailable'
            (root / review_path).write_text(json.dumps(review))
            (root / post_path).unlink()
            self.assertEqual(findings.power_observation(root, evidence, bind),
                             {'source': None, 'basis': 'unavailable'})

    def test_report_rebuilds_from_closed_source_and_tracks_all_configurations(self):
        report = findings.build(ROOT)
        saved = json.loads((ROOT / findings.OUTPUT).read_text())
        if report != saved:
            # The feed is regenerated by the publication owner. During the handoff,
            # only the newly terminal Qwen continuation rows may be ahead of it.
            current_other = [row for row in report['series']
                             if row['configuration'] != 'qwen3.5-4b-sdk-thinking-on']
            saved_other = [row for row in saved['series']
                           if row['configuration'] != 'qwen3.5-4b-sdk-thinking-on']
            self.assertEqual(current_other, saved_other)
            current_qwen = next(row for row in report['series']
                                if row['configuration'] == 'qwen3.5-4b-sdk-thinking-on')
            saved_qwen = next(row for row in saved['series']
                              if row['configuration'] == 'qwen3.5-4b-sdk-thinking-on')
            # Newly closed host-successor phases may be ahead of the publication owner.
            for repeat, conditions in saved_qwen['passes'].items():
                for condition, value in conditions.items():
                    self.assertEqual(current_qwen['passes'][repeat][condition], value)
            terminal = {(row['pass'], row['condition']): row
                        for row in current_qwen['missingPasses']}
            self.assertEqual(terminal['fresh2', 'P2']['status'], 'smoke_blocked')
            self.assertTrue(terminal['fresh2', 'P2']['intrinsicModelFailure'])
            self.assertEqual(terminal['fresh2', 'P1']['status'], 'stopped_unknown')
            self.assertFalse(terminal['fresh2', 'P1']['intrinsicModelFailure'])
        self.assertEqual([row['configuration'] for row in report['series']], list(findings.CONFIGS))
        self.assertEqual([row['displayName'] for row in report['series']],
                         [findings.DISPLAY_NAMES[name] for name in findings.CONFIGS])
        target = report['series'][0]
        self.assertGreaterEqual(target['completedConditions'], 1)
        self.assertEqual(target['passes']['fresh1']['P0']['score']['denominator'], 60)
        self.assertEqual(target['passes']['fresh1']['P0']['score']['valid'], 60)
        self.assertEqual(target['passes']['fresh1']['P0']['score']['allFour'], 0)
        self.assertEqual(target['passes']['fresh1']['P0']['predictedClassCounts']['testimonial_potential'],
                         {'yes': 60})
        self.assertEqual(target['passes']['fresh1']['P0']['classConfusion']['testimonial_potential'],
                         {'insufficient_information': {'yes': 1},
                          'no': {'yes': 50}, 'yes': {'yes': 9}})
        self.assertEqual(len(target['missingPasses']) + target['completedConditions'], 9)
        self.assertEqual(target['passes']['fresh1']['P0']['usage']['actualCostUsd'], None)
        for other in report['series'][1:]:
            self.assertEqual(other['completedConditions'] + len(other['missingPasses']), 9)
        qwen35 = next(row for row in report['series']
                      if row['configuration'] == 'qwen3.5-4b-sdk-thinking-on')
        self.assertGreaterEqual(qwen35['completedConditions'], 2)
        self.assertEqual(set(qwen35['passes']['fresh1']), {'P1', 'P2'})
        p1 = qwen35['passes']['fresh1']['P1']
        self.assertEqual((p1['score']['denominator'], p1['score']['valid'],
                          p1['score']['allFour']), (60, 51, 47))
        self.assertEqual(p1['score']['invalidReasonIds'], {'non_json': [
            'DEV-002', 'DEV-005', 'DEV-010', 'DEV-013', 'DEV-015',
            'DEV-021', 'DEV-022', 'DEV-058', 'DEV-059']})
        self.assertEqual(p1['source'], 'qwen35_remaining_phases_v1')
        self.assertTrue(p1['cleanRepeatCredit'])
        self.assertFalse(p1['predecessorP0CleanRepeatCredit'])

    def test_sdk_successor_development_preserves_rejected_smoke_and_invalid_outputs(self):
        report = findings.build(ROOT)
        for config_id, expected in [('qwen3-0.6b-sdk-thinking-on', (1, 2, 27, 33)),
                                    ('qwen3-0.6b-sdk-thinking-off', (0, 3, 1, 59))]:
            with self.subTest(config_id=config_id):
                series = next(row for row in report['series']
                              if row['configuration'] == config_id)
                item = series['passes']['fresh1']['P0']
                self.assertEqual(item['completionStatus'], 'complete')
                self.assertEqual(item['score']['denominator'], 60)
                self.assertEqual(item['score']['valid'], expected[2])
                self.assertEqual(item['score']['outcomes']['invalid_output'], expected[3])
                self.assertEqual((item['originalSmoke']['status'], item['originalSmoke']['attempted'],
                                  item['originalSmoke']['saved'], item['originalSmoke']['valid'],
                                  item['originalSmoke']['invalid']), ('smoke_blocked', 3, 3, *expected[:2]))
                self.assertGreaterEqual(series['completedConditions'], 1)
                self.assertNotIn(('fresh1', 'P0'), [(row['pass'], row['condition'])
                                                  for row in series['missingPasses']])
                bound = {source['path'] for source in series['sourceBindings']}
                self.assertTrue({item['evidence']['smoke']['inspection']['path'],
                                 item['evidence']['smoke']['raw']['path'],
                                 item['evidence']['smokeSuccessor']['manifest']['path'],
                                 item['evidence']['smokeSuccessor']['inspection']['path'],
                                 item['evidence']['development']['completion']['path']} <= bound)

    def test_successor_accepts_closed_all_valid_sdk_smoke_for_next_phase(self):
        plan = json.loads((ROOT / findings.MANIFEST).read_text())
        original, successor = findings.successor_smoke(
            ROOT, plan, 'qwen3-0.6b-sdk-thinking-on', 'fresh1', 'P2',
            findings.binder(ROOT)[0], require_development_review=False)
        self.assertEqual((original['status'], original['valid'], original['invalid']),
                         ('smoke_complete', 3, 0))
        self.assertIn('smoke-format-successor-inspection.json',
                      successor['inspection']['path'])

    def test_successor_binds_stopped_sdk_smoke_without_legacy_inspection(self):
        plan = json.loads((ROOT / findings.MANIFEST).read_text())
        original, successor = findings.successor_smoke(
            ROOT, plan, 'qwen3-0.6b-sdk-thinking-off', 'fresh1', 'P2',
            findings.binder(ROOT)[0], require_development_review=False)
        self.assertEqual((original['status'], original['valid'], original['invalid']),
                         ('smoke_blocked', 0, 3))
        self.assertNotIn('inspection', original['evidence'])
        self.assertIn('smoke-format-successor-inspection.json',
                      successor['inspection']['path'])

    def test_qwen17_off_successor_preserves_stopped_smoke_and_binds_closed_development(self):
        plan = json.loads((ROOT / findings.MANIFEST).read_text())
        original, admitted = findings.successor_17off_smoke(
            ROOT, plan, findings.binder(ROOT)[0], require_development_review=False)
        self.assertEqual((original['status'], original['attempted'], original['saved'],
                          original['valid'], original['invalid']),
                         ('smoke_blocked', 3, 3, 2, 1))
        self.assertNotIn('score', original)
        self.assertEqual(set(admitted), {'manifest', 'controller', 'inspection'})
        report = findings.build(ROOT)
        series = next(row for row in report['series']
                      if row['configuration'] == 'qwen3-1.7b-sdk-thinking-off')
        phase = series['passes']['fresh3'].get('P2')
        if phase is None:
            stopped = next(row for row in series['missingPasses']
                           if row['pass'] == 'fresh3' and row['condition'] == 'P2')
            self.assertEqual((stopped['status'], stopped['valid'], stopped['invalid']),
                             ('smoke_blocked', 2, 1))
            self.assertNotIn('score', stopped)
            self.assertEqual(set(stopped['evidence']['smokeSuccessor']),
                             {'manifest', 'controller', 'inspection'})
        else:
            self.assertEqual((phase['score']['denominator'], phase['score']['valid'],
                              phase['score']['allFour']), (60, 55, 30))
            self.assertEqual(phase['originalSmoke']['status'], 'smoke_blocked')
            self.assertEqual(set(phase['evidence']['smokeSuccessor']),
                             {'manifest', 'controller', 'inspection', 'review', 'candidate'})
            bound = {source['path'] for source in series['sourceBindings']}
            self.assertTrue({item['path'] for item in phase['evidence']['smokeSuccessor'].values()} <= bound)

    def test_second_sdk_phases_keep_fixed_denominator_and_distinct_smoke_evidence(self):
        report = findings.build(ROOT)
        for config_id, expected in [('qwen3-0.6b-sdk-thinking-on', (56, 4, 3, 'smoke_complete')),
                                    ('qwen3-0.6b-sdk-thinking-off', (1, 59, 0, 'smoke_blocked'))]:
            with self.subTest(config_id=config_id):
                series = next(row for row in report['series']
                              if row['configuration'] == config_id)
                entry = series['passes']['fresh1']['P2']
                self.assertEqual((entry['score']['denominator'], entry['score']['valid'],
                                  entry['score']['outcomes']['invalid_output'],
                                  entry['score']['allFour'], entry['originalSmoke']['status']),
                                 (60, *expected))
                self.assertEqual(entry['evidence']['development']['completion']['path'],
                                 str(findings.BASE / config_id / 'fresh1/P2/development.completion.json'))
                if config_id.endswith('thinking-off'):
                    self.assertNotIn('inspection', entry['evidence']['smoke'])

    def test_closed_phase_rejects_mutated_saved_record(self):
        phase = findings.BASE / findings.TARGET / 'fresh1' / 'P0'
        plan = json.loads((ROOT / findings.MANIFEST).read_text())
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            for name in ('smoke', 'development'):
                for suffix in ('root-review.json', 'claim.json', 'raw.jsonl',
                               'records.jsonl', 'journal.jsonl', 'completion.json'):
                    relative = phase / f'{name}.{suffix}'
                    dest = temp / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / relative, dest)
            review = json.loads((ROOT / phase / 'development.root-review.json').read_text())
            audit = Path(review['route_catalog_file'])
            (temp / audit).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / audit, temp / audit)
            record_file = temp / phase / 'development.records.jsonl'
            record_file.write_bytes(record_file.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'Source hash differs|Closed stage evidence differs'):
                findings.closed_stage(temp, plan, findings.TARGET, 'fresh1', 'P0',
                                      'development', findings.binder(temp)[0])

    def test_pairwise_flips_wait_for_two_closed_passes_and_use_shared_valid_ids(self):
        prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
                      'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        first = {rid: {'status': 'ok', 'prediction': prediction.copy()} for rid in findings.IDS}
        second = {rid: {'status': 'ok', 'prediction': prediction.copy()} for rid in findings.IDS}
        second['DEV-001']['prediction']['sentiment'] = 'negative'
        second['DEV-002'] = {'status': 'invalid_output', 'prediction': None}
        score = {'allFour': 0, 'fields': {field: 0 for field in findings.FIELDS}}
        passes = {'fresh1': {'P0': {'score': score}}, 'fresh2': {}, 'fresh3': {}}
        by_condition, flips, across = findings.summary(passes, {('fresh1', 'P0'): first})
        self.assertEqual(flips, [])
        self.assertEqual(by_condition['P0']['allFour']['completedPasses'], 1)
        passes['fresh2']['P0'] = {'score': score}
        _, flips, across = findings.summary(passes, {('fresh1', 'P0'): first,
                                                     ('fresh2', 'P0'): second})
        self.assertEqual(len(flips), 1)
        self.assertEqual(flips[0]['denominator'], 59)
        self.assertEqual(flips[0]['excludedIds'], ['DEV-002'])
        self.assertEqual(flips[0]['sentiment']['caseIds'], ['DEV-001'])
        self.assertEqual(across, {})

    def test_confusion_excludes_invalid_response_from_each_reference_class(self):
        prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
                      'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        labels = {rid: prediction.copy() for rid in findings.IDS}
        rows = {rid: {'status': 'ok', 'prediction': prediction.copy()} for rid in findings.IDS}
        labels['DEV-001']['testimonial_potential'] = 'yes'
        rows['DEV-001'] = {'status': 'invalid_output', 'prediction': None}
        rows['DEV-002']['prediction']['testimonial_potential'] = 'yes'
        counts, confusion = findings.class_counts(rows, labels)
        self.assertEqual(counts['testimonial_potential'], {'no': 58, 'yes': 1})
        self.assertEqual(confusion['testimonial_potential'], {'no': {'no': 58, 'yes': 1},
                                                             'yes': {}})

    def test_sdk_frozen_adapter_fixture_classification_and_usage(self):
        plan = json.loads((ROOT / findings.MANIFEST).read_text())
        config = plan['configurations']['qwen3-0.6b-sdk-thinking-on']
        request = config['conditions']['P0']['requests'][0]
        historical = json.loads((ROOT / 'results/qwen3-0.6b-sdk-thinking-2026-09-21/'
                                 'development.jsonl').read_text().splitlines()[0])
        prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
                      'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        result = {'modelInfo': historical['model_info'],
                  'loadConfig': historical['load_config'],
                  'predictionConfig': historical['prediction_config'],
                  'stats': historical['stats'], 'content': historical['raw_response'],
                  'nonReasoningContent': json.dumps(prediction)}
        raw = {'result': result, 'elapsed_seconds': 1.5}
        self.assertEqual(findings.classify_sdk(raw, config, request),
                         {'status': 'ok', 'prediction': prediction})
        tokens = findings.usage([raw], 'lmstudio_sdk')['tokens']
        self.assertEqual(tokens['input_tokens'], result['stats']['promptTokensCount'])
        self.assertEqual(tokens['output_tokens'], result['stats']['predictedTokensCount'])
        self.assertEqual(tokens['total_tokens'], result['stats']['totalTokensCount'])
        self.assertIsNone(tokens['reasoning_output_tokens'])

        altered = copy.deepcopy(raw)
        altered['result']['stats']['promptTokensCount'] += 1
        self.assertEqual(findings.classify_sdk(altered, config, request),
                         {'status': 'control_failure', 'reason': 'prompt_token_count'})
        altered = copy.deepcopy(raw)
        altered['result']['predictionConfig']['fields'][0]['value'] = 'changed'
        self.assertEqual(findings.classify_sdk(altered, config, request),
                         {'status': 'control_failure', 'reason': 'prediction_config'})
        altered = copy.deepcopy(raw)
        altered['result']['nonReasoningContent'] = '```json\n{}\n```'
        self.assertEqual(findings.classify_sdk(altered, config, request),
                         {'status': 'invalid_output', 'reason': 'non_json'})
        altered = copy.deepcopy(raw)
        altered['result']['stats']['stopReason'] = 'maxPredictedTokensReached'
        self.assertEqual(findings.classify_sdk(altered, config, request),
                         {'status': 'invalid_output', 'reason': 'stop_reason'})


if __name__ == '__main__':
    unittest.main()

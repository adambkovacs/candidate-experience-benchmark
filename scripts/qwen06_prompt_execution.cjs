#!/usr/bin/env node
// Frozen Qwen3-0.6B Q4_K_M P1/P2 continuation. This file never reads labels.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const runDir = path.join(root, 'results/qwen06-prompt-exact-v1');
const manifestPath = path.join(runDir, 'manifest.json');
const preflightPath = path.join(runDir, 'preflight.json');
const cliPath = '/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms';
const modelIdentifier = 'recruitment-qwen3-0.6b-q4km';
const modelPath = 'lmstudio-community/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q4_K_M.gguf';
const conditions = ['thinking-on-P2', 'thinking-on-P1', 'thinking-off-P1', 'thinking-off-P2'];
const decisionKeys = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const shaFile = filename => sha(fs.readFileSync(filename));
const stable = value => JSON.stringify(value);
const readJson = filename => JSON.parse(fs.readFileSync(filename, 'utf8'));
const checkedPath = relative => {
  assert.equal(typeof relative, 'string');
  assert(!path.isAbsolute(relative) && !relative.split('/').includes('..'), 'Unsafe source path');
  const full = path.resolve(root, relative);
  assert(full.startsWith(`${root}${path.sep}`), 'Source outside repository');
  return full;
};
function argsFrom(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    assert(key?.startsWith('--') && i + 1 < argv.length, 'Expected --key value pairs');
    assert(!Object.hasOwn(args, key.slice(2)), 'Duplicate argument');
    args[key.slice(2)] = argv[i + 1];
  }
  return args;
}
function validateFeedback(record, expectedFeedback) {
  assert.deepEqual(record.messages.map(m=>m.role),['system','user']);
  const user = JSON.parse(record.messages[1].content);
  assert.deepEqual(Object.keys(user),['feedback']);
  assert.equal(user.feedback,expectedFeedback,`Canonical feedback mismatch: ${record.id}`);
}
function validateComposition(record, base, compose) {
  const composed = compose(base.messages[0].content,record.variant,
    {role:'system',parent_baseline_id:record.configuration});
  assert.equal(record.messages[0].content,composed.instruction,`Composed instruction mismatch: ${record.id}`);
  assert.deepEqual(record.prompt_audit,composed.audit,`Composition audit mismatch: ${record.id}`);
}
function sourceCheck(manifest) {
  assert.equal(manifest.version, 'qwen06-prompt-exact-v1');
  assert.deepEqual(manifest.conditions, conditions);
  assert.deepEqual(manifest.record_ids, Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`));
  assert.deepEqual(manifest.smoke_ids, manifest.record_ids.slice(0,3));
  assert.equal(manifest.model.identifier, modelIdentifier);
  assert.equal(manifest.model.path, modelPath);
  assert.equal(manifest.model.context, 8192);
  assert.equal(manifest.model.output_reserve, 4096);
  assert.equal(manifest.model.parallel, 1);
  assert.equal(manifest.model.artifact_sha256.length, 64);
  assert.equal(manifest.local_gpu_lock_file,'results/prompt-comparison-v1-2026-09-24/local-gpu.lock');
  assert.equal(shaFile(manifest.runtime.sdk_path), manifest.runtime.sdk_sha256, 'SDK binary drift');
  assert.equal(shaFile(cliPath), manifest.runtime.cli_sha256, 'CLI binary drift');
  assert.equal(shaFile(manifest.runtime.app_info_plist), manifest.runtime.app_info_plist_sha256, 'LM Studio app drift');
  for (const [relative, expected] of Object.entries(manifest.source_sha256)) {
    assert.match(expected, /^[0-9a-f]{64}$/);
    assert.equal(shaFile(checkedPath(relative)), expected, `Source drift: ${relative}`);
  }
  assert.equal(shaFile(__filename), manifest.controller_sha256, 'Controller drift');
  const originalSchedule = readJson(checkedPath(manifest.original_schedule_file));
  const originalPairs = originalSchedule.order.filter(item =>
    ['qwen3-0.6b-sdk-thinking-on','qwen3-0.6b-sdk-thinking-off'].includes(item.id));
  assert.deepEqual(originalPairs,[
    {id:'qwen3-0.6b-sdk-thinking-on',conditions:['P2','P1']},
    {id:'qwen3-0.6b-sdk-thinking-off',conditions:['P1','P2']}]);
  const linked = readJson(checkedPath(manifest.linked_schedule_file));
  assert.equal(linked.original_schedule_sha256,shaFile(checkedPath(manifest.original_schedule_file)));
  assert.deepEqual(linked.conditions,conditions);
  assert.deepEqual(linked.prior_condition,[null,...conditions.slice(0,-1)]);
  const render = readJson(checkedPath(manifest.render_file));
  const counts = readJson(checkedPath(manifest.counts_file));
  const canonical = fs.readFileSync(checkedPath(manifest.canonical_inputs_file),'utf8').trim().split('\n').map(JSON.parse);
  assert.equal(canonical.length,60);
  const feedbackById = new Map(canonical.map(row=>[row.id,row.feedback]));
  assert.equal(feedbackById.size,60);
  const {compose_instruction} = require(path.join(root,'scripts/frozen_prompt_variants.cjs'));
  assert.equal(render.length, 360); assert.equal(counts.length, 360);
  const seen = new Set(), groups = {}, p0 = {};
  for (let i = 0; i < render.length; i++) {
    const record = render[i], count = counts[i];
    const condition = `${record.configuration}/${record.variant}`;
    assert(['qwen3-0.6b-sdk-thinking-on', 'qwen3-0.6b-sdk-thinking-off'].includes(record.configuration));
    assert(['P0', 'P1', 'P2'].includes(record.variant));
    assert.match(record.id, /^DEV-0[0-5][0-9]$|^DEV-060$/);
    assert(Number(record.id.slice(4)) >= 1);
    const key = `${condition}/${record.id}`;
    assert(!seen.has(key), `Duplicate ${key}`); seen.add(key);
    groups[condition] = (groups[condition] || 0) + 1;
    assert.equal(sha(Buffer.from(record.rendered, 'utf8')), record.rendered_sha256);
    assert.equal(stable([record.id, record.configuration, record.variant, record.rendered_sha256]),
      stable([count.id, count.configuration, count.variant, count.rendered_sha256]));
    assert.equal(count.fits_context, true);
    assert.equal(count.token_plus_reserve, count.prompt_tokens + 4096);
    assert(count.token_plus_reserve <= 8192);
    assert.equal(record.context, 8192); assert.equal(record.output_reserve, 4096);
    assert.equal(shaFile(checkedPath(record.source_file)), record.source_sha256);
    validateFeedback(record,feedbackById.get(record.id));
    assert.deepEqual(record.config, manifest.prediction_configs[record.configuration]);
    if (record.variant === 'P0') {
      assert.equal(count.p0_count_match, true);
      assert.equal(count.prompt_tokens, record.saved_prompt_tokens);
      p0[`${record.configuration}/${record.id}`] = record;
    } else {
      const audit = record.prompt_audit;
      assert.equal(audit.variant, record.variant);
      assert.equal(audit.parent_baseline_id, record.configuration);
      assert.equal(audit.reference_labels_read, false);
      assert.equal(audit.inference_performed, false);
      assert.equal(shaFile(checkedPath(audit.manifest_path)), audit.manifest_sha256);
      assert.equal(shaFile(checkedPath(audit.addition_path)), audit.addition_sha256);
    }
  }
  assert.equal(Object.keys(groups).length, 6);
  assert(Object.values(groups).every(n => n === 60));
  for (const setting of Object.keys(manifest.prediction_configs)) {
    for (const variant of ['P0','P1','P2']) {
      assert.deepEqual(render.filter(r=>r.configuration===setting && r.variant===variant).map(r=>r.id),manifest.record_ids);
    }
  }
  for (const record of render.filter(r => r.variant !== 'P0')) {
    const base = p0[`${record.configuration}/${record.id}`];
    assert(base, 'Missing P0 parent');
    assert.equal(record.source_file, base.source_file);
    assert.equal(record.source_sha256, base.source_sha256);
    assert.equal(record.prompt_audit.parent_baseline_id, base.configuration);
    validateComposition(record,base,compose_instruction);
  }
  for (const setting of Object.keys(manifest.baseline_files)) {
    const baseline = fs.readFileSync(checkedPath(manifest.baseline_files[setting]), 'utf8').trim().split('\n').map(JSON.parse);
    assert.equal(baseline.length, 60);
    assert.equal(new Set(baseline.map(row => row.id)).size, 60);
    for (const row of baseline) {
      const parent = p0[`${setting}/${row.id}`];
      assert(parent, 'Missing saved P0 result');
      assert.deepEqual(row.request, {messages:parent.messages,config:parent.config});
      assert.equal(row.stats.promptTokensCount, parent.saved_prompt_tokens);
      assert.deepEqual(row.prediction_config, manifest.observed_prediction_configs[setting]);
      assert.deepEqual(row.load_config, manifest.observed_load_config);
    }
  }
  return { render, counts, groups };
}
function preflight(manifest) {
  const { groups } = sourceCheck(manifest);
  const host = readJson(checkedPath(manifest.hosted_route_evidence));
  assert.equal(host.serving_endpoints, 0);
  assert.equal(host.returned_model_id, 'qwen/qwen3-0.6b-04-28:free');
  const control = readJson(checkedPath(manifest.hosted_route_control_evidence));
  assert.equal(control.returned_model_id, 'google/gemini-2.5-flash');
  assert(control.serving_endpoints > 0, 'Public endpoint API control was empty');
  const countEvidence = readJson(checkedPath(manifest.count_evidence));
  assert.equal(countEvidence.records, 360);
  assert.equal(countEvidence.p0_saved_count_matches, 120);
  assert.equal(countEvidence.overflow_count, 0);
  return {version: manifest.version, manifest_sha256: shaFile(manifestPath), controller_sha256: shaFile(__filename),
    source_sha256: manifest.source_sha256, groups, p0_parity: 120, context_fit: 360,
    hosted_route_endpoints_at_prior_check: 0, inference_performed: false,
    limitation: 'Count parity is not token-sequence parity; runtime prompt-template application needs smoke inspection.'};
}
function buildRunInputs(manifest) {
  return {checked:preflight(manifest), source:sourceCheck(manifest)};
}
function validateSmokeRows(smokeRows, smokeJournal, condition) {
  assert.deepEqual(smokeRows.map(row=>row.id),['DEV-001','DEV-002','DEV-003']);
  assert(smokeRows.every(row=>row.condition===condition && row.phase==='smoke' &&
    ['ok','invalid_output'].includes(row.decision?.status)), 'Smoke is incomplete or has a control failure');
  assert.deepEqual(smokeJournal.map(event=>[event.event,event.id]),[
    ['started','DEV-001'],['finished','DEV-001'],['started','DEV-002'],['finished','DEV-002'],
    ['started','DEV-003'],['finished','DEV-003']]);
  for (let i=0;i<3;i++) {
    const row=smokeRows[i], start=smokeJournal[i*2], finish=smokeJournal[i*2+1];
    assert.match(row.attempt_id,/^[0-9a-f-]{36}$/);
    assert.equal(start.attempt_id,row.attempt_id);
    assert.equal(finish.attempt_id,row.attempt_id);
    assert.equal(start.request_sha256,row.request_sha256);
    assert.equal(row.request_sha256,sha(Buffer.from(stable(row.request))));
    assert.equal(finish.status,row.decision.status);
    assert.equal(finish.output_sha256,sha(Buffer.from(stable(row))));
  }
}
function validatePriorTerminal(terminal, prior, manifestHash) {
  assert.equal(terminal.condition,prior);
  assert.equal(terminal.phase,'development');
  assert.equal(terminal.status,'completed');
  assert.equal(terminal.finished_attempts,60);
  assert.equal(terminal.saved_rows,60);
  assert.equal(terminal.ambiguous_timeout,false);
  assert.equal(terminal.manifest_sha256,manifestHash);
}
function checkReview(manifest, expectedPreflight, opts) {
  assert.equal(opts['approved-manifest-sha256'], shaFile(manifestPath));
  assert.equal(opts['approved-preflight-sha256'], shaFile(preflightPath));
  assert.deepEqual(readJson(preflightPath), expectedPreflight, 'Preflight drift');
  assert(opts['review-receipt'] && opts['review-receipt-sha256']);
  const receiptPath = checkedPath(opts['review-receipt']);
  assert.equal(shaFile(receiptPath), opts['review-receipt-sha256']);
  const receipt = readJson(receiptPath);
  assert.equal(receipt.manifest_sha256, shaFile(manifestPath));
  assert.equal(receipt.preflight_sha256, shaFile(preflightPath));
  assert.equal(receipt.controller_sha256, shaFile(__filename));
  assert.equal(receipt.approved_for_execution, true);
  assert(receipt.approved_conditions?.includes(opts.condition));
  assert(receipt.approved_phases?.includes(opts.phase));
  if (opts.phase === 'development') {
    assert(opts['inspection-receipt'] && opts['inspection-receipt-sha256']);
    const inspectionPath = checkedPath(opts['inspection-receipt']);
    assert.equal(shaFile(inspectionPath), opts['inspection-receipt-sha256']);
    const inspection = readJson(inspectionPath);
    assert.equal(inspection.condition, opts.condition);
    assert.equal(inspection.accepted_for_development, true);
    assert.equal(inspection.smoke_output_sha256, shaFile(path.join(runDir, opts.condition, 'smoke.jsonl')));
    assert.equal(inspection.smoke_journal_sha256, shaFile(path.join(runDir, opts.condition, 'smoke.attempts.jsonl')));
    assert.equal(inspection.smoke_ids_inspected, 3);
    const smokeRows = fs.readFileSync(path.join(runDir, opts.condition, 'smoke.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
    const smokeJournal = fs.readFileSync(path.join(runDir, opts.condition, 'smoke.attempts.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
    validateSmokeRows(smokeRows, smokeJournal, opts.condition);
  }
}
function parseResult(result, expected) {
  const info = result?.modelInfo;
  if (!info || info.identifier !== modelIdentifier || info.path !== modelPath || info.contextLength !== 8192 ||
      info.quantization?.name !== 'Q4_K_M' || info.sizeBytes !== 484219808) return {status:'control_failure', reason:'model_identity'};
  const kv = value => Object.fromEntries((value?.fields || []).map(field => [field.key, field.value]).sort((a,b) => a[0].localeCompare(b[0])));
  if (stable(kv(result.predictionConfig)) !== stable(kv(expected.observed_prediction_config)))
    return {status:'control_failure',reason:'prediction_config'};
  if (stable(kv(result.loadConfig)) !== stable(kv(expected.observed_load_config)))
    return {status:'control_failure',reason:'load_config'};
  if (!Number.isInteger(result.stats?.promptTokensCount) || result.stats.promptTokensCount !== expected.prompt_tokens)
    return {status:'control_failure',reason:'prompt_token_count'};
  if (typeof result.content !== 'string' || typeof result.nonReasoningContent !== 'string')
    return {status:'service_failure',reason:'malformed_sdk_result'};
  let parsed;
  try { parsed = JSON.parse(result.nonReasoningContent); } catch { return {status:'invalid_output',reason:'non_json'}; }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed) ||
      stable(Object.keys(parsed).sort()) !== stable([...decisionKeys].sort())) return {status:'invalid_output',reason:'schema'};
  for (const key of decisionKeys) {
    const allowed = key === 'sentiment' ? ['positive','negative','mixed','neutral','insufficient_information'] : ['yes','no','insufficient_information'];
    if (!allowed.includes(parsed[key])) return {status:'invalid_output',reason:'schema'};
  }
  if (!['eosFound','stopStringFound'].includes(result.stats.stopReason)) return {status:'invalid_output',reason:'stop_reason'};
  return {status:'ok',prediction:parsed};
}
function appendDurable(fd, object) {
  fs.writeSync(fd, JSON.stringify(object) + '\n'); fs.fsyncSync(fd);
}
async function hashArtifact(file) {
  const digest = crypto.createHash('sha256');
  for await (const part of fs.createReadStream(file, {highWaterMark:8*1024*1024})) digest.update(part);
  return digest.digest('hex');
}
async function run(manifest, checked, source, opts) {
  assert(conditions.includes(opts.condition));
  assert(['smoke','development'].includes(opts.phase));
  checkReview(manifest, checked, opts);
  const conditionDir = path.join(runDir, opts.condition);
  const outputPath = path.join(conditionDir, `${opts.phase}.jsonl`);
  const journalPath = path.join(conditionDir, `${opts.phase}.attempts.jsonl`);
  const terminalPath = path.join(conditionDir, `${opts.phase}.terminal.json`);
  const lockPath = checkedPath(manifest.local_gpu_lock_file);
  assert(!fs.existsSync(outputPath) && !fs.existsSync(journalPath) && !fs.existsSync(terminalPath),
    'Existing output, journal, or terminal; no automatic replay');
  if (opts.phase === 'smoke' && conditions.indexOf(opts.condition)>0) {
    const prior = conditions[conditions.indexOf(opts.condition)-1];
    const priorTerminal = readJson(path.join(runDir,prior,'development.terminal.json'));
    validatePriorTerminal(priorTerminal,prior,shaFile(manifestPath));
  }
  const [setting, variant] = opts.condition.startsWith('thinking-on') ? ['qwen3-0.6b-sdk-thinking-on',opts.condition.slice(-2)] :
    ['qwen3-0.6b-sdk-thinking-off',opts.condition.slice(-2)];
  const selected = source.render.filter(record => record.configuration === setting && record.variant === variant);
  const countMap = new Map(source.counts.map(c => [`${c.configuration}/${c.variant}/${c.id}`,c.prompt_tokens]));
  const records = opts.phase === 'smoke' ? selected.slice(0, 3) : selected;
  assert.equal(records.length, opts.phase === 'smoke' ? 3 : 60);
  fs.mkdirSync(conditionDir, {recursive:true});
  const lock = fs.openSync(lockPath,'wx');
  let output, journal;
  let holdLock = false;
  let completed = false, terminalError = null, runtimeAttestation = null;
  const manifestHash = shaFile(manifestPath), preflightHash = shaFile(preflightPath);
  try {
    fs.writeSync(lock, JSON.stringify({pid:process.pid,condition:opts.condition,phase:opts.phase,started_utc:new Date().toISOString()}));
    fs.fsyncSync(lock);
    const version = execFileSync(cliPath,['--version'],{encoding:'utf8',timeout:15000}).trim();
    assert.equal(version, `CLI commit: ${manifest.runtime.cli_commit}`, `LM Studio CLI commit drift: ${version}`);
    const runtimes = execFileSync(cliPath,['runtime','ls'],{encoding:'utf8',timeout:15000});
    const selectedRuntime = runtimes.split('\n').find(value => value.startsWith(manifest.runtime.selected_engine));
    assert(selectedRuntime && selectedRuntime.includes('✓') && selectedRuntime.includes('GGUF'), 'Selected GGUF runtime drift');
    const ps = execFileSync(cliPath,['ps'],{encoding:'utf8',timeout:15000});
    const line = ps.split('\n').find(value => value.trim().startsWith(modelIdentifier));
    assert(line && line.includes('8192') && line.includes('1'), 'Loaded model missing or wrong CLI context/parallel');
    const hardware = {model_identifier:execFileSync('/usr/sbin/sysctl',['-n','hw.model'],{encoding:'utf8'}).trim(),
      chip:execFileSync('/usr/sbin/sysctl',['-n','machdep.cpu.brand_string'],{encoding:'utf8'}).trim(),
      architecture:require('node:os').arch()};
    assert.equal(hardware.model_identifier,manifest.hardware.model_identifier);
    assert.equal(hardware.chip,manifest.hardware.chip);
    assert.equal(hardware.architecture,manifest.hardware.architecture);
    runtimeAttestation={cli_commit:manifest.runtime.cli_commit,selected_engine:manifest.runtime.selected_engine,
      lm_studio_version:manifest.runtime.lm_studio_version,loaded_model_line:line.trim(),hardware};
    const artifact = path.join(manifest.runtime.models_dir, modelPath);
    assert.equal(await hashArtifact(artifact), manifest.model.artifact_sha256, 'GGUF artifact drift');
    const { LMStudioClient } = require(manifest.runtime.sdk_path);
    const client = new LMStudioClient();
    const model = client.llm.createDynamicHandle(modelIdentifier);
    const info = await model.getModelInfo();
    assert(info && info.identifier === modelIdentifier && info.path === modelPath && info.contextLength === 8192 &&
      info.quantization?.name === 'Q4_K_M' && info.sizeBytes === 484219808, 'Loaded SDK model drift');
    output = fs.openSync(outputPath,'wx'); journal = fs.openSync(journalPath,'wx');
    for (const record of records) {
      const before = await model.getModelInfo();
      assert(before && before.instanceReference === info.instanceReference, 'Loaded instance changed');
      const attempt = crypto.randomUUID();
      const request = {messages:record.messages,config:record.config};
      appendDurable(journal,{event:'started',attempt_id:attempt,id:record.id,request_sha256:sha(Buffer.from(stable(request))),
        condition:opts.condition,phase:opts.phase,manifest_sha256:manifestHash,preflight_sha256:preflightHash,
        timeout_ms:600000,at:new Date().toISOString()});
      const started = performance.now();
      let result, decision;
      try {
        const {predictWithTimeout} = require(path.join(root,'scripts/lmstudio_reasoning_benchmark.cjs'));
        result = await predictWithTimeout(model,record.messages,record.config,600000);
        const after = await model.getModelInfo();
        decision = after?.instanceReference !== info.instanceReference ? {status:'control_failure',reason:'loaded_instance_changed'} :
          parseResult(result,{prompt_tokens:countMap.get(`${setting}/${variant}/${record.id}`),
            observed_prediction_config:manifest.observed_prediction_configs[setting],
            observed_load_config:manifest.observed_load_config});
      } catch(error) {
        if (error.code === 'PREDICTION_TIMEOUT' && error.cancellationAcknowledged !== true) holdLock = true;
        decision={status:error.code==='PREDICTION_TIMEOUT'?'timeout':'service_failure',reason:String(error.message),
          cancellation_acknowledged:error.cancellationAcknowledged ?? null};
      }
      const row = {id:record.id,condition:opts.condition,phase:opts.phase,attempt_id:attempt,
        manifest_sha256:manifestHash,preflight_sha256:preflightHash,controller_sha256:shaFile(__filename),
        timeout_ms:600000,runtime_attestation:runtimeAttestation,
        request,request_sha256:sha(Buffer.from(stable(request))),rendered_sha256:record.rendered_sha256,
        reference_labels_read:false,model_identifier:modelIdentifier,model_path:modelPath,
        raw_response:result?.content ?? null,reasoning_content:result?.reasoningContent ?? null,
        non_reasoning_content:result?.nonReasoningContent ?? null,stats:result?.stats ?? null,
        model_info:result?.modelInfo ?? null,load_config:result?.loadConfig ?? null,
        prediction_config:result?.predictionConfig ?? null,decision,
        elapsed_seconds:(performance.now()-started)/1000,finished_utc:new Date().toISOString()};
      appendDurable(output,row);
      appendDurable(journal,{event:'finished',attempt_id:attempt,id:record.id,status:decision.status,
        output_sha256:sha(Buffer.from(stable(row))),at:new Date().toISOString()});
      console.log(`${opts.condition} ${opts.phase} ${record.id} ${decision.status}`);
      if (['control_failure','service_failure','timeout'].includes(decision.status)) throw Error(`Stopped after ${record.id}: ${decision.reason}`);
    }
    completed = true;
  } catch (error) {
    terminalError = String(error.message);
    throw error;
  } finally {
    if (journal !== undefined) fs.closeSync(journal);
    if (output !== undefined) fs.closeSync(output);
    const rows = fs.existsSync(outputPath) ? fs.readFileSync(outputPath,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [];
    const events = fs.existsSync(journalPath) ? fs.readFileSync(journalPath,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [];
    const terminal = {condition:opts.condition,phase:opts.phase,status:completed?'completed':'stopped',
      manifest_sha256:manifestHash,preflight_sha256:preflightHash,controller_sha256:shaFile(__filename),
      requested_records:records.length,claimed_attempts:events.filter(event=>event.event==='started').length,
      finished_attempts:events.filter(event=>event.event==='finished').length,saved_rows:rows.length,
      ok_rows:rows.filter(row=>row.decision.status==='ok').length,
      invalid_output_rows:rows.filter(row=>row.decision.status==='invalid_output').length,
      ambiguous_timeout:holdLock,timeout_ms:600000,runtime_attestation:runtimeAttestation,
      output_sha256:fs.existsSync(outputPath)?shaFile(outputPath):null,
      journal_sha256:fs.existsSync(journalPath)?shaFile(journalPath):null,
      stopped_reason:terminalError,finished_utc:new Date().toISOString()};
    fs.writeFileSync(terminalPath,JSON.stringify(terminal,null,2)+'\n',{flag:'wx'});
    fs.closeSync(lock);
    if (!holdLock) fs.unlinkSync(lockPath);
  }
}
async function main() {
  const opts = argsFrom(process.argv.slice(2));
  const manifest = readJson(manifestPath);
  if (opts.mode === 'preflight') {
    const checked = preflight(manifest);
    fs.writeFileSync(preflightPath,JSON.stringify(checked,null,2)+'\n',{flag:'wx'});
    console.log(`preflight ${shaFile(preflightPath)}`);
  } else if (opts.mode === 'run') {
    const {checked,source} = buildRunInputs(manifest);
    await run(manifest,checked,source,opts);
  } else throw Error('Use --mode preflight or --mode run');
}
if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode=1; });
module.exports = {argsFrom,sourceCheck,preflight,checkReview,parseResult,validateSmokeRows,
  validatePriorTerminal,validateFeedback,validateComposition,buildRunInputs};

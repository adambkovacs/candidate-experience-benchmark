#!/usr/bin/env node
// Exact local repeats. Import, prepare and verify never contact LM Studio.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const os = require('node:os');
const {execFileSync} = require('node:child_process');
const parent = require('./local_prompt_execution_v1.cjs');
const predictor = require('./lmstudio_reasoning_benchmark.cjs');

const ROOT = path.resolve(__dirname, '..');
const PLAN = path.join(ROOT, 'results/repeatability-v1/small-local-v1/manifest.json');
const LOCK = path.join(ROOT, 'results/repeatability-v1/laya-expanded-cpu-v1/execution.lock');
const NAMES = [
  'gemma4-e2b-sdk-thinking-off', 'gemma4-e2b-sdk-thinking-on',
  'gemma4-e4b-sdk-thinking-off', 'gemma4-e4b-sdk-thinking-on',
  'qwen3.5-4b-sdk-thinking-off',
];
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const hashFile = filename => hash(fs.readFileSync(filename));
const read = filename => JSON.parse(fs.readFileSync(filename, 'utf8'));
const rows = filename => fs.readFileSync(filename, 'utf8').split('\n').filter(Boolean).map(JSON.parse);
const stable = value => JSON.stringify(value);
const rel = filename => {
  assert.equal(typeof filename, 'string');
  assert(!path.isAbsolute(filename) && !filename.split('/').includes('..'), 'Unsafe source path');
  const full = path.resolve(ROOT, filename);
  assert(full.startsWith(ROOT + path.sep), 'Source outside repository');
  return full;
};
const bound = filename => ({file: filename, sha256: hashFile(rel(filename))});
const source = (report, condition) => condition === 'P0'
  ? report.conditions.P0.sources.output
  : report.conditions[condition].sources.development.output;
const namesFor = () => ['fresh1','fresh2','fresh3'];
const originalOrder = id => id.endsWith('thinking-off') && id.startsWith('gemma')
  ? ['P0','P2','P1'] : ['P0','P1','P2'];
const rotations = id => {
  const order = originalOrder(id);
  const passes = namesFor();
  return passes.map((name, index) => ({name, conditions: order.map((_, n) => order[(n + index) % 3])}));
};

function makePlan() {
  const parentManifest = read(rel('results/local-prompt-exact-v1/manifest.json'));
  const config = {};
  const inputs = rows(rel('data/pilot/inputs.jsonl'));
  assert.equal(inputs.length, 60);
  assert.deepEqual(inputs.map(x => x.id), Array.from({length:60}, (_,i) => `DEV-${String(i+1).padStart(3,'0')}`));
  for (const id of NAMES) {
    const reportFile = `results/local-prompt-pairs-v1/${id}.json`;
    const report = read(rel(reportFile));
    assert.equal(report.configuration, id);
    assert.equal(report.eligible_paired_comparison, true);
    assert.equal(report.controls_verified, true);
    assert.deepEqual(Object.keys(report.conditions), ['P0','P1','P2']);
    const verifyBindings = value => {
      if (Array.isArray(value)) { value.forEach(verifyBindings); return; }
      if (!value || typeof value !== 'object') return;
      if (typeof value.file === 'string' && typeof value.sha256 === 'string')
        assert.equal(hashFile(rel(value.file)), value.sha256, `Historical binding differs: ${value.file}`);
      Object.values(value).forEach(verifyBindings);
    };
    verifyBindings(report.sources);
    Object.values(report.conditions).forEach(item => verifyBindings(item.sources));
    const conditions = {};
    for (const condition of ['P0','P1','P2']) {
      const saved = source(report, condition);
      assert.equal(hashFile(rel(saved.file)), saved.sha256, 'Historical source differs');
      const historical = rows(rel(saved.file));
      assert.deepEqual(historical.map(x => x.id), inputs.map(x => x.id));
      const requests = historical.map((row, i) => {
        const request = row.request;
        assert.deepEqual(request.messages.map(x => x.role), ['system','user']);
        assert.equal(JSON.parse(request.messages[1].content).feedback, inputs[i].feedback);
        assert.equal(row.reference_labels_read, false);
        return {id: row.id, sha256: hash(stable(request)), prompt_tokens: row.expected_prompt_tokens ?? row.stats?.promptTokensCount};
      });
      assert(requests.every(x => Number.isSafeInteger(x.prompt_tokens) && x.prompt_tokens > 0));
      conditions[condition] = {source: saved, requests};
    }
    const p0 = rows(rel(conditions.P0.source.file))[0];
    const artifact = id.includes('e2b') ? 'gemma4-e2b' : id.includes('e4b') ? 'gemma4-e4b' : 'qwen3.5-4b';
    const historicalManifest = id.includes('e2b')
      ? `results/gemma4-e2b-2026-09-21/${id.endsWith('thinking-on')?'thinking':'nonthinking'}-manifest.json`
      : id.includes('e4b')
        ? `results/gemma4-e4b-2026-09-23/${id.endsWith('thinking-on')?'on':'off'}-manifest.json`
        : 'results/qwen3.5-4b-2026-09-21/nonthinking-manifest.json';
    const history = read(rel(historicalManifest));
    assert.equal(p0.artifact_sha256, history.artifact.sha256);
    assert.equal(history.artifact.quantization, 'Q4_K_M');
    assert.equal(history.valid_outputs, 60);
    if (id.includes('e4b')) {
      assert.equal(history.prompt_cache.enabled,null);
    } else {
      assert.equal(history.prompt_cache.enabled,true);
      assert.equal(history.prompt_cache.size_limit_mib,8192);
    }
    config[id] = {
      disposition: 'fresh_matched_three_historical_pass_observational',
      historical_order: originalOrder(id), schedule: rotations(id),
      artifact, artifact_sha256: history.artifact.sha256, artifact_bytes: history.artifact.bytes,
      artifact_path: p0.artifact_path, model_identifier: p0.requested_model,
      timeout_ms: parentManifest.configs[id].timeout_ms,
      historical_manifest: bound(historicalManifest), paired_report: bound(reportFile),
      historical_cache: history.prompt_cache,
      controls: {load_config: p0.load_config, prediction_config: p0.prediction_config,
                 thinking: p0.thinking, template_sha256: p0.template_sha256},
      conditions,
    };
  }
  const sources = Object.fromEntries([
    'data/pilot/inputs.jsonl', 'docs/LABELING_GUIDE.md', 'schemas/judgments.schema.json',
    'scripts/frozen_prompt_variants.cjs', 'scripts/lmstudio_reasoning_benchmark.cjs',
    'scripts/local_prompt_execution_v1.cjs', 'scripts/local_prompt_tail_v3.cjs',
    'results/local-prompt-exact-v1/manifest.json', 'results/local-prompt-tail-v3/manifest.json',
  ].map(name => [name, hashFile(rel(name))]));
  return {schema:'small-local-repeat-admission-v1', status:'offline_prepared_unapproved',
    reference_labels_used_for_requests:false, historical_predictions_used_for_requests:false,
    controller_sha256: hashFile(__filename), parent_runtime: parentManifest.runtime,
    source_sha256: sources, configurations: config,
    policy: {denominator:60, smoke_ids:['DEV-001','DEV-002','DEV-003'],
             cache_policy:{enabled:true,size_limit_mib:8192},
             loaded_engine_identity:'unavailable_from_installed_sdk_and_cli; selected_backend_observational_only',
             seed_policy:'uncontrolled_sampling_no_seed',
             invalid_output:'retain_and_continue', service_or_control_failure:'stop_without_retry',
             lock_path:path.relative(ROOT, LOCK)},
  };
}

function verifyPlan() {
  const actual = read(PLAN), expected = makePlan();
  assert.equal(stable(actual), stable(expected), 'Frozen local repeat plan differs from sources, controller or protocol');
  return {plan:actual, sha256:hashFile(PLAN)};
}

function phaseInfo(plan, id, pass, condition) {
  const config = plan.configurations[id];
  assert(config, 'Configuration not in frozen local repeat plan');
  const phaseIndex = config.schedule.findIndex(x => x.name === pass && x.conditions.includes(condition));
  assert(phaseIndex >= 0, 'Phase not in frozen local repeat plan');
  const preceding = [];
  for (const item of config.schedule) {
    for (const c of item.conditions) {
      if (item.name === pass && c === condition) return {config, preceding};
      preceding.push(`${item.name}/${c}`);
    }
  }
  throw Error('Unreachable phase');
}

function checkReceipt(receipt, planSha, phase, stage, config, smokeHash, now=Date.now()) {
  assert.equal(receipt.kind, 'root-reviewed-small-local-stage-v1');
  assert.equal(receipt.approved, true);
  assert.equal(receipt.plan_sha256, planSha);
  assert.equal(receipt.controller_sha256, hashFile(__filename));
  assert.equal(receipt.phase, phase);
  assert.equal(receipt.stage, stage);
  assert.equal(receipt.model_identifier, config.model_identifier);
  assert.equal(receipt.artifact_sha256, config.artifact_sha256);
  assert.deepEqual(receipt.cache_policy, {enabled:true,size_limit_mib:8192});
  assert.equal(receipt.reference_labels_read, false);
  assert.equal(receipt.exact_openrouter_route_absent, true);
  const catalog = read(rel(receipt.route_catalog_file));
  assert.equal(typeof receipt.route_catalog_sha256, 'string');
  assert.match(receipt.route_catalog_sha256, /^[0-9a-f]{64}$/);
  assert.equal(hashFile(rel(receipt.route_catalog_file)), receipt.route_catalog_sha256);
  assert.equal(catalog.source, 'https://openrouter.ai/api/v1/models');
  assert.deepEqual(catalog.matches, []);
  const expectedFragment = config.artifact === 'qwen3.5-4b' ? 'qwen3.5-4b'
    : config.artifact === 'gemma4-e2b' ? 'gemma-4-e2b' : 'gemma-4-e4b';
  assert(catalog.searched_name_fragments.includes(expectedFragment), 'Catalog did not search exact family');
  assert.equal(receipt.route_checked_utc, catalog.retrieved_utc);
  assert(now - Date.parse(catalog.retrieved_utc) >= 0 && now - Date.parse(catalog.retrieved_utc) < 24*3600*1000,
         'Route attestation must be fresh');
  if (stage === 'development') {
    assert.equal(receipt.smoke_inspection_sha256, smokeHash);
    assert.equal(receipt.smoke_all_three_valid, true);
  }
}

function inspectLoadEvidence(logText, fullModelPath, instanceReference, expectedLimit=8192) {
  const lines = logText.split('\n');
  const loadPrefix = 'LlamaV4::load called with model path: ';
  const loads = lines.flatMap((line,index) => line.includes(loadPrefix)
    ? [{index,path:line.slice(line.indexOf(loadPrefix)+loadPrefix.length).trim()}] : []);
  assert(loads.length, 'No actual loaded-model log event');
  const latest = loads.at(-1);
  assert.equal(latest.path,fullModelPath,'Newest loaded model is not the admitted artifact');
  const after = lines.slice(latest.index+1);
  const cacheLine = after.findIndex(line => /load_model: prompt cache is (enabled|disabled)/.test(line));
  assert(cacheLine >= 0 && cacheLine < 250,'No load-time prompt-cache observation');
  const expected = `load_model: prompt cache is enabled, size limit: ${expectedLimit} MiB`;
  assert(after[cacheLine].includes(expected),'Loaded-model cache state or size limit differs');
  const refLine = after.findIndex(line => line.includes(`"instanceReference":"${instanceReference}"`));
  assert(refLine > cacheLine && refLine < 300,'Load log does not link current SDK instance');
  assert(!lines.slice(0,latest.index).some(line => line.includes(`"instanceReference":"${instanceReference}"`)),
         'Current SDK instance appeared before the selected load event');
  return {cache:{enabled:true,size_limit_mib:expectedLimit},instance_reference:instanceReference,
          log_sha256:hash(logText),load_line:latest.index+1,cache_line:latest.index+cacheLine+2,
          instance_line:latest.index+refLine+2};
}

function selectedBackendPreference(preferences, expectedEngine) {
  assert(Array.isArray(preferences),'LM Studio selected-backend preferences unavailable');
  const selected = preferences.filter(item=>item.model_format==='gguf');
  assert.equal(selected.length,1,'GGUF selected-backend preference missing or ambiguous');
  assert.equal(`${selected[0].name}@${selected[0].version}`,expectedEngine,
               'Selected GGUF backend differs from frozen protocol');
  return {name:selected[0].name,version:selected[0].version,loaded_instance_version_verified:false};
}

function recentLoadLogs(directory) {
  const candidates = fs.readdirSync(directory,{withFileTypes:true}).filter(x=>x.isDirectory())
    .flatMap(month => fs.readdirSync(path.join(directory,month.name))
      .filter(name=>name.endsWith('.log')).map(name=>path.join(directory,month.name,name)));
  const recent = candidates.map(file=>({file,mtime:fs.statSync(file).mtimeMs}))
    .sort((a,b)=>b.mtime-a.mtime).slice(0,10).reverse();
  assert(recent.length,'No LM Studio load logs');
  return recent.map(x=>fs.readFileSync(x.file,'utf8')).join('\n');
}

function durable(fd, value) {
  fs.writeSync(fd, stable(value) + '\n');
  fs.fsyncSync(fd);
}

function stagePaths(id, pass, condition, stage) {
  const folder = path.join(ROOT, 'results/repeatability-v1/small-local-v1', id, pass, condition);
  assert(['smoke','development'].includes(stage));
  return {folder, claim:path.join(folder, `${stage}.claim.json`),
          journal:path.join(folder, `${stage}.journal.jsonl`),
          raw:path.join(folder, `${stage}.raw.jsonl`),
          records:path.join(folder, `${stage}.records.jsonl`),
          completion:path.join(folder, `${stage}.completion.json`)};
}

function checkPredecessor(plan, id, pass, condition, stage) {
  const {preceding} = phaseInfo(plan, id, pass, condition);
  for (const earlier of preceding) {
    const [p,c] = earlier.split('/');
    const terminal = stagePaths(id,p,c,'development').completion;
    assert(fs.existsSync(terminal) && read(terminal).status === 'completed', `Prior phase incomplete: ${earlier}`);
    const closed = read(terminal), files = stagePaths(id,p,c,'development');
    assert.equal(closed.attempted,60,`Prior phase incomplete: ${earlier}`);
    assert.equal(closed.saved,60,`Prior phase incomplete: ${earlier}`);
    assert.equal(hashFile(files.journal),closed.journal_sha256);
    assert.equal(hashFile(files.raw),closed.raw_sha256);
    assert.equal(hashFile(files.records),closed.records_sha256);
  }
  if (stage !== 'development') return null;
  const smoke = stagePaths(id,pass,condition,'smoke');
  assert(fs.existsSync(smoke.completion) && read(smoke.completion).status === 'completed', 'Smoke not complete');
  const smokeTerminal = read(smoke.completion);
  assert.equal(smokeTerminal.attempted,3);
  assert.equal(smokeTerminal.saved,3);
  assert.equal(hashFile(smoke.journal),smokeTerminal.journal_sha256);
  assert.equal(hashFile(smoke.raw),smokeTerminal.raw_sha256);
  assert.equal(hashFile(smoke.records),smokeTerminal.records_sha256);
  const inspection = path.join(smoke.folder, 'smoke-inspection.json');
  assert(fs.existsSync(inspection), 'Root smoke inspection missing');
  const checked = read(inspection);
  assert.equal(checked.kind, 'small-local-three-record-smoke-inspection-v1');
  assert.equal(checked.approved, true);
  assert.equal(checked.raw_sha256, hashFile(smoke.raw));
  assert.equal(checked.records_sha256, hashFile(smoke.records));
  assert.deepEqual(rows(smoke.records).map(x => x.decision.status), ['ok','ok','ok']);
  return hashFile(inspection);
}

function stageRows(plan, id, condition, stage) {
  const frozen = plan.configurations[id].conditions[condition];
  assert.equal(hashFile(rel(frozen.source.file)), frozen.source.sha256);
  const saved = rows(rel(frozen.source.file));
  const expected = stage === 'smoke' ? plan.policy.smoke_ids : frozen.requests.map(x => x.id);
  return expected.map(key => {
    const i = frozen.requests.findIndex(x => x.id === key);
    assert(i >= 0 && saved[i].id === key);
    const request = saved[i].request;
    assert.equal(hash(stable(request)), frozen.requests[i].sha256, 'Frozen request differs');
    return {id:key, request, prompt_tokens:frozen.requests[i].prompt_tokens,
            load_config:saved[i].load_config, prediction_config:saved[i].prediction_config};
  });
}

async function realRuntime(plan, config, probes={}) {
  const runtime = plan.parent_runtime;
  const cli = '/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms';
  const fileHash = probes.hashFile || hashFile;
  const command = probes.execFileSync || execFileSync;
  assert.equal(fileHash(runtime.sdk_path), runtime.sdk_sha256, 'SDK changed');
  assert.equal(fileHash(cli), runtime.cli_sha256, 'LM Studio CLI changed');
  assert.equal(fileHash(runtime.app_plist_path), runtime.app_plist_sha256, 'LM Studio app changed');
  assert.equal(command(cli,['--version'],{encoding:'utf8',timeout:15000}).trim(), `CLI commit: ${runtime.cli_commit}`);
  const available = command(cli,['runtime','ls'],{encoding:'utf8',timeout:15000});
  assert(available.split('\n').some(x => x.startsWith(runtime.selected_engine) && x.includes('✓') && x.includes('GGUF')),
         'Pinned engine unavailable');
  const loaded = parent.requireLoadedModel(command(cli,['ps'],{encoding:'utf8',timeout:15000}),config.model_identifier,8192,1);
  const hardware = {model_identifier:command('/usr/sbin/sysctl',['-n','hw.model'],{encoding:'utf8'}).trim(),
                    chip:command('/usr/sbin/sysctl',['-n','machdep.cpu.brand_string'],{encoding:'utf8'}).trim(),
                    architecture:os.arch()};
  const parentPlan = read(rel('results/local-prompt-exact-v1/manifest.json'));
  assert.deepEqual(hardware, parentPlan.hardware, 'Host hardware changed');
  assert.equal(fileHash(path.join(runtime.models_dir, config.artifact_path)), config.artifact_sha256, 'GGUF changed');
  const model = probes.model || new (require(runtime.sdk_path).LMStudioClient)().llm.createDynamicHandle(config.model_identifier);
  const info = await model.getModelInfo();
  assert(info && info.identifier === config.model_identifier && info.path === config.artifact_path &&
         info.sizeBytes === config.artifact_bytes && info.contextLength === 8192 &&
         info.quantization?.name === 'Q4_K_M', 'Loaded model differs');
  const logText = (probes.loadLogs || recentLoadLogs)(path.join(path.dirname(runtime.models_dir),'server-logs'));
  const loadEvidence = inspectLoadEvidence(logText,path.join(runtime.models_dir,config.artifact_path),
                                           info.instanceReference,plan.policy.cache_policy.size_limit_mib);
  const preferenceFile = path.join(path.dirname(runtime.models_dir),'.internal/backend-preferences-v1.json');
  const selectedBackend = selectedBackendPreference(probes.backendPreferences || read(preferenceFile),runtime.selected_engine);
  return {model, instance:info.instanceReference, attestation:{hardware, loaded,
          cli_commit:runtime.cli_commit, artifact_sha256:config.artifact_sha256,
          load_evidence:loadEvidence,selected_backend_preference:selectedBackend,
          selected_backend_file_sha256:fileHash(preferenceFile),loaded_engine_version:null,
          loaded_engine_version_status:'unavailable_from_read_only_instance_surfaces'}};
}

async function runStage(plan, planSha, id, pass, condition, stage, receiptPath, dependencies={}) {
  const phase = `${id}/${pass}/${condition}`;
  const {config} = phaseInfo(plan,id,pass,condition);
  const paths = (dependencies.paths || stagePaths)(id,pass,condition,stage);
  const smokeHash = (dependencies.predecessor || checkPredecessor)(plan,id,pass,condition,stage);
  const receipt = read(receiptPath);
  (dependencies.admit || checkReceipt)(receipt,planSha,phase,stage,config,smokeHash);
  const selection = stageRows(plan,id,condition,stage);
  const runtime = await (dependencies.runtime || realRuntime)(plan,config);
  for (const file of Object.values(paths).filter(x => x !== paths.folder))
    assert(!fs.existsSync(file), 'Phase already claimed; no replay');
  fs.mkdirSync(paths.folder,{recursive:true});
  fs.writeFileSync(paths.claim,stable({phase,stage,plan_sha256:planSha,controller_sha256:hashFile(__filename),
    receipt_sha256:hashFile(receiptPath),runtime_attestation:runtime.attestation,started_utc:new Date().toISOString()})+'\n',{flag:'wx'});
  const journal = fs.openSync(paths.journal,'wx'), raw = fs.openSync(paths.raw,'wx'), records = fs.openSync(paths.records,'wx');
  let status = 'stopped', reason = null, invalid = 0;
  try {
    for (const row of selection) {
      const info = await runtime.model.getModelInfo();
      assert.equal(info.instanceReference,runtime.instance,'Loaded model instance changed');
      const attempt = crypto.randomUUID();
      durable(journal,{event:'started',attempt_id:attempt,id:row.id,request_sha256:hash(stable(row.request)),at:new Date().toISOString()});
      let result;
      const started = process.hrtime.bigint();
      try {
        result = await (dependencies.predict || predictor.predictWithTimeout)(runtime.model,row.request.messages,row.request.config,config.timeout_ms);
      } catch (error) {
        durable(raw,{attempt_id:attempt,id:row.id,error:String(error.message),code:error.code ?? null,
          cancellationAcknowledged:error.cancellationAcknowledged ?? null,
          cancellationError:error.cancellationError ?? null,partialResult:error.partialResult ?? null,
          elapsed_seconds:Number(process.hrtime.bigint()-started)/1e9,result:null});
        durable(journal,{event:'stopped_unknown',attempt_id:attempt,id:row.id,at:new Date().toISOString()});
        throw error;
      }
      durable(raw,{attempt_id:attempt,id:row.id,result:{content:result?.content ?? null,
        nonReasoningContent:result?.nonReasoningContent ?? null,reasoningContent:result?.reasoningContent ?? null,
        stats:result?.stats ?? null,modelInfo:result?.modelInfo ?? null,
        loadConfig:result?.loadConfig ?? null,predictionConfig:result?.predictionConfig ?? null},
        elapsed_seconds:Number(process.hrtime.bigint()-started)/1e9}); // Before parsing.
      const expected = {identifier:config.model_identifier,path:config.artifact_path,bytes:config.artifact_bytes,
                        promptTokens:row.prompt_tokens,loadConfig:row.load_config,predictionConfig:row.prediction_config};
      const decision = parent.classifySdk(result,expected);
      durable(records,{id:row.id,attempt_id:attempt,request_sha256:hash(stable(row.request)),decision,
                       reference_labels_read:false,finished_utc:new Date().toISOString()});
      durable(journal,{event:'finished',attempt_id:attempt,id:row.id,status:decision.status,at:new Date().toISOString()});
      if (decision.status === 'invalid_output') invalid++;
      else if (decision.status !== 'ok') throw Error(`Stopped on ${decision.status} at ${row.id}`);
    }
    assert(stage !== 'smoke' || invalid === 0, 'Smoke has invalid output; development admission refused');
    status = 'completed';
  } catch (error) {reason = String(error.message); throw error;}
  finally {
    for (const fd of [journal,raw,records]) fs.closeSync(fd);
    fs.writeFileSync(paths.completion,stable({phase,stage,status,reason,attempted:rows(paths.journal).filter(x=>x.event==='started').length,
      saved:rows(paths.records).length,invalid,raw_sha256:hashFile(paths.raw),records_sha256:hashFile(paths.records),
      journal_sha256:hashFile(paths.journal),finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});
  }
  return read(paths.completion);
}

const lockCode = 'import fcntl,os,subprocess,sys\nfd=os.open(sys.argv[1],os.O_CREAT|os.O_RDWR,0o600)\ntry: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError: sys.exit(73)\nenv=dict(os.environ,SMALL_LOCAL_HOST_LOCK_HELD="1")\nraise SystemExit(subprocess.call(sys.argv[2:],env=env))';
async function cli(argv) {
  const [action,...args] = argv;
  if (action === 'prepare') {
    const plan = makePlan();
    fs.mkdirSync(path.dirname(PLAN),{recursive:true});
    fs.writeFileSync(PLAN,stable(plan)+'\n',{flag:'wx'});
    console.log(hashFile(PLAN)); return;
  }
  const {plan,sha256} = verifyPlan();
  if (action === 'verify') {console.log(sha256);return;}
  if (action === 'preview') {
    const [id,pass,condition,stage] = args;
    phaseInfo(plan,id,pass,condition);
    console.log(stable({phase:`${id}/${pass}/${condition}`,stage,ids:stageRows(plan,id,condition,stage).map(x=>x.id)}));return;
  }
  if (action === 'run') {
    const status = execFileSync('python3',['-c',lockCode,LOCK,process.execPath,__filename,'internal-run',...args],{stdio:'inherit'});
    return status;
  }
  if (action === 'internal-run') {
    assert.equal(process.env.SMALL_LOCAL_HOST_LOCK_HELD,'1','Use run to acquire the common native host lock');
    const [id,pass,condition,stage,receiptPath] = args;
    assert(id && pass && condition && stage && receiptPath, 'Require config pass condition stage receipt');
    await runStage(plan,sha256,id,pass,condition,stage,receiptPath);return;
  }
  throw Error('Use prepare, verify, preview, or run');
}
if (require.main === module) cli(process.argv.slice(2)).catch(e => {console.error(e.message);process.exitCode=1;});

module.exports = {ROOT, PLAN, LOCK, NAMES, makePlan, verifyPlan, phaseInfo, checkReceipt,
                  hash, hashFile, rows, read, rel, source, rotations, stagePaths, checkPredecessor,
                  stageRows, inspectLoadEvidence, selectedBackendPreference, recentLoadLogs, lockCode,
                  realRuntime, runStage};

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { LMStudioClient } = require('./lmstudio-sdk/node_modules/@lmstudio/sdk/dist/index.cjs');

const workspace = path.resolve(__dirname, '..');
const repo = '/Users/adamkovacs/Documents/codebuild/recruitment-feedback-demo';
const source = path.join(workspace, 'work/qwen06-all-prompts-rendered.json');
const destination = path.join(workspace, 'results/qwen06-sdk-token-preflight-2026-09-24');
const sdkPath = path.join(workspace, 'work/lmstudio-sdk/node_modules/@lmstudio/sdk/dist/index.cjs');
const sdkPackagePath = path.join(workspace, 'work/lmstudio-sdk/node_modules/@lmstudio/sdk/package.json');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileHash = filename => hash(fs.readFileSync(filename));

async function main() {
  if (fs.existsSync(destination)) throw new Error(`Refusing to overwrite ${destination}`);
  const records = JSON.parse(fs.readFileSync(source, 'utf8'));
  if (!Array.isArray(records) || records.length !== 360) throw new Error('Expected exactly 360 rendered prompts');
  const expectedGroups = new Set(['qwen3-0.6b-sdk-thinking-on', 'qwen3-0.6b-sdk-thinking-off']);
  const groupCounts = {};
  const seen = new Set();
  const sourceHashes = {};
  for (const record of records) {
    const { id, configuration, variant, rendered, rendered_sha256, source_file, source_sha256, context, output_reserve } = record;
    if (!/^DEV-0[0-6][0-9]$/.test(id) || Number(id.slice(4)) < 1 || Number(id.slice(4)) > 60 ||
        !expectedGroups.has(configuration) || !['P0', 'P1', 'P2'].includes(variant)) throw new Error('Unexpected prompt identity');
    const key = `${configuration}/${variant}/${id}`;
    if (seen.has(key)) throw new Error(`Duplicate ${key}`);
    seen.add(key);
    groupCounts[`${configuration}/${variant}`] = (groupCounts[`${configuration}/${variant}`] || 0) + 1;
    if (hash(Buffer.from(rendered, 'utf8')) !== rendered_sha256) throw new Error(`Rendered hash mismatch ${key}`);
    if (context !== 8192 || output_reserve !== 4096) throw new Error(`Unexpected context/reserve ${key}`);
    const sourcePath = path.resolve(repo, source_file);
    if (!sourcePath.startsWith(`${repo}/`) || fileHash(sourcePath) !== source_sha256) throw new Error(`Source hash mismatch ${key}`);
    sourceHashes[source_file] = source_sha256;
    if (variant === 'P0' && !Number.isInteger(record.saved_prompt_tokens)) throw new Error(`Missing P0 baseline ${key}`);
    if (variant !== 'P0' && record.saved_prompt_tokens != null) throw new Error(`Unexpected non-P0 baseline ${key}`);
  }
  if (Object.keys(groupCounts).length !== 6 || Object.values(groupCounts).some(n => n !== 60)) throw new Error('Incomplete prompt groups');

  const client = new LMStudioClient();
  const model = client.llm.createDynamicHandle('recruitment-qwen3-0.6b-q4km');
  const modelInfo = await model.getModelInfo();
  if (!modelInfo || modelInfo.identifier !== 'recruitment-qwen3-0.6b-q4km' || modelInfo.contextLength !== 8192 ||
      modelInfo.path !== 'lmstudio-community/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q4_K_M.gguf') throw new Error('Loaded model identity/context mismatch');
  const counts = [];
  for (let offset = 0; offset < records.length; offset += 10) {
    const batch = records.slice(offset, offset + 10);
    const tokenIds = await model.tokenize(batch.map(record => record.rendered));
    if (!Array.isArray(tokenIds) || tokenIds.length !== batch.length) throw new Error(`Tokenizer batch mismatch at ${offset}`);
    for (let i = 0; i < batch.length; i++) {
      if (!Array.isArray(tokenIds[i])) throw new Error('Tokenizer returned non-array');
      const record = batch[i], promptTokens = tokenIds[i].length;
      counts.push({ id: record.id, configuration: record.configuration, variant: record.variant,
        rendered_sha256: record.rendered_sha256, prompt_tokens: promptTokens,
        saved_p0_prompt_tokens: record.variant === 'P0' ? record.saved_prompt_tokens : null,
        p0_count_match: record.variant === 'P0' ? promptTokens === record.saved_prompt_tokens : null,
        context: record.context, output_reserve: record.output_reserve,
        token_plus_reserve: promptTokens + record.output_reserve,
        fits_context: promptTokens + record.output_reserve <= record.context });
    }
  }
  const p0 = counts.filter(r => r.variant === 'P0');
  const evidence = {
    measured_utc: new Date().toISOString(),
    method: 'Public @lmstudio/sdk 1.5.0 LLM dynamic handle tokenize(rendered string), batches of 10; token ID arrays discarded after counting; no prediction calls.',
    loaded_model: { identifier: modelInfo.identifier, path: modelInfo.path, context_length: modelInfo.contextLength, instance_reference: modelInfo.instanceReference },
    source_bindings: { rendered_prompts_file: path.relative(workspace, source), rendered_prompts_sha256: fileHash(source),
      source_development_files: sourceHashes, sdk_index_cjs_sha256: fileHash(sdkPath), sdk_package_json_sha256: fileHash(sdkPackagePath),
      script_sha256: fileHash(__filename) },
    groups: groupCounts,
    records: counts.length,
    p0_saved_count_matches: p0.filter(r => r.p0_count_match).length,
    p0_count_mismatches: p0.filter(r => !r.p0_count_match).length,
    fit_count: counts.filter(r => r.fits_context).length,
    overflow_count: counts.filter(r => !r.fits_context).length,
    min_prompt_tokens: Math.min(...counts.map(r => r.prompt_tokens)),
    max_prompt_tokens: Math.max(...counts.map(r => r.prompt_tokens)),
    max_token_plus_reserve: Math.max(...counts.map(r => r.token_plus_reserve)),
    limitation: 'Count parity and context fit only. This does not prove token sequence equivalence or per-prediction template override support.'
  };
  fs.mkdirSync(destination, { recursive: true });
  const countsPath = path.join(destination, 'counts.json');
  fs.writeFileSync(countsPath, JSON.stringify(counts, null, 2) + '\n', { flag: 'wx' });
  evidence.counts_sha256 = fileHash(countsPath);
  fs.writeFileSync(path.join(destination, 'evidence.json'), JSON.stringify(evidence, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ destination, records: evidence.records, p0_matches: evidence.p0_saved_count_matches,
    p0_mismatches: evidence.p0_count_mismatches, fits: evidence.fit_count, overflow: evidence.overflow_count,
    max_token_plus_reserve: evidence.max_token_plus_reserve }));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });

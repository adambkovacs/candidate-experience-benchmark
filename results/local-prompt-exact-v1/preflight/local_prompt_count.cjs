#!/usr/bin/env node
// Public LM Studio SDK tokenization only. This file never calls respond/predict.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { LMStudioClient } = require('./lmstudio-sdk/node_modules/@lmstudio/sdk/dist/index.cjs');

const dir = path.resolve(__dirname, 'local-prompt-preflight-build-v1');
const family = process.argv[2];
const plan = {
  qwen06: {identifier:'recruitment-qwen3-0.6b-q4km', prefix:'qwen3-0.6b-q4km-nonthinking', file:'http-messages.jsonl', http:true,
    modelPath:'lmstudio-community/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q4_K_M.gguf', sizeBytes:484219808, reserve:512},
  qwen17: {identifier:'recruitment-qwen3-1.7b-q4km', prefix:'qwen3-1.7b-sdk-', file:'sdk-rendered.jsonl',
    modelPath:'lmstudio-community/Qwen3-1.7B-GGUF/Qwen3-1.7B-Q4_K_M.gguf', sizeBytes:1282439328, reserve:4096},
  qwen35: {identifier:'recruitment-qwen3.5-4b-q4km', prefix:'qwen3.5-4b-sdk-', file:'sdk-rendered.jsonl',
    modelPath:'lmstudio-community/Qwen3.5-4B-GGUF/Qwen3.5-4B-Q4_K_M.gguf', sizeBytes:2707513696, reserve:4096},
  gemmae2: {identifier:'recruitment-gemma4-e2b-q4km', prefix:'gemma4-e2b-sdk-', file:'sdk-rendered.jsonl',
    modelPath:'lmstudio-community/gemma-4-E2B-it-GGUF/gemma-4-E2B-it-Q4_K_M.gguf', sizeBytes:3427880384, reserve:4096},
  gemmae4: {identifier:'benchmark-gemma4-e4b', prefix:'gemma4-e4b-sdk-', file:'sdk-rendered.jsonl',
    modelPath:'lmstudio-community/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf', sizeBytes:5335291936, reserve:4096},
}[family];
if (!plan) throw Error('Specify qwen06, qwen17, qwen35, gemmae2, or gemmae4');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const shaFile = file => sha(fs.readFileSync(file));
const readRows = file => fs.readFileSync(file, 'utf8').trim().split('\n').map(JSON.parse);
async function main() {
  const source = path.join(dir,plan.file);
  const rows = readRows(source).filter(row => row.configuration.startsWith(plan.prefix));
  if (rows.length !== (plan.http ? 180 : 360)) throw Error('Incomplete condition set');
  const client = new LMStudioClient();
  const model = client.llm.createDynamicHandle(plan.identifier);
  const info = await model.getModelInfo();
  if (!info || info.identifier!==plan.identifier || info.path!==plan.modelPath || info.sizeBytes!==plan.sizeBytes ||
      info.contextLength!==8192 || info.quantization?.name!=='Q4_K_M') throw Error('Loaded model mismatch');
  const counted=[];
  const renderedHttp=[];
  for (let start=0; start<rows.length; start+=10) {
    const batch=rows.slice(start,start+10);
    const rendered=[];
    for (const row of batch) {
      const text=plan.http ? await model.applyPromptTemplate(row.messages) : row.rendered;
      if (typeof text!=='string' || !text) throw Error('Empty rendered prompt');
      rendered.push(text);
      if (plan.http) renderedHttp.push({id:row.id,configuration:row.configuration,variant:row.variant,
        messages_sha256:row.messages_sha256,rendered:text,rendered_sha256:sha(Buffer.from(text))});
      else if (sha(Buffer.from(text))!==row.rendered_sha256) throw Error('Render hash changed');
    }
    const tokenIds=await model.tokenize(rendered);
    if (!Array.isArray(tokenIds) || tokenIds.length!==batch.length) throw Error('Tokenization result mismatch');
    for (let i=0;i<batch.length;i++) {
      const row=batch[i], count=tokenIds[i].length;
      counted.push({id:row.id,configuration:row.configuration,variant:row.variant,
        rendered_sha256:sha(Buffer.from(rendered[i])),prompt_tokens:count,
        saved_p0_prompt_tokens:row.saved_p0_prompt_tokens,
        p0_delta:row.variant==='P0' ? row.saved_p0_prompt_tokens-count : null,
        context:8192,output_reserve:plan.reserve,token_plus_reserve:count+plan.reserve,
        fits_context:count+plan.reserve<=8192});
    }
  }
  const countFile=path.join(dir,`counts-${family}.jsonl`);
  fs.writeFileSync(countFile,counted.map(JSON.stringify).join('\n')+'\n',{flag:'wx'});
  let renderedFile=null;
  if (plan.http) {
    renderedFile=path.join(dir,'http-rendered.jsonl');
    fs.writeFileSync(renderedFile,renderedHttp.map(JSON.stringify).join('\n')+'\n',{flag:'wx'});
  }
  const p0=counted.filter(row=>row.variant==='P0');
  const evidence={version:'local-prompt-public-sdk-token-count-v1',measured_utc:new Date().toISOString(),family,
    method:plan.http?'Public SDK applyPromptTemplate(messages) and tokenize(rendered), no inference':
      'Offline exact per-prediction Jinja rendering, then public SDK tokenize(rendered), no inference',
    loaded_model:{identifier:info.identifier,path:info.path,size_bytes:info.sizeBytes,quantization:info.quantization?.name,
      context_length:info.contextLength,instance_reference:info.instanceReference},
    source_file:path.basename(source),source_sha256:shaFile(source),counts_file:path.basename(countFile),counts_sha256:shaFile(countFile),
    ...(renderedFile?{rendered_file:path.basename(renderedFile),rendered_sha256:shaFile(renderedFile)}:{}),
    sdk_file:'work/lmstudio-sdk/node_modules/@lmstudio/sdk/dist/index.cjs',
    sdk_sha256:shaFile(path.resolve(__dirname,'lmstudio-sdk/node_modules/@lmstudio/sdk/dist/index.cjs')),
    counter_file:'work/local_prompt_count.cjs',counter_sha256:shaFile(__filename),
    records:counted.length,p0_records:p0.length,p0_delta_values:[...new Set(p0.map(row=>row.p0_delta))].sort((a,b)=>a-b),
    p0_exact_count_matches:p0.filter(row=>row.p0_delta===0).length,
    fit_count:counted.filter(row=>row.fits_context).length,overflow_count:counted.filter(row=>!row.fits_context).length,
    maximum_prompt_tokens:Math.max(...counted.map(row=>row.prompt_tokens)),
    maximum_token_plus_reserve:Math.max(...counted.map(row=>row.token_plus_reserve)),
    limitation:plan.http?'HTTP response_format schema may add tokens beyond public template rendering; compare saved P0 usage deltas and apply a separate conservative admission bound.':
      'Count parity does not prove historical token IDs or future runtime behavior; loaded configuration and actual prompt count must be verified in smoke.'};
  const evidenceFile=path.join(dir,`evidence-${family}.json`);
  fs.writeFileSync(evidenceFile,JSON.stringify(evidence,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({family,records:evidence.records,p0_deltas:evidence.p0_delta_values,
    p0_matches:evidence.p0_exact_count_matches,fit_count:evidence.fit_count,
    overflow_count:evidence.overflow_count,max_token_plus_reserve:evidence.maximum_token_plus_reserve}));
}
main().catch(error=>{console.error(error.message);process.exitCode=1});

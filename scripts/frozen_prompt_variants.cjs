'use strict';
/** Offline composition only. Callers retain their P0 role/output method and must
 * perform tokenizer/context preflight before any separately authorized inference.
 * Combined CLI prompts insert this instruction block before feedback serialization.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {TextDecoder} = require('node:util');
const ROOT = path.resolve(__dirname, '..');
const BUNDLE = 'prompts/variants-v1';
const MANIFEST_SHA256 = 'd4be944de76d94b85743c536997051755a0247ea13f0d27b612dbbf025fb8264';
const FILES = Object.freeze({P1:'P1-classifier.txt', P2:'P2-classifier-sop.txt'});
const ROLES = new Set(['system','user','cli_combined_prompt']);
const SEPARATOR = '\n\n';
const sha = raw => crypto.createHash('sha256').update(raw).digest('hex');
// Python UTF-8 decoding preserves BOMs and rejects invalid byte sequences.
const decode = raw => new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw);
function utf8(text) {
  // Buffer.from otherwise silently replaces lone surrogates, unlike str.encode().
  for (let i=0;i<text.length;i++) {
    const code=text.charCodeAt(i);
    if (code>=0xd800 && code<=0xdbff) {
      const next=text.charCodeAt(++i);
      if (!(next>=0xdc00 && next<=0xdfff)) throw new TypeError('Invalid Unicode surrogate');
    } else if (code>=0xdc00 && code<=0xdfff) throw new TypeError('Invalid Unicode surrogate');
  }
  return Buffer.from(text,'utf8');
}
function load_frozen_bundle(root=ROOT) {
  const manifestBytes=fs.readFileSync(path.join(root,BUNDLE,'manifest.json'));
  if (sha(manifestBytes)!==MANIFEST_SHA256) throw new Error('Frozen variant manifest changed; use a new reviewed version');
  const manifest=JSON.parse(decode(manifestBytes));
  if (manifest.version!=='variants-v1' || manifest.status!=='frozen_candidate_offline_only') throw new Error('Unexpected variant bundle');
  if (JSON.stringify(Object.keys(manifest.files||{}).sort())!==JSON.stringify(Object.values(FILES).sort())) throw new Error('Unexpected frozen files');
  // Path.read_text() uses universal newlines; only the source policy is normalized.
  const policy=decode(fs.readFileSync(path.join(root,'docs/LABELING_GUIDE.md'))).replace(/\r\n|\r/g,'\n').split('## Simulated routing')[0];
  if (sha(utf8(policy))!==manifest.source_policy_sha256) throw new Error('Source rubric changed');
  const additions={};
  for (const [variant,name] of Object.entries(FILES)) {
    const raw=fs.readFileSync(path.join(root,BUNDLE,name)),entry=manifest.files[name];
    if (raw.length!==entry.bytes || sha(raw)!==entry.sha256) throw new Error('Frozen candidate changed: '+name);
    additions[variant]=decode(raw);
  }
  const one=utf8(additions.P1),two=utf8(additions.P2);
  if (!two.subarray(0,one.length).equals(one)) throw new Error('P2 must start with verbatim P1');
  return {manifest,additions};
}
function compose_instruction(baseline_instruction,variant,{role,parent_baseline_id,root=ROOT}={}) {
  if (typeof baseline_instruction!=='string' || !baseline_instruction) throw new TypeError('Require a nonempty P0 instruction string');
  if (!['P0','P1','P2'].includes(variant)) throw new Error('Unknown prompt variant');
  if (!ROLES.has(role)) throw new Error('Role must match system, user or cli_combined_prompt');
  // Python str.strip() whitespace differs from JavaScript trim() for U+0085/BOM.
  if (typeof parent_baseline_id!=='string' || !parent_baseline_id.replace(/^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/g,'')) throw new TypeError('Require parent baseline ID');
  const {manifest,additions}=load_frozen_bundle(root);
  const addition=variant==='P0'?null:additions[variant];
  const composed=addition===null?baseline_instruction:baseline_instruction+SEPARATOR+addition;
  const baselineBytes=utf8(baseline_instruction),composedBytes=utf8(composed),additionBytes=addition===null?null:utf8(addition);
  return {instruction:composed,role,audit:{
    variant,parent_baseline_id,instruction_role:role,bundle_version:manifest.version,
    manifest_path:BUNDLE+'/manifest.json',manifest_sha256:MANIFEST_SHA256,source_policy_sha256:manifest.source_policy_sha256,
    baseline_instruction_sha256:sha(baselineBytes),baseline_instruction_bytes:baselineBytes.length,
    addition_path:addition===null?null:BUNDLE+'/'+FILES[variant],addition_sha256:addition===null?null:sha(additionBytes),addition_bytes:addition===null?0:additionBytes.length,
    composition_separator:addition===null?'':SEPARATOR,composed_instruction_sha256:sha(composedBytes),composed_instruction_bytes:composedBytes.length,
    token_length:null,token_length_status:'not_measured; adapter preflight required',reference_labels_read:false,inference_performed:false
  }};
}
module.exports={load_frozen_bundle,compose_instruction};

'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const {execFileSync} = require('node:child_process');
const Module = require('node:module');
const ROOT = path.resolve(__dirname, '..');
const SOURCE = path.join(ROOT, 'scripts/frozen_prompt_variants.cjs');
function composer() {
  assert.ok(fs.existsSync(SOURCE), 'Standalone CommonJS composer is required');
  return require(SOURCE);
}
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'frozen-variants-'));
  t.after(() => fs.rmSync(root, {recursive:true, force:true}));
  fs.cpSync(path.join(ROOT, 'prompts/variants-v1'), path.join(root, 'prompts/variants-v1'), {recursive:true});
  fs.mkdirSync(path.join(root, 'docs'));
  fs.copyFileSync(path.join(ROOT, 'docs/LABELING_GUIDE.md'), path.join(root, 'docs/LABELING_GUIDE.md'));
  return root;
}
function pythonFixture(baseline, variant, role, root=ROOT) {
  const script = 'import json,sys\nsys.path.insert(0,sys.argv[1])\nfrom frozen_prompt_variants import compose_instruction\nx=json.load(sys.stdin)\nprint(json.dumps(compose_instruction(**x)))';
  return JSON.parse(execFileSync('python3', ['-c', script, path.join(ROOT,'scripts')], {
    input:JSON.stringify({baseline_instruction:baseline,variant,role,parent_baseline_id:'frozen-parent',root}), encoding:'utf8'
  }));
}
const options = {role:'system', parent_baseline_id:'frozen-parent', root:ROOT};
test('exact Python parity for all variants, roles, Unicode and CRLF P0 bytes', () => {
  const {compose_instruction} = composer();
  for (const baseline of ['BASE', ' \r\nCafé e\u0301 🧪 中文\t\rTrailing\n']) {
    for (const variant of ['P0','P1','P2']) for (const role of ['system','user','cli_combined_prompt']) {
      const actual=compose_instruction(baseline,variant,{...options,role});
      assert.deepEqual(actual,pythonFixture(baseline,variant,role));
      if (variant==='P0') assert.deepEqual(Buffer.from(actual.instruction),Buffer.from(baseline));
    }
  }
});
test('P2 preserves the complete P1 prefix and only appends after two LF bytes', () => {
  const {compose_instruction}=composer();
  const one=compose_instruction('BASE\r\n','P1',options),two=compose_instruction('BASE\r\n','P2',options);
  assert.ok(two.instruction.startsWith(one.instruction));
  assert.equal(one.instruction,'BASE\r\n\n\n'+fs.readFileSync(path.join(ROOT,'prompts/variants-v1/P1-classifier.txt'),'utf8'));
  assert.equal(two.audit.reference_labels_read,false);assert.equal(two.audit.inference_performed,false);
});
test('source-policy universal newlines match Python while baseline bytes remain untouched', t => {
  const root=fixture(t),p=path.join(root,'docs/LABELING_GUIDE.md');
  fs.writeFileSync(p,fs.readFileSync(p,'utf8').replace(/\n/g,'\r\n'));
  assert.deepEqual(composer().compose_instruction('a\r\nb','P2',{...options,root}),pythonFixture('a\r\nb','P2','system',root));
});
test('text after simulated-routing heading does not enter source policy hash', t => {
  const root=fixture(t),p=path.join(root,'docs/LABELING_GUIDE.md');fs.appendFileSync(p,'\npost-routing edit\n');
  assert.deepEqual(composer().compose_instruction('base','P1',{...options,root}),pythonFixture('base','P1','system',root));
});
test('candidate tampering, including same-size edits, is rejected even for P0', t => {
  const root=fixture(t),p=path.join(root,'prompts/variants-v1/P1-classifier.txt');
  const raw=fs.readFileSync(p);raw[0]^=1;fs.writeFileSync(p,raw);
  for(const variant of ['P0','P1','P2']) assert.throws(()=>composer().compose_instruction('base',variant,{...options,root}),/candidate changed/);
});
test('manifest cannot silently repin changed additions', t => {
  const root=fixture(t),p=path.join(root,'prompts/variants-v1/P2-classifier-sop.txt'),m=path.join(root,'prompts/variants-v1/manifest.json');
  fs.writeFileSync(p,'replacement');const data=JSON.parse(fs.readFileSync(m));data.files[path.basename(p)]={bytes:11,sha256:crypto.createHash('sha256').update('replacement').digest('hex')};fs.writeFileSync(m,JSON.stringify(data));
  assert.throws(()=>composer().compose_instruction('base','P2',{...options,root}),/manifest changed/);
});
test('source rubric changes are rejected before composition', t => {
  const root=fixture(t),p=path.join(root,'docs/LABELING_GUIDE.md');fs.writeFileSync(p,'changed\n'+fs.readFileSync(p,'utf8'));
  assert.throws(()=>composer().compose_instruction('base','P1',{...options,root}),/rubric changed/);
});
test('P2 nesting remains guarded with a deliberately reapproved test-only manifest', t => {
  const root=fixture(t),p=path.join(root,'prompts/variants-v1/P2-classifier-sop.txt'),m=path.join(root,'prompts/variants-v1/manifest.json');
  fs.writeFileSync(p,'No P1 prefix');const data=JSON.parse(fs.readFileSync(m));data.files[path.basename(p)]={bytes:12,sha256:crypto.createHash('sha256').update('No P1 prefix').digest('hex')};fs.writeFileSync(m,JSON.stringify(data));
  const replacement=crypto.createHash('sha256').update(fs.readFileSync(m)).digest('hex');
  const isolated=new Module(SOURCE,module);isolated.filename=SOURCE;isolated.paths=module.paths;
  isolated._compile(fs.readFileSync(SOURCE,'utf8').replace(/d4be944de76d94b85743c536997051755a0247ea13f0d27b612dbbf025fb8264/g,replacement),SOURCE);
  assert.throws(()=>isolated.exports.compose_instruction('base','P2',{...options,root}),/verbatim P1/);
});
test('invalid inputs fail closed, including unpaired Unicode surrogates', () => {
  const {compose_instruction}=composer();
  for(const [base,variant,opt] of [['','P0',options],[Buffer.from('x'),'P0',options],['x','other',options],['x','P0',{...options,role:'assistant'}],['x','P0',{...options,parent_baseline_id:'\u001c\u0085'}],['\ud800','P0',options]]) assert.throws(()=>compose_instruction(base,variant,opt));
  assert.equal(compose_instruction('x','P0',{...options,parent_baseline_id:'\ufeff'}).audit.parent_baseline_id,'\ufeff');
});
test('bundle-only fixture needs no data or reference files', t => {
  const root=fixture(t);assert.equal(fs.existsSync(path.join(root,'data')),false);
  assert.equal(composer().compose_instruction('base','P2',{...options,root}).audit.reference_labels_read,false);
});

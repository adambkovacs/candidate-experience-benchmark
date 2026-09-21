const test=require('node:test');
const assert=require('node:assert/strict');
const {configureThinking,validateOptions}=require('../scripts/lmstudio_reasoning_benchmark.cjs');
const qwen="{% if enable_thinking %}<think>{% endif %}";
test('existing Qwen template and parsing stay byte-identical',()=>{
 const x=configureThinking(qwen,'on');
 assert.equal(x.template,'{%- set enable_thinking = true %}\n'+qwen);
 assert.deepEqual(x.parsing,{enabled:true,startString:'<think>',endString:'</think>'});
});
test('Gemma verified template uses thought channel parser',()=>{
 const t="{% if enable_thinking %}<|think|>{% endif %}<|channel>thought\n<channel|>";
 assert.deepEqual(configureThinking(t,'on').parsing,{enabled:true,startString:'<|channel>thought',endString:'<channel|>'});
 assert.match(configureThinking(t,'off').template,/enable_thinking = false/);
});
test('unknown reasoning template rejected',()=>assert.throws(()=>configureThinking('{% if enable_thinking %}unknown{% endif %}','on'),/delimiters/));
test('Qwen3.8 effort must be explicit and artifact supported',()=>{
 const t=qwen+"{% set resolved_reasoning_effort = reasoning_effort|default('xhigh') %}";
 for(const effort of ['low','medium','xhigh']) assert.match(configureThinking(t,'on',effort).template,new RegExp("reasoning_effort = '"+effort+"'"));
 assert.throws(()=>configureThinking(t,'on'),/explicit/);
 assert.throws(()=>configureThinking(t,'on','high'),/effort/);
 assert.throws(()=>configureThinking(qwen,'on','low'),/support/);
 assert.throws(()=>configureThinking(t,'off','low'),/off/);
});
test('reject typo formats and unsupported thinking options',()=>{
 assert.throws(()=>validateOptions({format:'promt',thinking:'on'}),/format/);
 assert.throws(()=>validateOptions({format:'prompt',thinking:'maybe'}),/thinking/);
 validateOptions({thinking:'off'});validateOptions({format:'constrained',thinking:'on'});
});
test('retained Qwen artifacts preserve both historical template controls',()=>{
 const fs=require('node:fs'), path=require('node:path');
 for(const folder of ['qwen3-1.7b-2026-09-21','qwen3.5-4b-2026-09-21']) {
  const artifact=JSON.parse(fs.readFileSync(path.join(__dirname,'../results',folder,'artifact-metadata.json')));
  const template=artifact.metadata['tokenizer.chat_template'];
  for(const thinking of ['on','off']) assert.equal(configureThinking(template,thinking).template,
   '{%- set enable_thinking = '+(thinking==='on'?'true':'false')+' %}\n'+template);
 }
});
const {predictWithTimeout,writeJournal}=require('../scripts/lmstudio_reasoning_benchmark.cjs');
test('completion before deadline preserves request and never cancels',async()=>{
 let cancelled=0; const config={temperature:0.6},messages=[{role:'user',content:'x'}]; const result={content:'ok'};
 const model={respond:(m,c)=>{assert.strictEqual(m,messages);assert.strictEqual(c,config);return {result:()=>Promise.resolve(result),cancel:()=>{cancelled++;}};}};
 assert.strictEqual(await predictWithTimeout(model,messages,config,100),result); assert.equal(cancelled,0);
});
test('timeout cancels SDK prediction and retains acknowledged partial result',async()=>{
 let resolve,cancelled=0; const partial={content:'partial',stats:{stopReason:'userStopped'}};
 const model={respond:()=>({result:()=>new Promise(r=>{resolve=r;}),cancel:()=>{cancelled++;resolve(partial);}})};
 await assert.rejects(predictWithTimeout(model,[],{},5,20),error=>error.code==='PREDICTION_TIMEOUT' && error.partialResult===partial && error.cancellationAcknowledged===true); assert.equal(cancelled,1);
});
test('unresponsive cancellation has bounded grace and preserves uncertainty',async()=>{
 const model={respond:()=>({result:()=>new Promise(()=>{}),cancel:()=>{}})};
 await assert.rejects(predictWithTimeout(model,[],{},5,5),error=>error.code==='PREDICTION_TIMEOUT' && error.cancellationAcknowledged===false);
});
test('journal is durable before request and records final state separately',()=>{
 const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'journal-test-'));const p=path.join(dir,'attempts.jsonl');const fd=fs.openSync(p,'wx');
 try {writeJournal(fd,{event:'started',id:'DEV-001'});assert.equal(JSON.parse(fs.readFileSync(p,'utf8')).event,'started');writeJournal(fd,{event:'finished',id:'DEV-001',status:'ok'});assert.equal(fs.readFileSync(p,'utf8').trim().split('\n').length,2);} finally {fs.closeSync(fd);fs.rmSync(dir,{recursive:true});}
});
const {selectRows}=require('../scripts/lmstudio_reasoning_benchmark.cjs');
test('one-based start preserves default first-three and selects continuation',()=>{
 const rows=Array.from({length:60},(_,i)=>({id:'DEV-'+(i+1),feedback:'text'}));
 assert.deepEqual(selectRows(rows,{}),rows.slice(0,3));
 assert.deepEqual(selectRows(rows,{start:'31',limit:'30'}),rows.slice(30));
 assert.deepEqual(selectRows(rows,{start:'60',limit:'1'}),[rows[59]]);
});
test('range rejects overflow, fractions, malformed and non-positive values',()=>{
 const rows=Array.from({length:60},(_,i)=>({id:String(i),feedback:'text'}));
 for(const options of [{start:'0'},{start:'61'},{start:'60',limit:'2'},{start:'1.5'},{start:'1x'},{start:''},{limit:'0'},{limit:'61'},{limit:'2.5'},{limit:'1e1'},{start:'-1'}]) assert.throws(()=>selectRows(rows,options),/range|integer/);
});
test('duplicate and malformed inputs rejected even outside selected range',()=>{
 const rows=Array.from({length:60},(_,i)=>({id:String(i),feedback:'text'}));
 rows[59].id=rows[58].id; assert.throws(()=>selectRows(rows,{limit:'1'}),/Duplicate/);
 rows[59]={id:'59',feedback:'x',reference:'yes'};assert.throws(()=>selectRows(rows,{limit:'1'}),/contract/);
});
const {configureArtifact,buildMessages}=require('../scripts/lmstudio_reasoning_benchmark.cjs');
const dsHash='d0f0b016bb20e4e9f4978ef82123240a7f31750f675154e469664b8f292a0f1a';
const ms3Hash='9829cc54f2105c79499b783e81fbb476b610e91ee9373cc68334c267e49f6bbc';
const ms4Hash='c83250ae5b88eb5d0e8702d02b495c6f0c305527dfc9ad915b89f800f49f13b0';
const artifact=(hash,t)=>({artifact_sha256:hash,metadata:{'tokenizer.chat_template':t}});
test('DeepSeek verified artifact keeps native prefix and uses user instructions',()=>{
 const t="{% if add_generation_prompt %}{{'<｜Assistant｜><think>\\n'}}{% endif %}";
 const a=artifact(dsHash,t),options={family:'deepseek-r1-distill-qwen32b',thinking:'native'};
 const x=configureArtifact(a,options);assert.equal(x.template,t);assert.equal(x.instructionRole,'user');
 assert.deepEqual(buildMessages('RUBRIC',{type:'object'},'feedback',true,x.instructionRole),[{role:'user',content:'RUBRIC\n\n'+JSON.stringify({feedback:'feedback'})}]);
 assert.throws(()=>configureArtifact(a,{...options,thinking:'off'}),/native/);
 assert.throws(()=>configureArtifact(a,{...options,effort:'high'}),/effort/);
 assert.throws(()=>configureArtifact(artifact('wrong',t),options),/verified/);
});
test('Mistral3 effort is N/A and reasoning parsing disabled',()=>{
 const t='[INST]user[/INST]',a=artifact(ms3Hash,t),options={family:'mistral-small3.2',thinking:'not_applicable'};
 const x=configureArtifact(a,options);assert.equal(x.template,t);assert.deepEqual(x.parsing,{enabled:false});
 assert.throws(()=>configureArtifact(a,{...options,thinking:'on'}),/not_applicable/);
 assert.throws(()=>configureArtifact(a,{...options,effort:'low'}),/effort/);
});
test('Mistral4 none/high use verified settings tokens and parser',()=>{
 const t="[INST][/INST][THINK][/THINK][MODEL_SETTINGS]reasoning_effort[/MODEL_SETTINGS]";
 for(const [thinking,effort] of [['on','high'],['off','none']]) {
  const x=configureArtifact(artifact(ms4Hash,t),{family:'mistral-small4',thinking,effort});
  assert.equal(x.template,"{%- set reasoning_effort = '"+effort+"' %}\n"+t);
  assert.deepEqual(x.parsing,{enabled:true,startString:'[THINK]',endString:'[/THINK]'});
 }
 assert.throws(()=>configureArtifact(artifact(ms4Hash,t),{family:'mistral-small4',thinking:'on',effort:'none'}),/requires/);
 assert.throws(()=>configureArtifact(artifact(ms4Hash,'[INST]'),{family:'mistral-small4',thinking:'on',effort:'high'}),/template/);
});
test('legacy artifact configuration and messages remain identical',()=>{
 const a=artifact('legacy',qwen);
 assert.deepEqual(configureArtifact(a,{thinking:'on'}),{...configureThinking(qwen,'on'),instructionRole:'system',family:'template-controlled'});
 const schema={type:'object'};
 assert.deepEqual(buildMessages('policy',schema,'feedback',false,'system'),[{role:'system',content:'policy\nReturn raw JSON only, with no Markdown code fences and no text outside the JSON object. Output must satisfy this JSON schema: '+JSON.stringify(schema)},{role:'user',content:JSON.stringify({feedback:'feedback'})}]);
 assert.throws(()=>configureArtifact(a,{family:'made-up',thinking:'on'}),/family/);
});

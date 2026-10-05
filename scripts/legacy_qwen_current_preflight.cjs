// Usage: node scripts/legacy_qwen_current_preflight.cjs CONFIG smoke|development P0|P1|P2 fresh1|fresh2|fresh3
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=process.cwd(), a=require(root+'/scripts/legacy_qwen_repeat_admission.cjs'),s=require(root+'/scripts/small_local_repeat_admission.cjs'),h=require(root+'/scripts/local_host_admission.cjs');
(async()=>{
 const {plan,sha256}=a.verifyPlan(),id=process.argv[2],pass=process.argv[5]||'fresh1',condition=process.argv[4]||'P2',stage=process.argv[3]||'smoke',c=plan.configurations[id],phase=`${id}/${pass}/${condition}`;
 const predecessor=a.checkPredecessor(plan,id,pass,condition,stage),p=a.stagePaths(id,pass,condition,stage);
 assert(!fs.existsSync(p.claim)&&!fs.existsSync(p.completion),'Stage already attempted');
 const host=h.currentHost(),runtime=await s.realRuntime(plan,c),selected=a.stageRows(plan,id,condition,'development'),measured=[];
 for(const row of selected)measured.push(await a.verifyRequestRuntime(runtime,c,row));
 const stamp=new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d+Z/,'Z');
 const routeId=id.replace(/[^a-zA-Z0-9_-]/g,'_');
 const dir=`results/route-audits/${routeId}-${condition}-${stage}-${stamp}`;fs.mkdirSync(dir,{recursive:true});
 const response=await fetch('https://openrouter.ai/api/v1/models');assert.equal(response.status,200);const raw=await response.text(),body=JSON.parse(raw);assert(body.data.length>=100);
 const families={'Qwen3-0.6B':'qwen306b','Qwen3-1.7B':'qwen317b','Qwen3.5-4B':'qwen354b'};
 const matches=body.data.filter(m=>Object.values(families).some(f=>[m.id,m.name,m.canonical_slug,m.hugging_face_id].some(v=>typeof v==='string'&&v.toLowerCase().replace(/[^a-z0-9]/g,'').includes(f))));assert.equal(matches.length,0,'Hosted route requires review');
 fs.writeFileSync(dir+'/catalog.raw.json',raw,{flag:'wx'});
 const audit={source:'https://openrouter.ai/api/v1/models',retrieved_utc:new Date().toISOString(),http_status:200,raw_sha256:s.hash(raw),model_count:body.data.length,catalog_matches:matches,exact_family_decisions:Object.fromEntries(Object.keys(families).map(f=>[f,{catalog_id_found:false,matching_ids:[],endpoint_query:'not_applicable_no_catalog_id'}]))};
 fs.writeFileSync(dir+'/catalog-audit.json',JSON.stringify(audit,null,2)+'\n',{flag:'wx'});
 const preflightFile=`results/repeatability-v1/legacy-qwen-fresh3-v1/${id}-${condition}-${stage}-preflight-${stamp}.json`;
 fs.writeFileSync(preflightFile,JSON.stringify({phase,stage,host,runtime:runtime.attestation,measurements:measured},null,2)+'\n',{flag:'wx'});
 const receipt={kind:'root-reviewed-legacy-qwen-stage-v1',approved:true,reviewer:'/root',reviewed_utc:new Date().toISOString(),plan_sha256:sha256,controller_sha256:s.hashFile(root+'/scripts/legacy_qwen_repeat_admission.cjs'),phase,stage,model_identifier:c.model_identifier,artifact_sha256:c.artifact_sha256,cache_policy:{enabled:true,size_limit_mib:8192},reference_labels_read:false,exact_openrouter_route_absent:true,route_catalog_file:dir+'/catalog-audit.json',route_catalog_sha256:s.hashFile(dir+'/catalog-audit.json'),route_checked_utc:audit.retrieved_utc,gpu_available:true,capacity_reviewed:true,capacity_evidence:host,preflight_file:preflightFile,preflight_sha256:s.hashFile(preflightFile),runtime_token_preflight:{phase,model_identifier:c.model_identifier,artifact_sha256:c.artifact_sha256,context:8192,output_reserve:c.output_reserve,request_count:60,requests_sha256:s.hash(JSON.stringify(c.conditions[condition].requests)),observed_preflight_sha256:s.hash(JSON.stringify(measured)),observed_instance_reference:runtime.instance}};
 if(stage==='development')receipt.smoke_inspection_sha256=predecessor;
 a.checkReceipt(receipt,sha256,phase,stage,c,predecessor);fs.mkdirSync(p.folder,{recursive:true});const out=path.join(p.folder,`${stage}.root-review-${stamp}.json`);fs.writeFileSync(out,JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({receipt:out,phase,stage,requests:measured.length,instance:runtime.instance,routeModels:body.data.length,host:{ac:host.ac_power,lid:host.lid_open,memory:host.memory_free_percent}}));
})().catch(e=>{console.error(e.stack);process.exitCode=1});

const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'public-site/disputed-reviews.js'),'utf8');
const data=JSON.parse(fs.readFileSync(path.join(root,'public-site/disputed-reviews-v1.json'),'utf8'));
const context={document:{getElementById:()=>null},location:{href:'https://example.test/?cohort=all&run=example#review-evidence'},URL,console};
context.globalThis=context;
vm.runInNewContext(source,context);
const api=context.BenchmarkDisputedReviews;

test('review evidence covers exactly 60 comments and seven source-bound first passes',()=>{
  assert.equal(api.validate(data),data);
  assert.equal(data.reviews.length,60);
  assert.equal(data.models.length,7);
  assert.equal(data.models.at(-1).id,'perplexity-decider-native-fresh1-p0');
  assert.ok(data.reviews.every(review=>review.answers.length===7));
  assert.ok(data.models.every(model=>model.condition==='P0'&&model.repeat_pass==='fresh1'));
});

test('review controls select source-grounded difficult subsets without hiding all 60',()=>{
  assert.equal(api.filterReviews(data).length,60);
  const any=api.filterReviews(data,{subset:'any'});
  assert.ok(any.length<60&&any.length>0);
  assert.ok(any.every(review=>review.models_with_any_mismatch>0));
  const testimonial=api.filterReviews(data,{subset:'testimonial'});
  assert.equal(testimonial.length,data.testimonial_reference_positive.count);
  assert.ok(testimonial.every(review=>review.reference.testimonial_potential==='yes'));
  const offTopic=api.filterReviews(data,{subset:'off-topic'});
  assert.deepEqual([...offTopic.map(review=>review.id)],['DEV-029']);
  assert.deepEqual([...api.filterReviews(data,{search:'tiny portions'}).map(review=>review.id)],['DEV-029']);
  const model=data.models[0].id;
  const field='testimonial_potential';
  const matching=api.filterReviews(data,{model,field});
  assert.equal(matching.length,data.reviews.filter(review=>review.answers.find(answer=>answer.model_id===model).different_fields.includes(field)).length);
});

test('hashes, answer differences and review links cannot silently drift',()=>{
  const altered=structuredClone(data);
  altered.reviews[0].answers[0].different_fields=[];
  assert.throws(()=>api.validate(altered),/inconsistent/);
  const hash=structuredClone(data);
  hash.source_sha256['public-site/supplemental-decision-runs-v1.json']='bad';
  assert.throws(()=>api.validate(hash),/source header/);
  assert.equal(api.reviewUrl('DEV-029'),'/\?cohort=all&run=example&review=DEV-029#review-evidence');
});

test('the review panel states its limited cohort and links original evidence',()=>{
  const html=fs.readFileSync(path.join(root,'public-site/explore.html'),'utf8');
  assert.match(html,/seven native decision models/i);
  assert.match(html,/does not combine repeat passes or cover every model/i);
  assert.match(html,/id="disputed-search"/);
  assert.match(html,/id="disputed-field"/);
  assert.match(html,/disputed-reviews-v1\.json/);
  assert.match(source,/Run detail →/);
});

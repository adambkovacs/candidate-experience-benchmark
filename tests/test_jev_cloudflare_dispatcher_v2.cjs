const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { spawnSync } = require('node:child_process');

const source = fs.readFileSync(path.join(__dirname, '../scripts/jev_cloudflare_dispatcher_v2.js'), 'utf8');
const dispatchOne = eval(source);
const directory = 'results/jev-cloudflare-native-v1/fresh1/P0/smoke';
const attempt = '123e4567-e89b-12d3-a456-426614174000';
const accountId = 'a'.repeat(32);
const ready = {
  kind: 'jev-cloudflare-native-execution-v2-request', model: 'typesafe/jev',
  method: 'POST', path: '/accounts/{ACCOUNT_ID}/ai/run',
  attempt_id: attempt, id: 'DEV-001',
  body: { model: 'typesafe/jev', input: { state: {}, questions: {} } },
};

function harness({ outer = { content: [{ type: 'text', text: '{"status":200}' }] },
                   prepareExit = 0, throwPost = false, throwSave = false,
                   prepared = ready } = {}) {
  const events = [];
  const tools = {
    exec_command: async ({ cmd }) => {
      assert.ok(cmd.includes('scripts/jev_cloudflare_native_execution_v2.py'));
      if (cmd.includes(' prepare ')) {
        assert.ok(cmd.includes('--account-id ' + accountId));
        events.push('prepare');
        return { exit_code: prepareExit, output: prepareExit ? 'blocked' : JSON.stringify(prepared) };
      }
      if (cmd.includes(' mark-unknown ')) {
        events.push('mark-unknown');
        return { exit_code: 0, output: 'outcome_unknown_no_replay' };
      }
      if (cmd.includes(' record-timing ')) {
        assert.ok(cmd.includes('--start-ms '));
        assert.ok(cmd.includes('--end-ms '));
        assert.ok(cmd.includes('--duration-ms '));
        assert.ok(cmd.includes('--clock '));
        const outcome = cmd.match(/--outcome ([a-z_]+)/)?.[1];
        assert.ok(outcome);
        events.push('timing:' + outcome);
        return { exit_code: 0, output: 'timing saved' };
      }
      assert.ok(cmd.includes(' consume '));
      assert.ok(events.includes('save-original') || events.includes('mark-unknown'));
      events.push('consume');
      return { exit_code: 0, output: JSON.stringify({ id: prepared.id, status: 'valid' }) };
    },
    mcp__codex_apps__cloudflare_execute: async ({ code }) => {
      assert.ok(code.includes('"/accounts/' + accountId + '/ai/run"'));
      assert.ok(code.includes('"model":"typesafe/jev"'));
      events.push('post');
      if (throwPost) throw new Error('ambiguous tool exception');
      return outer;
    },
    apply_patch: async (patch) => {
      assert.ok(patch.includes(prepared.attempt_id + '.tool-result.original.json'));
      assert.ok(patch.includes(JSON.stringify(outer)));
      events.push('save-original');
      if (throwSave) throw new Error('save failed');
      return {};
    },
  };
  return { events, run: () => dispatchOne({ tools,
    store: (key) => events.push(key.startsWith('jev_timing_') ? 'store-timing' : 'store-recovery'),
    text: () => events.push('done'), directory, accountId,
    cwd: '/tmp/jev-test' }) };
}

test('original result is saved before parser; exactly one POST', async () => {
  const h = harness();
  await h.run();
  assert.deepEqual(h.events, ['prepare', 'post', 'store-timing', 'store-recovery',
    'save-original', 'timing:outer_returned_original_saved', 'consume', 'done']);
});

test('prepare rejection makes no POST', async () => {
  const h = harness({ prepareExit: 1 });
  await assert.rejects(h.run(), /No single safe Jev request/);
  assert.deepEqual(h.events, ['prepare']);
});

test('ambiguous tool exception closes unknown without retry', async () => {
  const h = harness({ throwPost: true });
  await h.run();
  assert.deepEqual(h.events, ['prepare', 'post', 'store-timing',
    'timing:outer_tool_exception', 'mark-unknown', 'consume', 'done']);
});

test('failed durable save retains recovery store and prevents consume', async () => {
  const h = harness({ throwSave: true });
  await assert.rejects(h.run(), /save failed; timing saved/);
  assert.deepEqual(h.events, ['prepare', 'post', 'store-timing', 'store-recovery',
    'save-original', 'timing:outer_returned_original_save_failed']);
});

test('real v2 prepared request passes dispatcher validation before one POST', async () => {
  const script = String.raw`
import json, sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, 'scripts')
import clef_native_remaining_cloudflare_v1 as clef
import jev_cloudflare_native_execution_v2 as execution
import jev_cloudflare_native_preparation_v1 as prep
account = 'a' * 32
page = (b'<html><h1>typesafe/jev</h1><p>Third-party Zero data retention</p>'
        b'<h2>Model Info</h2><p>Context Window &#x2197; 32,000 tokens</p>'
        b'<h2>Pricing</h2><p>Input (per 1M tokens) $0.042</p>'
        b'<p>Output (per 1M tokens) $0.00</p>'
        b'<p>Cached input (per 1M tokens) $0.00</p><h2>Usage</h2></html>')
with TemporaryDirectory() as temp:
    root = Path(temp)
    base = root / 'jev'
    authority = root / 'authority.jsonl'
    authority.write_text(json.dumps(clef.initial_header(clef.digest(clef.PLAN), 'b'*64))+'\n')
    plan, plan_hash = prep.checked_plan(execution.PLAN)
    price_hash = prep.sha(prep.canonical(execution.price_snapshot(page)))
    grant = execution.grant_value('fresh1','P0','smoke',account,plan_hash,
                                  prep.sha(authority.read_bytes()),price_hash,None,None)
    grant_path = root / 'grant.json'
    grant_path.write_text(json.dumps(grant)+'\n')
    execution.admit('fresh1','P0','smoke',grant_path,account,
                    authority_path=authority,base=base,
                    fetcher=lambda _: page,price_evidence_dir=root/'price-observations')
    directory = execution.stage_dir('fresh1','P0','smoke',base)
    print(json.dumps(execution.prepare(directory,account,base=base,
                                      authority_path=authority)))
`;
  const generated = spawnSync('python3', ['-c', script], {
    cwd: path.join(__dirname, '..'), encoding: 'utf8', timeout: 30000,
  });
  assert.equal(generated.status, 0, generated.stderr);
  const prepared = JSON.parse(generated.stdout.trim());
  assert.equal(prepared.kind, 'jev-cloudflare-native-execution-v2-request');
  assert.equal(prepared.id, 'DEV-001');
  const h = harness({ prepared });
  await h.run();
  assert.equal(h.events.filter((event) => event === 'post').length, 1);
});

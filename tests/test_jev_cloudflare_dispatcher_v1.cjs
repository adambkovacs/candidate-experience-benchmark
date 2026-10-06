const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../scripts/jev_cloudflare_dispatcher_v1.js'), 'utf8');
const dispatchOne = eval(source);
const directory = 'results/jev-cloudflare-native-v1/fresh1/P0/smoke';
const attempt = '123e4567-e89b-12d3-a456-426614174000';
const accountId = 'a'.repeat(32);
const ready = {
  kind: 'jev-cloudflare-native-execution-v1-request', model: 'typesafe/jev',
  method: 'POST', path: '/accounts/{ACCOUNT_ID}/ai/run',
  attempt_id: attempt, id: 'DEV-001',
  body: { model: 'typesafe/jev', input: { state: {}, questions: {} } },
};

function harness({ outer = { content: [{ type: 'text', text: '{"status":200}' }] },
                   prepareExit = 0, throwPost = false, throwSave = false } = {}) {
  const events = [];
  const tools = {
    exec_command: async ({ cmd }) => {
      if (cmd.includes(' prepare ')) {
        assert.ok(cmd.includes('--account-id ' + accountId));
        events.push('prepare');
        return { exit_code: prepareExit, output: prepareExit ? 'blocked' : JSON.stringify(ready) };
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
      return { exit_code: 0, output: JSON.stringify({ id: ready.id, status: 'valid' }) };
    },
    mcp__codex_apps__cloudflare_execute: async ({ code }) => {
      assert.ok(code.includes('"/accounts/' + accountId + '/ai/run"'));
      assert.ok(code.includes('"model":"typesafe/jev"'));
      events.push('post');
      if (throwPost) throw new Error('ambiguous tool exception');
      return outer;
    },
    apply_patch: async (patch) => {
      assert.ok(patch.includes(attempt + '.tool-result.original.json'));
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

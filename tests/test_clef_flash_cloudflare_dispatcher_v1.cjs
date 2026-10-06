const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../scripts/clef_flash_cloudflare_dispatcher_v1.js'), 'utf8');
const dispatchOne = eval(source);
const directory = 'results/clef-native-v1/clef-flash/fresh3/P0/development-exact58-cloudflare-v1/app-bridge';
const attempt = '123e4567-e89b-12d3-a456-426614174000';
const ready = {
  kind: 'clef-connected-app-bridge-v1-request', model: 'clef-flash', method: 'POST',
  path: '/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/clef-flash',
  attempt_id: attempt, id: 'DEV-003', body: { model: 'clef-flash', state: 'sample', questions: {} },
};

function harness(outer, consumeExit = 0, prepareExit = 0, saveFails = false) {
  const events = [];
  let stored;
  const tools = {
    exec_command: async ({ cmd }) => {
      if (cmd.includes(' prepare ')) {
        assert.ok(cmd.includes('--account-id ' + 'a'.repeat(32)));
        events.push('prepare');
        return { exit_code: prepareExit, output: prepareExit ? 'account mismatch' : JSON.stringify(ready) };
      }
      if (cmd.includes(' record-timing ')) {
        assert.ok(cmd.includes('--start-ms '));
        assert.ok(cmd.includes('--end-ms '));
        assert.ok(cmd.includes('--duration-ms '));
        assert.ok(cmd.includes('--clock '));
        events.push('record-timing');
        return { exit_code: 0, output: 'timing saved' };
      }
      assert.ok(cmd.includes(' consume '));
      assert.ok(stored, 'original result must be durably saved before consume');
      events.push('consume');
      return { exit_code: consumeExit, output: consumeExit ? 'ambiguous blocks' : 'response saved' };
    },
    mcp__codex_apps__cloudflare_execute: async ({ code }) => {
      assert.ok(code.includes('"/accounts/' + 'a'.repeat(32) + '/ai/run/@cf/cloudflare/clef-flash"'));
      events.push('post');
      if (outer instanceof Error) throw outer;
      return outer;
    },
    apply_patch: async (patch) => {
      assert.ok(patch.includes(attempt + '.tool-result.original.json'));
      assert.ok(patch.includes(JSON.stringify(outer)));
      if (saveFails) throw new Error('synthetic disk failure');
      events.push('save-original');
      stored = patch;
      return {};
    },
  };
  return { events, run: () => dispatchOne({ tools,
    store: (key) => events.push(key.startsWith('clef_flash_timing_') ? 'store-timing' : 'store-recovery'),
    text: () => events.push('done'), directory, accountId: 'a'.repeat(32),
    cwd: '/tmp/clef-test' }) };
}

test('missing optional isError is saved before the consumer validates it', async () => {
  const h = harness({ content: [{ type: 'text', text: '{"status":200}' }] });
  await h.run();
  assert.deepEqual(h.events, ['prepare', 'post', 'store-timing', 'store-recovery', 'save-original', 'record-timing', 'consume', 'done']);
});

test('account-binding rejection prevents POST', async () => {
  const h = harness({ content: [] }, 0, 1);
  await assert.rejects(h.run(), /No single safe request: account mismatch/);
  assert.deepEqual(h.events, ['prepare']);
});

test('multiple blocks or error remain saved and never trigger a second POST', async () => {
  for (const outer of [
    { isError: true, content: [{ type: 'text', text: 'failed' }] },
    { content: [{ type: 'text', text: 'first' }, { type: 'text', text: 'second' }] },
  ]) {
    const h = harness(outer, 1);
    await assert.rejects(h.run(), /Original result saved; consume failed/);
    assert.deepEqual(h.events, ['prepare', 'post', 'store-timing', 'store-recovery', 'save-original', 'record-timing', 'consume']);
  }
});

test('outer exception records observed timing and does not retry', async () => {
  const h = harness(new Error('synthetic MCP loss'));
  await assert.rejects(h.run(), /outcome unknown; timing saved; do not replay/);
  assert.deepEqual(h.events, ['prepare', 'post', 'store-timing', 'record-timing']);
});

test('original-save failure records timing without consuming or retrying', async () => {
  const h = harness({ content: [{ type: 'text', text: '{}' }] }, 0, 0, true);
  await assert.rejects(h.run(), /result save failed; timing saved; do not replay/);
  assert.deepEqual(h.events, ['prepare', 'post', 'store-timing', 'store-recovery', 'record-timing']);
});

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../scripts/clef_cloudflare_dispatcher_v1.js'), 'utf8');
const dispatchOne = eval(source);
const directory = 'results/clef-native-v1/clef/fresh1/P2/development-suffix-v1/app-bridge';
const attempt = '123e4567-e89b-12d3-a456-426614174000';
const ready = {
  kind: 'clef-connected-app-bridge-v1-request', model: 'clef', method: 'POST',
  path: '/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/clef',
  attempt_id: attempt, id: 'DEV-002', body: { model: 'clef', state: 'sample', questions: {} },
};

function harness(outer, consumeExit = 0, prepareExit = 0) {
  const events = [];
  let stored;
  const tools = {
    exec_command: async ({ cmd }) => {
      if (cmd.includes(' prepare ')) {
        assert.ok(cmd.includes('--account-id ' + 'a'.repeat(32)));
        events.push('prepare');
        return { exit_code: prepareExit, output: prepareExit ? 'account mismatch' : JSON.stringify(ready) };
      }
      assert.ok(cmd.includes(' consume '));
      assert.ok(stored, 'original result must be durably saved before consume');
      events.push('consume');
      return { exit_code: consumeExit, output: consumeExit ? 'ambiguous blocks' : 'response saved' };
    },
    mcp__codex_apps__cloudflare_execute: async ({ code }) => {
      assert.ok(code.includes('"/accounts/' + 'a'.repeat(32) + '/ai/run/@cf/cloudflare/clef"'));
      events.push('post');
      return outer;
    },
    apply_patch: async (patch) => {
      assert.ok(patch.includes(attempt + '.tool-result.original.json'));
      assert.ok(patch.includes(JSON.stringify(outer)));
      events.push('save-original');
      stored = patch;
      return {};
    },
  };
  return { events, run: () => dispatchOne({ tools, store: () => events.push('store-recovery'),
    text: () => events.push('done'), directory, accountId: 'a'.repeat(32),
    cwd: '/tmp/clef-test' }) };
}

test('missing optional isError is saved before the consumer validates it', async () => {
  const h = harness({ content: [{ type: 'text', text: '{"status":200}' }] });
  await h.run();
  assert.deepEqual(h.events, ['prepare', 'post', 'store-recovery', 'save-original', 'consume', 'done']);
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
    assert.deepEqual(h.events, ['prepare', 'post', 'store-recovery', 'save-original', 'consume']);
  }
});

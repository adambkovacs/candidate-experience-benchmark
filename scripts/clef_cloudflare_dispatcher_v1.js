(async function dispatchOne({ tools, store, text, directory, accountId, cwd }) {
  // This source is loaded verbatim into functions.exec after its SHA is checked.
  // Each invocation operates on one durable request and makes at most one POST.
  if (!/^results\/[A-Za-z0-9/._-]+\/app-bridge$/.test(directory) ||
      directory.includes('..') ||
      !/^[a-f0-9]{32}$/.test(accountId) ||
      !/^\/[A-Za-z0-9/._-]+$/.test(cwd)) {
    throw new Error('Unpinned dispatcher location or account');
  }
  const picked = await tools.exec_command({
    cmd: `PYTHONPATH=scripts python3 scripts/clef_cloudflare_operator_v1.py prepare ${directory} --account-id ${accountId}`,
    workdir: cwd, max_output_tokens: 12000,
  });
  if (picked.exit_code !== 0) throw new Error('No single safe request: ' + picked.output);
  const ready = JSON.parse(picked.output.trim());
  if (ready.model !== 'clef' || ready.method !== 'POST' ||
      ready.path !== '/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/clef' ||
      !/^[a-f0-9-]{36}$/.test(ready.attempt_id)) {
    throw new Error('Prepared request differs; do not dispatch');
  }
  const outer = await tools.mcp__codex_apps__cloudflare_execute({
    account_id: accountId,
    code: `async () => cloudflare.request({method:"POST",path:"/accounts/${accountId}/ai/run/@cf/cloudflare/clef",body:${JSON.stringify(ready.body)}})`,
  });
  // No result-shape assertion may precede this durable save. Store additionally
  // permits recovery if the filesystem write itself fails after the POST.
  store('clef_outer_' + ready.attempt_id, outer);
  const originalJson = JSON.stringify(outer);
  await tools.apply_patch(`*** Begin Patch\n*** Add File: ${cwd}/${directory}/${ready.attempt_id}.tool-result.original.json\n+${originalJson}\n*** End Patch`);
  const submitted = await tools.exec_command({
    cmd: `PYTHONPATH=scripts python3 scripts/clef_cloudflare_operator_v1.py consume ${directory}/${ready.attempt_id}.request.json`,
    workdir: cwd, max_output_tokens: 500,
  });
  if (submitted.exit_code !== 0) {
    throw new Error('Original result saved; consume failed without replay: ' + submitted.output);
  }
  text({ id: ready.id, attempt_id: ready.attempt_id, original_saved: true,
         response_saved: true });
  return ready.id;
})

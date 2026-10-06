(async function dispatchOne({ tools, store, text, directory, accountId, cwd }) {
  // Load this source verbatim into functions.exec only after checking its SHA.
  // A dispatch claim is durable before the single POST. Unknowns are never replayed.
  if (!/^results\/jev-cloudflare-native-v1\/fresh[123]\/P[012]\/(smoke|development)$/.test(directory) ||
      !/^[a-f0-9]{32}$/.test(accountId) ||
      !/^\/[A-Za-z0-9/._-]+$/.test(cwd) || cwd.includes('..')) {
    throw new Error('Unpinned Jev stage or account');
  }
  const picked = await tools.exec_command({
    cmd: `PYTHONPATH=scripts python3 scripts/jev_cloudflare_native_execution_v1.py prepare ${directory} --account-id ${accountId}`,
    workdir: cwd, max_output_tokens: 12000,
  });
  if (picked.exit_code !== 0) throw new Error('No single safe Jev request: ' + picked.output);
  const ready = JSON.parse(picked.output.trim());
  if (ready.kind !== 'jev-cloudflare-native-execution-v1-request' ||
      ready.model !== 'typesafe/jev' || ready.method !== 'POST' ||
      ready.path !== '/accounts/{ACCOUNT_ID}/ai/run' ||
      ready.body?.model !== 'typesafe/jev' ||
      !/^[a-f0-9-]{36}$/.test(ready.attempt_id)) {
    throw new Error('Prepared Jev request differs; do not dispatch');
  }
  let outer;
  try {
    outer = await tools.mcp__codex_apps__cloudflare_execute({
      account_id: accountId,
      code: `async () => cloudflare.request({method:"POST",path:"/accounts/${accountId}/ai/run",body:${JSON.stringify(ready.body)}})`,
    });
  } catch (_) {
    const failed = await tools.exec_command({
      cmd: `PYTHONPATH=scripts python3 scripts/jev_cloudflare_native_execution_v1.py mark-unknown ${directory}/app-bridge/${ready.attempt_id}.request.json`,
      workdir: cwd, max_output_tokens: 500,
    });
    if (failed.exit_code !== 0) throw new Error('Tool outcome unknown; marker failed; do not replay');
    const closed = await tools.exec_command({
      cmd: `PYTHONPATH=scripts python3 scripts/jev_cloudflare_native_execution_v1.py consume ${directory}/app-bridge/${ready.attempt_id}.request.json`,
      workdir: cwd, max_output_tokens: 500,
    });
    if (closed.exit_code !== 0) throw new Error('Tool outcome unknown; closure failed; do not replay');
    text(JSON.parse(closed.output.trim()));
    return ready.id;
  }
  // Save the untouched outer result before inspecting its shape or consuming it.
  store('jev_outer_' + ready.attempt_id, outer);
  const originalJson = JSON.stringify(outer);
  await tools.apply_patch(`*** Begin Patch\n*** Add File: ${cwd}/${directory}/app-bridge/${ready.attempt_id}.tool-result.original.json\n+${originalJson}\n*** End Patch`);
  const submitted = await tools.exec_command({
    cmd: `PYTHONPATH=scripts python3 scripts/jev_cloudflare_native_execution_v1.py consume ${directory}/app-bridge/${ready.attempt_id}.request.json`,
    workdir: cwd, max_output_tokens: 500,
  });
  if (submitted.exit_code !== 0) {
    throw new Error('Original Jev result saved; consume failed without replay: ' + submitted.output);
  }
  text(JSON.parse(submitted.output.trim()));
  return ready.id;
})

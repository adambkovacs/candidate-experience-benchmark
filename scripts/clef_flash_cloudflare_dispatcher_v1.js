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
  if (ready.model !== 'clef-flash' || ready.method !== 'POST' ||
      ready.path !== '/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/clef-flash' ||
      !/^[a-f0-9-]{36}$/.test(ready.attempt_id)) {
    throw new Error('Prepared request differs; do not dispatch');
  }
  const requestFile = `${directory}/${ready.attempt_id}.request.json`;
  const monotonic = typeof performance !== 'undefined' && typeof performance.now === 'function';
  const clock = monotonic ? 'performance_now_monotonic' : 'date_now_wall';
  const startMs = Date.now();
  const startTick = monotonic ? performance.now() : startMs;
  let outer;
  let toolException = false;
  try {
    outer = await tools.mcp__codex_apps__cloudflare_execute({
      account_id: accountId,
      code: `async () => cloudflare.request({method:"POST",path:"/accounts/${accountId}/ai/run/@cf/cloudflare/clef-flash",body:${JSON.stringify(ready.body)}})`,
    });
  } catch (_) {
    toolException = true;
  }
  const endMs = Date.now();
  const endTick = monotonic ? performance.now() : endMs;
  const durationMs = Math.max(0, Math.round(endTick - startTick));
  const timing = { startMs, endMs, durationMs, clock };
  store('clef_flash_timing_' + ready.attempt_id, timing);
  const recordTiming = async (outcome) => {
    const saved = await tools.exec_command({
      cmd: `PYTHONPATH=scripts python3 scripts/clef_flash_p0_exact58_cloudflare_v1.py record-timing --request ${requestFile} --start-ms ${startMs} --end-ms ${endMs} --duration-ms ${durationMs} --clock ${clock} --outcome ${outcome}`,
      workdir: cwd, max_output_tokens: 500,
    });
    if (saved.exit_code !== 0) throw new Error('Client timing not saved; do not replay: ' + saved.output);
  };
  if (toolException) {
    await recordTiming('outer_tool_exception');
    throw new Error('Flash outer tool outcome unknown; timing saved; do not replay');
  }
  // No result-shape assertion may precede this durable save. Store additionally
  // permits recovery if the filesystem write itself fails after the POST.
  store('clef_flash_outer_' + ready.attempt_id, outer);
  try {
    const originalJson = JSON.stringify(outer);
    if (originalJson === undefined) throw new Error('Unserializable outer result');
    await tools.apply_patch(`*** Begin Patch\n*** Add File: ${cwd}/${directory}/${ready.attempt_id}.tool-result.original.json\n+${originalJson}\n*** End Patch`);
  } catch (_) {
    await recordTiming('outer_returned_original_save_failed');
    throw new Error('Original Flash result save failed; timing saved; do not replay');
  }
  await recordTiming('outer_returned_original_saved');
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

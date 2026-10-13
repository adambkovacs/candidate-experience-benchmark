/* Readable labels for runs and money, shared by every panel. Loads before the panel scripts.
   BM_LABEL.model('claude-opus-5-5') -> 'Opus 5.5'
   BM_LABEL.run(run) -> 'Opus 5.5, high effort, Claude subscription'
   BM_LABEL.usd(0.00589092) -> '$0.0059'   BM_LABEL.count(1551) -> '1,551' */
(() => {
  'use strict';
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  const NAMED = [
    [/^jev-?1\.13/, () => 'Jev 1.13'], [/typesafe-jev113/, () => 'Jev 1.13'], [/^jev/, () => 'Jev'],
    [/^solar-decide/, () => 'Solar Decide'], [/^clef-flash/, () => 'Clef Flash'], [/^clef/, () => 'Clef'],
    [/pplx-decider|perplexity-decider/, () => 'Perplexity Decider 27B'], [/luna-decisions/, () => 'Luna Decisions'],
    [/^tev1-4b/, () => 'Tev 1 4B'], [/^d1$|liquid-d1/, () => 'Liquid d1'], [/^kev-4b|^kev/, () => 'Kev 4B'],
    [/^laya[- ](\w+)/, m => `Laya ${cap(m[1])}`], [/^laya/, () => 'Laya'],
    [/^openjev[- ]qwen3\.5-0\.8b|alex-openjev08/, () => 'Alex OpenJev 0.8B'], [/^openjev[- ]qwen3\.5-4b|alex-openjev4b/, () => 'Alex OpenJev 4B'],
    [/^openjev-?([a-z-]*)/, m => `OpenJev${m[1] ? ' ' + m[1].replace(/-/g, ' ').replace(/^0\.1$/, '') : ''}`.trim()],
    [/^semif-?([a-z0-9-]*)/, m => `SemIf${m[1] ? ' ' + m[1].replace(/-/g, ' ') : ''}`],
    [/^anyjev/, () => 'AnyJev'], [/regex/, () => 'Rules baseline'],
    [/^claude-(opus|sonnet|haiku|fable)-(\d+)(?:-(\d)(?=-|$))?/, m => `${cap(m[1])} ${m[2]}${m[3] ? '.' + m[3] : ''}`],
    [/^gpt-([\d.]+)-(\w+)/, m => `GPT-${m[1]} ${cap(m[2])}`],
    [/^gemini-([\d.]+)-(pro|flash)/, m => `Gemini ${m[1]} ${cap(m[2])}`],
    [/^diffusiongemma-(\d+b)/, m => `DiffusionGemma ${m[1].toUpperCase()}`],
    [/^gemma-?4[- ](e?\d+b)/, m => `Gemma 4 ${m[1].toUpperCase()}`],
    [/^qwen(3(?:\.\d)?)-?([\d.]+b)/, m => `Qwen${m[1]} ${m[2].toUpperCase()}`],
    [/^deepseek-v([\d.]+)-flash/, m => `DeepSeek V${m[1]} Flash`],
    [/^mistral-small-([\d.]+)-(\d+b)/, m => `Mistral Small ${m[1]} ${m[2].toUpperCase()}`], [/^mistral-small/, () => 'Mistral Small'],
  ];
  function model(slug) {
    const s = String(slug || '').toLowerCase().replace(/^@cf\//, '').replace(/^[\w.-]+\/(?=\S)/, '');
    for (const [re, f] of NAMED) { const m = re.exec(s); if (m) return f(m); }
    return cap(s.replace(/[-_]+/g, ' '));
  }
  // Effort words a reader knows; anything else (runtime notes) stays in the slug line.
  function effort(e, slug) {
    const v = String(e || '').toLowerCase();
    if (/^(low|medium|high|xhigh|max)$/.test(v)) return `${v} effort`;
    if (v === 'on' || /thinking-on/.test(slug)) return 'thinking on';
    if (v === 'off' || /thinking-off|nonthinking/.test(slug)) return 'thinking off';
    return '';
  }
  function route(r) {
    const v = String(r || '').toLowerCase();
    if (!v) return '';
    if (/claude/.test(v)) return 'Claude subscription';
    if (/codex/.test(v)) return 'Codex subscription';
    if (/gemini subscription/.test(v)) return 'Gemini subscription';
    if (/ai studio/.test(v)) return 'Google AI Studio';
    if (/typesafe/.test(v)) return 'TypeSafe API';
    if (/cloudflare/.test(v)) return 'Cloudflare direct';
    if (/siliconflow/.test(v)) return 'SiliconFlow';
    if (/openrouter/.test(v)) return 'OpenRouter';
    if (/local/.test(v)) return 'local';
    return r;
  }
  const run = r => [model(r?.model || r?.id), effort(r?.effort, String(r?.model || '') + ' ' + String(r?.id || '')), route(r?.surface || r?.provider)].filter(Boolean).join(', ');
  // ponytail: one money rule site-wide, rounded to four decimals ($0.0059, $1.2013); under $0.001 keeps two significant digits ($0.00027).
  const usd = v => {
    if (v == null || v === '' || !Number.isFinite(Number(v))) return '';
    const x = Number(v);
    return x !== 0 && Math.abs(x) < 0.001 ? `$${x.toPrecision(2)}` : `$${x.toLocaleString('en-US', {minimumFractionDigits: 4, maximumFractionDigits: 4})}`;
  };
  const count = v => Number.isFinite(Number(v)) ? Number(v).toLocaleString('en-US') : String(v ?? '');
  window.BM_LABEL = {model, effort, route, run, usd, count};
})();

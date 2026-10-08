// Bakes public-site/presentation-offline.html: presentation.html plus every feed it uses, inlined as
// <script type="application/json" data-feed="name"> blocks read by deck/data.js. Chrome blocks fetch() on file://,
// so this is the copy to present from a laptop with no server. Scripts, fonts and images stay relative.
// Usage: node public-site/deck/verify/bake-offline.mjs   (rebuild after ANY deck change)
import { readFile, writeFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { SITE } from './lib.mjs';

const SKIP = /(^|\/)(node_modules|vendor|verify|fonts|assets)\//;
const FEED = /(?:[\w-]+\/)*[\w.-]+\.json/g;

const html = await readFile(join(SITE, 'presentation.html'), 'utf8');
const sources = (await readdir(join(SITE, 'deck'), { recursive: true })).filter(f => /\.(js|html)$/.test(f) && !SKIP.test(f));
const texts = [html, ...(await Promise.all(sources.map(f => readFile(join(SITE, 'deck', f), 'utf8'))))];

// Feeds = every deck/data/*.json plus any "<name>.json" mentioned in the page or deck scripts that exists under public-site/.
const names = new Set((await readdir(join(SITE, 'deck/data'))).filter(f => f.endsWith('.json')).map(f => `deck/data/${f}`));
for (const text of texts) for (const m of text.match(FEED) ?? []) names.add(m.replace(/^\.\//, ''));

const blocks = [];
const used = [];
for (const name of [...names].sort()) {
  let raw;
  try { raw = await readFile(join(SITE, name), 'utf8'); } catch { continue; } // prose or a template, not a real feed
  // \u003c keeps "</script>" and "<!--" inside the data from ending the block.
  blocks.push(`<script type="application/json" data-feed="${name}">${JSON.stringify(JSON.parse(raw)).replace(/</g, '\\u003c')}</script>`);
  used.push(name);
}

const marker = '<script src="./deck/data.js"></script>';
if (!html.includes(marker)) throw new Error(`${marker} not found in presentation.html`);
await writeFile(join(SITE, 'presentation-offline.html'), html.replace(marker, () => `${blocks.join('\n')}\n${marker}`));
console.log(`presentation-offline.html: ${used.length} feeds inlined: ${used.join(', ')}`);

// Counts spoken words per [notes beat=N] block, stripping [stage directions].
const file = process.argv[2] ?? "docs/talk/05-session-outline.md";
const text = await Bun.file(file).text();
const re = /\[notes beat=(\d+)\]([\s\S]*?)\[\/notes\]/g;
let total = 0;
for (const m of text.matchAll(re)) {
  const words = m[2].replace(/\[[^\]]*\]/g, " ").trim().split(/\s+/).filter(Boolean).length;
  total += words;
  console.log(`beat ${m[1]}: ${words}`);
}
console.log(`total: ${total}`);

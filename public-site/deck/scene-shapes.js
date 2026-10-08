/* Formations for the background scene: 60 points, one per review (DEV-001 is point 0), in stage pixels (1920x1080).
   Shared by the WebGL scene and its static SVG fallback, and seeded, so every formation is identical every time.
   Modes (data-scene): field, lattice, title (lattice reached by a fly-in), number (the points become a figure),
   mark (the points become an image, coloured by it). Options: data-scene-highlight="DEV-006,...",
   data-scene-number="54", data-scene-image="deck/assets/aea-icon-transparent.svg", data-scene-at="x,y". */
(() => {
  'use strict';
  const N = 60;
  const PAPER = [0.984, 0.988, 0.996], HOT = [0.961, 0.486, 0]; // #fbfcfe, and #f57c00 (--diff)
  const SIZE = 18, HOT_SIZE = 30, FIGURE_SIZE = 34; // stage px: bold enough to survive a compressed 30fps screen share
  const rand = k => { const x = Math.sin(k * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); };
  const idOf = i => `DEV-${String(i + 1).padStart(3, '0')}`;
  const ids = Array.from({ length: N }, (_, i) => i);

  const lattice = (i, [cx, cy]) => [cx + ((i % 12) - 5.5) * 60, cy + (Math.floor(i / 12) - 2) * 60, 0];
  const scatter = (i, [cx, cy]) => [cx + (rand(i * 3) - 0.5) * 760, cy + (rand(i * 3 + 1) - 0.5) * 720, (rand(i * 3 + 2) - 0.5) * 600];
  const deep = i => [960 + (rand(i * 7) - 0.5) * 2600, 540 + (rand(i * 7 + 1) - 0.5) * 1500, -4200 + rand(i * 7 + 2) * 5200];

  // Draw something on a small canvas, keep its filled pixels, then pick `count` of them as far apart as possible.
  function sample(draw, width, height, count) {
    const s = 0.25, w = Math.ceil(width * s), h = Math.ceil(height * s);
    const canvas = Object.assign(document.createElement('canvas'), { width: w, height: h });
    const g = canvas.getContext('2d', { willReadFrequently: true });
    g.scale(s, s);
    draw(g);
    const { data } = g.getImageData(0, 0, w, h); // throws on a tainted canvas (file://); callers fall back
    const filled = [];
    for (let p = 0; p < w * h; p++) if (data[p * 4 + 3] > 140) filled.push([(p % w) / s, Math.floor(p / w) / s, ...[0, 1, 2].map(c => data[p * 4 + c] / 255)]);
    if (filled.length < count) throw new Error('shape too small to sample');
    const far = filled.map(() => Infinity), picks = [];
    let next = 0;
    while (picks.length < count) {
      const [px, py] = filled[next];
      picks.push(filled[next]);
      let best = 0;
      filled.forEach(([x, y], j) => { far[j] = Math.min(far[j], (x - px) ** 2 + (y - py) ** 2); if (far[j] > far[best]) best = j; });
      next = best;
    }
    return picks.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  }

  // A thin weight puts the points along the strokes, so they read as dotted numerals. A bold fill spreads them into blobs.
  async function figure(text, count, [cx, cy]) {
    await document.fonts.load('200 200px Archivo');
    const W = 1100, H = 640;
    return sample(g => {
      let size = H * 0.98;
      g.font = `200 ${size}px Archivo`;
      size *= Math.min(1, (W * 0.96) / g.measureText(text).width);
      Object.assign(g, { font: `200 ${size}px Archivo`, fillStyle: '#fff', textAlign: 'center', textBaseline: 'middle' });
      g.fillText(text, W / 2, H / 2 + size * 0.04);
    }, W, H, count).map(([x, y]) => [cx - W / 2 + x, cy - H / 2 + y, 0]);
  }

  async function image(url, count, [cx, cy]) {
    const img = new Image();
    img.src = url;
    await img.decode();
    const H = 600, W = Math.round(H * img.naturalWidth / img.naturalHeight);
    return sample(g => g.drawImage(img, 0, 0, W, H), W, H, count).map(([x, y, r, gr, b]) => [cx - W / 2 + x, cy - H / 2 + y, 0, [r, gr, b]]);
  }

  async function formation(slide) {
    const mode = slide.dataset.scene;
    const hot = new Set((slide.dataset.sceneHighlight || '').split(',').map(s => s.trim()).filter(Boolean));
    const custom = (slide.dataset.sceneAt || '').split(',').map(Number);
    const at = fallback => (custom.length === 2 && custom.every(Number.isFinite) ? custom : fallback);
    const isHot = i => hot.has(idOf(i));
    const out = { pos: [], color: ids.map(i => (isHot(i) ? HOT : PAPER)), size: ids.map(i => (isHot(i) ? HOT_SIZE : SIZE)),
      alpha: ids.map(i => (isHot(i) ? 1 : 0.7)), hot: ids.map(isHot), loose: mode === 'field' ? 1 : 0, start: null, dolly: false };
    try {
      if (mode === 'number' && slide.dataset.sceneNumber && !slide.dataset.sceneNumber.startsWith('@')) {
        // The highlighted reviews (misses) line up under the figure; every other point becomes part of it.
        const [cx, cy] = at([960, 470]), keep = ids.filter(i => !isHot(i)), miss = ids.filter(isHot);
        const spots = await figure(slide.dataset.sceneNumber, keep.length, [cx, cy]);
        keep.forEach((i, j) => { out.pos[i] = spots[j]; out.size[i] = FIGURE_SIZE; out.alpha[i] = 1; });
        miss.forEach((i, j) => { out.pos[i] = [cx + (j - (miss.length - 1) / 2) * 72, cy + 410, 0]; });
        return out;
      }
      if (mode === 'mark' && slide.dataset.sceneImage) {
        const spots = await image(slide.dataset.sceneImage, N, at([1440, 540]));
        spots.forEach(([x, y, z, rgb], i) => { out.pos[i] = [x, y, z]; out.color[i] = rgb; out.size[i] = 22; out.alpha[i] = 1; });
        return out;
      }
    } catch (error) {
      console.info(`[deck-scene] ${mode} formation fell back to the lattice: ${error.message}`);
    }
    out.pos = ids.map(i => (mode === 'field' ? scatter(i, at([1500, 540])) : lattice(i, at([1480, 560]))));
    if (mode === 'title') Object.assign(out, { start: ids.map(deep), dolly: true });
    return out;
  }

  window.DeckShapes = { N, formation };
})();

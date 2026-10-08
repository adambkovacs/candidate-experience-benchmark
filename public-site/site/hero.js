/* Read page hero scene. Sixty points, one per test review (DEV-001 to DEV-060 in record order, row by row), drift in
   as a field and settle into a 10 x 6 grid. Orange marks the reviews named in data-diff on .hero-stage: the six where
   Jev's direct P0 answers differed from the provisional reference (findings.json#charts.jev.disagreementCaseIds).
   data-ring rings the review shown in the example card. Decorative (aria-hidden). With reduced motion, without
   WebGL 2, or if three.js fails, the static hero-lattice.svg stays. Timings and colours follow deck/MOTION.md. */
const stage = document.querySelector('.hero-stage');
const frame = stage && stage.querySelector('.hero-stage-frame');
const reduceQuery = matchMedia('(prefers-reduced-motion: reduce)');

const COLS = 10, ROWS = 6, N = COLS * ROWS;
const SETTLE = 1.7, STAGGER = 0.7, FOV = 35, TILT = -0.3, SIZE = 0.28; // SIZE in grid units (1 unit = point spacing)
const rand = k => { const x = Math.sin(k * 91.7 + 13.1) * 43758.5453; return x - Math.floor(x); }; // seeded, as in deck/scene.js
const easeOut = p => 1 - (1 - p) ** 3;
// Raw sRGB triples: the shader writes them straight to the sRGB canvas, so no colour-space conversion on the way.
const rgb = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
const clamp01 = v => Math.min(1, Math.max(0, v));
const reviews = name => (stage?.dataset[name] || '').split(',').map(id => id.trim())
  .filter(id => /^DEV-\d{3}$/.test(id)).map(id => Number(id.slice(4)) - 1).filter(i => i >= 0 && i < N);

const webgl2 = () => {
  try {
    const probe = document.createElement('canvas').getContext('webgl2');
    probe?.getExtension('WEBGL_lose_context')?.loseContext();
    return !!probe;
  } catch { return false; }
};
const idle = cb => ('requestIdleCallback' in globalThis ? requestIdleCallback(cb, {timeout: 700}) : setTimeout(cb, 120));

if (frame && !reduceQuery.matches && webgl2()) {
  const wake = new IntersectionObserver(entries => {
    if (!entries.some(entry => entry.isIntersecting)) return;
    wake.disconnect();
    idle(() => boot().catch(() => stage.classList.remove('is-live')));
  });
  wake.observe(stage);
}

const vertexShader = /* glsl */`
  attribute vec3 aColor; attribute float aSize; attribute float aAlpha; uniform float uScale;
  varying vec3 vColor; varying float vAlpha; varying float vSize;
  void main() {
    vColor = aColor; vAlpha = aAlpha;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * uScale / -mv.z; vSize = gl_PointSize;
    gl_Position = projectionMatrix * mv;
  }`;
// Round, bold points. Only points well inside the camera's near range (bigger than 1.3x the settled size) go soft.
const fragmentShader = /* glsl */`
  uniform float uBase; varying vec3 vColor; varying float vAlpha; varying float vSize;
  void main() {
    float soft = clamp((vSize - uBase * 1.3) / (uBase * 3.0), 0.0, 0.4);
    float a = smoothstep(0.5, 0.5 - max(1.5 / vSize, soft), length(gl_PointCoord - 0.5));
    gl_FragColor = vec4(vColor, a * vAlpha * (1.0 - soft));
  }`;

async function boot() {
  const THREE = await import('./vendor/three/three.module.min.js');
  const diff = new Set(reviews('diff'));
  const ring = reviews('ring')[0];
  const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true, powerPreference: 'low-power'});
  renderer.setClearColor(0x000000, 0);
  const canvas = renderer.domElement;
  const scene = new THREE.Scene(), group = new THREE.Group();
  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 100);
  group.rotation.x = TILT;
  scene.add(group);

  const grid = new Float32Array(N * 3), field = new Float32Array(N * 3), drift = new Float32Array(N * 3);
  const begin = new Float32Array(N);
  const pos = new Float32Array(N * 3), color = new Float32Array(N * 3).fill(1), size = new Float32Array(N), alpha = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const col = i % COLS, row = Math.floor(i / COLS);
    grid.set([col - (COLS - 1) / 2, (ROWS - 1) / 2 - row, 0], i * 3);
    field.set([(rand(i * 3) - 0.5) * 17, (rand(i * 3 + 1) - 0.5) * 10, (rand(i * 3 + 2) - 0.5) * 9], i * 3);
    drift.set([(rand(i + 101) - 0.5) * 3, (rand(i + 202) - 0.5) * 2, rand(i + 303) * 3], i * 3);
    begin[i] = 0.3 + (col / (COLS - 1)) * STAGGER + rand(i + 404) * 0.15; // left to right over 0.7s, seeded jitter
  }
  const paper = rgb('#fbfcfe');
  const targets = Array.from({length: N}, (_, i) => rgb(diff.has(i) ? '#f57c00' : i === ring ? '#9cc3f2' : '#fbfcfe'));

  const geometry = new THREE.BufferGeometry();
  [['position', pos, 3], ['aColor', color, 3], ['aSize', size, 1], ['aAlpha', alpha, 1]]
    .forEach(([name, array, n]) => geometry.setAttribute(name, new THREE.BufferAttribute(array, n)));
  const uniforms = {uScale: {value: 1}, uBase: {value: 10}};
  const material = new THREE.ShaderMaterial({uniforms, vertexShader, fragmentShader, transparent: true, depthWrite: false});
  group.add(new THREE.Points(geometry, material));

  const ringGeometry = new THREE.RingGeometry(0.21, 0.28, 48);
  const ringMaterial = new THREE.MeshBasicMaterial({color: 0x5e9ce8, transparent: true, opacity: 0, depthWrite: false});
  const ringMesh = new THREE.Mesh(ringGeometry, ringMaterial);
  if (ring !== undefined) group.add(ringMesh);

  frame.append(canvas);
  const hero = stage.closest('section') || stage;
  let heroHeight = hero.offsetHeight || 1;
  const fit = () => {
    const w = frame.clientWidth, h = frame.clientHeight;
    heroHeight = hero.offsetHeight || 1;
    if (!w || !h) return;
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, innerWidth < 700 ? 1.5 : 1.75));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    const tan = Math.tan(THREE.MathUtils.degToRad(FOV / 2));
    // Keep the whole grid (9 x 5 units plus points) in frame with margin, whichever side binds.
    const depth = Math.max(6.6 / (2 * tan), 10.8 / (2 * tan * camera.aspect));
    camera.position.set(0, 0, depth);
    camera.updateProjectionMatrix();
    uniforms.uScale.value = h * renderer.getPixelRatio() / (2 * tan);
    uniforms.uBase.value = SIZE * uniforms.uScale.value / depth;
  };
  const resize = new ResizeObserver(fit);
  resize.observe(frame);
  resize.observe(hero);
  fit();

  const aim = {x: 0, y: 0};
  const follow = event => { aim.x = event.clientX / innerWidth - 0.5; aim.y = event.clientY / innerHeight - 0.5; };
  if (matchMedia('(pointer: fine)').matches) addEventListener('pointermove', follow, {passive: true});

  const born = performance.now();
  let raf = 0, onScreen = true, first = true;
  const draw = now => {
    raf = requestAnimationFrame(draw);
    const t = (now - born) / 1000;
    const scroll = clamp01(scrollY / (heroHeight * 0.85));
    const pulse = 0.08 * Math.sin(t * 2 * Math.PI * 0.35); // highlighted points breathe about 8% at 0.35 Hz
    const intro = easeOut(clamp01(t / 0.8));
    for (let i = 0; i < N; i++) {
      const settle = easeOut(clamp01((t - begin[i]) / SETTLE));
      const landed = clamp01((t - begin[i] - SETTLE) / 0.6);
      for (let a = 0; a < 3; a++) {
        const k = i * 3 + a;
        pos[k] = field[k] + (grid[k] - field[k]) * settle + drift[k] * scroll + Math.sin(t * 0.4 + k * 1.7) * 0.03 * settle;
      }
      const to = targets[i];
      for (let c = 0; c < 3; c++) color[i * 3 + c] = paper[c] + (to[c] - paper[c]) * landed;
      size[i] = SIZE * (diff.has(i) || i === ring ? 1 + pulse * landed : 1);
      alpha[i] = intro * (0.55 + 0.45 * settle) * (1 - 0.9 * scroll);
    }
    ['position', 'aColor', 'aSize', 'aAlpha'].forEach(name => { geometry.attributes[name].needsUpdate = true; });
    if (ring !== undefined) {
      ringMesh.position.set(pos[ring * 3], pos[ring * 3 + 1], pos[ring * 3 + 2] + 0.01);
      ringMesh.scale.setScalar(1 + pulse);
      ringMaterial.opacity = clamp01((t - begin[ring] - SETTLE) / 0.6) * (1 - scroll) * 0.95;
    }
    camera.position.x += (aim.x * 0.8 - camera.position.x) * 0.05;
    camera.position.y += (-aim.y * 0.5 - camera.position.y) * 0.05;
    camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
    if (first) { first = false; stage.classList.add('is-live'); }
  };
  const play = () => { if (!raf && onScreen && !document.hidden) raf = requestAnimationFrame(draw); };
  const pause = () => { cancelAnimationFrame(raf); raf = 0; };
  const watch = new IntersectionObserver(entries => {
    onScreen = entries.some(entry => entry.isIntersecting);
    onScreen ? play() : pause();
  });
  watch.observe(stage);
  const visibility = () => (document.hidden ? pause() : play());
  document.addEventListener('visibilitychange', visibility);

  const teardown = () => {
    pause();
    watch.disconnect();
    resize.disconnect();
    removeEventListener('pointermove', follow);
    document.removeEventListener('visibilitychange', visibility);
    geometry.dispose(); ringGeometry.dispose(); material.dispose(); ringMaterial.dispose();
    renderer.dispose();
    canvas.remove();
    stage.classList.remove('is-live');
  };
  canvas.addEventListener('webglcontextlost', event => { event.preventDefault(); teardown(); }, {once: true});
  reduceQuery.addEventListener('change', event => { if (event.matches) teardown(); }, {once: true});
  play();
}

/* Background scene: 60 points, one per review. data-scene="field" drifts; data-scene="lattice" settles them into a 12x5 grid.
   data-scene-highlight="DEV-006,..." (or "@feed.json#path", resolved by data.js) lights reviews in orange.
   WebGL via three.js only when allowed; otherwise a static SVG inside each scene slide. Never blocks navigation. */
(() => {
  'use strict';
  // Positions are in stage design pixels (1920x1080), so the lattice sits at the same slide spot at every viewport.
  const N = 60, COLS = 12, ROWS = 5, GAP = 60, DEPTH = 14, CENTER = [1500, 560], SPREAD = [760, 720, 600];
  const threeUrl = new URL('vendor/three/three.module.min.js', document.currentScript.src).href;
  const PAPER = [0.984, 0.988, 0.996], HOT = [0.961, 0.486, 0]; // #fbfcfe, #f57c00
  const idOf = i => `DEV-${String(i + 1).padStart(3, '0')}`;
  const hotIds = slide => new Set((slide?.dataset.sceneHighlight || '').split(',').map(s => s.trim()));
  const rand = k => { const x = Math.sin(k * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); };

  function staticSvg(slide) {
    slide.querySelector(':scope > .d-scene-static')?.remove();
    const hot = hotIds(slide), grid = slide.dataset.scene === 'lattice';
    const dots = Array.from({ length: N }, (_, i) => {
      const x = CENTER[0] + (grid ? ((i % COLS) - (COLS - 1) / 2) * GAP : (rand(i * 3) - 0.5) * SPREAD[0]);
      const y = CENTER[1] + (grid ? (Math.floor(i / COLS) - (ROWS - 1) / 2) * GAP : (rand(i * 3 + 1) - 0.5) * SPREAD[1]);
      const on = hot.has(idOf(i));
      return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${on ? 9 : 6}" fill="${on ? '#f57c00' : '#fbfcfe'}" fill-opacity="${on ? 1 : .4}"/>`;
    }).join('');
    slide.insertAdjacentHTML('afterbegin', `<svg class="d-scene-static" viewBox="0 0 1920 1080" aria-hidden="true" focusable="false">${dots}</svg>`);
  }

  function fallback(reason) {
    if (reason) console.info(`[deck-scene] static background: ${reason}`);
    document.documentElement.classList.add('scene-static');
    document.getElementById('deck-scene')?.remove();
    document.querySelectorAll('.slides section[data-scene]').forEach(staticSvg);
    document.addEventListener('deck:bound', e => { if (e.target.matches?.('section[data-scene]')) staticSvg(e.target); });
  }

  async function webgl(Reveal, host) {
    const THREE = await import(threeUrl);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    host.append(renderer.domElement);
    const scene = new THREE.Scene(), group = new THREE.Group(), camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
    camera.position.z = DEPTH;
    scene.add(group);

    const field = Float32Array.from({ length: N * 3 }, (_, k) => (rand(k) - 0.5) * SPREAD[k % 3]);
    const grid = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) grid.set([((i % COLS) - (COLS - 1) / 2) * GAP, ((ROWS - 1) / 2 - Math.floor(i / COLS)) * GAP, 0], i * 3);
    const pos = field.slice(), color = new Float32Array(N * 3).fill(PAPER[0]), size = new Float32Array(N).fill(12);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geometry.setAttribute('aColor', new THREE.BufferAttribute(color, 3));
    geometry.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
    const material = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { uScale: { value: 1 } },
      vertexShader: `attribute vec3 aColor; attribute float aSize; uniform float uScale; varying vec3 vColor;
        void main() { vColor = aColor; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = aSize * uScale / -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `varying vec3 vColor;
        void main() { float d = length(gl_PointCoord - 0.5); gl_FragColor = vec4(vColor, smoothstep(0.5, 0.16, d) * 0.9); }`,
    });
    group.add(new THREE.Points(geometry, material));
    group.rotation.y = -0.3;

    // Lattice edges between grid neighbours fade in as the field resolves.
    const pairs = [];
    for (let i = 0; i < N; i++) { if (i % COLS < COLS - 1) pairs.push(i, i + 1); if (i + COLS < N) pairs.push(i, i + COLS); }
    const edgePos = new Float32Array(pairs.length * 3);
    const edges = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(edgePos, 3));
    const edgeMaterial = new THREE.LineBasicMaterial({ color: 0x93a0bb, transparent: true, opacity: 0, depthWrite: false });
    group.add(new THREE.LineSegments(edges, edgeMaterial));

    let mix = 0, goal = 0, hot = new Set(), raf = 0, last = 0;
    const t0 = performance.now();
    const ease = (from, to, dt, rate) => from + (to - from) * (1 - Math.exp(-dt * rate));

    function frame(now) {
      const dt = Math.min(0.05, (now - last) / 1000 || 0), t = (now - t0) / 1000;
      last = now;
      mix = ease(mix, goal, dt, 1.6);
      const settled = mix * mix * (3 - 2 * mix);
      for (let i = 0; i < N; i++) {
        const on = hot.has(idOf(i)), tint = on ? HOT : PAPER;
        for (let a = 0; a < 3; a++) {
          const k = i * 3 + a, drift = Math.sin(t * 0.21 + k * 1.7) * 42 * (1 - settled);
          pos[k] = field[k] + drift + (grid[k] - field[k]) * settled;
          color[k] = ease(color[k], tint[a], dt, 4);
        }
        size[i] = ease(size[i], on ? 20 : 12, dt, 4);
      }
      pairs.forEach((p, j) => edgePos.set(pos.subarray(p * 3, p * 3 + 3), j * 3));
      edgeMaterial.opacity = settled * 0.2;
      ['position', 'aColor', 'aSize'].forEach(name => { geometry.attributes[name].needsUpdate = true; });
      edges.attributes.position.needsUpdate = true;
      group.rotation.y = -0.3 + Math.sin(t * 0.07) * 0.06;
      group.rotation.x = Math.sin(t * 0.05) * 0.04;
      renderer.render(scene, camera);
      raf = running() ? requestAnimationFrame(frame) : 0;
      api.settled = !raf || Math.abs(goal - mix) < 0.002;
    }
    const running = () => document.visibilityState === 'visible' && host.classList.contains('is-active');
    const wake = () => { if (running() && !raf) { last = performance.now(); raf = requestAnimationFrame(frame); } };

    // Reveal centres the stage, so stage pixel (960, 540) is the camera axis; k converts stage pixels to world units.
    function resize() {
      const w = host.clientWidth || 1, h = host.clientHeight || 1, scale = Reveal.getScale();
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      const k = scale * 2 * DEPTH * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) / h;
      group.scale.setScalar(k);
      group.position.set((CENTER[0] - 960) * k, (540 - CENTER[1]) * k, 0);
      material.uniforms.uScale.value = renderer.getPixelRatio() * scale * DEPTH;
      if (!raf) renderer.render(scene, camera);
    }

    function retarget(slide) {
      const mode = slide?.dataset.scene;
      host.classList.toggle('is-active', Boolean(mode));
      if (mode) { goal = mode === 'lattice' ? 1 : 0; hot = hotIds(slide); api.settled = false; wake(); }
    }

    resize();
    retarget(Reveal.getCurrentSlide());
    Reveal.on('slidechanged', e => retarget(e.currentSlide));
    document.addEventListener('deck:bound', e => { if (e.target === Reveal.getCurrentSlide()) retarget(e.target); });
    document.addEventListener('visibilitychange', wake);
    Reveal.on('resize', resize);
  }

  function start(Reveal) {
    const host = document.getElementById('deck-scene');
    const query = location.search;
    if (!host) return fallback();
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return fallback('reduced motion');
    if (/print-pdf|receiver/i.test(query)) return fallback(/receiver/i.test(query) ? 'speaker view' : 'print view');
    let webglOk = false;
    try { const c = document.createElement('canvas'); webglOk = Boolean(c.getContext('webgl2') || c.getContext('webgl')); } catch { webglOk = false; }
    if (!webglOk) return fallback('WebGL unavailable');
    const go = () => (Reveal.isReady() ? Promise.resolve() : new Promise(r => Reveal.on('ready', r)))
      .then(() => webgl(Reveal, host)).catch(error => fallback(error.message));
    'requestIdleCallback' in window ? requestIdleCallback(go, { timeout: 1200 }) : setTimeout(go, 300);
  }

  const api = { start, settled: true };
  window.DeckScene = api;
})();

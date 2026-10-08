/* Background scene engine. Formations come from scene-shapes.js; this file moves 60 points between them.
   Every point settles on its own beat (staggered, overshoot-free), the title flies in through depth, near points
   go soft like a lens. Big bold dots only: no hairlines, nothing that a compressed 30fps screen share would smear.
   WebGL via three.js when allowed; otherwise each scene slide gets a static SVG of the same formation. */
(() => {
  'use strict';
  const { N, formation } = window.DeckShapes;
  const DEPTH = 14, SETTLE = 1.7, STAGGER = 0.7, DOLLY = 3.2, VANISH = 1480;
  const threeUrl = new URL('vendor/three/three.module.min.js', document.currentScript.src).href;
  const shapes = new WeakMap();
  const shape = slide => { if (!shapes.has(slide)) shapes.set(slide, formation(slide)); return shapes.get(slide); };
  const rand = k => { const x = Math.sin(k * 91.7 + 13.1) * 43758.5453; return x - Math.floor(x); };
  const easeOut = p => 1 - (1 - p) ** 3;
  const api = { start, settled: true, ready: Promise.resolve() };

  async function staticSvg(slide) {
    const f = await shape(slide);
    const hex = rgb => `#${rgb.map(v => Math.round(v * 255).toString(16).padStart(2, '0')).join('')}`;
    const dots = f.pos.map(([x, y], i) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(f.size[i] * 0.36).toFixed(1)}" fill="${hex(f.color[i])}" fill-opacity="${f.alpha[i]}"/>`).join('');
    slide.querySelector(':scope > .d-scene-static')?.remove();
    slide.insertAdjacentHTML('afterbegin', `<svg class="d-scene-static" viewBox="0 0 1920 1080" aria-hidden="true" focusable="false">${dots}</svg>`);
  }

  function fallback(reason) {
    if (reason) console.info(`[deck-scene] static background: ${reason}`);
    document.documentElement.classList.add('scene-static');
    document.getElementById('deck-scene')?.remove();
    document.addEventListener('deck:bound', e => { if (e.target.matches?.('section[data-scene]')) { shapes.delete(e.target); staticSvg(e.target); } });
    // Print view lays out pages from these SVGs, so deck.js waits for this promise there.
    api.ready = window.DeckData.ready.then(() => Promise.all([...document.querySelectorAll('.slides section[data-scene]')].map(staticSvg)));
    return api.ready;
  }

  async function webgl(Reveal, host, three) {
    const THREE = await three;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    host.append(renderer.domElement);
    const scene = new THREE.Scene(), group = new THREE.Group(), camera = new THREE.PerspectiveCamera(35, 1, 0.1, 200);
    camera.position.z = DEPTH;
    scene.add(group);

    const pos = new Float32Array(N * 3), color = new Float32Array(N * 3).fill(0.98), size = new Float32Array(N).fill(18), alpha = new Float32Array(N);
    const base = new Float32Array(N * 3), from = { pos: new Float32Array(N * 3), color: color.slice(), size: size.slice(), alpha: alpha.slice() };
    const to = { pos: new Float32Array(N * 3), color: color.slice(), size: size.slice(), alpha: alpha.slice() };
    const begin = new Float32Array(N), hot = new Uint8Array(N);
    const geometry = new THREE.BufferGeometry();
    [['position', pos, 3], ['aColor', color, 3], ['aSize', size, 1], ['aAlpha', alpha, 1]].forEach(([name, array, n]) => geometry.setAttribute(name, new THREE.BufferAttribute(array, n)));
    const material = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, uniforms: { uScale: { value: 1 } },
      vertexShader: `attribute vec3 aColor; attribute float aSize; attribute float aAlpha; uniform float uScale;
        varying vec3 vColor; varying float vAlpha; varying float vSize;
        void main() { vColor = aColor; vAlpha = aAlpha; vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = aSize * uScale / -mv.z; vSize = gl_PointSize; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `varying vec3 vColor; varying float vAlpha; varying float vSize;
        void main() { float soft = clamp((vSize - 70.0) / 300.0, 0.0, 0.4);
          float a = smoothstep(0.5, 0.5 - max(1.5 / vSize, soft), length(gl_PointCoord - 0.5));
          gl_FragColor = vec4(vColor, a * vAlpha * (1.0 - soft)); }`,
    });
    group.add(new THREE.Points(geometry, material));

    let loose = 0, looseGoal = 0, dolly = null, raf = 0, last = 0, token = 0;
    const running = () => document.visibilityState === 'visible' && host.classList.contains('is-active');
    const wake = () => { if (running() && !raf) { last = performance.now(); raf = requestAnimationFrame(frame); } };

    function frame(now) {
      const t = now / 1000, dt = Math.min(0.05, (now - last) / 1000 || 0);
      last = now;
      loose += (looseGoal - loose) * (1 - Math.exp(-dt * 1.6));
      let moving = false;
      for (let i = 0; i < N; i++) {
        const p = Math.min(1, Math.max(0, (t - begin[i]) / SETTLE)), e = easeOut(p);
        if (p < 1) moving = true;
        for (let a = 0; a < 3; a++) {
          const k = i * 3 + a;
          base[k] = from.pos[k] + (to.pos[k] - from.pos[k]) * e;
          pos[k] = base[k] + Math.sin(t * 0.21 + k * 1.7) * 42 * loose;
          color[k] = from.color[k] + (to.color[k] - from.color[k]) * e;
        }
        // The hold stays alive: highlighted points breathe slowly (slow enough for a 30fps share).
        size[i] = (from.size[i] + (to.size[i] - from.size[i]) * e) * (hot[i] ? 1 + 0.08 * Math.sin(t * 2.2 + i) : 1);
        alpha[i] = from.alpha[i] + (to.alpha[i] - from.alpha[i]) * e;
      }
      if (dolly) {
        const p = Math.min(1, (t - dolly.t0) / DOLLY);
        camera.position.z = DEPTH + (dolly.from - DEPTH) * (1 - easeOut(p));
        if (p >= 1) dolly = null;
      }
      ['position', 'aColor', 'aSize', 'aAlpha'].forEach(name => { geometry.attributes[name].needsUpdate = true; });
      group.rotation.y = -0.12 + Math.sin(t * 0.07) * 0.04;
      group.rotation.x = Math.sin(t * 0.05) * 0.03;
      renderer.render(scene, camera);
      api.settled = !moving && !dolly && Math.abs(loose - looseGoal) < 0.01;
      raf = running() ? requestAnimationFrame(frame) : 0;
    }

    // Stage pixels to world units: Reveal centres the stage, so stage (960, 540) is the world origin. An off-axis camera
    // (shifted right, view offset back) keeps the z=0 plane exactly in place but puts the vanishing point at stage x=VANISH,
    // so a fly-in streams out of the formation instead of across the headline.
    function resize() {
      const w = host.clientWidth || 1, h = host.clientHeight || 1, scale = Reveal.getScale();
      const k = scale * 2 * DEPTH * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) / h;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.position.x = (VANISH - 960) * k;
      camera.setViewOffset(w, h, -(VANISH - 960) * scale, 0, w, h);
      group.scale.setScalar(k);
      material.uniforms.uScale.value = renderer.getPixelRatio() * scale * DEPTH;
      if (!raf) renderer.render(scene, camera);
    }

    async function retarget(slide) {
      const mine = ++token, mode = slide?.dataset.scene;
      host.classList.toggle('is-active', Boolean(mode));
      api.settled = !mode; // the loop stops on slides without a scene, so it cannot report settling itself
      if (!mode) return;
      const f = await shape(slide);
      if (mine !== token) return;
      const t = performance.now() / 1000, xs = f.pos.map(p => p[0]), left = Math.min(...xs), span = Math.max(1, Math.max(...xs) - left);
      for (let i = 0; i < N; i++) {
        const origin = f.start?.[i], [x, y, z] = f.pos[i];
        from.pos.set(origin ? [origin[0] - 960, 540 - origin[1], origin[2]] : base.subarray(i * 3, i * 3 + 3), i * 3);
        to.pos.set([x - 960, 540 - y, z], i * 3);
        from.color.set(color.subarray(i * 3, i * 3 + 3), i * 3);
        to.color.set(f.color[i], i * 3);
        // Fly-ins launch big and dim: far points would otherwise start as 3px dust that a 30fps share smears.
        [from.size[i], to.size[i], from.alpha[i], to.alpha[i]] = origin ? [f.size[i] * 2.6, f.size[i], 0.35, f.alpha[i]] : [size[i], f.size[i], alpha[i], f.alpha[i]];
        hot[i] = f.hot[i] ? 1 : 0;
        // Staggered settle: left to right, a beat apart, with a little seeded jitter.
        begin[i] = t + ((x - left) / span) * STAGGER + rand(i) * 0.15;
      }
      looseGoal = f.loose;
      if (f.dolly) dolly = { t0: t, from: DEPTH * 2.6 };
      wake();
    }

    resize();
    retarget(Reveal.getCurrentSlide());
    Reveal.on('slidechanged', e => retarget(e.currentSlide));
    Reveal.on('resize', resize);
    document.addEventListener('deck:bound', e => {
      if (!e.target.matches?.('section[data-scene]')) return;
      shapes.delete(e.target);
      if (e.target === Reveal.getCurrentSlide()) retarget(e.target);
    });
    document.addEventListener('visibilitychange', wake);
  }

  function start(Reveal) {
    const host = document.getElementById('deck-scene');
    if (!host) return fallback();
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return fallback('reduced motion');
    if (/print-pdf|receiver/i.test(location.search)) return fallback(/receiver/i.test(location.search) ? 'speaker view' : 'print view');
    let webglOk = false;
    try { const c = document.createElement('canvas'); webglOk = Boolean(c.getContext('webgl2') || c.getContext('webgl')); } catch { webglOk = false; }
    if (!webglOk) return fallback('WebGL unavailable');
    // Start downloading three.js now so the points arrive with the headline; build only once Reveal is ready.
    const three = import(threeUrl);
    three.catch(() => {}); // a failed import is handled below by the static fallback
    (Reveal.isReady() ? Promise.resolve() : new Promise(r => Reveal.on('ready', r)))
      .then(() => webgl(Reveal, host, three)).catch(error => fallback(error.message));
    return api.ready;
  }

  window.DeckScene = api;
})();

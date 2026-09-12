/** 3D observatory — the federation as LOGOS actually observes it.
 *
 *  Pure Three.js, no R3F, code-split by the parent.
 *
 *  Every mark on screen is a measurement:
 *    · the core is this LOGOS node;
 *    · one satellite per source LOGOS polls, at a radius set by its MEASURED
 *      latency and coloured by its real status (reachable / unreachable);
 *    · one mote per capability the hub federates, in a shell around the hub;
 *    · one edge per observation — source → this node. Peer-to-peer topology the
 *      hub never reported is not drawn, because we do not know it;
 *    · three orbital planes around the core — quiet cyan when calm,
 *      amber→coral→crimson as unacknowledged alerts escalate (never a red scribble);
 *    · a pulse travels the edge each time that source answers again, so motion
 *      means data arrived rather than "there is an animation here".
 *
 *  With no sources at all there is nothing to show and we say so, rather than
 *  inventing a starfield that looks like a healthy federation.
 */

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

interface Peer { url: string; name: string; capabilities_count: number; trust_score: number; healthy: boolean; latency_ms?: number | null; }

/** One polled source, exactly as the snapshot reports it. */
export interface ObservedSource {
  name: string;
  /** "ok" | "unreachable" | whatever the adapter returned. */
  status: string;
  /** Measured round-trip for this source, from `_elapsed_ms`. */
  elapsedMs: number | null;
  /** Headline number this source contributes (capabilities, findings, …). */
  magnitude: number;
}

interface Props {
  peers: Peer[];
  anomaly_count?: number;
  theme: 'dark' | 'light';
  /** Sources LOGOS polled in the last snapshot. */
  sources?: ObservedSource[];
  /** Capabilities the hub federates — drawn as a shell, not invented. */
  capabilityCount?: number;
  t?: (k: string, v?: any, d?: string) => string;
}

/** What a source means, in one line, so a sphere is not a riddle. */
const SOURCE_ROLE: Record<string, string> = {
  hub: 'sourceRole.hub',
  momus: 'sourceRole.momus',
  treasury: 'sourceRole.treasury',
  skopos: 'sourceRole.skopos',
  lumen: 'sourceRole.lumen',
  argus: 'sourceRole.argus',
  bridges: 'sourceRole.bridges',
};

/** The number each source reports means something different — say which. */
const SOURCE_METRIC: Record<string, string> = {
  hub: 'sourceMetric.capabilities',
  momus: 'sourceMetric.findings',
  treasury: 'sourceMetric.availableUsd',
};

const NO_DATA = 'Nothing observed yet — the poll loop has not reported a source.';

/** Deterministic hash (ecosystem pattern: hash32 from MOMUS) — same layout every render. */
const hash32 = (n: number) => {
  let x = n | 0;
  x = (x ^ 61) ^ (x >>> 16);
  x = (x + (x << 3)) | 0;
  x = x ^ (x >>> 4);
  x = Math.imul(x, 0x27d4eb2d);
  x = x ^ (x >>> 15);
  return x >>> 0;
};

export default function DataConstellation({
  peers, anomaly_count, theme, sources = [], capabilityCount = 0, t,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const labelLayer = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<ObservedSource | null>(null);
  const [hovered, setHovered] = useState<string>('');
  const tr = (k: string, d: string, v?: any) => (t ? t(k, v, d) : d);

  // Nodes we can honestly draw: every polled source, plus every peer the hub named.
  const nodes: ObservedSource[] = [
    ...sources,
    ...peers.map((p) => ({
      name: p.name || p.url.replace(/^https?:\/\//, '').split('/')[0] || 'peer',
      status: p.healthy ? 'ok' : 'unreachable',
      elapsedMs: p.latency_ms ?? null,
      magnitude: p.capabilities_count,
    })),
  ];

  useEffect(() => {
    const el = ref.current;
    if (!el || nodes.length === 0) return;

    const W = el.clientWidth, H = el.clientHeight;
    if (W === 0 || H === 0) return;

    const accent = theme === 'dark' ? 0x00e5ff : 0x0077a8;
    const accent2 = theme === 'dark' ? 0x7c4dff : 0x5b2fd0;
    const good = theme === 'dark' ? 0x4ade80 : 0x0f8a45;
    const bad = theme === 'dark' ? 0xff2d55 : 0xcc1039;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(52, W / H, 0.1, 100);
    camera.position.set(0, 0.5, 6.6);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    } catch {
      return;                                   // no WebGL — the CSS fallback shows instead
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W, H);
    el.appendChild(renderer.domElement);

    // ── the core: this LOGOS node ───────────────────────────────────────────
    const coreGroup = new THREE.Group();
    const core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.72, 2),
      new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.9, wireframe: true }),
    );
    const coreShell = new THREE.Mesh(
      new THREE.SphereGeometry(1.05, 24, 24),
      new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.11, depthWrite: false }),
    );
    coreGroup.add(core, coreShell);
    scene.add(coreGroup);

    // Always three orbital planes — calm cyan when quiet; amber→coral→crimson
    // as unacknowledged alerts escalate (capped at 3 so the core never turns into a scribble).
    const quietPalette = theme === 'dark'
      ? [0x00e5ff, 0x5ad4ff, 0x7c4dff]
      : [0x0077a8, 0x3a9ec4, 0x5b2fd0];
    const alertPalette = theme === 'dark'
      ? [0xffcc33, 0xff6b3d, 0xff2d55]
      : [0xc9a227, 0xcc5520, 0xcc1039];
    const alertLevel = Math.min(Math.max(0, anomaly_count ?? 0), 3);
    type AlertOrbit = { mesh: THREE.Mesh; spin: number; precess: number; phase: number };
    const alertRings: AlertOrbit[] = [];
    for (let i = 0; i < 3; i++) {
      const isAlert = i < alertLevel;
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(1.48 + i * 0.4, isAlert ? 0.012 : 0.008, 12, 128),
        new THREE.MeshBasicMaterial({
          color: isAlert ? alertPalette[i] : quietPalette[i],
          transparent: true,
          opacity: isAlert ? 0.48 : 0.18,
          depthWrite: false,
        }),
      );
      // Distinct orbital planes — three readable layers, not a stacked red mess.
      ring.rotation.set(
        Math.PI / 2 + (i - 1) * 0.58,
        i * 1.12,
        i * 0.38,
      );
      alertRings.push({
        mesh: ring,
        spin: (isAlert ? 0.0024 : 0.0014) + i * 0.0009,
        precess: 0.0005 + i * 0.00022,
        phase: i * 1.7,
      });
      scene.add(ring);
    }

    // ── satellites: one per observed source ─────────────────────────────────
    // Radius carries MEASURED latency (a slow source sits further out), size
    // carries the number it reports, colour carries whether it answered.
    const maxLatency = Math.max(1, ...nodes.map((n) => n.elapsedMs ?? 0));
    const maxMag = Math.max(1, ...nodes.map((n) => n.magnitude));

    type Sat = { mesh: THREE.Mesh; base: THREE.Vector3; phase: number; ok: boolean; edge: THREE.Line };
    const sats: Sat[] = [];
    const edgesGroup = new THREE.Group();
    const N = nodes.length;

    nodes.forEach((n, i) => {
      const ok = n.status === 'ok';
      // Fibonacci sphere: an even spread that does not depend on a random seed.
      const phi = Math.acos(1 - (2 * (i + 0.5)) / N);
      const theta = Math.PI * (1 + Math.sqrt(5)) * (i + 0.5);
      const latency = (n.elapsedMs ?? 0) / maxLatency;  // 0..1 when measured; neutral radius if unknown
      const r = 2.35 + latency * 1.45;
      const pos = new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.cos(phi) * 0.62,
        r * Math.sin(phi) * Math.sin(theta) - 0.6,
      );

      const size = 0.22 + (n.magnitude / maxMag) * 0.3;
      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(size, 20, 20),
        new THREE.MeshBasicMaterial({ color: ok ? good : bad, transparent: true, opacity: ok ? 0.95 : 0.5 }),
      );
      mesh.position.copy(pos);
      const halo = new THREE.Mesh(
        new THREE.SphereGeometry(size * 2.1, 16, 16),
        new THREE.MeshBasicMaterial({
          color: ok ? good : bad, transparent: true,
          opacity: ok ? 0.14 : 0.06, depthWrite: false,
        }),
      );
      mesh.add(halo);
      scene.add(mesh);

      // The observation itself: this source → this node. Dimmer when unreachable.
      const edge = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([pos, new THREE.Vector3(0, 0, 0)]),
        new THREE.LineBasicMaterial({
          color: ok ? accent : bad, transparent: true,
          opacity: ok ? 0.26 : 0.12, depthWrite: false,
        }),
      );
      edgesGroup.add(edge);

      sats.push({ mesh, base: pos, phase: (hash32(i * 7919) % 628) / 100, ok, edge });
    });
    scene.add(edgesGroup);

    // ── capability shell: one mote per federated capability ─────────────────
    // A count is a fact; where each capability "is" is not, so they form an even
    // shell rather than pretending to sit at a location.
    let motes: THREE.Points | null = null;
    if (capabilityCount > 0) {
      const count = Math.min(capabilityCount, 400);
      const arr = new Float32Array(count * 3);
      for (let i = 0; i < count; i++) {
        const phi = Math.acos(1 - (2 * (i + 0.5)) / count);
        const theta = Math.PI * (1 + Math.sqrt(5)) * (i + 0.5);
        const r = 4.15 + ((hash32(i * 104729) % 100) / 100) * 0.45;
        arr[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        arr[i * 3 + 1] = r * Math.cos(phi) * 0.7;
        arr[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(arr, 3));
      motes = new THREE.Points(geo, new THREE.PointsMaterial({
        color: accent, size: 0.075, transparent: true,
        opacity: theme === 'dark' ? 0.7 : 0.85, depthWrite: false,
      }));
      scene.add(motes);
    }

    // ── pulses: one bead per reachable source, travelling inward ────────────
    // Motion carries meaning here — a bead arriving is that source answering.
    const pulses = sats.filter((s) => s.ok).map((s, i) => {
      const bead = new THREE.Mesh(
        new THREE.SphereGeometry(0.055, 10, 10),
        new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.9 }),
      );
      scene.add(bead);
      return { bead, from: s.base, offset: (i * 0.37) % 1 };
    });

    // ── labels: HTML over WebGL, so the text is crisp and translatable ──────
    // A sphere with no name is a riddle. Each node carries its name and the one
    // number it reports, projected from its 3D position every frame.
    const layer = labelLayer.current;
    const tags: HTMLDivElement[] = [];
    if (layer) {
      layer.innerHTML = '';
      nodes.forEach((n) => {
        const tag = document.createElement('div');
        tag.className = 'node-tag';
        tag.dataset.name = n.name;
        const value = n.name === 'treasury' && n.magnitude
          ? `$${n.magnitude}`
          : String(n.magnitude);
        tag.innerHTML =
          `<b>${n.name}</b>` +
          `<span class="tag-num">${n.status === 'ok' ? value : '—'}</span>` +
          (n.elapsedMs != null ? `<span class="tag-ms">${Math.round(n.elapsedMs)} ms</span>` : '');
        layer.appendChild(tag);
        tags.push(tag);
      });
    }

    // ── picking: hover highlights, click opens the detail ───────────────────
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let hoverIdx = -1;

    const pickAt = (clientX: number, clientY: number): number => {
      const rect = dom.getBoundingClientRect();
      pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(sats.map((x) => x.mesh), true);
      if (hits.length === 0) return -1;
      // A halo is a child of its node — walk up to the node itself.
      let obj: THREE.Object3D | null = hits[0].object;
      while (obj && !sats.some((x) => x.mesh === obj)) obj = obj.parent;
      return obj ? sats.findIndex((x) => x.mesh === obj) : -1;
    };

    // ── drag to orbit (no auto-spin fighting the pointer) ───────────────────
    let dragging = false, moved = 0, lastX = 0, lastY = 0;
    let yaw = 0, pitch = 0, spin = 0;
    const dom = renderer.domElement;

    const onDown = (e: PointerEvent) => { dragging = true; moved = 0; lastX = e.clientX; lastY = e.clientY; };
    const onMove = (e: PointerEvent) => {
      if (dragging) {
        const dx = e.clientX - lastX, dy = e.clientY - lastY;
        moved += Math.abs(dx) + Math.abs(dy);
        yaw += dx * 0.006;
        pitch = Math.max(-0.9, Math.min(0.9, pitch + dy * 0.004));
        lastX = e.clientX; lastY = e.clientY;
        return;
      }
      const idx = pickAt(e.clientX, e.clientY);
      if (idx !== hoverIdx) {
        hoverIdx = idx;
        dom.style.cursor = idx >= 0 ? 'pointer' : 'grab';
        setHovered(idx >= 0 ? nodes[idx].name : '');
      }
    };
    const onUp = () => { dragging = false; };
    // A drag that ends where it started is a click, not a rotation.
    const onClick = (e: PointerEvent) => {
      if (moved > 6) return;
      const idx = pickAt(e.clientX, e.clientY);
      setSelected(idx >= 0 ? nodes[idx] : null);
    };

    dom.style.touchAction = 'pan-y';
    dom.style.cursor = 'grab';
    dom.addEventListener('pointerdown', onDown);
    dom.addEventListener('pointerup', onClick);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);

    let running = true;
    let raf = 0;
    let tt = 0;

    function animate() {
      if (!running) return;
      tt += 0.006;
      if (!dragging) spin += 0.0016;

      const yr = yaw + spin;
      scene.rotation.y = yr;
      scene.rotation.x = pitch * 0.6;

      core.rotation.y += 0.004;
      core.rotation.x += 0.002;
      const breath = 1 + Math.sin(tt * 1.6) * 0.045;
      coreShell.scale.setScalar(breath);

      sats.forEach((s, i) => {
        // A reachable source pulses; an unreachable one sits still, which is the
        // point — stillness is the signal. Hover lifts it above the rest.
        const k = s.ok ? 1 + Math.sin(tt * 2.4 + s.phase) * 0.09 : 1;
        s.mesh.scale.setScalar(i === hoverIdx ? k * 1.35 : k);
        (s.edge.material as THREE.LineBasicMaterial).opacity =
          i === hoverIdx ? 0.75 : (s.ok ? 0.26 : 0.12);

        // Project the node into screen space and park its tag beside it.
        const tag = tags[i];
        if (tag) {
          const v = s.base.clone().applyEuler(scene.rotation).project(camera);
          const x = (v.x * 0.5 + 0.5) * W;
          const y = (-v.y * 0.5 + 0.5) * H;
          tag.style.transform = `translate(-50%,-50%) translate(${x}px,${y - 30}px)`;
          tag.style.opacity = v.z > 1 ? '0' : (i === hoverIdx ? '1' : '.82');
          tag.classList.toggle('on', i === hoverIdx);
          tag.classList.toggle('down', !s.ok);
        }
      });

      for (let i = 0; i < alertRings.length; i++) {
        const r = alertRings[i];
        const isAlert = i < alertLevel;
        r.mesh.rotation.z += r.spin;
        r.mesh.rotation.y += r.precess;
        r.mesh.rotation.x += Math.sin(tt * 0.35 + r.phase) * 0.0009;
        const base = isAlert ? 0.34 : 0.12;
        const amp = isAlert ? 0.14 : 0.05;
        (r.mesh.material as THREE.MeshBasicMaterial).opacity =
          base + Math.sin(tt * (isAlert ? 1.35 : 0.7) + r.phase) * amp;
      }

      for (const p of pulses) {
        const u = (tt * 0.28 + p.offset) % 1;
        p.bead.position.copy(p.from).multiplyScalar(1 - u);
        (p.bead.material as THREE.MeshBasicMaterial).opacity = 0.85 * (1 - Math.abs(u - 0.5) * 1.2);
      }

      if (motes) motes.rotation.y -= 0.0006;

      renderer.render(scene, camera);
      raf = requestAnimationFrame(animate);
    }
    animate();

    const onResize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      if (w === 0 || h === 0) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', onResize);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
      dom.removeEventListener('pointerdown', onDown);
      dom.removeEventListener('pointerup', onClick);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        if (m.geometry) m.geometry.dispose();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else mat?.dispose();
      });
      renderer.dispose();
      if (dom.parentNode === el) el.removeChild(dom);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(nodes), anomaly_count, theme, capabilityCount]);

  const sel = selected;
  const metricKey = sel ? SOURCE_METRIC[sel.name] : '';
  const roleKey = sel ? SOURCE_ROLE[sel.name] : '';

  return (
    <div
      ref={ref}
      className="constellation"
      style={{ position: 'relative', width: '100%', height: 340, borderRadius: 'var(--radius)', overflow: 'hidden' }}
    >
      {/* Names and numbers, projected over the canvas so they stay legible. */}
      <div ref={labelLayer} className="node-tags" aria-hidden="true" />

      {nodes.length > 0 && (
        <>
          {/* A colour that needs guessing carries no information. */}
          <div className="scene-legend">
            <span><i className="dot core" />{tr('scene.thisNode', 'this node')}</span>
            <span><i className="dot ok" />{tr('scene.reachable', 'answered')}</span>
            <span><i className="dot down" />{tr('scene.unreachable', 'no answer')}</span>
            {capabilityCount > 0 && (
              <span><i className="dot mote" />{tr('scene.capabilityMotes', '{{n}} capabilities', { n: capabilityCount })}</span>
            )}
            {(anomaly_count ?? 0) > 0 && (
              <span><i className="dot alert" />{tr('scene.alertOrbits', 'alerts (orbits)')}</span>
            )}
          </div>

          {!sel && (
            <div className="scene-hint">
              {hovered
                ? tr('scene.clickForDetail', 'click for detail')
                : tr('scene.hintDrag', 'drag to orbit · click a node')}
            </div>
          )}

          {sel && (
            <div className="scene-detail" role="status">
              <button
                className="scene-detail-close"
                onClick={() => setSelected(null)}
                aria-label={tr('scene.close', 'Close')}
              >×</button>
              <div className="sd-name">
                <i className={`dot ${sel.status === 'ok' ? 'ok' : 'down'}`} />
                {sel.name}
              </div>
              {roleKey && <div className="sd-role">{tr(`analytics.${roleKey}`, sel.name)}</div>}
              <dl className="sd-grid">
                <dt>{tr('scene.status', 'status')}</dt>
                <dd className={sel.status === 'ok' ? 'ok' : 'down'}>
                  {sel.status === 'ok'
                    ? tr('scene.reachable', 'answered')
                    : tr('scene.unreachable', 'no answer')}
                </dd>
                {sel.elapsedMs != null && (
                  <>
                    <dt>{tr('scene.latency', 'latency')}</dt>
                    <dd>{Math.round(sel.elapsedMs)} ms</dd>
                  </>
                )}
                <dt>{metricKey ? tr(`analytics.${metricKey}`, 'value') : tr('scene.value', 'value')}</dt>
                <dd>
                  {sel.status === 'ok'
                    ? (sel.name === 'treasury' ? `$${sel.magnitude}` : sel.magnitude)
                    : '—'}
                </dd>
              </dl>
            </div>
          )}
        </>
      )}

      {nodes.length === 0 && (
        <div className="empty-chart" style={{ paddingTop: 150 }}>
          {t ? t('analytics.noObservations', undefined, NO_DATA) : NO_DATA}
        </div>
      )}
    </div>
  );
}

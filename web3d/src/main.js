// P3-1: schematic 3D view of the 91 registry items. Layout is process-ordered and NOT to scale; sizes are registry values for five
// items and per-group estimates otherwise (see python/plant_3d.py). Generic cylinder/box shapes, not vendor drawings.
import * as T from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const D = window.__PLANT3D__;
const wrap = document.getElementById('wrap');
const W = () => wrap.clientWidth, H = () => wrap.clientHeight;
const GROUP_COLOR = { FE: 0xd9a03a, GA: 0x3d6fb5, GC: 0x2f8f6b, HB: 0x1f9fa6, EU: 0xd9603a, SA: 0x8e5cc7, AI: 0x5b6b85 };
const STATE_COLOR = { running_live: 0x3b82f6, running_assumed: 0xf59e0b, static: 0x94a3b8, missing: 0xe2e8f0, fault: 0xef4444 };
const STATE_TEXT = { running_live: 'Computed this cycle (model)', running_assumed: 'Assumed inputs only', static: 'Static (no live key)', missing: 'Missing', fault: 'DESIGN FINDING' };

const renderer = new T.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setSize(W(), H());
wrap.appendChild(renderer.domElement);
const scene = new T.Scene();
scene.background = new T.Color(0x0f1722);
const cam = new T.PerspectiveCamera(42, W() / H(), 0.1, 400);
cam.position.set(0, 21, 43);
const controls = new OrbitControls(cam, renderer.domElement);
controls.target.set(0, 0, 14.5);
controls.maxPolarAngle = Math.PI * 0.49;
scene.add(new T.HemisphereLight(0xdfeaf7, 0x35404c, 1.1));
const sun = new T.DirectionalLight(0xffffff, 1.4); sun.position.set(20, 40, 30); scene.add(sun);
const floor = new T.Mesh(new T.PlaneGeometry(160, 90), new T.MeshStandardMaterial({ color: 0x1b2634, roughness: 1 }));
floor.rotation.x = -Math.PI / 2; floor.position.set(0, -0.01, 14.5); scene.add(floor);
{ const grid = new T.GridHelper(160, 80, 0x2b3a4d, 0x223041); grid.position.set(0, 0, 14.5); scene.add(grid); }

function label(text, x, y, z, scale = 1, color = '#e5edf7') {
  const cv = document.createElement('canvas'); cv.width = 512; cv.height = 96;
  const c = cv.getContext('2d'); c.fillStyle = 'rgba(15,23,34,.85)'; c.fillRect(0, 0, 512, 96);
  c.fillStyle = color; c.font = 'bold 44px Arial'; c.textBaseline = 'middle'; c.fillText(text, 16, 48);
  const sp = new T.Sprite(new T.SpriteMaterial({ map: new T.CanvasTexture(cv), depthTest: false, transparent: true }));
  sp.scale.set(4.6 * scale, 0.86 * scale, 1); sp.position.set(x, y, z); sp.renderOrder = 5; scene.add(sp); return sp;
}

const pickable = [];
const steel = new T.MeshStandardMaterial({ color: 0xaab4bf, metalness: 0.85, roughness: 0.35 });
const darkM = new T.MeshStandardMaterial({ color: 0x2b3139, metalness: 0.6, roughness: 0.5 });
const paintM = c => new T.MeshStandardMaterial({ color: c, metalness: 0.3, roughness: 0.5 });
const ins = (g, mesh) => { g.add(mesh); return mesh; };
const cylM = (r, h, mat, seg = 32) => new T.Mesh(new T.CylinderGeometry(r, r, h, seg), mat);
const ringM = (r, tube, mat) => { const m = new T.Mesh(new T.TorusGeometry(r, tube, 8, 40), mat); m.rotation.x = Math.PI / 2; return m; };
const domeM = (r, mat, flip) => { const m = new T.Mesh(new T.SphereGeometry(r, 32, 12, 0, Math.PI * 2, 0, Math.PI / 2), mat); m.scale.set(1, 0.45, 1); if (flip) m.rotation.x = Math.PI; return m; };
function pipeM(a, b, r, mat) { const A = new T.Vector3(...a), B = new T.Vector3(...b); const L = A.distanceTo(B);
  const m = new T.Mesh(new T.CylinderGeometry(r, r, L, 14), mat); m.position.copy(A).add(B).multiplyScalar(0.5);
  m.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), B.clone().sub(A).normalize()); return m; }

// Detailed shapes for the five items whose size is a registry value. Shapes are typical equipment of that kind, not vendor drawings;
// the overall size (diameter, height, length) is the registry's.
const DETAIL = {
  'GA-001'(it, g) {            // reactor vessel: insulated shell, domed head, flange bands, legs, side ports
    const r = it.w / 2, h = it.h, col = paintM(GROUP_COLOR.GA);
    ins(g, cylM(r, h * 0.92, col)).position.y = h * 0.5 + 0.0;
    ins(g, domeM(r, col, false)).position.y = h * 0.96;
    for (const f of [0.18, 0.5, 0.82]) { const rg = ringM(r * 1.04, 0.03, steel); rg.position.y = h * f; g.add(rg); }
    for (const a of [0.25, 0.75]) { const p = pipeM([r, h * a, 0], [r + 0.35, h * a, 0], 0.045, steel); g.add(p); }
    for (let i = 0; i < 4; i++) { const ang = i * Math.PI / 2 + Math.PI / 4; const leg = cylM(0.03, 0.4, darkM, 8); leg.position.set(Math.cos(ang) * r * 0.8, -0.0, Math.sin(ang) * r * 0.8); g.add(leg); }
    g.position.y = 0.2;
  },
  'GC-004'(it, g) {            // quench tower: shell, conical bottom, spray-nozzle ring, gas outlet
    const r = it.w / 2, h = it.h, col = paintM(GROUP_COLOR.GC);
    ins(g, cylM(r, h * 0.82, col)).position.y = h * 0.59;
    const cone = new T.Mesh(new T.CylinderGeometry(r, r * 0.25, h * 0.16, 32), col); cone.position.y = h * 0.1; g.add(cone);
    ins(g, domeM(r, col, false)).position.y = h * 1.0;
    for (let i = 0; i < 6; i++) { const ang = i / 6 * Math.PI * 2; const n = cylM(0.025, 0.14, steel, 8); n.rotation.z = Math.PI / 2; n.position.set(Math.cos(ang) * r, h * 0.85, Math.sin(ang) * r); n.rotation.y = -ang; g.add(n); }
    g.add(pipeM([0, h * 1.05, 0], [0.5, h * 1.25, 0], 0.05, steel));
    for (const f of [0.35, 0.7]) { const rg = ringM(r * 1.04, 0.025, steel); rg.position.y = h * f; g.add(rg); }
  },
  'GC-006'(it, g) {            // packed-bed adsorber: shell, flange bands, conical hopper, manway
    const r = it.w / 2, h = it.h, col = paintM(GROUP_COLOR.GC);
    ins(g, cylM(r, h * 0.85, col)).position.y = h * 0.6;
    const hop = new T.Mesh(new T.CylinderGeometry(r, r * 0.2, h * 0.2, 32), col); hop.position.y = h * 0.1; g.add(hop);
    ins(g, domeM(r, col, false)).position.y = h * 1.02;
    for (const f of [0.2, 0.55, 0.95]) { const rg = ringM(r * 1.05, 0.03, steel); rg.position.y = h * f; g.add(rg); }
    const man = cylM(r * 0.3, 0.05, steel, 20); man.rotation.x = Math.PI / 2; man.position.set(0, h * 0.62, r + 0.02); g.add(man);
  },
  'GC-008'(it, g) {            // wet scrubber column: shell, demister dome, recirculation loop to a small sump tank
    const r = it.w / 2, h = it.h, col = paintM(GROUP_COLOR.GC);
    ins(g, cylM(r, h * 0.88, col)).position.y = h * 0.5;
    ins(g, domeM(r, col, false)).position.y = h * 0.94;
    const tank = cylM(r * 0.9, h * 0.1, paintM(0x1f6f55)); tank.position.y = h * 0.05; g.add(tank);
    g.add(pipeM([r, h * 0.1, 0], [r + 0.3, h * 0.1, 0], 0.03, steel)); g.add(pipeM([r + 0.3, h * 0.1, 0], [r + 0.3, h * 0.8, 0], 0.03, steel));
    g.add(pipeM([r + 0.3, h * 0.8, 0], [r * 0.3, h * 0.8, 0], 0.03, steel));
    for (const f of [0.3, 0.65]) { const rg = ringM(r * 1.05, 0.025, steel); rg.position.y = h * f; g.add(rg); }
  },
  'FE-003'(it, g) {            // weighing conveyor: belt, end rollers, rails, legs (length 3 m, belt 0.4 m: registry)
    const L = it.w, Wd = it.d, col = paintM(GROUP_COLOR.FE);
    const belt = new T.Mesh(new T.BoxGeometry(L, 0.04, Wd), darkM); belt.position.y = 0.55; g.add(belt);
    for (const sgn of [-1, 1]) { const rail = new T.Mesh(new T.BoxGeometry(L, 0.12, 0.03), col); rail.position.set(0, 0.6, sgn * (Wd / 2 + 0.02)); g.add(rail); }
    for (const sx of [-1, 1]) { const rl = cylM(0.07, Wd + 0.1, steel, 16); rl.rotation.x = Math.PI / 2; rl.position.set(sx * (L / 2 - 0.05), 0.55, 0); g.add(rl); }
    for (const sx of [-0.45, 0, 0.45]) for (const sz of [-1, 1]) { const lg = cylM(0.025, 0.55, darkM, 8); lg.position.set(sx * L, 0.275, sz * Wd * 0.5); g.add(lg); }
    const wcell = new T.Mesh(new T.BoxGeometry(0.3, 0.12, Wd + 0.06), paintM(0xd9a03a)); wcell.position.y = 0.3; g.add(wcell);
  },
};
const TOP = { 'FE-003': 0.8 };       // beacon height when the drawn shape is not the registry height

// P3-3: items whose registry row states a COUNT or a VOLUME but no dimension. The count drawn is the registry's (it.count); the footprint is
// an estimate (amber ring). Typical equipment of that kind, not vendor drawings.
const COUNTED = {
  'HB-006'(it, g) {            // PSA: N vertical adsorbers on a skid with a manifold
    const n = it.count, col = paintM(GROUP_COLOR.HB), pitch = it.w / n, r = Math.min(pitch * 0.36, 0.22);
    for (let i = 0; i < n; i++) { const x = -it.w / 2 + pitch * (i + 0.5);
      const v = cylM(r, it.h * 0.8, col); v.position.set(x, it.h * 0.45, 0); g.add(v);
      const dm = domeM(r, col, false); dm.position.set(x, it.h * 0.85, 0); g.add(dm);
      g.add(pipeM([x, 0.12, 0], [x, 0.12, it.d * 0.45], 0.03, steel)); }
    g.add(pipeM([-it.w / 2 + pitch * 0.5, 0.12, it.d * 0.45], [it.w / 2 - pitch * 0.5, 0.12, it.d * 0.45], 0.04, steel));
    const sk = new T.Mesh(new T.BoxGeometry(it.w, 0.06, it.d), darkM); sk.position.y = 0.03; g.add(sk);
  },
  'HB-013'(it, g) {            // cascade bank: N horizontal Type IV composite cylinders on a rack, with a common header
    const n = it.count, col = paintM(0x2a3340);
    for (let i = 0; i < n; i++) { const z = (i - (n - 1) / 2) * (it.d / n);
      const c = cylM(0.16, it.w * 0.9, col, 24); c.rotation.z = Math.PI / 2; c.position.set(0, 0.35, z); g.add(c);
      for (const sx of [-1, 1]) { const dm = domeM(0.16, col, false); dm.rotation.z = -sx * Math.PI / 2; dm.position.set(sx * it.w * 0.45, 0.35, z); g.add(dm); } }
    for (const sx of [-0.3, 0.3]) { const rk = new T.Mesh(new T.BoxGeometry(0.06, 0.2, it.d), darkM); rk.position.set(sx * it.w, 0.1, 0); g.add(rk); }
    g.add(pipeM([it.w * 0.5, 0.35, -it.d / 2], [it.w * 0.5, 0.35, it.d / 2], 0.03, steel));
  },
  'HB-010'(it, g) {            // N membrane modules: horizontal tubes in a frame
    const n = it.count, col = paintM(GROUP_COLOR.HB);
    for (let i = 0; i < n; i++) { const z = (i - (n - 1) / 2) * 0.3; const m = cylM(0.1, it.w * 0.9, col, 20); m.rotation.z = Math.PI / 2; m.position.set(0, 0.25, z); g.add(m); }
    const fr = new T.Mesh(new T.BoxGeometry(it.w, 0.04, it.d), darkM); fr.position.y = 0.04; g.add(fr);
  },
  'HB-012'(it, g) {            // diaphragm compressor: N cylinder heads in a row on a crankcase, interstage cooler pipes
    const n = it.count, col = paintM(GROUP_COLOR.HB);
    const cr = new T.Mesh(new T.BoxGeometry(it.w, it.h * 0.4, it.d), col); cr.position.y = it.h * 0.2; g.add(cr);
    for (let i = 0; i < n; i++) { const x = -it.w / 2 + it.w / n * (i + 0.5); const hd = cylM(0.12, it.h * 0.4, steel, 16); hd.position.set(x, it.h * 0.6, 0); g.add(hd);
      if (i < n - 1) g.add(pipeM([x, it.h * 0.85, 0], [x + it.w / n, it.h * 0.85, 0], 0.025, steel)); }
    const mo = cylM(0.18, 0.5, paintM(0x3d6fb5), 20); mo.rotation.z = Math.PI / 2; mo.position.set(-it.w / 2 - 0.1, it.h * 0.25, 0); g.add(mo);
  },
  'GC-010'(it, g) {            // bag filter: casing, N bags visible as tubes in a cut-away top, hopper
    const n = it.count, col = paintM(GROUP_COLOR.GC);
    const body = new T.Mesh(new T.BoxGeometry(it.w, it.h * 0.55, it.d), col); body.position.y = it.h * 0.55; g.add(body);
    const hop = new T.Mesh(new T.CylinderGeometry(Math.min(it.w, it.d) * 0.5, 0.08, it.h * 0.25, 4), col); hop.position.y = it.h * 0.15; hop.rotation.y = Math.PI / 4; g.add(hop);
    for (let i = 0; i < n; i++) { const x = (i % 2 - 0.5) * it.w * 0.45, z = (Math.floor(i / 2) - 0.5) * it.d * 0.45; const b = cylM(0.07, it.h * 0.3, paintM(0xe8e2cf), 12); b.position.set(x, it.h * 0.9, z); g.add(b); }
  },
  'GC-003'(it, g) {            // cyclone: cylinder, cone, inlet duct, vortex finder
    const r = it.w / 2, h = it.h, col = paintM(GROUP_COLOR.GC);
    const cy = cylM(r, h * 0.45, col); cy.position.y = h * 0.72; g.add(cy);
    const cone = new T.Mesh(new T.CylinderGeometry(r, r * 0.15, h * 0.5, 32), col); cone.position.y = h * 0.25; g.add(cone);
    g.add(pipeM([r + 0.4, h * 0.82, 0], [r * 0.6, h * 0.82, 0], 0.07, steel));
    const vf = cylM(0.06, 0.3, steel, 12); vf.position.y = h * 1.0; g.add(vf);
  },
  'FE-004'(it, g) {            // dual-shaft shredder: hopper above a cutting chamber with N rotors, drive
    const n = it.count, col = paintM(GROUP_COLOR.FE);
    const ch = new T.Mesh(new T.BoxGeometry(it.w, it.h * 0.4, it.d), col); ch.position.y = it.h * 0.25; g.add(ch);
    const hp = new T.Mesh(new T.CylinderGeometry(it.w * 0.5, it.w * 0.3, it.h * 0.35, 4), col); hp.position.y = it.h * 0.63; hp.rotation.y = Math.PI / 4; g.add(hp);
    for (let i = 0; i < n; i++) { const z = (i - (n - 1) / 2) * it.d * 0.35; const ro = cylM(0.1, it.w * 0.95, steel, 16); ro.rotation.z = Math.PI / 2; ro.position.set(0, it.h * 0.46, z); g.add(ro); }
    const dr = new T.Mesh(new T.BoxGeometry(0.4, 0.4, 0.4), paintM(0x3d6fb5)); dr.position.set(it.w / 2 + 0.25, it.h * 0.25, 0); g.add(dr);
  },
  'GC-012'(it, g) {            // carbon bed: vessel with dished ends and inlet/outlet pipes
    const r = it.w / 2, h = it.h, col = paintM(GROUP_COLOR.GC);
    ins(g, cylM(r, h * 0.9, col)).position.y = h * 0.5;
    const dm = domeM(r, col, false); dm.position.y = h * 0.95; g.add(dm);
    g.add(pipeM([r, h * 0.85, 0], [r + 0.25, h * 0.85, 0], 0.03, steel)); g.add(pipeM([r, h * 0.15, 0], [r + 0.25, h * 0.15, 0], 0.03, steel));
  },
  'HB-014'(it, g) {            // hydrogenation reactor: vertical vessel with jacket band and agitator motor
    const r = it.w / 2, h = it.h, col = paintM(GROUP_COLOR.HB);
    ins(g, cylM(r, h * 0.9, col)).position.y = h * 0.5;
    const dm = domeM(r, col, false); dm.position.y = h * 0.95; g.add(dm);
    const jk = cylM(r * 1.06, h * 0.4, paintM(0x167a80)); jk.position.y = h * 0.4; g.add(jk);
    const mo = cylM(0.1, 0.25, paintM(0x3d6fb5), 16); mo.position.y = h * 1.12; g.add(mo);
  },
  'HB-015'(it, g) {            // lean and rich carrier tanks: two vertical tanks side by side
    const n = it.count, r = it.d / 2, col = paintM(0x1d8b92);
    for (let i = 0; i < n; i++) { const x = (i - (n - 1) / 2) * (it.d + 0.3); const t = cylM(r, it.h * 0.92, col); t.position.set(x, it.h * 0.5, 0); g.add(t);
      const dm = domeM(r, col, false); dm.position.set(x, it.h * 0.96, 0); g.add(dm); }
    g.add(pipeM([-(it.d + 0.3) / 2, 0.2, r], [(it.d + 0.3) / 2, 0.2, r], 0.04, steel));
  },
};

function build(it) {
  const g = new T.Group();
  if (DETAIL[it.id]) DETAIL[it.id](it, g);
  else if (COUNTED[it.id]) COUNTED[it.id](it, g);
  else {
    const body = it.shape === 'cyl' ? new T.CylinderGeometry(it.w / 2, it.w / 2, it.h, 32) : new T.BoxGeometry(it.w, it.h, it.d);
    const m = new T.Mesh(body, new T.MeshStandardMaterial({ color: GROUP_COLOR[it.group], metalness: 0.35, roughness: 0.5 }));
    m.position.y = it.h / 2; g.add(m);
  }
  g.position.set(it.x, 0, it.z);
  g.traverse(o => { if (o.isMesh) { o.userData = it; pickable.push(o); } });
  return g;
}
const rowMin = {};
for (const it of D.items) {
  scene.add(build(it));
  const top = TOP[it.id] || it.h;
  // beacon on top: the item's state, the same state the Plant Overview counts
  const b = new T.Mesh(new T.SphereGeometry(Math.max(0.12, Math.min(0.28, it.w * 0.25)), 16, 12), new T.MeshBasicMaterial({ color: STATE_COLOR[it.state] }));
  b.position.set(it.x, top + 0.35, it.z); scene.add(b);
  // base ring: green = size from the registry, amber = estimate
  const r = (it.shape === 'cyl' ? it.w / 2 : Math.max(it.w, it.d) / 2) + 0.12;
  const ring = new T.Mesh(new T.RingGeometry(r, r + 0.07, 40), new T.MeshBasicMaterial({ color: it.basis === 'registry' ? 0x22c55e : 0xf59e0b, side: T.DoubleSide }));
  ring.rotation.x = -Math.PI / 2; ring.position.set(it.x, 0.02, it.z); scene.add(ring);
  rowMin[it.group] = Math.min(rowMin[it.group] ?? 1e9, it.x - it.w / 2);
}
D.order.forEach((g, i) => label(D.groups[g], rowMin[g] - 2.6, 0.9, i * 4.8, 0.8, '#' + GROUP_COLOR[g].toString(16).padStart(6, '0')));

// P3-4: camera poses (Fit view, Focus on a group), click-to-select card, and schematic flow arrows between the group rows.
const rows = {};
for (const it of D.items) { const r = rows[it.group] || (rows[it.group] = { z: it.z, x0: 1e9, x1: -1e9 }); r.x0 = Math.min(r.x0, it.x - it.w / 2); r.x1 = Math.max(r.x1, it.x + it.w / 2); }
const vf = Math.tan(cam.fov * Math.PI / 360);
function fitPose() { const a = W() / H(), k = Math.max(1, 1.8 / a); return { pos: [0, 21 * k, 43 * k], tgt: [0, 0, 14.5] }; }
function groupPose(g) { const r = rows[g], a = W() / H(), cx = (r.x0 + r.x1) / 2, d = Math.max(9, ((r.x1 - r.x0) / 2 + 1.5) / (vf * a));
  return { pos: [cx, d * 0.45 + 1, r.z + d * 0.9], tgt: [cx, 0.8, r.z] }; }
let anim = null;
function flyTo(p) { anim = { t0: performance.now(), p0: cam.position.toArray(), t0v: controls.target.toArray(), p1: p.pos, t1v: p.tgt }; }
function stepAnim(now) { if (!anim) return; const k = Math.min(1, (now - anim.t0) / 700), e = k * k * (3 - 2 * k);
  cam.position.set(...anim.p0.map((v, i) => v + (anim.p1[i] - v) * e)); controls.target.set(...anim.t0v.map((v, i) => v + (anim.t1v[i] - v) * e));
  if (k >= 1) anim = null; }
// flow arrows between the group rows: ORDER OF THE GROUPS ONLY (FE -> GA -> GC -> HB -> EU, the process order of the plant), not a stream path
for (let i = 0; i < D.order.length - 1; i++) { const a = D.order[i], b = D.order[i + 1];
  if (!['FE', 'GA', 'GC', 'HB'].includes(a) || !rows[a] || !rows[b]) continue;
  const x = Math.min(rows[a].x0, rows[b].x0) - 1.2, z0 = rows[a].z + 0.9, z1 = rows[b].z - 0.9;
  const sh = pipeM([x, 0.05, z0], [x, 0.05, z1 - 0.5], 0.05, paintM(0x94a3b8)); scene.add(sh);
  const hd = new T.Mesh(new T.ConeGeometry(0.18, 0.5, 12), paintM(0x94a3b8)); hd.rotation.x = Math.PI / 2; hd.position.set(x, 0.05, z1 - 0.25); scene.add(hd); }
let selected = null;
const selRing = new T.Mesh(new T.RingGeometry(0.1, 0.16, 48), new T.MeshBasicMaterial({ color: 0xffffff, side: T.DoubleSide }));
selRing.rotation.x = -Math.PI / 2; selRing.visible = false; scene.add(selRing);
const card = document.createElement('div');
card.style.cssText = 'position:absolute;right:10px;top:10px;background:rgba(15,23,34,.92);color:#e5edf7;font:12px Arial;padding:10px 12px;border-radius:8px;width:270px;line-height:1.5;display:none;border:1px solid #334155';
wrap.appendChild(card);
function select(id) {
  selected = D.items.find(i => i.id === id) || null;
  if (!selected) { card.style.display = 'none'; selRing.visible = false; return; }
  const u = selected, r = (u.shape === 'cyl' ? u.w / 2 : Math.max(u.w, u.d) / 2) + 0.4;
  selRing.geometry.dispose(); selRing.geometry = new T.RingGeometry(r, r + 0.1, 48); selRing.position.set(u.x, 0.04, u.z); selRing.visible = true;
  const esc = t => String(t).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  card.innerHTML = `<div style="font-size:14px"><b>${esc(u.id)}</b> ${esc(u.name)}</div><div style="color:#94a3b8">${esc(D.groups[u.group])}</div>` +
    `<div style="margin-top:6px">${dot(STATE_COLOR[u.state])}${esc(u.state_label)}</div>` +
    `<div style="margin-top:6px"><b>Size:</b> ${u.basis === 'registry' ? 'from the registry' : 'estimated'}<br><span style="color:#94a3b8">${esc(u.basis_note)}</span></div>` +
    (u.count ? `<div style="margin-top:6px"><b>Drawn count:</b> ${u.count} (registry)</div>` : '') +
    `<div style="margin-top:8px;color:#94a3b8">Simulated model state, no plant data. Schematic, not to scale.</div>`;
  card.style.display = 'block';
}
const bar = document.createElement('div');
bar.style.cssText = 'position:absolute;right:10px;bottom:10px;display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end;max-width:70%';
const btn = (text, fn) => { const b = document.createElement('button'); b.textContent = text; fn && (b.onclick = fn);
  b.style.cssText = 'background:#1e293b;color:#e5edf7;border:1px solid #475569;border-radius:6px;padding:4px 9px;font:12px Arial;cursor:pointer'; bar.appendChild(b); return b; };
btn('Fit view', () => { select(null); flyTo(fitPose()); });
for (const g of D.order) btn(D.groups[g], () => flyTo(groupPose(g)));
wrap.appendChild(bar);

// legend (HTML overlay)
const lg = document.createElement('div');
lg.style.cssText = 'position:absolute;left:10px;top:10px;background:rgba(15,23,34,.88);color:#e5edf7;font:12px Arial;padding:8px 10px;border-radius:8px;max-width:280px;line-height:1.5';
const dot = c => `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#${c.toString(16).padStart(6, '0')};margin-right:6px"></span>`;
lg.innerHTML = '<b style="cursor:pointer" title="click to fold">Schematic, not to scale &#9662;</b><div class="lgbody"><div style="margin-top:4px">Top sphere = state</div>' +
  Object.keys(STATE_TEXT).map(k => '<div style="white-space:nowrap">' + dot(STATE_COLOR[k]) + STATE_TEXT[k] + '</div>').join('') +
  '<div style="margin-top:4px">Base ring</div><div style="white-space:nowrap">' + dot(0x22c55e) + 'size from registry</div><div style="white-space:nowrap">' + dot(0xf59e0b) + 'size estimated</div>' +
  '<div style="margin-top:4px">Simulated model state, no plant data.</div></div>';
wrap.appendChild(lg);
lg.firstChild.onclick = () => { const b = lg.querySelector('.lgbody'); b.style.display = b.style.display === 'none' ? 'block' : 'none'; };
const tip = document.createElement('div');
tip.style.cssText = 'position:absolute;pointer-events:none;display:none;background:rgba(15,23,34,.95);color:#fff;font:12px Arial;padding:6px 9px;border-radius:6px;max-width:280px;border:1px solid #334155';
wrap.appendChild(tip);

const ray = new T.Raycaster(), mouse = new T.Vector2();
renderer.domElement.addEventListener('pointermove', e => {
  const r = renderer.domElement.getBoundingClientRect();
  mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(mouse, cam);
  const hit = ray.intersectObjects(pickable)[0];
  if (hit) {
    const u = hit.object.userData;
    tip.innerHTML = `<b>${u.id}</b> ${u.name}<br>${u.state_label}<br><span style="color:#94a3b8">Size: ${u.basis === 'registry' ? 'registry' : 'estimate'}. ${u.basis_note}</span>`;
    tip.style.left = (e.clientX - r.left + 14) + 'px'; tip.style.top = (e.clientY - r.top + 14) + 'px'; tip.style.display = 'block';
  } else tip.style.display = 'none';
});
let down = null;
renderer.domElement.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; anim = null; });
renderer.domElement.addEventListener('pointerup', e => {
  if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) { down = null; return; }   // a drag (orbit), not a click
  down = null;
  const r = renderer.domElement.getBoundingClientRect();
  mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(mouse, cam);
  const hit = ray.intersectObjects(pickable)[0];
  select(hit ? hit.object.userData.id : null);
});
window.addEventListener('resize', () => { renderer.setSize(W(), H()); cam.aspect = W() / H(); cam.updateProjectionMatrix(); });
(function loop(now) { stepAnim(now || performance.now()); controls.update(); renderer.render(scene, cam); requestAnimationFrame(loop); })();
window.__PLANT3D_VIEW__ = { cam, controls, select, flyTo, fitPose, groupPose };   // lets a test or a screenshot script move the camera
window.__PLANT3D_READY__ = true;

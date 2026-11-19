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

function build(it) {
  const g = new T.Group();
  if (DETAIL[it.id]) DETAIL[it.id](it, g);
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

// legend (HTML overlay)
const lg = document.createElement('div');
lg.style.cssText = 'position:absolute;left:10px;top:10px;background:rgba(15,23,34,.88);color:#e5edf7;font:12px Arial;padding:8px 10px;border-radius:8px;max-width:280px;line-height:1.5';
const dot = c => `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#${c.toString(16).padStart(6, '0')};margin-right:6px"></span>`;
lg.innerHTML = '<b>Schematic, not to scale</b><div style="margin-top:4px">Top sphere = state</div>' +
  Object.keys(STATE_TEXT).map(k => '<div style="white-space:nowrap">' + dot(STATE_COLOR[k]) + STATE_TEXT[k] + '</div>').join('') +
  '<div style="margin-top:4px">Base ring</div><div style="white-space:nowrap">' + dot(0x22c55e) + 'size from registry</div><div style="white-space:nowrap">' + dot(0xf59e0b) + 'size estimated</div>' +
  '<div style="margin-top:4px">Simulated model state, no plant data.</div>';
wrap.appendChild(lg);
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
window.addEventListener('resize', () => { renderer.setSize(W(), H()); cam.aspect = W() / H(); cam.updateProjectionMatrix(); });
(function loop() { controls.update(); renderer.render(scene, cam); requestAnimationFrame(loop); })();
window.__PLANT3D_VIEW__ = { cam, controls };   // lets a test or a screenshot script move the camera
window.__PLANT3D_READY__ = true;

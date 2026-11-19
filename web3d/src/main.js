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
let minX = 0, maxX = 0;
for (const it of D.items) {
  const body = it.shape === 'cyl' ? new T.CylinderGeometry(it.w / 2, it.w / 2, it.h, 32) : new T.BoxGeometry(it.w, it.h, it.d);
  const mat = new T.MeshStandardMaterial({ color: GROUP_COLOR[it.group], metalness: 0.35, roughness: 0.5 });
  const m = new T.Mesh(body, mat);
  m.position.set(it.x, it.h / 2, it.z); m.userData = it; scene.add(m); pickable.push(m);
  // beacon on top: the item's state, the same state the Plant Overview counts
  const b = new T.Mesh(new T.SphereGeometry(Math.max(0.12, Math.min(0.28, it.w * 0.25)), 16, 12), new T.MeshBasicMaterial({ color: STATE_COLOR[it.state] }));
  b.position.set(it.x, it.h + 0.3, it.z); scene.add(b);
  // base ring: green = size from the registry, amber = estimate
  const r = (it.shape === 'cyl' ? it.w / 2 : Math.max(it.w, it.d) / 2) + 0.12;
  const ring = new T.Mesh(new T.RingGeometry(r, r + 0.07, 40), new T.MeshBasicMaterial({ color: it.basis === 'registry' ? 0x22c55e : 0xf59e0b, side: T.DoubleSide }));
  ring.rotation.x = -Math.PI / 2; ring.position.set(it.x, 0.02, it.z); scene.add(ring);
  minX = Math.min(minX, it.x - it.w / 2); maxX = Math.max(maxX, it.x + it.w / 2);
}
D.order.forEach((g, i) => label(D.groups[g], minX - 3.2, 0.9, i * 4.8, 0.8, '#' + GROUP_COLOR[g].toString(16).padStart(6, '0')));

// legend (HTML overlay)
const lg = document.createElement('div');
lg.style.cssText = 'position:absolute;left:10px;top:10px;background:rgba(15,23,34,.88);color:#e5edf7;font:12px Arial;padding:8px 10px;border-radius:8px;max-width:280px;line-height:1.5';
const dot = c => `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#${c.toString(16).padStart(6, '0')};margin-right:6px"></span>`;
lg.innerHTML = '<b>Schematic, not to scale</b><br>Top sphere = state: ' + Object.keys(STATE_TEXT).map(k => dot(STATE_COLOR[k]) + STATE_TEXT[k]).join(' ') +
  '<br>Base ring: ' + dot(0x22c55e) + 'size from registry ' + dot(0xf59e0b) + 'size estimated<br>Simulated model state, no plant data.';
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
window.__PLANT3D_READY__ = true;

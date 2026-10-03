/* Marfa Lights Field Guide: 3D terrain (docs/terrain.html).
 *
 * Data (analysis/terrain3d.py):
 *   data/terrain/meta.json      grid extent (UTM 13N metres), mesh size, height scaling
 *   data/terrain/height.bin     uint16 decimetres above z0, (ny x nx) vertices at 120 m, row 0 = north edge
 *   data/terrain/relief.webp    20 m shaded relief (hypsometric tint, multi-directional hillshade, local relief)
 *   data/terrain/creeks.png     20 m computed drainage lines (alpha)
 *   data/terrain/overlays.json  roads, visible US-67, rail, power lines, towers, places, in grid metres from the SW corner
 * Scene units are kilometres: x east, z south (north is -z), y up = (height - z0 - curvature drop) x exaggeration.
 */
import * as THREE from "three";
import {OrbitControls} from "./vendor/three/OrbitControls.js";

const $ = id => document.getElementById(id);
const BASE = "data/terrain/";
const R_EARTH = 6371000, K_REFR = 0.13, EYE = 1.6;
const BEACON_FPM = 30, BEACON_DUTY = 0.5, BEACON_RAMP = 0.12;   // FAA L-864 red flasher, as in the animations
const status = $("status");

const st = {exag: 4, curve: false, layers: {}};
document.querySelectorAll("[data-layer]").forEach(i => { st.layers[i.dataset.layer] = i.checked; });

/* ---------- UTM 13N (NAD83/GRS80) inverse, Snyder (1987) eqs. 8-12..8-25 */
function utmToLatLon(x, y) {
  const a = 6378137, f = 1 / 298.257222101, k0 = 0.9996, lon0 = -105 * Math.PI / 180;
  const e2 = f * (2 - f), ep2 = e2 / (1 - e2);
  const M = y / k0;
  const mu = M / (a * (1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2 ** 3 / 256));
  const e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));
  const p1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * Math.sin(2 * mu) + (21 * e1 * e1 / 16 - 55 * e1 ** 4 / 32) * Math.sin(4 * mu)
    + (151 * e1 ** 3 / 96) * Math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * Math.sin(8 * mu);
  const s = Math.sin(p1), c = Math.cos(p1), t = Math.tan(p1);
  const C1 = ep2 * c * c, T1 = t * t, N1 = a / Math.sqrt(1 - e2 * s * s), R1 = a * (1 - e2) / (1 - e2 * s * s) ** 1.5;
  const D = (x - 500000) / (N1 * k0);
  const lat = p1 - (N1 * t / R1) * (D * D / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * ep2) * D ** 4 / 24
    + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * ep2 - 3 * C1 * C1) * D ** 6 / 720);
  const lon = lon0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6 + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * ep2 + 24 * T1 * T1) * D ** 5 / 120) / c;
  return [lat * 180 / Math.PI, lon * 180 / Math.PI];
}
// distance (m) and forward true azimuth (deg) on the ellipsoid; local-plane approximation, checked against pyproj Geod
// (Viewing Area to the US-67 high point: 39 879 m, 228.93 deg; both match to 0.1 m and 0.01 deg)
function distAz(lat1, lon1, lat2, lon2) {
  const a = 6378137, e2 = 0.00669438002290, r = Math.PI / 180, lm = (lat1 + lat2) / 2 * r, s2 = Math.sin(lm) ** 2;
  const M = a * (1 - e2) / (1 - e2 * s2) ** 1.5, N = a / Math.sqrt(1 - e2 * s2);
  const dn = (lat2 - lat1) * r * M, de = (lon2 - lon1) * r * N * Math.cos(lm);
  // the plane azimuth holds at the midpoint; the forward azimuth at the start differs by half the meridian convergence
  const az = Math.atan2(de, dn) / r - (lon2 - lon1) * Math.sin(lm) / 2;
  return [Math.hypot(dn, de), (az + 360) % 360];
}
const card = az => ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][Math.round(az / 22.5) % 16];

async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(u + " " + r.status); return r.json(); }
async function getBin(u) { const r = await fetch(u); if (!r.ok) throw new Error(u + " " + r.status); return r.arrayBuffer(); }
function getImg(u) {
  return new Promise((res, rej) => { const i = new Image(); i.decoding = "async"; i.onload = () => res(i); i.onerror = () => rej(new Error(u)); i.src = u; });
}

/* ---------- WebGL check */
const canvas = $("gl");
let renderer;
try {
  renderer = new THREE.WebGLRenderer({canvas, antialias: true, powerPreference: "high-performance"});
} catch (e) {
  status.innerHTML = 'This view needs WebGL, which this browser has switched off. The <a href="map.html">2D map</a> has the same roads, towers and sight lines.';
  throw e;
}
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;

Promise.all([getJSON(BASE + "meta.json"), getJSON(BASE + "overlays.json"), getBin(BASE + "height.bin"),
  getImg(BASE + "relief.webp"), getImg(BASE + "creeks.png")])
  .then(init)
  .catch(err => { console.error(err); status.textContent = "The terrain data could not be loaded. Check the connection and reload the page."; });

function init([meta, ov, hbuf, relief, creeks]) {
  const NX = meta.nx, NY = meta.ny, CELL = meta.mesh_m;
  const WM = meta.x1 - meta.x0, HM = meta.y1 - meta.y0;            // grid size, m
  const q = new Uint16Array(hbuf);
  const elev = new Float32Array(NX * NY);
  for (let i = 0; i < elev.length; i++) elev[i] = meta.z0 + q[i] * meta.zscale;
  const viewer = ov.places.find(p => p.k === "viewer");
  const [VLAT, VLON] = utmToLatLon(meta.x0 + viewer.p[0], meta.y0 + viewer.p[1]);

  // grid metres (from SW corner) -> scene km
  const sx = x => (x - WM / 2) / 1000, sz = y => (HM / 2 - y) / 1000;
  function elevAt(x, y) {                                         // bilinear on the 120 m vertices
    const c = Math.min(Math.max(x / CELL, 0), NX - 1.001), r = Math.min(Math.max((HM - y) / CELL, 0), NY - 1.001);
    const c0 = Math.floor(c), r0 = Math.floor(r), fc = c - c0, fr = r - r0, i = r0 * NX + c0;
    return (elev[i] * (1 - fc) + elev[i + 1] * fc) * (1 - fr) + (elev[i + NX] * (1 - fc) + elev[i + NX + 1] * fc) * fr;
  }
  const drop = (x, y) => {
    if (!st.curve) return 0;
    const d2 = (x - viewer.p[0]) ** 2 + (y - viewer.p[1]) ** 2;
    return d2 * (1 - K_REFR) / (2 * R_EARTH);
  };
  const sy = (z, x, y) => (z - meta.z0 - drop(x, y)) * st.exag / 1000;
  const V3 = (x, y, z) => new THREE.Vector3(sx(x), sy(z, x, y), sz(y));

  /* ---------- scene */
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 400);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true; controls.dampingFactor = 0.09;
  controls.maxPolarAngle = Math.PI * 0.495; controls.minDistance = 0.3; controls.maxDistance = 260;
  controls.zoomToCursor = true;
  const hemi = new THREE.HemisphereLight(0xfff4e2, 0x6b5a44, 2.2); scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xfff1dc, 1.3); sun.position.set(-30, 40, -30); scene.add(sun);

  // texture: relief + creeks + vector layers, composed on a canvas
  const big = renderer.capabilities.maxTextureSize >= 4096 && !(navigator.deviceMemory && navigator.deviceMemory < 4);
  const TW = big ? meta.tex_w : Math.round(meta.tex_w / 2), TH = big ? meta.tex_h : Math.round(meta.tex_h / 2);
  const tcan = document.createElement("canvas"); tcan.width = TW; tcan.height = TH;
  const tctx = tcan.getContext("2d");
  const tex = new THREE.CanvasTexture(tcan);
  tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  const PX = TW / WM, LW = TW / meta.tex_w;                         // canvas px per metre; line-width scale
  const tp = ([x, y]) => [x * PX, (HM - y) * PX];
  function path(c, close) {
    tctx.beginPath(); c.forEach((p, i) => { const [u, v] = tp(p); i ? tctx.lineTo(u, v) : tctx.moveTo(u, v); }); if (close) tctx.closePath();
  }
  function stroke(lines, color, w, dash, casing) {
    tctx.lineJoin = "round"; tctx.lineCap = "round";
    if (casing) { tctx.setLineDash([]); tctx.strokeStyle = casing; tctx.lineWidth = (w + 2.2) * LW; lines.forEach(c => { path(c); tctx.stroke(); }); }
    tctx.setLineDash(dash ? dash.map(d => d * LW) : []); tctx.strokeStyle = color; tctx.lineWidth = w * LW;
    lines.forEach(c => { path(c); tctx.stroke(); });
    tctx.setLineDash([]);
  }
  const roadsBy = k => ov.roads.filter(r => k.includes(r.k)).map(r => r.c);
  function compose() {
    tctx.drawImage(relief, 0, 0, TW, TH);
    if (st.layers.creeks) tctx.drawImage(creeks, 0, 0, TW, TH);
    if (st.layers.power) stroke(ov.power.map(r => r.c), "#e0c04a", 1.6, [7, 6]);
    if (st.layers.rail) { stroke(ov.rail.map(r => r.c), "#9b6fd0", 2.2, null, "rgba(30,20,40,.55)"); }
    if (st.layers.roads) {
      stroke(roadsBy(["CS"]), "#f1ece0", 1.1, null, "rgba(40,30,20,.35)");
      stroke(roadsBy(["CR"]), "#f4efe2", 1.6, [5, 3], "rgba(40,30,20,.45)");
      stroke(roadsBy(["FM", "RM"]), "#f4efe2", 2.2, null, "rgba(40,30,20,.55)");
      stroke(roadsBy(["US", "SH", "IH", "BU", "SL"]), "#fffaf0", 3.0, null, "rgba(40,30,20,.6)");
    }
    if (st.layers.us67) stroke(ov.us67_visible, "#ff8a00", 5.0, null, "rgba(60,25,0,.7)");
    if (st.layers.nopal && ov.roads_visible) {
      ov.roads_visible.filter(r => !/Nopal/.test(r.n)).forEach(r => stroke(r.runs, "#f39ac7", 3.6, null, "rgba(60,10,35,.6)"));
      ov.roads_visible.filter(r => /Nopal/.test(r.n)).forEach(r => stroke(r.runs, "#e8318a", 5.0, null, "rgba(60,10,35,.75)"));
    }
    tex.needsUpdate = true;
  }

  // terrain mesh
  const geo = new THREE.PlaneGeometry(WM / 1000, HM / 1000, NX - 1, NY - 1);
  geo.rotateX(-Math.PI / 2);
  geo.setAttribute("elev", new THREE.BufferAttribute(elev, 1));
  const pos = geo.attributes.position;
  const uni = {uContour: {value: 0}};
  const mat = new THREE.MeshLambertMaterial({map: tex});
  mat.onBeforeCompile = sh => {
    sh.uniforms.uContour = uni.uContour;
    sh.vertexShader = sh.vertexShader.replace("#include <common>", "#include <common>\nattribute float elev;\nvarying float vElev;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvElev = elev;");
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", "#include <common>\nuniform float uContour;\nvarying float vElev;")
      .replace("#include <map_fragment>", `#include <map_fragment>
      if (uContour > 0.0) {
        float e = vElev / uContour;
        float w = fwidth(e);
        float d = abs(fract(e - 0.5) - 0.5) / max(w, 1e-4);
        bool major = mod(floor(e + 0.5), 5.0) == 0.0;
        float line = 1.0 - smoothstep(major ? 0.8 : 0.4, major ? 1.8 : 1.2, d);
        line *= 1.0 - smoothstep(0.45, 0.9, w);   // fade where contours would crowd into a smear
        diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.30, 0.20, 0.12), line * (major ? 0.75 : 0.5));
      }`);
  };
  const terrain = new THREE.Mesh(geo, mat);
  scene.add(terrain);

  // side walls down to a base, so the terrain reads as a block
  const ring = [];                                          // vertex indices around the edge, clockwise from NW
  for (let c = 0; c < NX; c++) ring.push(c);
  for (let r = 1; r < NY; r++) ring.push(r * NX + NX - 1);
  for (let c = NX - 2; c >= 0; c--) ring.push((NY - 1) * NX + c);
  for (let r = NY - 2; r > 0; r--) ring.push(r * NX);
  ring.push(0);
  const skPos = new Float32Array(ring.length * 6), skIdx = [];
  for (let i = 0; i < ring.length - 1; i++) { const a = 2 * i, b = 2 * i + 2; skIdx.push(a, a + 1, b, b, a + 1, b + 1); }
  const skGeo = new THREE.BufferGeometry();
  skGeo.setAttribute("position", new THREE.BufferAttribute(skPos, 3)); skGeo.setIndex(skIdx);
  const skirt = new THREE.Mesh(skGeo, new THREE.MeshLambertMaterial({color: 0x8a6c4f, side: THREE.DoubleSide}));
  scene.add(skirt);
  function updateSkirt() {
    let base = Infinity;
    for (let i = 0; i < pos.count; i++) base = Math.min(base, pos.getY(i));
    base -= 0.6;
    ring.forEach((vi, i) => {
      skPos.set([pos.getX(vi), pos.getY(vi), pos.getZ(vi), pos.getX(vi), base, pos.getZ(vi)], 6 * i);
    });
    skGeo.attributes.position.needsUpdate = true; skGeo.computeVertexNormals(); skGeo.computeBoundingSphere();
  }

  function updateHeights() {
    for (let r = 0, i = 0; r < NY; r++) {
      const y = HM - r * CELL;
      for (let c = 0; c < NX; c++, i++) pos.setY(i, sy(elev[i], c * CELL, y));
    }
    pos.needsUpdate = true; geo.computeVertexNormals(); geo.computeBoundingSphere(); geo.computeBoundingBox();
    updateSkirt();
  }

  /* ---------- markers: towers, viewer, sight lines, pick marker */
  function glow(color) {
    const c = document.createElement("canvas"); c.width = c.height = 64; const g = c.getContext("2d");
    const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.18, color); gr.addColorStop(0.5, color.replace(/[\d.]+\)$/, "0.35)")); gr.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  }
  const redTex = glow("rgba(255,40,25,1)"), goldTex = glow("rgba(255,205,110,1)");
  const markers = new THREE.Group(); scene.add(markers);
  const towers = ov.towers.map(t => {
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineBasicMaterial({color: t.lit ? 0xd8d2c8 : 0x9a9a9a}));
    const sp = t.lit ? new THREE.Sprite(new THREE.SpriteMaterial({map: redTex, depthWrite: false, sizeAttenuation: false, transparent: true})) : null;
    if (sp) sp.scale.setScalar(0.028);
    markers.add(line); if (sp) markers.add(sp);
    return {t, line, sp};
  });
  const pin = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineBasicMaterial({color: 0xffd27a}));
  const pinDot = new THREE.Sprite(new THREE.SpriteMaterial({map: goldTex, depthWrite: false, depthTest: false, sizeAttenuation: false}));
  pinDot.scale.setScalar(0.04); markers.add(pin, pinDot);
  const pick = new THREE.Sprite(new THREE.SpriteMaterial({map: goldTex, depthWrite: false, depthTest: false, sizeAttenuation: false}));
  pick.scale.setScalar(0.03); pick.visible = false; markers.add(pick);
  let pickXY = null;
  const sightMat = new THREE.LineBasicMaterial({color: 0xffd27a, transparent: true, opacity: 0.55});
  const sight = new THREE.LineSegments(new THREE.BufferGeometry(), sightMat); markers.add(sight);
  const sightPts = ov.us67_visible.flatMap(run => run.filter((_, i) => i % 2 === 0 || run.length < 3));
  const NOPAL = (ov.roads_visible || []).find(r => /Nopal/.test(r.n));
  const sightMat2 = new THREE.LineBasicMaterial({color: 0xff5fb0, transparent: true, opacity: 0.6});
  const sight2 = new THREE.LineSegments(new THREE.BufferGeometry(), sightMat2); markers.add(sight2);
  const sightPts2 = NOPAL ? NOPAL.runs.flat() : [];

  function eyeZ() { return Math.max(viewer.z, elevAt(viewer.p[0], viewer.p[1])) + EYE; }
  function updateMarkers() {
    towers.forEach(({t, line, sp}) => {
      const g = elevAt(t.p[0], t.p[1]);
      const a = V3(t.p[0], t.p[1], g), b = V3(t.p[0], t.p[1], g + t.h);
      line.geometry.setFromPoints([a, b]); line.visible = st.layers.towers;
      if (sp) { sp.position.copy(b); sp.visible = st.layers.towers; }
    });
    const g = elevAt(viewer.p[0], viewer.p[1]);
    const top = V3(viewer.p[0], viewer.p[1], g); top.y += 0.35;
    pin.geometry.setFromPoints([V3(viewer.p[0], viewer.p[1], g), top]); pinDot.position.copy(top);
    if (pickXY) { const p = V3(pickXY[0], pickXY[1], elevAt(pickXY[0], pickXY[1])); pick.position.copy(p); }
    // sight lines: eye to each visible point of US-67 (headlamp 0.66 m above the road)
    if (st.layers.sight) {
      const e = V3(viewer.p[0], viewer.p[1], eyeZ()), arr = [];
      sightPts.forEach(p => { const b = V3(p[0], p[1], elevAt(p[0], p[1]) + 0.66); arr.push(e.x, e.y, e.z, b.x, b.y, b.z); });
      sight.geometry.setAttribute("position", new THREE.Float32BufferAttribute(arr, 3)); sight.geometry.computeBoundingSphere();
      const arr2 = [];
      sightPts2.forEach(p => { const b = V3(p[0], p[1], elevAt(p[0], p[1]) + 0.66); arr2.push(e.x, e.y, e.z, b.x, b.y, b.z); });
      sight2.geometry.setAttribute("position", new THREE.Float32BufferAttribute(arr2, 3)); sight2.geometry.computeBoundingSphere();
    }
    sight.visible = st.layers.sight && st.layers.us67;
    sight2.visible = st.layers.sight && st.layers.nopal;
    labels.forEach(L => { L.pos = V3(L.x, L.y, elevAt(L.x, L.y) + (L.lift || 0)); if (L.k === "viewer") L.pos.copy(top); });
  }

  /* ---------- labels */
  const labelBox = $("labels");
  const labels = [];
  function addLabel(text, x, y, k, sub) {
    const el = document.createElement("div"); el.className = "lab3 " + k; el.textContent = text;
    if (sub) { const s = document.createElement("small"); s.textContent = sub; el.appendChild(s); }
    labelBox.appendChild(el); labels.push({el, x, y, k, pos: new THREE.Vector3()});
  }
  ov.places.forEach(p => {
    if (p.k === "viewer") addLabel("Viewing area", p.p[0], p.p[1], "viewer", "you are here");
    else if (p.k === "town") addLabel(p.n, p.p[0], p.p[1], "town");
    else if (p.k === "peak") addLabel(p.n, p.p[0], p.p[1], "peak", `${p.z.toLocaleString()} m`);
    else if (p.k === "ref") addLabel(p.n, p.p[0], p.p[1], "peak", "1,650 m");
  });
  // one label per named highway, at the middle of its longest piece inside the grid
  const named = {};
  ov.roads.filter(r => !["CS", "CR"].includes(r.k) || /Nopal/.test(r.n)).forEach(r => {
    const c = r.c.filter(p => p[0] > 2000 && p[0] < WM - 2000 && p[1] > 2000 && p[1] < HM - 2000);
    if (c.length >= 2 && (!named[r.n] || c.length > named[r.n].length)) named[r.n] = c;
  });
  Object.entries(named).forEach(([n, c]) => {
    const p = c[Math.floor(c.length * (n === "US-67" ? 0.25 : 0.5))];
    addLabel(n.replace(" (county road)", ""), p[0], p[1], "road");
  });
  { const run = ov.us67_visible.reduce((a, b) => (b.length > a.length ? b : a)); const p = run[Math.floor(run.length / 2)];
    addLabel("US-67 visible from the platform", p[0], p[1], "road vis"); }
  if (NOPAL) { const run = NOPAL.runs.reduce((a, b) => (b.length > a.length ? b : a)); const p = run[Math.floor(run.length / 2)];
    addLabel("Nopal Road visible from the platform", p[0], p[1], "road vis nopal"); }

  // labels: projected every frame; lower-priority labels give way where they would overlap
  const PRI = {viewer: 0, peak: 1, town: 2, "road vis": 3, "road vis nopal": 3, road: 4};
  labels.sort((A, B) => PRI[A.k] - PRI[B.k]);
  const v = new THREE.Vector3();
  function placeLabels() {
    const w = canvas.clientWidth, h = canvas.clientHeight, show = st.layers.labels;
    labelBox.hidden = !show; if (!show) return;
    const camPos = camera.position, taken = [];
    labels.forEach(L => {
      const road = L.k.startsWith("road"), vis = L.k.includes("vis");
      const nop = L.k.includes("nopal");
      let ok = !(road && !vis && !st.layers.roads) && !(vis && !nop && !st.layers.us67) && !(nop && !st.layers.nopal);
      if (ok) {
        v.copy(L.pos).project(camera);
        ok = v.z < 1 && Math.abs(v.x) < 1.05 && Math.abs(v.y) < 1.05 && !(road && camPos.distanceTo(L.pos) > 90);
      }
      if (ok) {
        if (!L.w) { L.el.style.display = ""; L.w = L.el.offsetWidth; L.h = L.el.offsetHeight; }
        const x = (v.x + 1) / 2 * w, y = (1 - v.y) / 2 * h;
        const r = [x - L.w / 2, road ? y - L.h / 2 : y - L.h, L.w, L.h];
        ok = r[0] >= 2 && r[0] + r[2] <= w - 2 && r[1] >= 2 && !taken.some(q => r[0] < q[0] + q[2] + 4 && q[0] < r[0] + r[2] + 4 && r[1] < q[1] + q[3] + 2 && q[1] < r[1] + r[3] + 2);
        if (ok) { taken.push(r); L.el.style.transform = `translate(${r[0].toFixed(1)}px,${r[1].toFixed(1)}px)`; }
      }
      L.el.style.display = ok ? "" : "none";
    });
  }

  /* ---------- views (positions in grid metres, so they follow the exaggeration and curvature) */
  const ground = (x, y) => sy(elevAt(x, y), x, y);
  const pt = (x, y, up) => [sx(x), ground(x, y) + up, sz(y)];
  const wide = () => canvas.clientWidth / canvas.clientHeight;
  const AZ_US67 = 229 * Math.PI / 180;                     // platform to the US-67 high point (true bearing 228.9 deg)
  const VIEWS = {
    overview() {
      const [x, y] = viewer.p, ux = -0.845, uy = -0.534;   // toward Chinati Peak
      const back = 15000 * Math.max(1, 1.35 / wide());
      return {pos: pt(x - ux * back, y - uy * back, 13 * Math.max(1, 1.1 / wide())), tgt: pt(x + ux * 30000, y + uy * 30000, 0)};
    },
    platform() {
      const [x, y] = viewer.p, ux = Math.sin(AZ_US67), uy = Math.cos(AZ_US67);
      return {pos: pt(x - ux * 5500, y - uy * 5500, 1.7), tgt: pt(x + ux * 24000, y + uy * 24000, 0)};
    },
    us67() {
      const [x, y] = [37658, 29314];                       // US-67 high point
      return {pos: pt(x + 10000, y + 8000, 5.5), tgt: pt(x - 1500, y - 1500, 0)};
    },
    nopal() {
      const [x, y] = viewer.p, a = 196 * Math.PI / 180, ux = Math.sin(a), uy = Math.cos(a);   // toward the visible stretch of Nopal Road
      return {pos: pt(x - ux * 3500, y - uy * 3500, 1.4), tgt: pt(x + ux * 10000, y + uy * 10000, 0)};
    },
    top() {
      const panelOpen = !panel.classList.contains("closed") && wide() > 1.1;
      const h = Math.min(250, 1.15 * Math.max(76 / wide(), 70) / (2 * Math.tan(22.5 * Math.PI / 180)));
      const dx = panelOpen ? -0.13 * 2 * h * Math.tan(22.5 * Math.PI / 180) * wide() : 0;
      return {pos: [dx, h, 0.001], tgt: [dx, 0, 0]};
    },
  };
  const NOTES = {
    platform: "About 1.5 km above and 5 km behind the viewing area, looking southwest along the sight lines to the stretch of US-67 that can be seen from the platform. Relief doubled; curved Earth with normal refraction, as the line-of-sight model uses.",
    nopal: "Nopal Road, the county road south of the platform. Magenta marks the stretches, about 5 km in all at 7 to 13 km, where a car's lights can reach the platform. They lie between about 178° and 213° true, well left of US-67: the direction of the lights in Rob Pettengill's 2015 photo and in James Bunnell's photos of 19 February 2003, which a later re-analysis attributed to cars on this road. Relief tripled; sight lines over the curved Earth.",
    us67: "US-67 climbing out of the flat toward its high point. Orange is the stretch whose headlights reach the platform; the white road in between is hidden behind low rises.",
  };
  let mode = "overview";
  function setView(name, instant) {
    mode = name;
    document.querySelectorAll("[data-view]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.view === name)));
    if (name === "nopal") {
      if (st.exag !== 3) setExag(3);
      if (!st.curve) setCurve(true);
      if (!st.layers.sight) { st.layers.sight = true; document.querySelector('[data-layer="sight"]').checked = true; }
      if (!st.layers.nopal) { st.layers.nopal = true; document.querySelector('[data-layer="nopal"]').checked = true; compose(); }
      updateHeights(); updateMarkers();
    }
    if (name === "platform") {
      if (st.exag !== 2) setExag(2);
      if (!st.curve) setCurve(true);
      if (!st.layers.sight) { st.layers.sight = true; document.querySelector('[data-layer="sight"]').checked = true; }
      updateHeights(); updateMarkers();
    }
    const note = $("viewNote"); note.hidden = !NOTES[name]; note.textContent = NOTES[name] || "";
    const V = VIEWS[name]();
    fly(V.pos, V.tgt, instant);
  }
  let anim = null;
  function fly(pos, tgt, instant) {
    const p1 = new THREE.Vector3(...pos), t1 = new THREE.Vector3(...tgt);
    if (instant || matchMedia("(prefers-reduced-motion: reduce)").matches) { camera.position.copy(p1); controls.target.copy(t1); controls.update(); return; }
    anim = {p0: camera.position.clone(), t0: controls.target.clone(), p1, t1, start: performance.now(), dur: 1400};
  }

  /* ---------- controls */
  function setExag(e) {
    st.exag = e; $("exag").value = e; $("exagOut").textContent = (e % 1 ? e.toFixed(1) : e) + "×";
    rebuild();
  }
  function setCurve(on) {
    st.curve = on; st.layers.curve = on; document.querySelector('[data-layer="curve"]').checked = on; rebuild();
  }
  let pending = false;
  function rebuild() {
    if (pending) return; pending = true;
    requestAnimationFrame(() => {
      pending = false;
      updateHeights(); updateMarkers();
    });
  }
  $("exag").addEventListener("input", e => {
    // scale the camera and its target with the terrain so the framing holds
    const ratio = +e.target.value / st.exag;
    controls.target.y *= ratio; camera.position.y *= ratio;
    setExag(+e.target.value);
  });
  document.querySelectorAll("[data-layer]").forEach(inp => inp.addEventListener("change", () => {
    const k = inp.dataset.layer; st.layers[k] = inp.checked;
    if (k === "curve") { setCurve(inp.checked); if (!inp.checked && st.layers.sight) { st.layers.sight = false; document.querySelector('[data-layer="sight"]').checked = false; updateMarkers(); } return; }
    if (k === "nopal" || k === "us67") { compose(); updateMarkers(); return; }
    if (k === "sight") { if (inp.checked && !st.curve) setCurve(true); else updateMarkers(); return; }
    if (k === "contours") { uni.uContour.value = inp.checked ? 100 : 0; return; }
    if (k === "towers") { updateMarkers(); return; }
    if (k === "labels") return;
    compose();
  }));
  document.querySelectorAll("[data-view]").forEach(b => b.addEventListener("click", () => setView(b.dataset.view)));
  $("compass").addEventListener("click", () => {
    const t = controls.target, p = camera.position, r = Math.hypot(p.x - t.x, p.z - t.z);
    fly([t.x, p.y, t.z + r], [t.x, t.y, t.z]);
  });
  const panel = $("panel"), tog = $("toggle");
  tog.addEventListener("click", () => {
    const closed = panel.classList.toggle("closed");
    tog.textContent = closed ? "Show" : "Hide"; tog.setAttribute("aria-expanded", String(!closed));
  });
  if (matchMedia("(max-width:760px)").matches) { panel.classList.add("closed"); tog.textContent = "Show"; tog.setAttribute("aria-expanded", "false"); }

  /* ---------- tap for height, distance and bearing */
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  let down = null;
  canvas.addEventListener("pointerdown", e => { down = [e.clientX, e.clientY]; });
  canvas.addEventListener("pointerup", e => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 6) return;
    const r = canvas.getBoundingClientRect();
    ndc.set((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObject(terrain)[0]; if (!hit) return;
    const x = (hit.point.x * 1000) + WM / 2, y = HM / 2 - hit.point.z * 1000;
    pickXY = [x, y]; pick.visible = true; updateMarkers();
    const z = elevAt(x, y), [lat, lon] = utmToLatLon(meta.x0 + x, meta.y0 + y), [d, az] = distAz(VLAT, VLON, lat, lon);
    const dz = z - viewer.z;
    const out = $("readout"); out.hidden = false;
    out.innerHTML = `<b>${Math.round(z).toLocaleString()} m</b> (${Math.round(z * 3.28084).toLocaleString()} ft) above sea level, ` +
      `<b>${Math.abs(Math.round(dz))} m</b> ${dz >= 0 ? "above" : "below"} the platform.<br>` +
      `<b>${(d / 1000).toFixed(1)} km</b> from the viewing area, bearing <b>${az.toFixed(0)}°</b> (${card(az)}).<br>` +
      `<span class="fine">${lat.toFixed(5)}, ${lon.toFixed(5)} · height from the 120 m mesh, so ± a few metres</span>`;
    if (panel.classList.contains("closed")) tog.click();
  });

  /* ---------- theme */
  function applyTheme() {
    const t = document.documentElement.getAttribute("data-theme");
    const dark = t === "dark" || t === "night" || (!t && matchMedia("(prefers-color-scheme: dark)").matches);
    const sky = new THREE.Color(dark ? 0x101826 : 0xc9d6e2);
    scene.background = sky; scene.fog = new THREE.Fog(sky, 60, 230);
    hemi.intensity = dark ? 1.6 : 2.2; sun.intensity = dark ? 0.9 : 1.3;      // dusk light in the dark themes
  }
  document.addEventListener("themechange", applyTheme);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
  applyTheme();

  /* ---------- size and loop */
  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(canvas);
  resize();

  const needle = $("needle");
  const dir = new THREE.Vector3();
  renderer.setAnimationLoop(now => {
    if (anim) {
      const k = Math.min((now - anim.start) / anim.dur, 1), e = k < 0.5 ? 4 * k ** 3 : 1 - (-2 * k + 2) ** 3 / 2;
      camera.position.lerpVectors(anim.p0, anim.p1, e); controls.target.lerpVectors(anim.t0, anim.t1, e);
      if (k >= 1) anim = null;
    }
    controls.update();
    // beacons: 30 flashes a minute, half on, soft 0.12 s ramps
    const ph = (now / 1000 * BEACON_FPM / 60) % 1, on = BEACON_DUTY;
    const lv = ph < on ? Math.min(1, ph * 60 / BEACON_FPM / BEACON_RAMP, (on - ph) * 60 / BEACON_FPM / BEACON_RAMP) : 0;
    towers.forEach(({sp}) => { if (sp) sp.material.opacity = 0.15 + 0.85 * lv; });
    camera.getWorldDirection(dir);
    needle.setAttribute("transform", `rotate(${(-Math.atan2(dir.x, -dir.z) * 180 / Math.PI).toFixed(1)})`);
    renderer.render(scene, camera);
    placeLabels();
  });

  compose();
  updateHeights(); updateMarkers();
  setView("overview", true);
  status.hidden = true;
  window.__t3d = {scene, camera, controls, st, setView, setExag, uni, renderer};   // for debugging in the console
}

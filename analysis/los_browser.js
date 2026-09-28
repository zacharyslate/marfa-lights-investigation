/*
 * Marfa Lights investigation — terrain line-of-sight engine (browser version).
 *
 * WHY IN A BROWSER: the analysis workspace used on 2026-09-28 could not reach USGS servers,
 * so the DEM was fetched and the line-of-sight computed in a browser tab, and only the
 * results were exported (data/derived/los_results.json, data/derived/los_near_far.json).
 * This file is the exact procedure, collected into one script for reproducibility.
 *
 * HOW TO RUN: open https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer
 * in a browser, open the developer console, paste this file, then run:
 *     await runAll(HWY)     // HWY = contents of data/inputs/hwy.json
 * It downloads data/derived/los_results.json and los_near_far.json equivalents.
 *
 * MODEL
 *   DEM     USGS 3DEP 3DEPElevation exportImage, bbox -104.62,29.72,-103.86,30.40 (EPSG:4326),
 *           2736 x 2448 px (~1 arc-second), F32 BSQ, bilinear resampling.
 *   Earth   sphere R = 6,371,000 m for path distance/azimuth (error << DEM error here).
 *   Viewer  -103.8827973, 30.2751108; eye 1.6 m above DEM.
 *   Target  highway resampled every 60 m; headlight 0.7 m (also 2.5 m).
 *   Path    terrain sampled every 15 m; first 30 m and last 60 m skipped.
 *   Refraction  constant coefficient k, apparent drop d^2 (1-k) / 2R.
 *   k_crit  target visible iff k >= k_crit, where
 *           1 - k_crit = min_i 2R [ (z_t - E)/d_t - (z_i - E)/d_i ] / (d_t - d_i)
 *           (checked against brute-force visibility at k_crit +/- 0.01: 0/30 mismatches).
 */
const R = 6371000, D2R = Math.PI / 180, V = [-103.8827973, 30.2751108];
const EYE = 1.6, KSTD = 0.13, SS = 15, EXCL_START = 30, EXCL_END = 60, NEAR_ZONE = 1000;
const BBOX = [-104.62, 29.72, -103.86, 30.40], W = 2736, H = 2448;
let Z = null;

async function loadDEM() {
  const p = new URLSearchParams({bbox: BBOX.join(","), bboxSR: "4326", imageSR: "4326", size: W + "," + H,
    format: "bsq", pixelType: "F32", noDataInterpretation: "esriNoDataMatchAny",
    interpolation: "RSP_BilinearInterpolation", renderingRule: JSON.stringify({rasterFunction: "None"}), f: "image"});
  const r = await fetch("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage?" + p);
  const buf = await r.arrayBuffer();
  Z = new Float32Array(buf.slice(0, W * H * 4));   // server appends trailing bytes; row-major, north-up
}
const dx = (BBOX[2] - BBOX[0]) / W, dy = (BBOX[3] - BBOX[1]) / H;
function dem(lon, lat) {
  const fx = (lon - BBOX[0]) / dx - 0.5, fy = (BBOX[3] - lat) / dy - 0.5;
  const c = Math.floor(fx), r = Math.floor(fy);
  if (c < 0 || r < 0 || c >= W - 1 || r >= H - 1) return NaN;
  const tx = fx - c, ty = fy - r, i = r * W + c;
  return (Z[i] * (1 - tx) + Z[i + 1] * tx) * (1 - ty) + (Z[i + W] * (1 - tx) + Z[i + W + 1] * tx) * ty;
}
function inv(lon1, lat1, lon2, lat2) {
  const p1 = lat1 * D2R, p2 = lat2 * D2R, dl = (lon2 - lon1) * D2R;
  const a = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  const d = 2 * R * Math.asin(Math.sqrt(a));
  const az = (Math.atan2(Math.sin(dl) * Math.cos(p2), Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl)) / D2R + 360) % 360;
  return [az, d];
}
function fwd(lon, lat, az, d) {
  const p1 = lat * D2R, l1 = lon * D2R, t = az * D2R, dr = d / R;
  const p2 = Math.asin(Math.sin(p1) * Math.cos(dr) + Math.cos(p1) * Math.sin(dr) * Math.cos(t));
  const l2 = l1 + Math.atan2(Math.sin(t) * Math.sin(dr) * Math.cos(p1), Math.cos(dr) - Math.sin(p1) * Math.sin(p2));
  return [l2 / D2R, p2 / D2R];
}
function resample(hwy, step = 60) {
  const pts = []; let ch = 0, carry = 0;
  for (let s = 0; s < hwy.length - 1; s++) {
    const a = hwy[s], b = hwy[s + 1], [, L] = inv(a[0], a[1], b[0], b[1]); let t = carry;
    while (t <= L) { const f = t / L; pts.push([a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), ch + t]); t += step; }
    carry = t - L; ch += L;
  }
  return pts;
}
function analyse(tlon, tlat, z0) {
  const Ee = z0 + EYE, cs = 1 - KSTD;
  const [az, dt] = inv(V[0], V[1], tlon, tlat), zT = dem(tlon, tlat), n = Math.ceil(dt / SS);
  const out = {az, dt, zT, kc: {}, kcd: {}};
  const di = [], zi = [];
  for (let i = 1; i < n; i++) {
    const d = i * dt / n; if (d < EXCL_START || d > dt - EXCL_END) continue;
    const [lo, la] = fwd(V[0], V[1], az, d); di.push(d); zi.push(dem(lo, la));
  }
  for (const h of [0.7, 2.5]) {
    const gt = (zT + h - Ee) / dt; let cmax = Infinity, dlim = null, cfar = Infinity;
    for (let j = 0; j < di.length; j++) {
      const c = 2 * R * (gt - (zi[j] - Ee) / di[j]) / (dt - di[j]);
      if (c < cmax) { cmax = c; dlim = di[j]; }
      if (di[j] <= dt - NEAR_ZONE && c < cfar) cfar = c;
    }
    out.kc[h] = 1 - cmax; out.kcd[h] = dlim; if (h === 0.7) out.kcFar = 1 - cfar;
  }
  let thmax = -Infinity, dob = null, thfar = -Infinity, dfar = null;
  for (let j = 0; j < di.length; j++) {
    const th = (zi[j] - Ee - di[j] * di[j] * cs / (2 * R)) / di[j];
    if (th > thmax) { thmax = th; dob = di[j]; }
    if (di[j] <= dt - NEAR_ZONE && th > thfar) { thfar = th; dfar = di[j]; }
  }
  const tht = (zT + 0.7 - Ee - dt * dt * cs / (2 * R)) / dt;
  Object.assign(out, {alpha: Math.atan(tht) * 1000, clr: (tht - thmax) * dt, dob, farclr: (tht - thfar) * dt, dfar});
  return out;
}
function skyline(z0, a0 = 215, a1 = 285, step = 0.1) {
  const E = z0 + EYE, cs = 1 - KSTD, sky = [];
  for (let a = a0; a <= a1 + 1e-9; a += step) {
    let mx = -Infinity, dm = 0;
    for (let d = 60; d < 95000; d += 30) {
      const [lo, la] = fwd(V[0], V[1], a, d), zz = dem(lo, la); if (isNaN(zz)) break;
      const th = (zz - E - d * d * cs / (2 * R)) / d; if (th > mx) { mx = th; dm = d; }
    }
    sky.push([+a.toFixed(1), +(Math.atan(mx) * 1000).toFixed(2), +(dm / 1000).toFixed(1)]);
  }
  return sky;
}
function profile(az, maxD = 45000, step = 250) {
  const arr = [];
  for (let d = 0; d <= maxD; d += step) { const [lo, la] = fwd(V[0], V[1], az, d), zz = dem(lo, la); arr.push(isNaN(zz) ? null : Math.round(zz * 10) / 10); }
  return arr;
}
function save(name, obj) {
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(obj)], {type: "application/json"}));
  a.download = name; a.click();
}
async function runAll(HWY) {
  await loadDEM();
  const z0 = dem(V[0], V[1]);
  const pts = resample(HWY), cap = v => Math.max(-9.99, Math.min(99, v));
  const res = pts.map(p => Object.assign({ch: p[2], lon: p[0], lat: p[1]}, analyse(p[0], p[1], z0)));
  const prof = {}; for (const a of [229.5, 234, 235, 240, 250, 260, 270, 277]) prof[a] = profile(a);
  save("los_results.json", {
    meta: {dem: "USGS 3DEP 3DEPElevation ImageServer exportImage, bbox " + BBOX.join(",") + ", " + W + "x" + H + " px (~1 arcsec), bilinear",
           viewer: V, z0, eye: EYE, sample_step_m: SS, excl_start_m: EXCL_START, excl_end_m: EXCL_END, hwy_step_m: 60, earth_R: R, kstd: KSTD},
    hwy_fields: ["ch_m", "lon", "lat", "zT", "kc07", "kc25", "alpha_mrad_k013_h07", "clear_m_k013_h07", "occluder_km_k013", "kcd07_km", "az", "dist_m"],
    hwy: res.map(r => [Math.round(r.ch), +r.lon.toFixed(6), +r.lat.toFixed(6), +r.zT.toFixed(2), +cap(r.kc[0.7]).toFixed(4), +cap(r.kc[2.5]).toFixed(4),
      +r.alpha.toFixed(3), +Math.max(-9999, r.clr).toFixed(2), r.dob == null ? null : +(r.dob / 1000).toFixed(3),
      r.kcd[0.7] == null ? null : +(r.kcd[0.7] / 1000).toFixed(3), +r.az.toFixed(3), Math.round(r.dt)]),
    sky: skyline(z0), prof});
  save("los_near_far.json", {
    fields: ["ch_m", "kc07_excl60", "kc07_excl1000", "farclr_m_k013", "far_occluder_km", "lon", "lat", "zT", "az", "dist_m", "alpha_mrad", "kc25", "clr_all"],
    rows: res.map(r => [Math.round(r.ch), +cap(r.kc[0.7]).toFixed(4), +cap(r.kcFar).toFixed(4), +Math.max(-9999, r.farclr).toFixed(2),
      r.dfar == null ? null : +(r.dfar / 1000).toFixed(3), +r.lon.toFixed(6), +r.lat.toFixed(6), +r.zT.toFixed(2), +r.az.toFixed(4),
      Math.round(r.dt), +r.alpha.toFixed(4), +cap(r.kc[2.5]).toFixed(4), +Math.max(-9999, r.clr).toFixed(3)])});
}

/* Marfa Lights Sky Finder: camera overlay, calibration and calibrated bearing/height measurement.
   Geometry
     Device orientation (W3C, Z-X'-Y''): R = Rz(alpha) Rx(beta) Ry(gamma) maps device axes to East-North-Up.
     The back camera looks along device -Z, so the pointing vector is R (0, 0, -1).
     Screen right/up follow screen.orientation.angle.
   Calibration
     true_az = raw_az + dAz, true_el = raw_el + dEl, with dAz, dEl set by centring a known target.
     A target's position comes from this project's terrain model (towers) or Astronomy Engine (stars, planets). */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const D2R = Math.PI / 180, R2D = 180 / Math.PI;
  const VIEW = {lat: 30.2751108, lon: -103.8827973, h: 1495.2};
  let DECL = 6.2;                 // replaced by the value in site.json once it loads
  const norm = a => ((a % 360) + 360) % 360, angDiff = (a, b) => ((a - b + 540) % 360) - 180;
  const fmt = (v, n = 1) => { const s = Number(v).toFixed(n); return /^-0(\.0+)?$/.test(s) ? s.slice(1) : s; };
  const mrad2deg = m => Math.atan(m / 1000) * R2D;

  // ------------------------------------------------------------------ data
  let S = null, ZR = null, STARS = [], MK = null, dataFailed = false;
  const okJson = r => { if (!r.ok) throw new Error(r.status); return r.json(); };
  const ready = Promise.all([
    fetch("data/site.json?v=9").then(okJson).then(j => { S = j; if (S.declination) DECL = S.declination.deg; }).catch(() => { dataFailed = true; }),
    fetch("data/zos_rate.json?v=9").then(okJson).then(j => { ZR = j; }).catch(() => {}),
    fetch("data/bright_stars.json?v=1").then(okJson).then(j => { STARS = j.stars; }).catch(() => {})])
    .then(() => { if (S && window.MarfaMask) MK = MarfaMask.build(ZR, null, skyM); });
  function skyM(az) { if (!S) return null; const s = S.sky.find(x => Math.abs(x[0] - Math.round(az * 10) / 10) < 0.051); return s ? s[1] : null; }

  // ------------------------------------------------------------------ orientation maths
  function rotMatrix(a, b, g) {
    const ca = Math.cos(a * D2R), sa = Math.sin(a * D2R), cb = Math.cos(b * D2R), sb = Math.sin(b * D2R), cg = Math.cos(g * D2R), sg = Math.sin(g * D2R);
    // Rz(a) * Rx(b) * Ry(g), rows of the 3x3 matrix
    return [
      [ca * cg - sa * sb * sg, -sa * cb, ca * sg + sa * sb * cg],
      [sa * cg + ca * sb * sg, ca * cb, sa * sg - ca * sb * cg],
      [-cb * sg, sb, cb * cg]];
  }
  const mulv = (M, v) => [M[0][0] * v[0] + M[0][1] * v[1] + M[0][2] * v[2], M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2], M[2][0] * v[0] + M[2][1] * v[1] + M[2][2] * v[2]];
  const mulTv = (M, v) => [M[0][0] * v[0] + M[1][0] * v[1] + M[2][0] * v[2], M[0][1] * v[0] + M[1][1] * v[1] + M[2][1] * v[2], M[0][2] * v[0] + M[1][2] * v[1] + M[2][2] * v[2]];
  const enu = (az, el) => [Math.cos(el * D2R) * Math.sin(az * D2R), Math.cos(el * D2R) * Math.cos(az * D2R), Math.sin(el * D2R)];
  const azel = v => [norm(Math.atan2(v[0], v[1]) * R2D), Math.asin(Math.max(-1, Math.min(1, v[2]))) * R2D];
  function screenAxes() {
    const ang = (screen.orientation && typeof screen.orientation.angle === "number") ? screen.orientation.angle : (window.orientation || 0);
    const t = ang * D2R;
    return {right: [Math.cos(t), -Math.sin(t), 0], up: [Math.sin(t), Math.cos(t), 0]};
  }

  // ------------------------------------------------------------------ state
  const st = {R: null, hist: [], raw: null, absolute: false, headingOffset: null, dAz: 0, dEl: 0, cal: null, check: null,
    fovLong: 69, zoom: 1, camera: false, zone: true, stars: true, mag: false, lastEvt: 0};
  // A saved calibration is reused for 30 minutes, but only on phones that report absolute compass headings (Android):
  // on iPhone the heading reference is re-derived each time the page loads, so an old correction would not apply.
  try { const c = JSON.parse(localStorage.getItem("mlfg-skycal") || "null"); if (c && c.abs && Date.now() - c.t < 30 * 60e3) { Object.assign(st, {dAz: c.dAz, dEl: c.dEl, cal: c.cal, calRestored: true}); } } catch (e) {}
  try { const f = parseFloat(localStorage.getItem("mlfg-fov")); if (f) st.fovLong = f; } catch (e) {}

  function onOrient(e) {
    if (e.alpha === null || e.beta === null || e.gamma === null) return;
    let a = e.alpha;
    const abs = e.absolute === true || e.type === "deviceorientationabsolute";
    if (abs) st.absolute = true;
    if (!abs && !st.absolute && st.calRestored) { st.dAz = 0; st.dEl = 0; st.cal = null; st.calRestored = false; }
    else if (st.absolute && e.type === "deviceorientation") return;      // prefer the absolute stream when both fire
    const R = rotMatrix(a, e.beta, e.gamma);
    const fwd = mulv(R, [0, 0, -1]);
    let [az, el] = azel(fwd);
    // iOS: alpha is relative; use the compass heading once for a first guess
    if (!abs && typeof e.webkitCompassHeading === "number" && st.headingOffset === null && e.webkitCompassAccuracy >= 0) {
      st.headingOffset = norm(e.webkitCompassHeading + DECL - az);
    }
    if (abs) st.headingOffset = DECL;           // absolute alpha is referenced to magnetic north
    const off = st.headingOffset || 0;
    st.R = R; st.rawAz = norm(az + off); st.rawEl = el; st.lastEvt = performance.now();
    st.hist.push(enu(st.rawAz, el)); if (st.hist.length > 20) st.hist.shift();
    schedule();
  }
  // mean pointing over the last ~0.3-1 s, and its scatter
  function pointing(n = 20) {
    const h = st.hist.slice(-n); if (!h.length) return null;
    const m = [0, 0, 0]; h.forEach(v => { m[0] += v[0]; m[1] += v[1]; m[2] += v[2]; });
    const L = Math.hypot(...m); const u = m.map(x => x / L);
    const [az, el] = azel(u);
    const sd = Math.sqrt(h.reduce((s, v) => { const d = Math.acos(Math.min(1, v[0] * u[0] + v[1] * u[1] + v[2] * u[2])) * R2D; return s + d * d; }, 0) / h.length);
    return {rawAz: az, rawEl: el, az: norm(az + st.dAz), el: el + st.dEl, sd};
  }

  // ------------------------------------------------------------------ projection
  const cv = $("ov"), ctx = cv.getContext("2d"), video = $("video");
  let W = 0, H = 0, DPR = 1;
  function resize() {
    DPR = Math.min(2, window.devicePixelRatio || 1); W = cv.clientWidth; H = cv.clientHeight;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); ctx.setTransform(DPR, 0, 0, DPR, 0, 0); schedule();
  }
  window.addEventListener("resize", resize);
  function focalPx() {
    // pixels per unit tangent: FOV along the camera's long side, cover-cropped into the screen
    const half = st.fovLong / 2 * D2R;
    if (st.camera && video.videoWidth) {
      const vw = video.videoWidth, vh = video.videoHeight, s = Math.max(W / vw, H / vh);
      return st.zoom * s * Math.max(vw, vh) / 2 / Math.tan(half);
    }
    return st.zoom * Math.max(W, H) / 2 / Math.tan(half);
  }
  function project(az, el, F, ax) {
    // target in true az/el -> uncalibrated frame -> device frame -> screen
    if (!st.R) return null;
    const w = enu(norm(az - st.dAz - (st.headingOffset || 0)), el - st.dEl);
    const v = mulTv(st.R, w);
    const f = -v[2]; if (f <= 0.02) return null;
    const x = (v[0] * ax.right[0] + v[1] * ax.right[1]) / f, y = (v[0] * ax.up[0] + v[1] * ax.up[1]) / f;
    return [W / 2 + F * x, H / 2 - F * y];
  }

  // ------------------------------------------------------------------ targets (calibration)
  function astroTargets(date) {
    if (typeof Astronomy === "undefined") return [];
    const A = Astronomy, t = A.MakeTime(date), obs = new A.Observer(VIEW.lat, VIEW.lon, VIEW.h), out = [];
    const rot = A.Rotation_EQJ_HOR(t, obs);
    STARS.forEach(([name, ra, dec, mag]) => {
      if (!name || mag > 2.2) return;
      const v = A.RotateVector(rot, A.VectorFromSphere(new A.Spherical(dec, ra, 1), t)), s = A.HorizonFromVector(v, "normal");
      if (s.lat > 3) out.push({kind: "star", name, az: s.lon, el: s.lat, mag});
    });
    ["Venus", "Jupiter", "Mars", "Saturn", "Mercury", "Moon"].forEach(b => {
      const eq = A.Equator(b, t, obs, true, true), hz = A.Horizon(t, obs, eq.ra, eq.dec, "normal");
      if (hz.altitude > 3) out.push({kind: b === "Moon" ? "moon" : "planet", name: b === "Moon" ? "Moon (centre)" : b, az: hz.azimuth, el: hz.altitude,
        mag: b === "Moon" ? -12 : A.Illumination(b, t).mag});
    });
    return out;
  }
  function towerTargets() {
    if (!S) return [];
    return S.towers.filter(t => t.light !== "none" && t.a !== null && t.kc !== null && t.kc <= 0.13)
      .map(t => ({kind: "tower", name: `${fmt(t.h, 0)} m tower (red light) at ${fmt(t.az, 1)}°`, az: t.az, el: mrad2deg(t.a), d: t.d}));
  }

  // ------------------------------------------------------------------ drawing
  let raf = 0;
  function schedule() { if (!raf) raf = requestAnimationFrame(draw); }
  const RED = "#ff4a2c", DIM = "rgba(255,74,44,.55)";
  function draw() {
    raf = 0;
    ctx.clearRect(0, 0, W, H);
    if (!st.R || !S) { hud(null); return; }
    const F = focalPx(), ax = screenAxes(), P = pointing(8);
    const halfSpan = Math.atan(Math.hypot(W, H) / 2 / F) * R2D + 3;
    const near = az => Math.abs(angDiff(az, P.az)) <= halfSpan;
    ctx.lineJoin = "round"; ctx.font = "600 12px 'JetBrains Mono', monospace"; ctx.textBaseline = "middle";

    // known-source mask (expected ordinary lights per hour, envelope of two refraction states)
    if (st.zone && ZR) {
      const fills = ["rgba(255,74,44,.10)", "rgba(255,74,44,.18)", "rgba(255,74,44,.26)", "rgba(255,74,44,.34)"];
      ZR.standard.levels.forEach((lv, i) => [ZR.standard, ZR.inversion].forEach(Z => Z.rate_polys[String(lv)].forEach(r => {
        if (!r.some(q => near(q[0]))) return;
        ctx.beginPath(); let ok = false;
        r.forEach((q, j) => { const p = project(q[0], mrad2deg(q[1]), F, ax); if (!p) return; if (!ok) { ctx.moveTo(p[0], p[1]); ok = true; } else ctx.lineTo(p[0], p[1]); });
        if (ok) { ctx.closePath(); ctx.fillStyle = fills[i]; ctx.fill("evenodd"); }
      })));
    }
    // horizon line and bearing ticks
    ctx.strokeStyle = DIM; ctx.lineWidth = 1; ctx.fillStyle = RED;
    ctx.beginPath(); let started = false;
    for (let a = P.az - halfSpan; a <= P.az + halfSpan; a += 0.5) {
      const p = project(norm(a), 0, F, ax); if (!p) { started = false; continue; }
      if (!started) { ctx.moveTo(p[0], p[1]); started = true; } else ctx.lineTo(p[0], p[1]);
    }
    ctx.setLineDash([4, 6]); ctx.stroke(); ctx.setLineDash([]);
    const step = F > 900 ? 1 : F > 450 ? 2 : 5;
    for (let a = Math.ceil((P.az - halfSpan) / step) * step; a <= P.az + halfSpan; a += step) {
      const p = project(norm(a), 0, F, ax), q = project(norm(a), a % (step * 5) === 0 ? -0.35 : -0.15, F, ax); if (!p || !q) continue;
      ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); ctx.stroke();
      if (a % (step * (step === 5 ? 2 : 5)) === 0) {
        const lab = st.mag ? `${fmt(norm(a - DECL), 0)}°M` : `${fmt(norm(a), 0)}°`;
        ctx.textAlign = "center"; ctx.fillText(lab, q[0], q[1] + 10);
      }
    }
    // skyline and ridges
    const sky = S.sky.filter(s => near(s[0]));
    [[3, "rgba(255,74,44,.35)", 1], [1, RED, 1.8]].forEach(([col, color, lw]) => {
      ctx.beginPath(); let on = false;
      sky.forEach(s => { const p = project(s[0], mrad2deg(s[col]), F, ax); if (!p) { on = false; return; } if (!on) { ctx.moveTo(p[0], p[1]); on = true; } else ctx.lineTo(p[0], p[1]); });
      ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.stroke();
    });
    // roads in view, rail in view
    const dot = (az, m, r, c) => { const p = project(az, mrad2deg(m), F, ax); if (!p) return; ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, 7); ctx.fillStyle = c; ctx.fill(); };
    S.hwy.forEach(p => { if ((p[6] === "v" || p[6] === "m") && near(p[2])) dot(p[2], p[7], p[6] === "v" ? 2.2 : 1.5, p[6] === "v" ? "#ff7a5c" : "rgba(255,122,92,.6)"); });
    S.roads.forEach(r => r.p.forEach(q => { if (q[6] === "v" && near(q[2])) dot(q[2], q[4], 1.8, "#ff9a7c"); }));
    S.railpano.forEach(r => { if (r[4] <= 0.13 && near(r[1])) dot(r[1], r[3], 1.5, "rgba(255,160,140,.8)"); });
    // road labels (once per road, at the middle of what is on screen)
    const label = (txt, az, m) => { const p = project(az, mrad2deg(m), F, ax); if (!p) return; ctx.textAlign = "left"; ctx.fillStyle = RED; ctx.fillText(txt, p[0] + 6, p[1] - 10); };
    const v67 = S.hwy.filter(p => p[6] === "v" && near(p[2])); if (v67.length) { const m = v67[Math.floor(v67.length / 2)]; label("US-67", m[2], m[7]); }
    S.roads.forEach(r => { const v = r.p.filter(q => q[6] === "v" && near(q[2])); if (v.length > 3) { const m = v[Math.floor(v.length / 2)]; label(r.n.replace(" (Pinto Canyon Rd)", ""), m[2], m[4]); } });
    // towers
    towerTargets().forEach(t => { if (!near(t.az)) return; const p = project(t.az, t.el, F, ax); if (!p) return;
      ctx.beginPath(); ctx.moveTo(p[0], p[1] - 6); ctx.lineTo(p[0] + 6, p[1]); ctx.lineTo(p[0], p[1] + 6); ctx.lineTo(p[0] - 6, p[1]); ctx.closePath();
      ctx.strokeStyle = RED; ctx.lineWidth = 1.5; ctx.stroke(); ctx.textAlign = "left"; ctx.fillStyle = RED; ctx.fillText("tower", p[0] + 9, p[1]); });
    // towns (label on the skyline)
    S.towns.forEach(t => { if (!near(t.az)) return; const s = S.sky.find(x => Math.abs(x[0] - Math.round(t.az * 10) / 10) < 0.051); if (!s) return;
      const p = project(t.az, mrad2deg(s[1]) + 0.6, F, ax); if (!p) return; ctx.textAlign = "center"; ctx.fillStyle = DIM; ctx.fillText(t.n.replace(", Chihuahua", ""), p[0], p[1]); });
    // stars and planets
    if (st.stars) {
      if (!st.astro || performance.now() - st.astroT > 20000) { st.astro = astroTargets(new Date()); st.astroT = performance.now(); }
      st.astro.forEach(o => { if (!near(o.az)) return; const p = project(o.az, o.el, F, ax); if (!p) return;
        const r = Math.max(1.5, 4 - o.mag); ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, 7); ctx.strokeStyle = RED; ctx.lineWidth = 1.2; ctx.stroke();
        if (o.mag < 1.6) { ctx.textAlign = "left"; ctx.fillStyle = DIM; ctx.fillText(o.name, p[0] + r + 4, p[1]); } });
    }
    // crosshair
    const cx = W / 2, cy = H / 2;
    ctx.strokeStyle = "#ff8a70"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(cx - 22, cy); ctx.lineTo(cx - 6, cy); ctx.moveTo(cx + 6, cy); ctx.lineTo(cx + 22, cy); ctx.moveTo(cx, cy - 22); ctx.lineTo(cx, cy - 6); ctx.moveTo(cx, cy + 6); ctx.lineTo(cx, cy + 22); ctx.stroke();
    ctx.beginPath(); ctx.arc(cx, cy, 14, 0, 7); ctx.stroke();
    hud(P);
  }
  function hud(P) {
    if (!P) { $("hudL").innerHTML = `<b>—</b>${dataFailed ? "Couldn't load the map data. Check your connection and reload." : st.R ? "" : "Waiting for motion sensors…"}`; return; }
    const b = st.mag ? `${fmt(norm(P.az - DECL))}° mag` : `${fmt(P.az)}° true`;
    $("hudL").innerHTML = `<b>${b}</b>height ${fmt(P.el, 2)}° · steadiness ±${fmt(P.sd, 2)}°`;
    const c = st.cal;
    $("hudR").innerHTML = c ? `Calibrated on ${c.name}<br>${fmt((Date.now() - c.t) / 60000, 0)} min ago${st.check ? ` · last check ${fmt(st.check.err, 2)}° off` : ""}`
      : `<span style="color:#ff8a70">Not calibrated: compass only, often 5–10° off</span>`;
  }

  // ------------------------------------------------------------------ sheets and buttons
  const sheets = ["calSheet", "recSheet", "moreSheet"];
  const open = id => sheets.forEach(s => $(s).classList.toggle("open", s === id));
  document.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", () => open(null)));
  const toast = (t, ms = 2600) => { const el = $("toast"); el.textContent = t; el.style.display = "block"; clearTimeout(toast.h); toast.h = setTimeout(() => { el.style.display = "none"; }, ms); };

  function listTargets() {
    const P = pointing(10); if (!P) return [];
    return towerTargets().concat(st.astro || astroTargets(new Date()))
      .map(t => ({...t, sep: Math.acos(Math.max(-1, Math.min(1, enu(t.az, t.el).reduce((s, x, i) => s + x * enu(P.az, P.el)[i], 0)))) * R2D}))
      .sort((a, b) => a.sep - b.sep).slice(0, 12);
  }
  $("bCal").addEventListener("click", () => {
    const T = listTargets(); if (!T.length) { toast("No sensor data yet."); return; }
    $("calList").innerHTML = T.map((t, i) => `<li><button type="button" data-i="${i}"><span>${t.name}</span><span class="mono">${fmt(t.az)}° · ${fmt(t.el, 1)}° · ${fmt(t.sep, 0)}° away</span></button></li>`).join("");
    $("calList").querySelectorAll("button").forEach(b => b.onclick = () => {
      // recompute a star or planet's position now: they move about 0.25° per minute
      const t0 = T[+b.dataset.i], P = pointing(20);
      const t = t0.kind === "tower" ? t0 : (astroTargets(new Date()).find(o => o.name === t0.name) || t0);
      st.dAz = angDiff(t.az, P.rawAz); st.dEl = t.el - P.rawEl;
      st.cal = {name: t.name, kind: t.kind, az: t.az, el: t.el, t: Date.now(), sd: P.sd}; st.check = null;
      st.calRestored = false;
      try { localStorage.setItem("mlfg-skycal", JSON.stringify({dAz: st.dAz, dEl: st.dEl, cal: st.cal, t: Date.now(), abs: st.absolute})); } catch (e) {}
      open(null); toast(`Calibrated on ${t.name}. Bearing corrected by ${fmt(st.dAz, 1)}°, height by ${fmt(st.dEl, 1)}°.`); schedule();
    });
    open("calSheet");
  });
  $("calClear").addEventListener("click", () => { st.dAz = 0; st.dEl = 0; st.cal = null; st.check = null; try { localStorage.removeItem("mlfg-skycal"); } catch (e) {} open(null); schedule(); });
  $("bCheck").addEventListener("click", () => {
    if (!st.cal) { toast("Calibrate first, then point back at the same light to check."); return; }
    const P = pointing(20), c = st.cal;
    let t = c; if (c.kind !== "tower") { const now = (st.astro = astroTargets(new Date())).find(o => o.name === c.name); if (now) t = now; }
    const dAz = angDiff(P.az, t.az), dEl = P.el - t.el, err = Math.hypot(dAz * Math.cos(t.el * D2R), dEl);
    st.check = {err, dAz, dEl, t: Date.now()};
    toast(`Crosshair is ${fmt(err, 2)}° from ${c.name} (bearing ${dAz >= 0 ? "+" : ""}${fmt(dAz, 2)}°, height ${dEl >= 0 ? "+" : ""}${fmt(dEl, 2)}°). ${err > 0.5 ? "Recalibrate." : "Good."}`, 4200);
    schedule();
  });

  // quick noise check (same logic as the report form; look-ups from assets/mask.js)
  const rateAt = (az, m) => MK ? MK.rate(az, m) : null, fixedAt = (az, m) => MK ? MK.fixed(az, m) : null;
  const RATE_TXT = ["about one every 10–100 hours", "0.1–1 per hour", "1–10 per hour", "10 or more per hour"];
  function nearby(az, tol) {
    const out = [], within = a => Math.abs(angDiff(a, az)) <= tol;
    if (S.hwy.some(p => (p[6] === "v" || p[6] === "m") && within(p[2]))) out.push("US-67 traffic");
    S.roads.forEach(r => { if (r.p.some(q => q[6] === "v" && within(q[2]))) out.push(`${r.n} traffic`); });
    if (S.railpano.some(r => r[4] <= 0.13 && within(r[1]))) out.push("railroad");
    S.towers.forEach(t => { if (t.light !== "none" && t.kc !== null && t.kc <= 1 && within(t.az)) out.push(`lit tower at ${fmt(t.az, 1)}°`); });
    S.towns.forEach(t => { if (within(t.az)) out.push(t.n.replace(", Chihuahua", "")); });
    return out;
  }
  $("bRec").addEventListener("click", () => {
    const P = pointing(20); if (!P) { toast("No sensor data yet."); return; }
    if (!S) { toast("Couldn't load the map data. Check your connection and reload."); return; }
    const DOM = (ZR && ZR.standard.params.az_domain_deg) || [150, 300], inDom = P.az >= DOM[0] && P.az <= DOM[1];
    const m = Math.tan(P.el * D2R) * 1000, rl = inDom ? rateAt(P.az, m) : null, fx = inDom ? fixedAt(P.az, m) : null;
    const skyMv = skyM(P.az);
    const err = st.check ? Math.max(st.check.err, P.sd) : null;
    const tol = st.cal ? Math.max(0.3, err || 0.3) : 5;
    const near = nearby(P.az, tol);
    const rec = {time: new Date().toISOString(), true_bearing: +P.az.toFixed(2), magnetic_bearing: +norm(P.az - DECL).toFixed(2), elev_deg: +P.el.toFixed(3),
      window_deg: +tol.toFixed(2), refraction_k: 0.13, us67_in_view: near.includes("US-67 traffic"),
      top_candidate: near[0] || "none", top: near[0] || "none", source: "camera",
      calibration: st.cal ? {target: st.cal.name, minutes_ago: +((Date.now() - st.cal.t) / 60000).toFixed(1), last_check_deg: st.check ? +st.check.err.toFixed(2) : null} : null,
      steadiness_deg: +P.sd.toFixed(3), note: ""};
    let LOG = []; try { LOG = JSON.parse(localStorage.getItem("mlfg-log") || "[]"); } catch (e) {}
    LOG.push(rec); try { localStorage.setItem("mlfg-log", JSON.stringify(LOG)); } catch (e) {}
    const above = skyMv !== null && m > skyMv + 1.75;
    $("recOut").innerHTML = `<p class="mono">${fmt(P.az, 2)}° true (${fmt(norm(P.az - DECL), 2)}° magnetic) · height ${fmt(P.el, 2)}°<br>${new Date().toLocaleTimeString()}</p>` +
      `<p>${st.cal ? `Calibrated on ${st.cal.name}${st.check ? `, last check ${fmt(st.check.err, 2)}° off` : ". Tap <b>Check</b> on the same light to measure your error"}.` : "<b>Not calibrated</b>: this bearing may be 5–10° off."}</p>` +
      `<p>${skyMv === null ? "" : above ? "<b>Above the skyline</b>: aircraft, stars, planets, satellites or the aerostat are the usual candidates. " : "Below the skyline, against the land. "}` +
      `${!inDom ? "<b>Outside the modelled view</b> (150°–300° true): traffic in this direction isn't worked out, so the app can't say whether this light is unusual. " : rl === null ? "" : rl >= 0 ? `Ordinary lights expected here: <b>${RATE_TXT[rl]}</b>.` : fx ? "" : "<b>Few moving ordinary lights expected here</b> (under one per 100 hours from known sources)."}${fx ? " <b>A fixed light can appear here</b>: a lit tower, town glow or the aerostat." : ""}</p>` +
      `<p>${near.length ? `Known sources within ±${fmt(tol, 1)}°: ${near.join(", ")}.` : `No known light source within ±${fmt(tol, 1)}°.`}</p>` +
      `<p>Saved to your field log on this phone.</p>`;
    open("recSheet");
  });
  $("bMore").addEventListener("click", () => open("moreSheet"));
  // magnifier: digital zoom of the picture and the overlay together
  const ZOOMS = [1, 3, 8];
  $("bZoom").addEventListener("click", () => {
    st.zoom = ZOOMS[(ZOOMS.indexOf(st.zoom) + 1) % ZOOMS.length];
    $("bZoom").textContent = `${st.zoom}×`; video.style.transform = `scale(${st.zoom})`; schedule();
  });
  $("fov").value = st.fovLong; $("fovOut").textContent = `${fmt(st.fovLong, 0)}°`;
  $("fov").addEventListener("input", e => { st.fovLong = +e.target.value; $("fovOut").textContent = `${fmt(st.fovLong, 0)}°`; try { localStorage.setItem("mlfg-fov", st.fovLong); } catch (err) {} schedule(); });
  $("vbright").addEventListener("input", e => { video.style.opacity = e.target.value; });
  video.style.opacity = $("vbright").value;
  $("lZone").addEventListener("change", e => { st.zone = e.target.checked; schedule(); });
  $("lStars").addEventListener("change", e => { st.stars = e.target.checked; schedule(); });
  $("lMag").addEventListener("change", e => { st.mag = e.target.checked; schedule(); });

  // ------------------------------------------------------------------ start / stop
  let stream = null, wake = null, prevTheme = null;
  async function start(withCamera) {
    try {
      if (typeof DeviceOrientationEvent !== "undefined" && typeof DeviceOrientationEvent.requestPermission === "function") {
        const r = await DeviceOrientationEvent.requestPermission(); if (r !== "granted") throw new Error("Motion sensors were not allowed.");
      }
    } catch (e) { $("support").textContent = String(e.message || e); return; }
    window.addEventListener("deviceorientationabsolute", onOrient);
    window.addEventListener("deviceorientation", onOrient);
    if (withCamera) {
      try {
        stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: {ideal: "environment"}, width: {ideal: 1920}, height: {ideal: 1080}}, audio: false});
        video.srcObject = stream; st.camera = true; video.onloadedmetadata = () => { video.play(); schedule(); };
      } catch (e) { toast("Camera not available. Showing the overlay only.", 3500); st.camera = false; }
    }
    try { if (navigator.wakeLock) wake = await navigator.wakeLock.request("screen"); } catch (e) {}
    try { prevTheme = localStorage.getItem("mlfg-theme"); localStorage.setItem("mlfg-theme", "night"); } catch (e) {}
    document.documentElement.setAttribute("data-theme", "night");
    document.body.classList.add("live"); resize();
    await ready; schedule();
    setTimeout(() => { if (!st.R) toast("No motion-sensor data. This page needs a phone or tablet with a compass and gyroscope.", 5000); }, 2500);
  }
  function stop() {
    window.removeEventListener("deviceorientationabsolute", onOrient); window.removeEventListener("deviceorientation", onOrient);
    if (stream) stream.getTracks().forEach(t => t.stop()); stream = null; st.camera = false;
    try { if (wake) wake.release(); } catch (e) {}
    document.body.classList.remove("live"); open(null);
    try { if (prevTheme) localStorage.setItem("mlfg-theme", prevTheme); else localStorage.removeItem("mlfg-theme"); } catch (e) {}
    if (prevTheme && prevTheme !== "auto") document.documentElement.setAttribute("data-theme", prevTheme); else document.documentElement.removeAttribute("data-theme");
    if (FROM_APP) location.href = "app/#identify";
  }
  const FROM_APP = new URLSearchParams(location.search).get("from") === "app";
  $("startCam").addEventListener("click", () => start(true));
  $("startNoCam").addEventListener("click", () => start(false));
  $("bExit").addEventListener("click", stop);
  const ok = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia) && "DeviceOrientationEvent" in window;
  $("support").textContent = ok ? "Works in current Safari (iPhone) and Chrome (Android). It needs camera and motion permission." :
    "This browser can't provide the camera or motion sensors. Try Safari on iPhone or Chrome on Android.";

  // test hook: feed a synthetic orientation (used by the automated checks)
  window.SKYFINDER = {st, onOrient, rotMatrix, azel, enu, mulv, pointing, project, focalPx, astroTargets, towerTargets, draw, start, ready: () => ready};
})();

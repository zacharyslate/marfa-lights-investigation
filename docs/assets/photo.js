/* Marfa Lights Field Guide: photo checker (docs/photo.html).
 *
 * A photo from the Viewing Area is treated as a pinhole camera at the platform. Its pointing (bearing, tilt,
 * roll) and focal length in pixels are found by one of three routes, or by hand:
 *   skyline  the sky/land edge found in the photo is matched to the modelled skyline (data/site.json "sky");
 *   lights   bright points in the photo are matched to fixed lights of known position (lit towers) and,
 *            when the time is known, to stars and planets (Astronomy Engine, normal refraction);
 *   both     the two together; the skyline fit is refined with every anchor it brings into line;
 *   by hand  drag the model over the photo, or tap a known light/peak and say what it is.
 * Each light in the photo is then turned into a true bearing and an apparent elevation and checked against
 * the known-source mask (assets/mask.js) and the catalogue of sources in data/site.json. The uncertainty of
 * the alignment decides whether the photo-quality mask (tier A, +-0.3 deg) or the compass-quality mask
 * (tier B, +-3 deg) applies, or whether no verdict can be given.
 * Nothing is uploaded: files are decoded in the browser (exifr for metadata, UTIF.js + pako for TIFF,
 * libheif for HEIC when the browser cannot open it, the camera's embedded preview for RAW files).
 */
(async function () {
  const $ = id => document.getElementById(id);
  const D2R = Math.PI / 180, R2D = 180 / Math.PI;
  const norm = a => ((a % 360) + 360) % 360;
  const angDiff = (a, b) => ((a - b + 540) % 360) - 180;
  const m2d = m => Math.atan(m / 1000) * R2D, d2m = d => Math.tan(d * D2R) * 1000;
  const fmt = (v, n = 1) => Number(v).toLocaleString("en-US", {minimumFractionDigits: n, maximumFractionDigits: n});
  const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  const okJson = r => { if (!r.ok) throw new Error(r.status); return r.json(); };

  let S, ZOS, ZR, STARS = [];
  try {
    [S, ZOS, ZR] = await Promise.all([fetch("data/site.json?v=9").then(okJson), fetch("data/zos.json?v=9").then(okJson),
      fetch("data/zos_rate.json?v=9").then(okJson)]);
    STARS = (await fetch("data/bright_stars.json?v=1").then(okJson).catch(() => ({stars: []}))).stars;
  } catch (e) {
    $("drop").innerHTML = "<span><b>Couldn't load the model data.</b><p>Check your connection and reload the page.</p></span>";
    return;
  }
  const VIEW = S.viewer;
  const skyAt = az => {
    const s = S.sky; if (az < s[0][0] || az > s[s.length - 1][0]) return null;
    const i = Math.min(s.length - 2, Math.max(0, Math.floor((az - s[0][0]) / 0.1))), f = (az - s[i][0]) / 0.1;
    return s[i][1] + f * (s[i + 1][1] - s[i][1]);
  };
  const MK = MarfaMask.build(ZR, ZOS, skyAt);
  const ridge10At = az => {
    const s = S.sky; if (az < s[0][0] || az > s[s.length - 1][0]) return null;
    const i = Math.min(s.length - 2, Math.max(0, Math.floor((az - s[0][0]) / 0.1))), f = (az - s[i][0]) / 0.1;
    return s[i][3] + f * (s[i + 1][3] - s[i][3]);
  };
  const SKY = S.sky.map(r => [r[0], m2d(r[1])]);                    // model skyline, true az / apparent el (deg)
  const RIDGE = S.sky.map(r => [r[0], m2d(r[3])]);                  // the nearest ridge (within 10 km)
  const K = 0.13;
  const HWY = S.hwy.filter(p => p[6] !== "h").map(p => ({az: p[2], el: m2d(p[7]), d: p[3], cls: p[6]}));
  const HWYINV = S.hwy.filter(p => p[6] === "h" && p[5] !== null && p[5] <= 1).map(p => ({az: p[2], el: m2d(p[7]), d: p[3], kc: p[5]}));
  const ROADS = S.roads.flatMap(r => r.p.filter(q => q[6] === "v").map(q => ({az: q[2], el: m2d(q[4]), d: q[3], n: r.n})));
  const RAIL = S.railpano.filter(r => r[4] !== null && r[4] <= K).map(r => ({az: r[1], el: m2d(r[3]), d: r[2], n: r[0] === "UP" ? "Union Pacific trains" : "Texas Pacifico trains"}));
  const TOWERS = S.towers.filter(t => t.light !== "none" && t.kc !== null && t.kc <= K && t.a !== null)
    .map(t => ({az: t.az, el: m2d(t.a), d: t.d, n: `${fmt(t.h, 0)} m tower, ${t.owner || "FCC " + t.id}`, id: t.id, kind: "tower"}));
  const TOWNS = S.towns.filter(t => t.a !== undefined && t.a !== null).map(t => ({az: t.az, el: m2d(t.a), d: t.d, n: `${t.n} (town lights)`}));
  const chAz = 238.252, PEAKS = [{az: chAz, el: m2d(skyAt(chAz)), d: 67.5, n: "Chinati Peak (summit on the skyline)", kind: "peak"}];

  /* ------------------------------------------------------------ camera model */
  const st = {img: null, W: 0, H: 0, exif: null, cam: null, f35: null, fKnown: false, when: null, gpsKm: null,
    det: null, anchors: [], lights: [], tool: "pan", fitInfo: null, view: {s: 1, x: 0, y: 0}, layers: {}};
  document.querySelectorAll("[data-l]").forEach(i => { st.layers[i.dataset.l] = i.checked; });

  function basis(c) {
    const a = c.az * D2R, e = c.el * D2R, r = c.roll * D2R;
    const F = [Math.cos(e) * Math.sin(a), Math.cos(e) * Math.cos(a), Math.sin(e)];
    const R0 = [Math.cos(a), -Math.sin(a), 0];
    const U0 = [R0[1] * F[2] - R0[2] * F[1], R0[2] * F[0] - R0[0] * F[2], R0[0] * F[1] - R0[1] * F[0]];
    const cr = Math.cos(r), sr = Math.sin(r);
    return {F, R: R0.map((v, i) => cr * v + sr * U0[i]), U: U0.map((v, i) => -sr * R0[i] + cr * v)};
  }
  function projector(c) {
    const B = basis(c), cx = st.W / 2, cy = st.H / 2, f = c.f;
    return (az, el) => {
      const ca = Math.cos(el * D2R), d = [ca * Math.sin(az * D2R), ca * Math.cos(az * D2R), Math.sin(el * D2R)];
      const z = d[0] * B.F[0] + d[1] * B.F[1] + d[2] * B.F[2]; if (z < 0.05) return null;
      return [cx + f * (d[0] * B.R[0] + d[1] * B.R[1] + d[2] * B.R[2]) / z, cy - f * (d[0] * B.U[0] + d[1] * B.U[1] + d[2] * B.U[2]) / z];
    };
  }
  function unproject(c, u, v) {
    const B = basis(c), x = (u - st.W / 2) / c.f, y = (st.H / 2 - v) / c.f;
    const d = B.F.map((F, i) => F + x * B.R[i] + y * B.U[i]), n = Math.hypot(...d);
    return [norm(Math.atan2(d[0], d[1]) * R2D), Math.asin(d[2] / n) * R2D];
  }
  const hfov = c => 2 * Math.atan(st.W / 2 / c.f) * R2D;
  const f35ToPx = f35 => f35 / 43.267 * Math.hypot(st.W, st.H);      // CIPA: 35 mm equivalent by the diagonal
  const pxToF35 = f => f * 43.267 / Math.hypot(st.W, st.H);

  /* ------------------------------------------------------------ file decoding */
  const RAWEXT = /\.(dng|cr2|cr3|nef|nrw|arw|srf|sr2|raf|orf|rw2|pef|srw|x3f|3fr|iiq|erf|kdc|mrw)$/i;
  function kind(buf, name) {
    const b = new Uint8Array(buf, 0, Math.min(64, buf.byteLength)), s = String.fromCharCode(...b.slice(0, 16));
    if (RAWEXT.test(name)) return "raw";
    if (b[0] === 0xff && b[1] === 0xd8) return "jpeg";
    if (b[0] === 0x89 && s.slice(1, 4) === "PNG") return "png";
    if (s.slice(0, 4) === "RIFF" && String.fromCharCode(...b.slice(8, 12)) === "WEBP") return "webp";
    if (s.slice(4, 8) === "ftyp") { const br = String.fromCharCode(...b.slice(8, 12)); return /hei|hev|mif|msf|avi/.test(br) ? (br === "avif" ? "avif" : "heic") : br === "crx " ? "raw" : "other"; }
    if ((b[0] === 0x49 && b[1] === 0x49) || (b[0] === 0x4d && b[1] === 0x4d)) return "tiff";
    return "other";
  }
  async function bitmapFrom(blob) {
    try { return await createImageBitmap(blob, {imageOrientation: "from-image"}); } catch (e) { return null; }
  }
  // the largest embedded JPEG (camera RAW files carry a full-size or large preview)
  function rawPreview(buf) {
    const b = new Uint8Array(buf); let best = null;
    for (let i = 0; i < b.length - 4; i++) {
      if (b[i] !== 0xff || b[i + 1] !== 0xd8 || b[i + 2] !== 0xff) continue;
      let j = i + 2, w = 0, h = 0, ok = false;
      while (j < Math.min(b.length - 9, i + 200000)) {           // walk the marker segments to the frame header
        if (b[j] !== 0xff) break;
        const m = b[j + 1], len = (b[j + 2] << 8) | b[j + 3];
        if (m === 0xc0 || m === 0xc1 || m === 0xc2) { h = (b[j + 5] << 8) | b[j + 6]; w = (b[j + 7] << 8) | b[j + 8]; ok = true; break; }
        if (m === 0xc3 || m === 0xda) break;                      // lossless (raw data) or scan start without a frame
        j += 2 + len;
      }
      if (ok && w * h > (best ? best.w * best.h : 0)) best = {off: i, w, h};
      if (ok) i += 1000;
    }
    return best;
  }
  async function decodeHeic(buf) {
    if (!window.libheif) await new Promise((res, rej) => { const s = document.createElement("script"); s.src = "assets/vendor/libheif/libheif.js"; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
    const wasmBinary = await fetch("assets/vendor/libheif/libheif.wasm").then(r => { if (!r.ok) throw new Error("HEIC decoder not available"); return r.arrayBuffer(); });
    let lib = window.libheif({wasmBinary});
    if (lib && lib.then) lib = await lib;
    const imgs = new lib.HeifDecoder().decode(new Uint8Array(buf));
    if (!imgs.length) throw new Error("no image in HEIC");
    const im = imgs[0], w = im.get_width(), h = im.get_height();
    const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
    const ctx = cv.getContext("2d"), id = ctx.createImageData(w, h);
    await new Promise((res, rej) => im.display(id, d => d ? res() : rej(new Error("HEIC decode"))));
    ctx.putImageData(id, 0, 0); return cv;
  }
  async function decodeTiff(buf) {
    if (!window.UTIF) {
      for (const src of ["assets/vendor/utif/pako_inflate.min.js", "assets/vendor/utif/UTIF.js"])
        await new Promise((res, rej) => { const s = document.createElement("script"); s.src = src; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
    }
    const ifds = UTIF.decode(buf);
    let best = ifds[0]; ifds.forEach(f => { if ((f.t256 ? f.t256[0] : 0) * (f.t257 ? f.t257[0] : 0) > (best.t256 ? best.t256[0] : 0) * (best.t257 ? best.t257[0] : 0)) best = f; });
    UTIF.decodeImage(buf, best, ifds);
    const rgba = UTIF.toRGBA8(best), w = best.width, h = best.height;
    const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
    cv.getContext("2d").putImageData(new ImageData(new Uint8ClampedArray(rgba.buffer, rgba.byteOffset, w * h * 4), w, h), 0, 0);
    return cv;
  }
  async function loadFile(file) {
    $("drop").innerHTML = `<span><b>Reading ${esc(file.name)}…</b></span>`;
    const buf = await file.arrayBuffer(), k = kind(buf, file.name);
    let exif = null;
    try { exif = await exifr.parse(buf, {tiff: true, exif: true, gps: true, ifd0: true, ifd1: false, xmp: false, icc: false, iptc: false, makerNote: false, translateValues: true, reviveValues: false}); } catch (e) {}
    let src = null, note = "";
    if (k === "raw") {
      const p = rawPreview(buf);
      if (p) { src = await bitmapFrom(new Blob([new Uint8Array(buf, p.off)], {type: "image/jpeg"})); note = `Camera RAW: using the embedded ${p.w} × ${p.h} preview.`; }
      if (!src && /^(II|MM)/.test(String.fromCharCode(...new Uint8Array(buf, 0, 2)))) { try { src = await decodeTiff(buf); note = "Camera RAW (TIFF-based)."; } catch (e) {} }
    } else if (k === "tiff") {
      src = await bitmapFrom(new Blob([buf], {type: "image/tiff"}));
      if (!src) src = await decodeTiff(buf);
    } else {
      src = await bitmapFrom(new Blob([buf], {type: file.type || "image/" + k}));
      if (!src && k === "heic") { $("drop").innerHTML = `<span><b>Opening the HEIC file…</b><p>Loading the HEIC decoder (about 1.5 MB, once).</p></span>`; src = await decodeHeic(buf); note = "HEIC decoded in the page."; }
    }
    if (!src) throw new Error(k === "raw" ? "No usable preview in this RAW file. Export a JPEG or TIFF from your RAW software and try that." : "This browser could not open the file.");
    // working copy: long side at most 3200 px
    const sc = Math.min(1, 3200 / Math.max(src.width, src.height));
    const cv = document.createElement("canvas"); cv.width = Math.round(src.width * sc); cv.height = Math.round(src.height * sc);
    cv.getContext("2d").drawImage(src, 0, 0, cv.width, cv.height);
    start(cv, exif || {}, file.name, note, {w: src.width, h: src.height});
  }

  /* ------------------------------------------------------------ setup after load */
  function marfaToUTC(local) {                                     // "YYYY-MM-DDTHH:MM[:SS]" in America/Chicago -> Date
    const [d, t] = local.split("T"), [Y, Mo, Da] = d.split("-").map(Number), [h, mi, se] = (t + ":0:0").split(":").map(Number);
    const guess = Date.UTC(Y, Mo - 1, Da, h, mi, se || 0);
    const off = dt => { const p = new Intl.DateTimeFormat("en-US", {timeZone: "America/Chicago", hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit"}).formatToParts(new Date(dt));
      const g = n => +p.find(x => x.type === n).value; return Date.UTC(g("year"), g("month") - 1, g("day"), g("hour"), g("minute"), g("second")) - dt; };
    return new Date(guess - off(guess - off(guess)));
  }
  function toMarfaLocal(date) {
    const p = new Intl.DateTimeFormat("en-CA", {timeZone: "America/Chicago", hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit"}).formatToParts(date);
    const g = n => p.find(x => x.type === n).value; return `${g("year")}-${g("month")}-${g("day")}T${g("hour")}:${g("minute")}:${g("second")}`;
  }
  function exifTime(ex) {
    // EXIF times are the camera's wall clock, "YYYY:MM:DD HH:MM:SS", with an optional offset in OffsetTimeOriginal
    // each time has its own offset tag: OffsetTime belongs to ModifyDate (often the editing computer's zone), not to the shot
    const pick = [[ex.DateTimeOriginal, ex.OffsetTimeOriginal], [ex.CreateDate || ex.DateTimeDigitized, ex.OffsetTimeDigitized], [ex.ModifyDate, ex.OffsetTime]].find(p => p[0]);
    if (!pick) return null;
    const t = pick[0], m = typeof t === "string" && t.match(/^(\d{4}):(\d\d):(\d\d)[ T](\d\d):(\d\d):(\d\d)/);
    if (!m) return null;
    const wall = `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}`, off = pick[1];
    if (off && /^[+-]\d\d:\d\d$/.test(off)) return {date: new Date(wall + off), src: `camera clock with its time zone (${off})`};
    return {date: marfaToUTC(wall), src: "camera clock, assumed set to Marfa time (no time zone in the file). Camera clocks are often off: check it"};
  }
  function start(cv, exif, name, note, orig) {
    st.img = cv; st.W = cv.width; st.H = cv.height; st.exif = exif;
    st.det = null; st.anchors = []; st.lights = []; st.fitInfo = null;
    // focal length: 35 mm equivalent, else focal length x sensor resolution, else unknown
    let f35 = exif.FocalLengthIn35mmFormat || exif.FocalLengthIn35mmFilm || null, fsrc = "";
    if (f35) fsrc = "from the file (35 mm equivalent)";
    else if (exif.FocalLength && exif.FocalPlaneXResolution && (exif.ExifImageWidth || exif.ImageWidth)) {
      const unit = {2: 25.4, 3: 10, 4: 1, 5: 0.001, "inches": 25.4, "Inches": 25.4, "Centimeter": 10, "centimeters": 10}[exif.FocalPlaneResolutionUnit] || 25.4;
      const longPx = Math.max(exif.ExifImageWidth || exif.ImageWidth, exif.ExifImageHeight || exif.ImageHeight || 0);
      const sensW = longPx / exif.FocalPlaneXResolution * unit;     // mm along the long side
      const sensD = sensW * Math.hypot(1, Math.min(st.W, st.H) / Math.max(st.W, st.H));
      f35 = exif.FocalLength * 43.267 / sensD; fsrc = `from the focal length (${fmt(exif.FocalLength, 1)} mm) and sensor size in the file`;
    }
    st.fKnown = !!f35; st.f35 = f35 || 50;
    $("f35").value = st.fKnown ? (+st.f35).toFixed(1) : "";
    $("fNote").textContent = st.fKnown ? `Lens ${fsrc}. Change it if the photo was cropped or zoomed digitally.` :
      "The file doesn't say which lens was used. Enter it if you know it; otherwise the alignment will work it out, which needs the skyline or two known lights.";
    const tm = exifTime(exif); st.when = tm ? tm.date : null;
    $("when").value = st.when ? toMarfaLocal(st.when) : "";
    const cam = [exif.Make, exif.Model].filter(Boolean).join(" ");
    const rows = [["File", esc(name)], ["Size", `${orig.w} × ${orig.h}${st.W !== orig.w ? ` (working at ${st.W} × ${st.H})` : ""}`]];
    if (cam) rows.push(["Camera", esc(cam)]);
    if (exif.LensModel) rows.push(["Lens", esc(exif.LensModel)]);
    if (exif.ExposureTime) rows.push(["Exposure", `${exif.ExposureTime >= 1 ? fmt(exif.ExposureTime, 1) + " s" : "1/" + Math.round(1 / exif.ExposureTime) + " s"}${exif.ISO ? ", ISO " + exif.ISO : ""}${exif.FNumber ? ", f/" + exif.FNumber : ""}`]);
    rows.push(["Time", tm ? esc(tm.src) : "not in the file: enter it for stars and planets"]);
    if (note) rows.push(["Note", esc(note)]);
    $("meta").innerHTML = rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("");
    // location check
    st.gpsKm = null;
    if (exif.latitude && exif.longitude) {
      const R = 6371, p1 = VIEW.lat * D2R, p2 = exif.latitude * D2R, dl = (exif.longitude - VIEW.lon) * D2R;
      st.gpsKm = 2 * R * Math.asin(Math.sqrt(Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2));
    }
    $("where").innerHTML = st.gpsKm === null ? `<p class="fine">No location in the file. The checker assumes the photo was taken on the viewing platform.</p>`
      : st.gpsKm <= 0.4 ? `<p class="fine">Location in the file: ${fmt(st.gpsKm * 1000, 0)} m from the platform. Good.</p>`
      : `<div class="warn"><b>This photo was taken ${fmt(st.gpsKm, 1)} km from the viewing platform.</b> The model is worked out for the platform, so bearings to nearby towers and roads will be off and the verdicts below are not reliable.</div>`;
    // starting pointing: toward the US-67 high point, level
    st.cam = {az: 229, el: 0, roll: 0, f: f35ToPx(st.f35)};
    ["s1", "s2", "s3", "s4"].forEach(id => { $(id).hidden = false; });
    $("drop").hidden = true; $("tools").hidden = false; $("hud").hidden = false;
    st.userZoomed = false; fitView(); syncSliders(); render();
    $("fit").hidden = false; $("fit").className = "fit"; $("fit").innerHTML = "Not aligned yet. Try <b>Skyline</b> first; if the mountains are black, try <b>Lights</b>, or line it up by hand.";
    renderLights();
  }

  /* ------------------------------------------------------------ sky objects */
  function skyObjects() {
    if (!st.when || typeof Astronomy === "undefined") return [];
    const A = Astronomy, t = A.MakeTime(st.when), obs = new A.Observer(VIEW.lat, VIEW.lon, VIEW.z), out = [];
    const rot = A.Rotation_EQJ_HOR(t, obs);
    STARS.forEach(([name, ra, dec, mag]) => {
      if (mag > 3.0) return;
      const s = A.HorizonFromVector(A.RotateVector(rot, A.VectorFromSphere(new A.Spherical(dec, ra, 1), t)), "normal");
      if (s.lat > -1) out.push({az: norm(s.lon), el: s.lat, n: name || "star", mag, kind: "star"});
    });
    ["Venus", "Jupiter", "Mars", "Saturn", "Mercury", "Moon"].forEach(b => {
      const eq = A.Equator(b, t, obs, true, true), hz = A.Horizon(t, obs, eq.ra, eq.dec, "normal");
      if (hz.altitude > -1) out.push({az: hz.azimuth, el: hz.altitude, n: b, mag: b === "Moon" ? -12 : A.Illumination(b, t).mag, kind: b === "Moon" ? "moon" : "planet"});
    });
    return out;
  }
  function sunAlt() {
    if (!st.when || typeof Astronomy === "undefined") return null;
    const A = Astronomy, t = A.MakeTime(st.when), obs = new A.Observer(VIEW.lat, VIEW.lon, VIEW.z);
    const eq = A.Equator("Sun", t, obs, true, true); return A.Horizon(t, obs, eq.ra, eq.dec, "normal").altitude;
  }
  function anchorCatalogue() {
    return [...TOWERS, ...PEAKS, ...skyObjects().filter(o => o.el > 1 && (o.kind !== "star" || o.mag <= 2.5)).map(o => ({...o, n: o.kind === "star" ? `${o.n} (star, mag ${fmt(o.mag, 1)})` : o.n}))];
  }

  /* ------------------------------------------------------------ image analysis */
  function lum(cv, maxW) {
    const sc = Math.min(1, maxW / cv.width), w = Math.round(cv.width * sc), h = Math.round(cv.height * sc);
    const t = document.createElement("canvas"); t.width = w; t.height = h; const g = t.getContext("2d", {willReadFrequently: true});
    g.drawImage(cv, 0, 0, w, h); const d = g.getImageData(0, 0, w, h).data, L = new Float32Array(w * h), B = new Float32Array(w * h);
    for (let i = 0, j = 0; i < L.length; i++, j += 4) { L[i] = 0.2126 * d[j] + 0.7152 * d[j + 1] + 0.0722 * d[j + 2]; B[i] = d[j + 2] - d[j]; }
    return {L, B, w, h, sc};
  }
  function boxBlur(A, w, h, rx, ry) {                              // separable box blur with clamped edges
    const T = new Float32Array(A.length), O = new Float32Array(A.length);
    for (let y = 0; y < h; y++) { let s = 0; const o = y * w;
      for (let x = -rx; x <= rx; x++) s += A[o + Math.min(w - 1, Math.max(0, x))];
      for (let x = 0; x < w; x++) { T[o + x] = s / (2 * rx + 1); s += A[o + Math.min(w - 1, x + rx + 1)] - A[o + Math.max(0, x - rx)]; } }
    for (let x = 0; x < w; x++) { let s = 0;
      for (let y = -ry; y <= ry; y++) s += T[Math.min(h - 1, Math.max(0, y)) * w + x];
      for (let y = 0; y < h; y++) { O[y * w + x] = s / (2 * ry + 1); s += T[Math.min(h - 1, y + ry + 1) * w + x] - T[Math.max(0, y - ry) * w + x]; } }
    return O;
  }
  const median = a => { const b = Float64Array.from(a).sort(); const n = b.length; return n ? (n % 2 ? b[(n - 1) / 2] : (b[n / 2 - 1] + b[n / 2]) / 2) : NaN; };

  // sky/land edge: in each column, the TOPMOST strong step in brightness or colour. The strongest step is often a
  // nearer ridge or the foreground; at dusk the far mountains differ from the sky mostly in colour (orange sky,
  // blue-grey hills). A wide horizontal blur keeps stars from counting as edges.
  function detectSkyline() {
    const {L, B, w, h, sc} = lum(st.img, 1200), Ls = boxBlur(L, w, h, 5, 1), Bs = boxBlur(B, w, h, 5, 1), k = 2;
    const cols = [];
    for (let x = 0; x < w; x++) {
      const E = new Float32Array(h); let mx = 0;
      for (let y = k + 2; y < h - k - 2; y++) {
        const dl = Ls[(y - k) * w + x] - Ls[(y + k) * w + x], db = Bs[(y - k) * w + x] - Bs[(y + k) * w + x];
        E[y] = Math.abs(dl) + 0.8 * Math.abs(db); if (E[y] > mx) mx = E[y];
      }
      const g = Array.from(E.subarray(k + 2, h - k - 2)), mg = median(g), noise = 1.4826 * median(g.map(v => Math.abs(v - mg))) + 0.25;
      const thr = Math.max(0.35 * mx, mg + 7 * noise, 2.5);
      // the first edge from the top that is a real STEP (sky above, land below), not a thin line such as a wire
      const D = 14, mean = (A, y0, y1) => { let s = 0, n = 0; for (let y = Math.max(0, y0); y <= Math.min(h - 1, y1); y++) { s += A[y * w + x]; n++; } return n ? s / n : 0; };
      let yb = -1;
      for (let y = k + 2; y < h - k - 2; y++) {
        if (E[y] < thr) continue;
        let yp = y; while (yp + 1 < h - k - 2 && E[yp + 1] >= E[yp]) yp++;          // the local peak of that edge
        const step = Math.abs(mean(Ls, yp - D, yp - 4) - mean(Ls, yp + 4, yp + D)) + 0.8 * Math.abs(mean(Bs, yp - D, yp - 4) - mean(Bs, yp + 4, yp + D));
        if (step >= 0.5 * E[yp]) { yb = yp; break; }
        y = yp + 2;
      }
      if (yb < 0) continue;
      cols.push({x, y: yb, s: E[yb] / noise});
    }
    if (cols.length < w * 0.15) return null;
    const ys = cols.map(c => c.y), out = [];
    for (let i = 0; i < cols.length; i++) {
      const win = ys.slice(Math.max(0, i - 7), i + 8), m = median(win);
      if (Math.abs(cols[i].y - m) <= Math.max(2, 0.004 * h)) out.push([cols[i].x / sc, (cols[i].y + 0.5) / sc]);
    }
    return out.length >= w * 0.12 ? out : null;
  }

  // bright points: compact local maxima that stand well above the local background AND its local texture
  // (brush and rocks in the foreground have high texture, so their bright specks do not count)
  function detectLights() {
    const {L, w, h, sc} = lum(st.img, 2400), bg = boxBlur(L, w, h, 16, 16), r = new Float32Array(L.length), ar = new Float32Array(L.length);
    for (let i = 0; i < L.length; i++) { r[i] = L[i] - bg[i]; ar[i] = Math.abs(r[i]); }
    const tex = boxBlur(ar, w, h, 24, 24);                           // wide, so a bloomed light does not raise its own noise floor
    const samp = []; for (let i = 0; i < r.length; i += 7) samp.push(ar[i]);
    const floor = Math.max(1.5, 1.4826 * median(samp));
    const seen = new Uint8Array(L.length), found = [];
    for (let y = 3; y < h - 3; y++) for (let x = 3; x < w - 3; x++) {
      const i = y * w + x, v = r[i]; if (v < 10 || seen[i]) continue;
      const sig = v / (2.5 * tex[i] + floor); if (sig < 4) continue;
      let peak = true; for (let dy = -2; dy <= 2 && peak; dy++) for (let dx = -2; dx <= 2; dx++) if (r[i + dy * w + dx] > v) { peak = false; break; }
      if (!peak) continue;
      const q = [i], half = v / 3; seen[i] = 1; let sw = 0, sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0, n = 0;
      while (q.length && n < 3000) {
        const j = q.pop(), jx = j % w, jy = (j / w) | 0, wt = r[j]; n++; sw += wt; sx += wt * jx; sy += wt * jy; sxx += wt * jx * jx; syy += wt * jy * jy; sxy += wt * jx * jy;
        for (const o of [-1, 1, -w, w]) { const k2 = j + o; if (k2 >= 0 && k2 < r.length && !seen[k2] && r[k2] > half) { seen[k2] = 1; q.push(k2); } }
      }
      const mx = sx / sw, my = sy / sw, vx = sxx / sw - mx * mx, vy = syy / sw - my * my, cxy = sxy / sw - mx * my;
      const tr = vx + vy, dt = vx * vy - cxy * cxy, l1 = tr / 2 + Math.sqrt(Math.max(0, tr * tr / 4 - dt)), l2 = tr / 2 - Math.sqrt(Math.max(0, tr * tr / 4 - dt));
      const streak = l1 > 9 * Math.max(l2, 0.25) && l1 > 4;
      // a bright headlight can bloom into a disc tens of pixels across; a lit area or a cloud edge is bigger or ragged
      if (n > 2500 || (!streak && (n > 1500 || l1 > 6 * Math.max(l2, 0.25)))) continue;
      found.push({u: (mx + 0.5) / sc, v: (my + 0.5) / sc, flux: sw, sig, n, streak, len: 4 * Math.sqrt(Math.max(l1, 0)) / sc, auto: true});
    }
    // rank by significance and size together: single hot pixels and JPEG specks are significant but tiny
    found.forEach(f => { f.score = f.sig * Math.sqrt(Math.min(f.n, 400)); });
    found.sort((a, b) => b.score - a.score);
    return found.slice(0, 40);
  }

  /* ------------------------------------------------------------ fitting */
  function nelderMead(fn, x0, step, iters = 400) {
    const n = x0.length; let P = [x0.slice()];
    for (let i = 0; i < n; i++) { const p = x0.slice(); p[i] += step[i]; P.push(p); }
    let F = P.map(fn);
    for (let it = 0; it < iters; it++) {
      const idx = F.map((v, i) => i).sort((a, b) => F[a] - F[b]); P = idx.map(i => P[i]); F = idx.map(i => F[i]);
      if (Math.abs(F[n] - F[0]) < 1e-10 * (1 + Math.abs(F[0])) && it > 40) break;
      const c = new Array(n).fill(0); for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) c[j] += P[i][j] / n;
      const ref = c.map((v, j) => v + (v - P[n][j])), fr = fn(ref);
      if (fr < F[0]) { const ex = c.map((v, j) => v + 2 * (v - P[n][j])), fe = fn(ex); if (fe < fr) { P[n] = ex; F[n] = fe; } else { P[n] = ref; F[n] = fr; } }
      else if (fr < F[n - 1]) { P[n] = ref; F[n] = fr; }
      else { const co = c.map((v, j) => v + 0.5 * (P[n][j] - v)), fc = fn(co);
        if (fc < F[n]) { P[n] = co; F[n] = fc; } else { for (let i = 1; i <= n; i++) { P[i] = P[i].map((v, j) => P[0][j] + 0.5 * (v - P[0][j])); F[i] = fn(P[i]); } } }
    }
    const b = F.indexOf(Math.min(...F)); return {x: P[b], f: F[b]};
  }
  // skyline residuals (px) for a camera; robust mean of the best 80 %, plus the fraction of edge columns covered
  function skyResid(c, det) {
    const P = projector(c), half = hfov(c) / 2 + 2, pts = [];
    const i0 = Math.max(0, Math.floor((c.az - half - SKY[0][0]) / 0.1)), i1 = Math.min(SKY.length - 1, Math.ceil((c.az + half - SKY[0][0]) / 0.1));
    for (let i = i0; i <= i1; i++) { const p = P(SKY[i][0], SKY[i][1]); if (p) pts.push(p); }
    if (pts.length < 3) return {cost: 1e9, cover: 0, res: []};
    pts.sort((a, b) => a[0] - b[0]);
    const res = [];
    for (const [u, v] of det) {
      if (u < pts[0][0] || u > pts[pts.length - 1][0]) continue;
      let lo = 0, hi = pts.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (pts[m][0] <= u) lo = m; else hi = m; }
      const f = (u - pts[lo][0]) / ((pts[hi][0] - pts[lo][0]) || 1); res.push(v - (pts[lo][1] + f * (pts[hi][1] - pts[lo][1])));
    }
    const cover = res.length / det.length;
    if (cover < 0.5) return {cost: 1e9, cover, res};
    const a = res.map(Math.abs).sort((x, y) => x - y), m = Math.max(3, Math.floor(a.length * 0.8));
    let s = 0; for (let i = 0; i < Math.min(m, a.length); i++) s += a[i];
    return {cost: s / Math.min(m, a.length) / cover, cover, res};
  }
  function anchorResid(c, anchors) {
    const P = projector(c); let s = 0; const res = [];
    for (const a of anchors) { const p = P(a.az, a.el); const e = p ? Math.hypot(p[0] - a.u, p[1] - a.v) : 1e4; res.push(e); s += e * e; }
    return {cost: anchors.length ? Math.sqrt(s / anchors.length) : 0, res};
  }
  // grid search over bearing and roll (tilt solved from the median offset), then Nelder-Mead
  function fitSkyline(det, fFixed, local) {
    // with the lens known: one focal length; unknown: 2 to 90 deg wide in 15 % steps. The best few grid cells
    // (any lens) are each refined, and the best refined fit wins.
    const fList = fFixed ? [st.cam.f] : (() => { const o = []; for (let hf = 2; hf <= 90; hf *= 1.15) o.push(st.W / 2 / Math.tan(hf / 2 * D2R)); return o; })();
    const coarse = det.length > (fFixed ? 300 : 120) ? det.filter((_, i) => i % Math.ceil(det.length / (fFixed ? 300 : 120)) === 0) : det;
    const rolls = fFixed ? [-3, -1.5, 0, 1.5, 3] : [-2, 0, 2];
    const cells = [];
    if (local) cells.push({c: {...st.cam}, n: 0});                     // refine from where the user put the model
    else for (const f of fList) {
      const hf = 2 * Math.atan(st.W / 2 / f) * R2D, step = Math.max(0.02, hf / (fFixed ? 80 : 40));
      for (let az = 140 - hf * 0.3; az <= 303 + hf * 0.3; az += step) for (const roll of rolls) {
        const c = {az, el: 0, roll, f};
        for (let k = 0; k < 2; k++) { const r = skyResid(c, coarse); if (r.res.length < 5) break; c.el += Math.atan(median(r.res) / f) * R2D; }
        const r = skyResid(c, coarse);
        if (r.cost < 1e8) cells.push({c, n: r.cost});                   // residual in pixels: the measurement noise is in pixels
      }
    }
    if (!cells.length) return null;
    if (local) {                                                      // a small search around the hand alignment
      const c0 = st.cam, hf = hfov(c0);
      for (let da = -Math.max(1, hf / 6); da <= Math.max(1, hf / 6); da += Math.max(0.01, hf / 200)) for (const dr of [-1, 0, 1]) {
        const c = {az: c0.az + da, el: c0.el, roll: c0.roll + dr, f: c0.f};
        for (let k = 0; k < 2; k++) { const r = skyResid(c, coarse); if (r.res.length < 5) break; c.el += Math.atan(median(r.res) / c.f) * R2D; }
        const r = skyResid(c, coarse); if (r.cost < 1e8) cells.push({c, n: r.cost});
      }
      cells.shift();
    }
    cells.sort((a, b) => a.n - b.n);
    // seeds: the best cell in each stretch of bearings (and lens), so one good-looking region can't crowd out the rest
    const seeds = [], binW = c => Math.max(1, hfov(c) / 3);
    for (const k of cells) { if (seeds.length >= 10) break; if (!seeds.some(q => Math.abs(angDiff(q.c.az, k.c.az)) < binW(k.c) && Math.abs(Math.log(q.c.f / k.c.f)) < 0.1)) seeds.push(k); }
    let best = null;
    for (const sd of seeds) {
      const f0 = sd.c.f, x0 = [sd.c.az, sd.c.el, sd.c.roll, 0];
      const fn = x => { const c = {az: x[0], el: x[1], roll: x[2], f: f0 * Math.exp(x[3])};
        const hf = hfov(c), pen = (fFixed ? Math.max(0, Math.abs(x[3]) - 0.06) * 200 : 0) + (hf < 1 || hf > 100 ? 1e6 : 0) + (Math.abs(x[2]) > 25 ? 1e6 : 0);
        return skyResid(c, det).cost + pen; };
      const nm = nelderMead(fn, x0, [0.3, 0.1, 0.5, 0.02]);
      const c = {az: norm(nm.x[0]), el: nm.x[1], roll: nm.x[2], f: f0 * Math.exp(nm.x[3])};
      const ang = fn(nm.x);
      if (!best || ang < best.ang) best = {c, ang};
    }
    const c = best.c, hf = hfov(c);
    const alt = cells.filter(b => Math.abs(angDiff(b.c.az, c.az)) > Math.max(2, hf / 2)).reduce((m, b) => Math.min(m, b.n), Infinity);
    const r = skyResid(c, det), rms = Math.sqrt(median(r.res.map(v => v * v)));
    return {c, rms, cover: r.cover, ratio: alt / Math.max(best.ang, 1e-9)};
  }
  function solveAnchors(anchors, base, freeF) {
    if (!anchors.length) return null;
    const c0 = {...base};
    if (anchors.length === 1) {                                     // shift so the one anchor lands on its pixel
      const a = anchors[0], [az, el] = unproject(c0, a.u, a.v); c0.az = norm(c0.az + angDiff(a.az, az)); c0.el += a.el - el;
      for (let k = 0; k < 3; k++) { const [az2, el2] = unproject(c0, a.u, a.v); c0.az = norm(c0.az + angDiff(a.az, az2)); c0.el += a.el - el2; }
      return c0;
    }
    const useF = freeF && anchors.length >= 2;
    const fn = x => anchorResid({az: x[0], el: x[1], roll: x[2], f: useF ? Math.exp(x[3]) : c0.f}, anchors).cost;
    const x0 = [c0.az, c0.el, c0.roll, Math.log(c0.f)];
    const nm = nelderMead(fn, useF ? x0 : x0.slice(0, 3), useF ? [0.2, 0.1, 0.5, 0.03] : [0.2, 0.1, 0.5], 800);
    return {az: norm(nm.x[0]), el: nm.x[1], roll: nm.x[2], f: useF ? Math.exp(nm.x[3]) : c0.f};
  }
  // lights route: try pairs of detected points against pairs of anchors; keep the pose that lines up most anchors
  function fitLights(lights, cat, fFixed, det) {
    const L = lights.filter(l => !l.streak).slice(0, 25), out = [];
    if (L.length < 2 || cat.length < 2) return null;
    const sep = (a, b) => { const ca = Math.cos(a.el * D2R), cb = Math.cos(b.el * D2R);
      const x = [ca * Math.sin(a.az * D2R), ca * Math.cos(a.az * D2R), Math.sin(a.el * D2R)], y = [cb * Math.sin(b.az * D2R), cb * Math.cos(b.az * D2R), Math.sin(b.el * D2R)];
      return Math.acos(Math.min(1, x[0] * y[0] + x[1] * y[1] + x[2] * y[2])) * R2D; };
    let best = null;
    for (let i = 0; i < L.length; i++) for (let j = 0; j < L.length; j++) {
      if (i === j) continue; const dp = Math.hypot(L[i].u - L[j].u, L[i].v - L[j].v); if (dp < 15) continue;
      for (let a = 0; a < cat.length; a++) for (let b = 0; b < cat.length; b++) {
        if (a === b) continue; const sa = sep(cat[a], cat[b]); if (sa < 0.05) continue;
        const f = dp / Math.tan(sa * D2R); if (fFixed && Math.abs(f / st.cam.f - 1) > 0.04) continue;
        if (!fFixed && (f < st.W / 2 / Math.tan(45 * D2R) || f > st.W / 2 / Math.tan(0.3 * D2R))) continue;
        const pair = [{...cat[a], u: L[i].u, v: L[i].v}, {...cat[b], u: L[j].u, v: L[j].v}];
        const c = solveAnchors(pair, {az: cat[a].az, el: cat[a].el, roll: 0, f: fFixed ? st.cam.f : f}, !fFixed);
        if (!c || Math.abs(c.roll) > 25) continue;
        // count other anchors that land on a detected light
        const P = projector(c), tol = Math.max(4, 0.004 * st.W); let inl = 2; const used = [pair[0], pair[1]];
        cat.forEach((k, ki) => { if (ki === a || ki === b) return; const p = P(k.az, k.el); if (!p) return;
          const hit = L.find(l => Math.hypot(l.u - p[0], l.v - p[1]) < tol); if (hit) { inl++; used.push({...k, u: hit.u, v: hit.v}); } });
        let score = inl;
        if (det) { const r = skyResid(c, det); score += r.cost < 1e8 ? Math.max(0, 2 - r.cost / 4) : -1; }
        if (!best || score > best.score) best = {score, c, used, inl};
      }
    }
    return best;
  }

  /* ------------------------------------------------------------ alignment actions */
  function uncert(kind, rmsPx, nAnch) {
    // 1-sigma pointing error in degrees, from the fit residuals, the lens and how the fit was made
    const c = st.cam, pxDeg = R2D / c.f;
    let s = kind === "manual" ? 0.5 : Math.max(0.02, (rmsPx || 1) * pxDeg * (kind === "sky" ? 1.5 : 2));
    if (!st.fKnown && kind !== "anchors3") s += 0.05 * hfov(c) / 10;
    return s;
  }
  function setFit(html, bad) { $("fit").hidden = false; $("fit").className = bad ? "fit bad" : "fit"; $("fit").innerHTML = html; }
  function autoSky(also, local) {
    if (!st.det) st.det = detectSkyline();
    if (!st.det) { setFit("<b>No clear skyline found.</b> The mountains need to stand out from the sky (dusk, moonlight or a long exposure). Try <b>Lights</b>, or line it up by hand.", true); return false; }
    const fFixed = st.fKnown;
    const r = fitSkyline(st.det, fFixed, local);
    if (!r) { setFit("<b>The skyline in this photo doesn't match the view from the platform</b> anywhere between south-southeast and west-northwest. Was it taken from the Viewing Area?", true); return false; }
    st.cam = r.c; st.f35 = pxToF35(r.c.f); $("f35").value = st.f35.toFixed(1);
    const sig = uncert("sky", r.rms);
    st.fitInfo = {kind: "skyline", sigma: sig, rms: r.rms, ratio: r.ratio};
    const amb = !local && r.ratio < 1.25;
    setFit(`<b>Skyline fit${local ? " (refined from your alignment)" : ""}</b>: bearing ${fmt(st.cam.az, 2)}° true at the centre, tilt ${fmt(st.cam.el, 2)}°, roll ${fmt(st.cam.roll, 2)}°, lens ${fmt(st.f35, 0)} mm (35 mm equivalent${fFixed ? ", refined from the file's value" : ", worked out from the skyline"}). Residual ${fmt(r.rms, 1)} px, so the pointing is good to about <b>±${fmt(sig, 2)}°</b>.` +
      (amb ? ` <br><b>Check it:</b> another bearing fits almost as well (${fmt(r.ratio, 2)}× worse). Make sure the magenta line sits on the mountains.` : ""), amb);
    if (!also) { syncSliders(); classifyAll(); render(); }
    return true;
  }
  function autoLights(useSky) {
    if (!st.lights.some(l => l.auto)) st.lights = st.lights.filter(l => !l.auto).concat(detectLights());
    const cat = anchorCatalogue().filter(k => k.kind !== "peak");
    const r = fitLights(st.lights, cat, st.fKnown, useSky ? st.det : null);
    if (!r || r.inl < (st.fKnown ? 2 : 3)) {
      setFit(`<b>Couldn't match the lights.</b> ${st.when ? "" : "Without the time, only the tower lights can be used, and few are usually in a photo. "}Try <b>Skyline</b>, or tap a known light with <i>Match a point</i>.`, true); return false;
    }
    st.cam = solveAnchors(r.used, r.c, !st.fKnown && r.used.length >= 3) || r.c;
    if (!st.fKnown) { st.f35 = pxToF35(st.cam.f); $("f35").value = st.f35.toFixed(1); }
    st.anchors = r.used.map(a => ({...a, auto: true}));
    const rr = anchorResid(st.cam, st.anchors), sig = uncert(st.anchors.length >= 3 ? "anchors3" : "anchors", rr.cost);
    st.fitInfo = {kind: "lights", sigma: sig, rms: rr.cost};
    setFit(`<b>Light fit</b> using ${st.anchors.map(a => esc(a.n)).join("; ")}. Residual ${fmt(rr.cost, 1)} px, about <b>±${fmt(sig, 2)}°</b>. ${r.inl === 2 ? "Only two lights matched: check that the drawn tower and star markers sit on the right lights." : ""}`, r.inl === 2);
    syncSliders(); classifyAll(); render(); return true;
  }
  function autoBoth() {
    const okSky = autoSky(true);
    if (!st.lights.some(l => l.auto)) st.lights = st.lights.filter(l => !l.auto).concat(detectLights());
    // bring in every anchor that the current pose puts on a detected light, then refine on skyline + anchors
    const cat = anchorCatalogue().filter(k => k.kind !== "peak");
    if (!okSky) { autoLights(false); return; }
    const P = projector(st.cam), tol = Math.max(5, 0.006 * st.W), used = [];
    cat.forEach(k => { const p = P(k.az, k.el); if (!p) return; const hit = st.lights.find(l => !l.streak && Math.hypot(l.u - p[0], l.v - p[1]) < tol); if (hit) used.push({...k, u: hit.u, v: hit.v, auto: true}); });
    if (used.length) {
      const det = st.det, f0 = st.cam.f, free = !st.fKnown;
      const fn = x => { const c = {az: x[0], el: x[1], roll: x[2], f: free ? Math.exp(x[3]) : f0};
        return skyResid(c, det).cost + 0.7 * anchorResid(c, used).cost; };
      const x0 = [st.cam.az, st.cam.el, st.cam.roll, Math.log(f0)];
      const nm = nelderMead(fn, free ? x0 : x0.slice(0, 3), free ? [0.1, 0.05, 0.3, 0.02] : [0.1, 0.05, 0.3], 600);
      st.cam = {az: norm(nm.x[0]), el: nm.x[1], roll: nm.x[2], f: free ? Math.exp(nm.x[3]) : f0};
      st.anchors = used;
      const rr = anchorResid(st.cam, used), rs = skyResid(st.cam, det), rms = Math.sqrt(median(rs.res.map(v => v * v)));
      const sig = Math.min(uncert("sky", rms), uncert("anchors", rr.cost)) * 0.9;
      st.fitInfo = {kind: "both", sigma: sig};
      setFit(`<b>Skyline and lights</b>: the skyline plus ${used.map(a => esc(a.n)).join("; ")}. Bearing ${fmt(st.cam.az, 2)}°, tilt ${fmt(st.cam.el, 2)}°, roll ${fmt(st.cam.roll, 2)}°. About <b>±${fmt(sig, 2)}°</b>.`);
    } else {
      $("fit").innerHTML += " No tower lights or stars landed on a detected light, so this is the skyline fit alone.";
    }
    syncSliders(); classifyAll(); render();
  }
  function manualFromAnchors() {
    const n = st.anchors.length; if (!n) return;
    const c = solveAnchors(st.anchors, st.cam, !st.fKnown && n >= 3);
    if (c) st.cam = c;
    const rr = anchorResid(st.cam, st.anchors);
    const sig = n === 1 ? Math.max(0.15, uncert("manual") * 0.5) : uncert(n >= 3 ? "anchors3" : "anchors", Math.max(rr.cost, 1.5));
    st.fitInfo = {kind: "manual", sigma: sig};
    setFit(`<b>Matched by hand</b> on ${st.anchors.map(a => esc(a.n)).join("; ")}${n === 1 ? ". With one point the roll is kept as it was; add a second point (or check the skyline) to fix it." : `. Residual ${fmt(rr.cost, 1)} px.`} About <b>±${fmt(sig, 2)}°</b>.`, n === 1);
    if (!st.fKnown && n >= 3) { st.f35 = pxToF35(st.cam.f); $("f35").value = st.f35.toFixed(1); }
    syncSliders(); classifyAll(); render();
  }

  /* ------------------------------------------------------------ classification */
  function nearestIn(list, az, el, tol) {
    let best = null;
    for (const p of list) { const d = Math.hypot(angDiff(p.az, az) * Math.cos(el * D2R), p.el - el); if (d <= tol && (!best || d < best.dd)) best = {...p, dd: d}; }
    return best;
  }
  function classify(l) {
    if (!st.fitInfo) return {v: "none", t: "Not aligned", why: "Line the photo up first."};
    const [az, el] = unproject(st.cam, l.u, l.v), m = d2m(el), sig = st.fitInfo.sigma;
    l.az = az; l.el = el;
    const far = st.gpsKm !== null && st.gpsKm > 0.4;
    const sky = skyAt(az), skyEl = sky === null ? null : m2d(sky);
    const tolPt = Math.max(0.12, 2 * sig);
    const above = skyEl !== null && el > skyEl + Math.max(0.05, 1.5 * sig);
    const objs = skyObjects(), so = nearestIn(objs, az, el, Math.max(0.25, 2 * sig));
    if (so) return {v: "ok", t: so.kind === "star" ? `Star: ${so.n}` : so.n, why: `${so.kind === "star" ? "A star" : so.kind === "moon" ? "The Moon" : "A planet"} sits here at the time of the photo (${fmt(so.dd, 2)}° away).`};
    if (far) return {v: "unk", t: "Can't tell", why: "The photo was not taken from the platform."};
    if (sig > 3) return {v: "unk", t: "Can't tell", why: `The alignment is only good to ±${fmt(sig, 1)}°.`};
    if (above) return {v: "no", t: "Above the skyline", why: `${fmt(el - skyEl, 2)}° above the skyline: not a ground light. Aircraft, a satellite, a star too faint for the list, or the radar balloon at ~293° are the usual ordinary candidates.${st.when ? "" : " Add the time to check stars and planets."}`};
    // anything that appears below the highest terrain within 10 km is itself within 10 km
    const r10 = ridge10At(az);
    if (r10 !== null && el < m2d(r10) - Math.max(0.03, 1.5 * sig)) {
      const near = nearestIn(ROADS.filter(p => p.d < 12), az, el, tolPt);
      return {v: "unk", t: "Foreground", why: `Below the nearest ridge, so the light is less than 10 km away${near ? `: ${esc(near.n)} is here (${fmt(near.d, 1)} km)` : ""}. Nearby lights (US-90 traffic, the viewing area, ranch houses, a reflection or a bright speck in the brush) are not what people mean by a Marfa light.`};
    }
    const tierA = sig <= 0.15, tier = tierA ? "A" : "B";
    if (!MK.inDomain(az)) {
      const fx = nearestIn([...TOWERS, ...TOWNS], az, el, tolPt);
      return fx ? {v: "ok", t: fx.n, why: `Outside the modelled traffic sector, but ${esc(fx.n)} is here (${fmt(fx.d, 1)} km).`}
        : {v: "unk", t: "Outside the model", why: "Traffic is only modelled between 150° and 300° true. Lights to the north and east are not checked."};
    }
    const inM = MK.inMask(az, m, tier), fixed = MK.fixed(az, m);
    const roadNames = [...new Set(ROADS.map(p => p.n))];
    const cands = [
      ["US-67 headlights", nearestIn(HWY, az, el, tolPt)], ...roadNames.map(n => ["Car headlights", nearestIn(ROADS.filter(p => p.n === n), az, el, tolPt)]),
      ["Train lights", nearestIn(RAIL, az, el, tolPt)], ["Tower light", nearestIn(TOWERS, az, el, tolPt)], ["Town lights", nearestIn(TOWNS, az, el, Math.max(1, tolPt))]
    ].filter(c => c[1]).sort((a, b) => a[1].dd - b[1].dd);
    const pos = `${fmt(az, 2)}° true, ${fmt(el, 2)}°`;
    if (inM) {
      const c = cands[0];
      const what = !c ? "a catalogued source" : c[0] === "US-67 headlights" ? `a car on US-67, ${fmt(c[1].d, 1)} km away` : c[0] === "Car headlights" ? `a car on ${esc(c[1].n)}, ${fmt(c[1].d, 1)} km away` : c[0] === "Train lights" ? `${c[1].n}, ${fmt(c[1].d, 1)} km away` : `${esc(c[1].n)}, ${fmt(c[1].d, 1)} km away`;
      const t = !c ? "Known source" : c[0] === "Tower light" ? "Tower light" : c[0];
      const motion = l.streak ? " The light is a streak, so it moved during the exposure: a fixed light would not." : "";
      const desc = k => k[0] === "US-67 headlights" ? `a car on US-67 (${fmt(k[1].d, 1)} km)` : k[0] === "Car headlights" ? `a car on ${esc(k[1].n)} (${fmt(k[1].d, 1)} km)` : k[0] === "Train lights" ? `${k[1].n} (${fmt(k[1].d, 1)} km)` : `${esc(k[1].n)} (${fmt(k[1].d, 1)} km)`;
      const seenT = new Set(), others = cands.slice(1).filter(k => { const key = k[0] + (k[1].n || ""); if (seenT.has(key) || key === cands[0][0] + (cands[0][1].n || "")) return false; seenT.add(key); return true; }).slice(0, 3);
      return {v: "ok", t, why: `Inside the known-source mask${tier === "B" ? " (compass-quality, because the alignment is only good to ±" + fmt(sig, 1) + "°)" : ""}: consistent with ${what}.${others.length ? ` Also within reach: ${others.map(desc).join("; ")}.` : ""}${fixed && c && c[0] !== "Tower light" ? " A fixed light can also appear here." : ""}${motion}`};
    }
    const inv = nearestIn(HWYINV, az, el, tolPt);
    return {v: "no", t: "Not explained by the catalogue", why: `Below the skyline but outside the known-source mask${tier === "B" ? " (compass-quality)" : ""}.${inv ? ` US-67 lies here, hidden at normal refraction; a strong inversion (k ≥ ${fmt(inv.kc, 2)}) would bring it into view.` : ""} Ranch lights and private roads are not in the catalogue. This is the kind of light worth a careful report.`};
  }
  function classifyAll() { st.lights.forEach(l => { l.c = classify(l); }); renderLights(); }
  const COL = {ok: "#4ad07a", no: "#ffb238", unk: "#9aa3ad", none: "#9aa3ad"};
  function renderLights() {
    const show = st.lights.filter(l => !l.auto || l.keep || st.fitInfo).slice(0, 40);
    st.shown = show;
    $("lights").innerHTML = show.length ? show.map((l, i) => {
      const c = l.c || {v: "none", t: "Not aligned", why: ""};
      return `<li data-i="${i}"><span class="id" style="background:${COL[c.v]}">${i + 1}</span><span class="v">${esc(c.t)}</span><span class="pos">${l.az !== undefined && st.fitInfo ? fmt(l.az, 2) + "°, " + fmt(l.el, 2) + "°" : ""}</span><span class="why">${c.why}${l.streak ? ` <span class="fine">(streak ${fmt(l.len * R2D / st.cam.f, 2)}°)</span>` : ""}</span></li>`;
    }).join("") : `<li style="cursor:default"><span></span><span class="why">No lights yet. Press <b>Find lights</b>, or tap one with <i>Mark a light</i>.</span><span></span></li>`;
    $("dl").disabled = !show.length || !st.fitInfo;
    $("lights").querySelectorAll("li[data-i]").forEach(li => li.addEventListener("click", () => { const l = show[+li.dataset.i]; centreOn(l.u, l.v); }));
  }

  /* ------------------------------------------------------------ view */
  const view = $("view"), stage = $("stage");
  function fitView() {
    const w = stage.clientWidth, h = stage.clientHeight; if (!st.img) return;
    const s = Math.min(w / st.W, h / st.H) * 0.98; st.view = {s, x: (w - st.W * s) / 2, y: (h - st.H * s) / 2};
  }
  function centreOn(u, v) { const w = stage.clientWidth, h = stage.clientHeight; st.view.s = Math.max(st.view.s, Math.min(w / st.W, h / st.H) * 4); st.view.x = w / 2 - u * st.view.s; st.view.y = h / 2 - v * st.view.s; render(); }
  let raf = 0;
  function render() { if (!raf) raf = requestAnimationFrame(draw); }
  function draw() {
    raf = 0; const dpr = Math.min(devicePixelRatio || 1, 2), w = stage.clientWidth, h = stage.clientHeight;
    if (view.width !== Math.round(w * dpr) || view.height !== Math.round(h * dpr)) { view.width = Math.round(w * dpr); view.height = Math.round(h * dpr); }
    const g = view.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
    if (!st.img) return;
    const V = st.view; g.save(); g.translate(V.x, V.y); g.scale(V.s, V.s);
    g.imageSmoothingEnabled = V.s < 2; g.drawImage(st.img, 0, 0);
    const P = projector(st.cam), lw = 1.6 / V.s, half = hfov(st.cam) / 2 + 3, Lay = st.layers;
    const inF = az => Math.abs(angDiff(az, st.cam.az)) <= half;
    const line = (pts, col, wd, dash) => { g.beginPath(); let pen = false;
      for (const [az, el] of pts) { if (!inF(az)) { pen = false; continue; } const p = P(az, el); if (!p) { pen = false; continue; } pen ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]); pen = true; }
      g.strokeStyle = col; g.lineWidth = wd * lw; g.setLineDash(dash ? dash.map(d => d * lw) : []); g.stroke(); g.setLineDash([]); };
    const dots = (list, col, r) => { g.fillStyle = col; for (const p of list) { if (!inF(p.az)) continue; const q = P(p.az, p.el); if (q) { g.beginPath(); g.arc(q[0], q[1], r * lw, 0, 7); g.fill(); } } };
    if (Lay.grid) {
      g.font = `${11 / V.s}px JetBrains Mono, monospace`; g.fillStyle = "rgba(220,225,232,.8)";
      for (let az = Math.ceil((st.cam.az - half) / 1) * 1; az <= st.cam.az + half; az += hfov(st.cam) > 20 ? 5 : 1) {
        line([[norm(az), -6], [norm(az), 10]], "rgba(200,205,215,.35)", 1); const p = P(norm(az), m2d(skyAt(norm(az)) ?? 0) + 0.3); if (p) g.fillText(`${norm(az).toFixed(0)}°`, p[0] + 3 / V.s, p[1]);
      }
    }
    if (Lay.mask && ZOS) {
      g.fillStyle = "rgba(69,192,122,.22)"; g.strokeStyle = "rgba(69,192,122,.75)"; g.lineWidth = 1 * lw;
      for (const ring of ZOS.tiers.A) {
        if (!ring.some(([az]) => inF(az))) continue;
        g.beginPath(); let pen = false; for (const [az, mm] of ring) { const p = P(az, m2d(mm)); if (!p) continue; pen ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]); pen = true; }
        g.closePath(); g.fill(); g.stroke();
      }
    }
    if (Lay.sky) { line(SKY, "rgba(127,211,255,.95)", 1.6); line(RIDGE, "rgba(127,211,255,.45)", 1, [6, 5]); }
    if (Lay.det && st.det) { g.fillStyle = "rgba(255,90,209,.9)"; for (const [u, v] of st.det) g.fillRect(u - 1 * lw, v - 1 * lw, 2 * lw, 2 * lw); }
    if (Lay.roads) { dots(ROADS, "rgba(240,107,180,.9)", 1.6); dots(RAIL, "rgba(176,138,224,.9)", 1.6); }
    if (Lay.hwy) dots(HWY, "rgba(255,138,0,.95)", 2);
    if (Lay.fixed) {
      g.font = `600 ${12 / V.s}px Barlow Condensed, sans-serif`;
      for (const t of [...TOWERS, ...PEAKS, ...TOWNS]) { if (!inF(t.az)) continue; const p = P(t.az, t.el); if (!p) continue;
        g.strokeStyle = t.kind === "tower" ? "#ff3b2f" : "#e8e8e8"; g.lineWidth = 1.5 * lw; g.beginPath(); g.arc(p[0], p[1], 6 * lw, 0, 7); g.stroke();
        g.fillStyle = "rgba(255,255,255,.9)"; g.fillText(t.n.split(",")[0].replace(" (summit on the skyline)", ""), p[0] + 8 * lw, p[1] - 6 * lw); }
    }
    if (Lay.stars) {
      g.font = `${11 / V.s}px Source Sans 3, sans-serif`;
      for (const o of skyObjects()) { if (!inF(o.az)) continue; const p = P(o.az, o.el); if (!p) continue;
        g.strokeStyle = "rgba(255,242,168,.9)"; g.lineWidth = 1.2 * lw; g.beginPath(); g.arc(p[0], p[1], (o.kind === "star" ? 5 : 8) * lw, 0, 7); g.stroke();
        if (o.mag < 1.6 || o.kind !== "star") { g.fillStyle = "rgba(255,242,168,.95)"; g.fillText(o.n, p[0] + 7 * lw, p[1] + 12 * lw); } }
    }
    // anchors
    for (const a of st.anchors) { const p = P(a.az, a.el); g.strokeStyle = "#fff"; g.lineWidth = 1.5 * lw;
      g.beginPath(); g.moveTo(a.u - 9 * lw, a.v); g.lineTo(a.u + 9 * lw, a.v); g.moveTo(a.u, a.v - 9 * lw); g.lineTo(a.u, a.v + 9 * lw); g.stroke();
      if (p) { g.strokeStyle = "#ffd27a"; g.beginPath(); g.moveTo(a.u, a.v); g.lineTo(p[0], p[1]); g.stroke(); } }
    // lights
    g.font = `700 ${12 / V.s}px JetBrains Mono, monospace`;
    (st.shown || []).forEach((l, i) => { const c = l.c ? COL[l.c.v] : COL.none; g.strokeStyle = c; g.lineWidth = 2 * lw;
      g.beginPath(); g.arc(l.u, l.v, 9 * lw, 0, 7); g.stroke(); g.fillStyle = c; g.fillText(String(i + 1), l.u + 11 * lw, l.v - 9 * lw); });
    g.restore();
    const c = st.cam;
    $("hud").textContent = `centre ${fmt(c.az, 2)}° true · tilt ${fmt(c.el, 2)}° · roll ${fmt(c.roll, 2)}° · field ${fmt(hfov(c), 2)}° wide${st.fitInfo ? ` · ±${fmt(st.fitInfo.sigma, 2)}°` : " · not aligned"}`;
  }

  /* ------------------------------------------------------------ sliders */
  const FMIN = Math.log(0.25), FMAX = Math.log(120);                // horizontal field of view range (deg), log scale
  function syncSliders() {
    const c = st.cam; $("sAz").value = c.az; $("sEl").value = c.el; $("sRo").value = c.roll;
    $("sFv").value = (FMAX - Math.log(hfov(c))) / (FMAX - FMIN);
    $("oAz").textContent = fmt(c.az, 2) + "°"; $("oEl").textContent = fmt(c.el, 2) + "°"; $("oRo").textContent = fmt(c.roll, 2) + "°"; $("oFv").textContent = fmt(hfov(c), hfov(c) < 5 ? 2 : 1) + "°";
  }
  function manualChanged() { st.fitInfo = {kind: "manual", sigma: uncert("manual")}; setFit("<b>Lined up by hand.</b> Pointing assumed good to about ±0.5°. Use <i>Match a point</i> on a tower light or star to tighten it."); syncSliders(); classifyAll(); render(); }
  $("sAz").addEventListener("input", e => { st.cam.az = +e.target.value; manualChanged(); });
  $("sEl").addEventListener("input", e => { st.cam.el = +e.target.value; manualChanged(); });
  $("sRo").addEventListener("input", e => { st.cam.roll = +e.target.value; manualChanged(); });
  $("sFv").addEventListener("input", e => { const hf = Math.exp(FMAX - (+e.target.value) * (FMAX - FMIN)); st.cam.f = st.W / 2 / Math.tan(hf / 2 * D2R); st.f35 = pxToF35(st.cam.f); $("f35").value = st.f35.toFixed(1); manualChanged(); });
  $("f35").addEventListener("change", e => { const v = parseFloat(e.target.value); if (v > 0) { st.f35 = v; st.fKnown = true; st.cam.f = f35ToPx(v); syncSliders(); if (st.fitInfo) classifyAll(); render(); } });
  $("when").addEventListener("change", e => { st.when = e.target.value ? marfaToUTC(e.target.value) : null; if (st.fitInfo) classifyAll(); render(); });

  /* ------------------------------------------------------------ interaction */
  document.querySelectorAll("[data-tool]").forEach(b => b.addEventListener("click", () => {
    st.tool = b.dataset.tool; document.querySelectorAll("[data-tool]").forEach(x => x.setAttribute("aria-pressed", String(x === b))); closePick();
    view.style.cursor = st.tool === "pan" ? "grab" : st.tool === "move" ? "move" : "crosshair";
  }));
  $("fitView").addEventListener("click", () => { st.userZoomed = false; fitView(); render(); });
  const toImg = (cx, cy) => { const r = view.getBoundingClientRect(); return [(cx - r.left - st.view.x) / st.view.s, (cy - r.top - st.view.y) / st.view.s]; };
  const ptrs = new Map(); let drag = null, pinch = null;
  view.addEventListener("pointerdown", e => {
    if (!st.img) return; view.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, [e.clientX, e.clientY]);
    if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; pinch = {d: Math.hypot(a[0] - b[0], a[1] - b[1]), s: st.view.s, mid: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], x: st.view.x, y: st.view.y}; drag = null; return; }
    drag = {x: e.clientX, y: e.clientY, vx: st.view.x, vy: st.view.y, cam: {...st.cam}, moved: false};
  });
  view.addEventListener("pointermove", e => {
    if (!ptrs.has(e.pointerId)) return; ptrs.set(e.pointerId, [e.clientX, e.clientY]);
    if (pinch && ptrs.size === 2) {
      const [a, b] = [...ptrs.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]), s = Math.min(40, Math.max(0.05, pinch.s * d / pinch.d)), r = view.getBoundingClientRect();
      const mx = pinch.mid[0] - r.left, my = pinch.mid[1] - r.top; st.view.s = s; st.view.x = mx - (mx - pinch.x) * s / pinch.s; st.view.y = my - (my - pinch.y) * s / pinch.s; st.userZoomed = true; render(); return;
    }
    if (!drag) return; const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (Math.hypot(dx, dy) > 4) drag.moved = true;
    if (st.tool === "pan" || (st.tool !== "move" && drag.moved)) { st.view.x = drag.vx + dx; st.view.y = drag.vy + dy; st.userZoomed = true; render(); }
    else if (st.tool === "move") {
      const f = st.cam.f * st.view.s; st.cam.az = norm(drag.cam.az - Math.atan(dx / f) * R2D / Math.cos(st.cam.el * D2R)); st.cam.el = drag.cam.el + Math.atan(dy / f) * R2D;
      syncSliders(); render();
    }
  });
  const end = e => {
    ptrs.delete(e.pointerId); if (ptrs.size < 2) pinch = null;
    if (!drag) return; const d = drag; drag = null;
    if (st.tool === "move" && d.moved) { manualChanged(); return; }
    if (d.moved) return;
    const [u, v] = toImg(e.clientX, e.clientY); if (u < 0 || v < 0 || u > st.W || v > st.H) return;
    if (st.tool === "light") { const p = refine(u, v); st.lights.unshift({u: p[0], v: p[1], auto: false, keep: true, streak: false}); st.lights.forEach(l => { if (st.fitInfo) l.c = classify(l); }); renderLights(); render(); }
    if (st.tool === "anchor") openPick(e.clientX, e.clientY, refine(u, v));
  };
  view.addEventListener("pointerup", end); view.addEventListener("pointercancel", end);
  view.addEventListener("wheel", e => {
    if (!st.img) return; e.preventDefault(); const r = view.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    const s = Math.min(40, Math.max(0.05, st.view.s * Math.exp(-e.deltaY * 0.0015)));
    st.view.x = mx - (mx - st.view.x) * s / st.view.s; st.view.y = my - (my - st.view.y) * s / st.view.s; st.view.s = s; st.userZoomed = true; render();
  }, {passive: false});
  // snap a tap to the brightest pixel nearby (the centre of a point light)
  function refine(u, v) {
    const R = Math.max(4, Math.round(6 / st.view.s)), x0 = Math.max(0, Math.round(u) - R), y0 = Math.max(0, Math.round(v) - R);
    const w = Math.min(st.W - x0, 2 * R + 1), h = Math.min(st.H - y0, 2 * R + 1);
    const d = st.img.getContext("2d", {willReadFrequently: true}).getImageData(x0, y0, w, h).data;
    let best = -1, bx = u, by = v, sw = 0, sx = 0, sy = 0;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const i = 4 * (y * w + x), L = d[i] + d[i + 1] + d[i + 2]; if (L > best) { best = L; bx = x0 + x; by = y0 + y; } }
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const i = 4 * (y * w + x), L = d[i] + d[i + 1] + d[i + 2]; if (L > best * 0.6) { sw += L; sx += L * (x0 + x + 0.5); sy += L * (y0 + y + 0.5); } }
    return best > 120 && sw ? [sx / sw, sy / sw] : [u, v];
  }
  const pick = $("pick");
  function closePick() { pick.hidden = true; pick.innerHTML = ""; }
  function openPick(cx, cy, uv) {
    // nearest first, judged from the current pointing (rough until the photo is aligned)
    const [az0, el0] = unproject(st.cam, uv[0], uv[1]);
    const cat = anchorCatalogue().map(k => ({k, d: Math.hypot(angDiff(k.az, az0), 0.5 * (k.el - el0))})).sort((a, b) => a.d - b.d).slice(0, 14);
    pick.innerHTML = `<h4>What is this point?</h4>` + cat.map((c, i) => `<button type="button" data-i="${i}">${esc(c.k.n)}<br><small>${fmt(c.k.az, 2)}° true, ${fmt(c.k.el, 2)}° up${c.k.d ? ", " + fmt(c.k.d, 1) + " km" : ""}</small></button>`).join("") + `<button type="button" data-x="1"><small>Cancel</small></button>`;
    const r = stage.getBoundingClientRect(); pick.style.left = Math.min(cx - r.left + 10, r.width - 310) + "px"; pick.style.top = Math.min(cy - r.top + 10, r.height - 240) + "px"; pick.hidden = false;
    pick.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
      if (!b.dataset.x) { const k = cat[+b.dataset.i].k; st.anchors = st.anchors.filter(a => a.auto !== true); st.anchors.push({...k, u: uv[0], v: uv[1]}); manualFromAnchors(); }
      closePick();
    }));
    pick.querySelector("button").focus();
  }
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closePick();
    if (!st.img || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
    const step = (e.shiftKey ? 0.2 : 0.02) * Math.max(1, hfov(st.cam) / 10);
    const k = {ArrowLeft: ["az", -step], ArrowRight: ["az", step], ArrowUp: ["el", step], ArrowDown: ["el", -step]}[e.key];
    if (k && st.tool === "move") { e.preventDefault(); st.cam[k[0]] += k[1]; st.cam.az = norm(st.cam.az); manualChanged(); }
  });

  /* ------------------------------------------------------------ buttons */
  const busy = (fn, btn) => async () => { const t = btn.textContent; btn.textContent = "Working…"; btn.disabled = true; await new Promise(r => setTimeout(r, 30));
    try { fn(); } catch (e) { console.error(e); setFit("<b>Something went wrong</b> with that step. Try another route or line it up by hand.", true); } btn.textContent = t; btn.disabled = false; };
  $("autoSky").addEventListener("click", busy(() => autoSky(false), $("autoSky")));
  $("refine").addEventListener("click", busy(() => autoSky(false, true), $("refine")));
  $("autoLights").addEventListener("click", busy(() => autoLights(true), $("autoLights")));
  $("autoBoth").addEventListener("click", busy(autoBoth, $("autoBoth")));
  $("clearAnch").addEventListener("click", () => { st.anchors = []; render(); });
  $("detect").addEventListener("click", busy(() => { st.lights = st.lights.filter(l => l.keep).concat(detectLights().slice(0, 25)); classifyAll(); render(); }, $("detect")));
  $("clearLights").addEventListener("click", () => { st.lights = []; renderLights(); render(); });
  document.querySelectorAll("[data-l]").forEach(i => i.addEventListener("change", () => { st.layers[i.dataset.l] = i.checked; render(); }));
  $("dl").addEventListener("click", () => {
    const out = {tool: "Marfa Lights Field Guide photo checker", version: 1, generated: new Date().toISOString(),
      photo: {file: $("meta").querySelector("dd") ? $("meta").querySelector("dd").textContent : "", width: st.W, height: st.H, lens_35mm: +(+st.f35).toFixed(1), taken_utc: st.when ? st.when.toISOString() : null},
      alignment: {method: st.fitInfo.kind, bearing_center_true_deg: +st.cam.az.toFixed(3), tilt_deg: +st.cam.el.toFixed(3), roll_deg: +st.cam.roll.toFixed(3), field_deg: +hfov(st.cam).toFixed(3), sigma_deg: +st.fitInfo.sigma.toFixed(3),
        anchors: st.anchors.map(a => ({name: a.n, az: a.az, el: a.el, u: +a.u.toFixed(1), v: +a.v.toFixed(1)}))},
      lights: (st.shown || []).map((l, i) => ({n: i + 1, u: +l.u.toFixed(1), v: +l.v.toFixed(1), az_true_deg: +(l.az ?? NaN).toFixed(3), el_deg: +(l.el ?? NaN).toFixed(3), streak: !!l.streak, verdict: l.c ? l.c.v : null, label: l.c ? l.c.t : null, why: l.c ? l.c.why.replace(/<[^>]+>/g, "") : null})),
      model: "Line-of-sight model v2, refraction k = 0.13; known-source mask (tiers A/B); see science.html"};
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {type: "application/json"})); a.download = "marfa-photo-check.json"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  });

  // file input and drag-and-drop
  const takeFile = f => { if (!f) return; loadFile(f).catch(e => { console.error(e); $("drop").hidden = false; $("drop").innerHTML = `<span><b>Couldn't open that file.</b><p>${esc(e.message || e)}</p></span>`; }); };
  $("file").addEventListener("change", e => takeFile(e.target.files[0]));
  ["dragenter", "dragover"].forEach(t => stage.addEventListener(t, e => { e.preventDefault(); $("drop").classList.add("over"); }));
  ["dragleave", "drop"].forEach(t => stage.addEventListener(t, e => { e.preventDefault(); $("drop").classList.remove("over"); }));
  stage.addEventListener("drop", e => { const f = e.dataTransfer.files[0]; if (f) { $("drop").hidden = false; takeFile(f); } });
  new ResizeObserver(() => { if (st.img && !st.userZoomed) fitView(); render(); }).observe(stage);
  window.__photo = {st, unproject, projector, detectSkyline, fitSkyline, skyResid, classifyAll, autoSky, autoLights, autoBoth, detectLights};
})();

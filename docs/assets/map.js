/* Marfa Lights Field Guide — interactive map, light identifier, panorama and field log. */
(async function () {
  const [S, ZOS, ZR] = await Promise.all([fetch("data/site.json?v=5").then(r => r.json()),
    fetch("data/zos.json?v=5").then(r => r.json()).catch(() => null),
    fetch("data/zos_rate.json?v=5").then(r => r.json()).catch(() => null)]);
  const V = [S.viewer.lat, S.viewer.lon];
  const DECL = S.declination.deg;          // east-positive: true = magnetic + DECL
  const R = 6371000, D2R = Math.PI / 180;
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const $ = id => document.getElementById(id);
  const fmt = (v, n = 1) => Number(v).toLocaleString("en-US", {minimumFractionDigits: n, maximumFractionDigits: n});
  const angDiff = (a, b) => ((a - b + 540) % 360) - 180;
  const norm = a => ((a % 360) + 360) % 360;
  const mrad2deg = m => Math.atan(m / 1000) / D2R;

  function fwd(lat, lon, az, d) {
    const p1 = lat * D2R, l1 = lon * D2R, t = az * D2R, dr = d / R;
    const p2 = Math.asin(Math.sin(p1) * Math.cos(dr) + Math.cos(p1) * Math.sin(dr) * Math.cos(t));
    const l2 = l1 + Math.atan2(Math.sin(t) * Math.sin(dr) * Math.cos(p1), Math.cos(dr) - Math.sin(p1) * Math.sin(p2));
    return [p2 / D2R, l2 / D2R];
  }
  function inv(lat1, lon1, lat2, lon2) {
    const p1 = lat1 * D2R, p2 = lat2 * D2R, dl = (lon2 - lon1) * D2R;
    const a = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
    const az = Math.atan2(Math.sin(dl) * Math.cos(p2), Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl)) / D2R;
    return [norm(az), 2 * R * Math.asin(Math.sqrt(a)) / 1000];
  }

  // ------------------------------------------------------------ data prep
  const H = S.hwy.map(p => ({lat: p[0], lon: p[1], az: p[2], d: p[3], z: p[4], kc: p[5], cls: p[6], a: p[7], ch: p[8],
    dir: p[9], h: p[10], mL: p[11], mLd: p[12], mLb: p[13], mH: p[14], mHd: p[15], mHb: p[16]}));
  // other state roads (TxDOT): [lat, lon, az, d, a, kc, cls, dir, h, mL, mLd, mLb, mH, mHd, mHb]
  const RD = S.roads.map(r => ({n: r.n, k: r.k, p: r.p.map(q => ({lat: q[0], lon: q[1], az: q[2], d: q[3], a: q[4], kc: q[5], cls: q[6],
    dir: q[7], h: q[8], mL: q[9], mLd: q[10], mLb: q[11], mH: q[12], mHd: q[13], mHb: q[14]}))}));
  // brightness wording for a run of road samples (the brightest facing sample in view)
  const TOWARD = {US67: "toward Marfa (northbound)", RM2810: "toward Marfa", US0090: "toward Marfa (eastbound)", US0067: "away from Marfa (eastbound)"};
  function brightText(run, key) {
    const f = run.filter(p => p.mH !== null && p.mH !== undefined);
    if (!f.length) return "";
    const b = f.reduce((a, p) => p.mH < a.mH ? p : a);
    const dirTxt = b.dir === 0 ? "heading toward Marfa" : "heading away from Marfa";
    const cmp = m => m <= -1 ? "as bright as the brightest stars" : m <= 1.5 ? "like a bright star" : m <= 4 ? "like a modest star" : m <= 6 ? "faint, near the naked-eye limit" : "too faint to see";
    const w = Math.abs(Math.sin(b.h * D2R)) * (100 / 3.6) / (b.d * 1000) * 180 / Math.PI * 60;
    return `At 100 km/h a car here crosses the view at about ${fmt(w, w < 0.1 ? 2 : 1)}° per minute. A car ${dirTxt} can point within ${fmt(Math.max(1, Math.abs(b.h)), 0)}° of the platform: about magnitude ${fmt(b.mH, 1)} on high beam (${cmp(b.mH)}), ${fmt(b.mL, 1)} on low beam. Cars going the other way show only red tail lights.`;
  }
  const HIT = S.rays.filter(r => r[4] === 1);
  const hwyDistAt = az => {           // distance to the first US-67 crossing, only where rays meet US-67
    const r = HIT; if (az < r[0][0] || az > r[r.length - 1][0]) return null;
    for (let i = 0; i < r.length - 1; i++) if (az >= r[i][0] && az <= r[i + 1][0]) {
      const f = (az - r[i][0]) / (r[i + 1][0] - r[i][0] || 1); return r[i][3] + f * (r[i + 1][3] - r[i][3]);
    }
    return null;
  };
  // densify rail and power lines so bearing matches don't miss segments between vertices
  function densify(lines, meta) {
    const out = [];
    lines.forEach((ln, li) => {
      for (let i = 0; i < ln.c.length - 1; i++) {
        const [a, b] = [ln.c[i], ln.c[i + 1]], [, dk] = inv(a[0], a[1], b[0], b[1]), n = Math.max(1, Math.ceil(dk / 0.2));
        for (let j = 0; j < n; j++) {
          const f = j / n, lat = a[0] + f * (b[0] - a[0]), lon = a[1] + f * (b[1] - a[1]), [az, d] = inv(V[0], V[1], lat, lon);
          out.push({li, lat, lon, az, d, ...meta(ln)});
        }
      }
    });
    return out;
  }
  const RAILPTS = densify(S.rail, ln => ({o: ln.o, s: ln.s, m: ln.m}));
  const skyAt = az => {
    const s = S.sky; if (az < s[0][0] || az > s[s.length - 1][0]) return null;
    const i = Math.min(s.length - 2, Math.max(0, Math.floor((az - s[0][0]) / 0.1)));
    const f = (az - s[i][0]) / 0.1; return {m: s[i][1] + f * (s[i + 1][1] - s[i][1]), d: s[i][2]};
  };

  // Zone of Skepticism (analysis/zone_of_skepticism.py): rings of [az, el_mrad]
  const inRing = (x, y, r) => { let c = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const [xi, yi] = r[i], [xj, yj] = r[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
  // activity-weighted zone (analysis/weighted_zone.py): expected ordinary lights per hour
  // envelope of two nights: normal refraction (k = 0.13) and a strong inversion (k = 1)
  const RATE = ZR ? ZR.standard : null, RATES = ZR ? [ZR.standard, ZR.inversion] : [];
  function rateAt(az, m) {          // index of the highest level containing the point in either scenario, -1 if none
    if (!RATE) return null;
    let lvl = -1;
    RATES.forEach(Rs => Rs.levels.forEach((lv, i) => { let n = 0; Rs.rate_polys[String(lv)].forEach(r => { if (inRing(az, m, r)) n++; }); if (n % 2 === 1 && i > lvl) lvl = i; }));
    return lvl;
  }
  const RATE_TXT = ["0.01–0.1 per hour (one every 10–100 hours)", "0.1–1 per hour", "1–10 per hour", "10 or more per hour"];
  function zosAt(az, m) {           // null = cannot say; true/false = inside/outside tier A (tier B if only a bearing)
    if (!ZOS) return null;
    if (m === null) return null;
    let n = 0; ZOS.tiers.A.forEach(r => { if (inRing(az, m, r)) n++; });
    return n % 2 === 1;
  }

  // ------------------------------------------------------------ map
  const map = L.map("map", {zoomControl: true, attributionControl: true}).setView(V, 10);
  const bases = {
    img: L.tileLayer("https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}", {maxZoom: 16, attribution: 'Imagery: <a href="https://www.usgs.gov/programs/national-geospatial-program/national-map">USGS The National Map</a>'}),
    topo: L.tileLayer("https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}", {maxZoom: 16, attribution: 'Topo: <a href="https://www.usgs.gov/programs/national-geospatial-program/national-map">USGS The National Map</a>'}),
    osm: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'})
  };
  let base = bases.img.addTo(map);
  $("base").addEventListener("change", e => { map.removeLayer(base); base = bases[e.target.value].addTo(map); base.bringToBack(); });
  map.fitBounds(L.latLngBounds(H.map(p => [p.lat, p.lon]).concat([V])).pad(0.08));

  const groups = {};
  const LAYERS = [
    ["hwy", "US-67 line of sight", "sw", "--vis", true],
    ["roads", "Other state roads (RM 2810, US-90…)", "sw", "--road2", true],
    ["fan", "Viewing fan, 120°, 0.5° rays", "sw", "--accent", true],
    ["rail", "Railroads", "sw", "--rail", true],
    ["xing", "Rail grade crossings", "swd", "--rail", false],
    ["power", "Power lines ≥ 69 kV", "sw", "--power", false],
    ["air", "Airfields, heliports, TARS", "swd", "--accent", true],
    ["tower", "Towers (FCC registered)", "swd", "--cell", true],
    ["towns", "Towns", "swd", "--town", true],
  ];
  LAYERS.forEach(([id]) => groups[id] = L.layerGroup());
  const bearingGroup = L.layerGroup().addTo(map);

  const LIGHT = {none: "No obstruction lights required", lit: "Registered with aviation obstruction lighting (typically red at night)",
    red: "Red obstruction lights", dual: "Red lights at night, flashing white by day", white: "Flashing white lights",
    white_high: "High-intensity flashing white lights", dual_high: "Red at night, high-intensity white by day", adls: "Lights come on only when aircraft approach"};
  const isLit = t => t.light && t.light !== "none";
  const inView = o => o.kc !== null && o.kc !== undefined && o.kc <= K;
  // a dark casing under each coloured line keeps it readable over desert imagery
  function cased(coords, opt, grp) {
    L.polyline(coords, {color: "#05070a", weight: (opt.weight || 2) + 3, opacity: .55, interactive: false, lineCap: opt.lineCap || "round"}).addTo(grp);
    return L.polyline(coords, opt).addTo(grp);
  }
  const diamond = (fill, stroke, size) => L.divIcon({className: "", iconSize: [size, size], iconAnchor: [size / 2, size / 2],
    html: `<svg width="${size}" height="${size}" viewBox="-6 -6 12 12"><path d="M0,-5 L5,0 L0,5 L-5,0 Z" fill="${fill}" stroke="${stroke}" stroke-width="1.4"/></svg>`});
  function popup(title, rows) { return `<b>${title}</b><br>${rows.filter(Boolean).join("<br>")}`; }
  const azLine = (az, d) => `Bearing ${fmt(az, 1)}° true (${fmt(norm(az - DECL), 1)}° magnetic) · ${fmt(d, 1)} km`;

  function drawStatic() {
    ["fan", "rail", "xing", "power", "air", "tower", "towns"].forEach(id => groups[id].clearLayers());
    const acc = css("--accent");
    // fan wedge + rays
    const FR = 80000, e1 = fwd(V[0], V[1], S.fan[0], FR), e2 = fwd(V[0], V[1], S.fan[1], FR);
    const arc = []; for (let a = S.fan[0]; a <= S.fan[1] + 1e-6; a += 1) arc.push(fwd(V[0], V[1], a, FR));
    L.polygon([V, e1, ...arc, e2], {color: acc, weight: 1.5, opacity: .85, fillColor: acc, fillOpacity: .08, interactive: false}).addTo(groups.fan);
    S.rays.forEach((r, i) => { if (i % 2 === 0 || i === S.rays.length - 1) L.polyline([V, [r[1], r[2]]], {color: acc, weight: 1, opacity: .42, interactive: false}).addTo(groups.fan); });
    // rail
    const rc = css("--rail");
    S.rail.forEach(ln => cased(ln.c, {color: rc, weight: ln.m ? 3.5 : 2, opacity: 1, dashArray: ln.o === "TXPF" ? "8 5" : null}, groups.rail)
      .bindPopup(popup(ln.o === "UP" ? "Union Pacific (Sunset Route)" : "Texas Pacifico (former South Orient)", [
        `${ln.s ? ln.s + " subdivision" : "Siding or yard track"}`, ln.o === "UP" ? "Main line through Marfa; freight and Amtrak" : "Marfa–Presidio line; light traffic",
        "Source: USDOT BTS North American Rail Network"]))); 
    S.xing.forEach(x => L.circleMarker([x.lat, x.lon], {radius: 4, color: rc, weight: 1.5, fillColor: css("--surface"), fillOpacity: 1})
      .bindPopup(popup(`Grade crossing ${x.id}`, [`${x.rr} · ${x.road} · ${x.pos}`, `Reported through trains: ${x.day} by day, ${x.night} at night`, azLine(x.az, x.d), "Source: FRA crossing inventory (self-reported)"])).addTo(groups.xing));
    S.tl.forEach(t => cased(t.c, {color: css("--power"), weight: 2, dashArray: "3 4", opacity: 1}, groups.power)
      .bindPopup(popup(`${t.kv || "?"} kV transmission line`, [`${t.a} – ${t.b}`, "Unlit structures; they appear in photos, not as lights", "Source: HIFLD-derived transmission lines"])));
    S.fields.forEach(f => {
      const col = f.k === "historic" ? css("--muted") : f.k === "balloon" ? css("--cell") : acc;
      L.circleMarker([f.lat, f.lon], {radius: f.k === "historic" ? 4 : 6, color: col, weight: 2, fillColor: col, fillOpacity: f.k === "historic" ? .2 : .6})
        .bindPopup(popup(f.n, [
          f.k === "historic" ? "Historic WWII Marfa Army Air Field site (closed)" : f.k === "balloon" ? "Tethered aerostat radar site (CBP). The balloon and tether can carry lights well above the terrain." : f.k === "heliport" ? "Heliport" : `Airfield${f.faa ? " · in current FAA records" : ""}`,
          f.elev ? `Elevation ${Number(f.elev).toLocaleString()} ft` : "", azLine(f.az, f.d),
          `<a href="https://ourairports.com/airports/${f.id}/" target="_blank" rel="noopener">OurAirports record</a>`])).addTo(groups.air);
    });
    const red = css("--cell");
    S.towers.forEach(t => {
      const lit = isLit(t), seen = inView(t);
      L.marker([t.lat, t.lon], {icon: lit ? diamond(red, "#000", seen ? 16 : 12) : diamond("#9aa3ad", "#000", 9), zIndexOffset: lit ? 500 : 0})
        .bindPopup(popup(`${fmt(t.h, 0)} m ${t.type === "LTOWER" ? "lattice tower" : t.type === "GTOWER" ? "guyed tower" : t.type === "MTOWER" ? "monopole" : t.type.toLowerCase()}`, [
          t.owner || "", `<b style="font-size:14px;color:${lit ? red : "inherit"}">${LIGHT[t.light]}</b>`, t.light === "lit" ? `<span class="muted">Spec: ${t.spec}</span>` : "",
          t.kc === null ? "" : seen ? `Top light <b>in view</b> from the Viewing Area at ${fmt(Math.atan(t.a / 1000) * 57.2958, 2)}° elevation` : "Top hidden by terrain from the Viewing Area",
          azLine(t.az, t.d), `FCC Antenna Structure Registration ${t.id}${t.built ? `, built ${t.built}` : ""}`])).addTo(groups.tower);
    });
    S.cells.forEach(c => L.marker([c.lat, c.lon], {icon: diamond(red, "#000", 12)})
      .bindPopup(popup("Cell site", [c.lic, c.addr, c.h ? `Structure ${fmt(c.h, 0)} m tall` : "", azLine(c.az, c.d), "Tall towers carry aviation obstruction lights"])).addTo(groups.tower));
    S.towns.forEach(t => {
      L.marker([t.lat, t.lon], {icon: L.divIcon({className: "town-label", html: t.n.replace(", Chihuahua", ""), iconSize: null, iconAnchor: t.n.startsWith("Ojinaga") ? [62, -4] : [-4, 6]}), keyboard: false})
        .bindPopup(popup(t.n, [t.note, azLine(t.az, t.d)])).addTo(groups.towns);
    });
    S.refs.forEach(t => L.circleMarker([t.lat, t.lon], {radius: 6, color: css("--ink"), weight: 2, fill: false})
      .bindPopup(popup(t.n, [t.note, azLine(t.az, t.d)])).addTo(groups.towns));
  }

  // highway, styled by current refraction mode
  let K = 0.13;
  const hwyClass = p => Math.abs(K - 0.13) < 1e-9 ? p.cls : (p.kc <= K ? "v" : "h");
  const roadClass = p => p.kc <= K ? "v" : "h";
  function drawHwy() {
    groups.hwy.clearLayers();
    const col = {v: css("--vis"), m: css("--marg"), h: css("--hid")}, w = {v: 6, m: 5, h: 3};
    var label = {v: "Visible from the Viewing Area", m: "Marginal: depends on detail finer than the terrain model", h: "Hidden by terrain"};
    let run = [H[0]];
    const flush = () => {
      if (run.length < 2) return; const c = hwyClass(run[0]), a = run[0], b = run[run.length - 1];
      cased(run.map(p => [p.lat, p.lon]), {color: col[c], weight: w[c], opacity: 1, lineCap: "butt"}, groups.hwy)
        .bindPopup(popup("US-67", [`<span style="color:${col[c]}">■</span> ${label[c]}${Math.abs(K - 0.13) < 1e-9 ? " (standard refraction)" : ` at k = ${fmt(K, 2)}`}`,
          `Road km ${fmt(a.ch, 1)}–${fmt(b.ch, 1)} from Shafter`, `Bearing ${fmt(Math.min(a.az, b.az), 1)}–${fmt(Math.max(a.az, b.az), 1)}° true`,
          `Distance ${fmt(Math.min(a.d, b.d), 1)}–${fmt(Math.max(a.d, b.d), 1)} km · road ${Math.min(a.z, b.z)}–${Math.max(a.z, b.z)} m`]));
    };
    for (let i = 1; i < H.length; i++) { run.push(H[i]); if (hwyClass(H[i]) !== hwyClass(run[0]) || i === H.length - 1) { flush(); run = [H[i]]; } }
    // other state roads: split at class changes and at gaps between separate pieces
    groups.roads.clearLayers();
    const rc = {v: css("--road2"), m: css("--marg"), h: css("--hid")};
    RD.forEach(rd => {
      let seg = [rd.p[0]];
      const cl = p => roadClass(p);
      const out = () => {
        if (seg.length < 2) return; const c = cl(seg[0]);
        cased(seg.map(p => [p.lat, p.lon]), {color: rc[c], weight: c === "h" ? 2 : 4.5, opacity: 1, lineCap: "butt"}, groups.roads)
          .bindPopup(popup(rd.n, [`<span style="color:${rc[c]}">■</span> ${label[c]}${Math.abs(K - 0.13) < 1e-9 ? " (standard refraction)" : ` at k = ${fmt(K, 2)}`}`,
            `Bearing ${fmt(Math.min(...seg.map(p => p.az)), 1)}–${fmt(Math.max(...seg.map(p => p.az)), 1)}° true · ${fmt(Math.min(...seg.map(p => p.d)), 1)}–${fmt(Math.max(...seg.map(p => p.d)), 1)} km`,
            c !== "h" ? brightText(seg, rd.k) : "", "Road geometry: TxDOT Roadways"]));
      };
      for (let i = 1; i < rd.p.length; i++) {
        const a = rd.p[i - 1], b = rd.p[i], gap = Math.abs(a.d - b.d) > 0.5 || Math.abs(angDiff(a.az, b.az)) > 3;
        if (gap) { out(); seg = [b]; continue; }
        seg.push(b); if (cl(b) !== cl(seg[0]) || i === rd.p.length - 1) { out(); seg = [b]; }
      }
    });
  }
  const viewer = L.marker(V, {icon: L.divIcon({className: "viewer-icon", html: `<svg width="26" height="26" viewBox="-13 -13 26 26"><path d="M0,-11 L3,-3.5 L11,-3.5 L4.6,1.6 L7,10 L0,5 L-7,10 L-4.6,1.6 L-11,-3.5 L-3,-3.5 Z" fill="#f0a43a" stroke="#000" stroke-width="1"/></svg>`, iconSize: [26, 26], iconAnchor: [13, 13]}), zIndexOffset: 1000})
    .bindPopup(popup("Marfa Lights Viewing Area", [`Ground ${fmt(S.viewer.z, 0)} m above sea level (USGS 3DEP)`, "US-90, about 9 miles east of Marfa"])).addTo(map);

  // layer checkboxes
  $("layerList").innerHTML = LAYERS.map(([id, t, sw, v, on]) => `<label><input type="checkbox" id="ly-${id}"${on ? " checked" : ""}><span class="${sw}" style="background:var(${v})"></span>${t}</label>`).join("")
    + `<p class="hint muted" style="font-size:13.5px;margin-top:4px"><span class="sw" style="background:var(--vis)"></span> visible &nbsp;<span class="sw" style="background:var(--marg)"></span> marginal &nbsp;<span class="sw" style="background:var(--hid)"></span> hidden</p>`;
  LAYERS.forEach(([id, , , , on]) => { if (on) groups[id].addTo(map); $("ly-" + id).addEventListener("change", e => e.target.checked ? groups[id].addTo(map) : map.removeLayer(groups[id])); });
  drawStatic(); drawHwy();

  const kEl = $("k");
  function kText() {
    const km = H.filter(p => p.kc <= K).length * 0.06, dT = K / (503 * 850 / 283 ** 2) - 0.0343;
    $("kout").textContent = `k = ${fmt(K, 2)} · ${fmt(km, 1)} km of road visible · dT/dz ≈ ${dT >= 0 ? "+" : "−"}${fmt(Math.abs(dT), 3)} K/m`;
  }
  kEl.addEventListener("input", () => { K = +kEl.value; if (Math.abs(K - 0.13) < 0.006) K = 0.13; kText(); drawHwy(); drawPano(); identify(); });
  kText();

  // ------------------------------------------------------------ identifier
  let refMag = true, compassOn = false;
  $("declNote").textContent = `Magnetic declination here is about ${fmt(DECL, 1)}° east (NOAA WMM2025, 2026). True bearing = magnetic + ${fmt(DECL, 1)}°.`;
  const setRef = mag => {
    const b = parseFloat($("bearing").value);
    if (!isNaN(b) && mag !== refMag) $("bearing").value = fmt(norm(mag ? b - DECL : b + DECL), 1).replace(",", "");
    refMag = mag; $("refMag").setAttribute("aria-pressed", mag); $("refTrue").setAttribute("aria-pressed", !mag); identify();
  };
  $("refMag").onclick = () => setRef(true); $("refTrue").onclick = () => setRef(false);
  const trueBearing = () => { const b = parseFloat($("bearing").value); return isNaN(b) ? null : norm(refMag ? b + DECL : b); };
  function setTrueBearing(bt, elevDeg) {
    $("bearing").value = fmt(norm(refMag ? bt - DECL : bt), 1).replace(",", "");
    if (elevDeg !== undefined) $("elev").value = elevDeg === null ? "" : fmt(elevDeg, 2);
    identify();
  }
  ["bearing", "elev", "tol"].forEach(id => $(id).addEventListener("input", identify));
  map.on("click", e => { const [az] = inv(V[0], V[1], e.latlng.lat, e.latlng.lng); setTrueBearing(az, null); });

  let last = null;
  function identify() {
    const b = trueBearing(), tol = +$("tol").value, eRaw = $("elev").value.trim(), elev = eRaw === "" ? null : parseFloat(eRaw);
    bearingGroup.clearLayers();
    if (b === null) { $("verdict").innerHTML = ""; $("cands").innerHTML = ""; return; }
    // bearing wedge on the map
    const far = 90000, wedge = [V]; for (let a = b - tol; a <= b + tol + 1e-6; a += tol / 6) wedge.push(fwd(V[0], V[1], a, far));
    L.polygon(wedge, {color: css("--accent"), weight: 0, fillOpacity: .12, interactive: false}).addTo(bearingGroup);
    L.polyline([V, fwd(V[0], V[1], b, far)], {color: css("--accent"), weight: 2.5, interactive: false}).addTo(bearingGroup);

    const within = az => Math.abs(angDiff(az, b)) <= tol;
    const C = [];   // candidates
    // US-67 runs within the window
    const idx = H.map((p, i) => within(p.az) ? i : -1).filter(i => i >= 0);
    const hwyRuns = []; let cur = [];
    idx.forEach((i, j) => { if (j && i !== idx[j - 1] + 1) { hwyRuns.push(cur); cur = []; } cur.push(H[i]); }); if (cur.length) hwyRuns.push(cur);
    let anyVisible = false, anyRoad = false;
    hwyRuns.forEach(run => {
      const cls = run.map(hwyClass), nv = cls.filter(c => c === "v").length, nm = cls.filter(c => c === "m").length;
      const st = nv ? "v" : nm ? "m" : "h"; if (st === "v") anyVisible = true;
      const vis = run.filter(p => hwyClass(p) !== "h"), dmin = Math.min(...run.map(p => p.d)), dmax = Math.max(...run.map(p => p.d));
      let match = "";
      if (elev !== null && vis.length) {
        const ed = vis.map(p => mrad2deg(p.a)); const lo = Math.min(...ed), hi = Math.max(...ed);
        match = elev >= lo - 0.25 && elev <= hi + 0.25 ? " · elevation matches" : ` · headlights here appear at ${fmt(lo, 2)}° to ${fmt(hi, 2)}°`;
      }
      C.push({d: dmin, chip: "US-67", col: st === "v" ? "--vis" : st === "m" ? "--marg" : "--hid",
        t: st === "v" ? "Car headlights: road in view" : st === "m" ? "Car headlights: road marginally in view" : "US-67, hidden by terrain",
        dist: `${fmt(dmin, 1)}–${fmt(dmax, 1)} km`, sub: `${fmt(run.length * 0.06, 1)} km of road on this bearing, road km ${fmt(run[0].ch, 1)}–${fmt(run[run.length - 1].ch, 1)} from Shafter${match}${vis.length ? ". " + brightText(vis, "US67") : ""}`});
    });
    // other state roads within the window
    RD.forEach(rd => {
      const w = rd.p.filter(p => within(p.az)); if (!w.length) return;
      const vis = w.filter(p => roadClass(p) === "v"); if (!vis.length) return; anyRoad = true;
      const dmin = Math.min(...w.map(p => p.d)), dmax = Math.max(...w.map(p => p.d));
      let match = "";
      if (elev !== null && vis.length) {
        const ed = vis.map(p => mrad2deg(p.a)); const lo = Math.min(...ed), hi = Math.max(...ed);
        match = elev >= lo - 0.25 && elev <= hi + 0.25 ? " · elevation matches. " : ` · headlights here appear at ${fmt(lo, 2)}° to ${fmt(hi, 2)}°. `;
      } else if (vis.length) match = ". ";
      C.push({d: vis.length ? Math.min(...vis.map(p => p.d)) : dmin, chip: "Road", col: vis.length ? "--road2" : "--hid",
        t: vis.length ? `${rd.n}: car headlights, road in view` : `${rd.n}, hidden by terrain`, dist: `${fmt(dmin, 1)}–${fmt(dmax, 1)} km`,
        sub: vis.length ? `${fmt(vis.length * 0.12, 1)} km in view on this bearing${match}${brightText(vis, rd.k)}` : "No line of sight at this refraction"});
    });
    // railroads: nearest point per line within window
    const byLine = {};
    RAILPTS.forEach(p => { if (within(p.az) && (!byLine[p.li] || p.d < byLine[p.li].d)) byLine[p.li] = p; });
    const railSeen = {};
    Object.values(byLine).forEach(p => {
      const key = p.o + (p.m ? "m" : "s"); if (railSeen[key] && railSeen[key].d <= p.d) return; railSeen[key] = p;
    });
    Object.values(railSeen).forEach(p => {
      const hd = hwyDistAt(p.az), front = hd && p.d < hd;
      const rv = S.railpano.filter(r => r[0] === p.o && within(r[1]));
      const seen = rv.some(r => r[4] <= K), known = rv.length > 0;
      C.push({d: p.d, chip: "Rail", col: "--rail", t: p.o === "UP" ? "Union Pacific trains (headlight, ditch lights)" : "Texas Pacifico trains, Marfa–Presidio line",
        dist: `${fmt(p.d, 1)} km`, sub: `${p.m ? "Main track" : "Siding/yard"}${known ? (seen ? " · track in view" : " · track hidden by terrain") : ""}${front ? " · in front of US-67 on this bearing" : ""}`});
    });
    const pts = [
      ...S.fields.map(f => ({...f, chip: f.k === "balloon" ? "Aerostat" : f.k === "historic" ? "Historic" : "Air", col: f.k === "balloon" ? "--cell" : "--accent",
        t: f.n, sub: f.k === "balloon" ? "Radar balloon and tether lights can sit high above the skyline" : f.k === "historic" ? "WWII field, closed: no lights expected" : "Runway, beacon or aircraft lights"})),
      ...S.towers.filter(isLit).map(t => ({...t, chip: "Tower", col: "--cell", t: `${fmt(t.h, 0)} m tower: ${LIGHT[t.light].toLowerCase()}`,
        sub: `${t.owner ? t.owner + " · " : ""}${t.kc === null ? "" : inView(t) ? "top light in view" : "hidden by terrain"}`})),
      ...S.cells.map(c => ({...c, chip: "Tower", col: "--cell", t: "Cell tower with aviation lights", sub: c.addr})),
      ...S.towns.map(t => ({...t, chip: "Town", col: "--ink-2", t: t.n, sub: t.note + " (skyglow or direct lights)"})),
      ...S.xing.filter(x => x.night > 0).map(x => ({...x, chip: "Crossing", col: "--rail", t: `Grade crossing ${x.id}`, sub: `${x.rr}; ${x.night} reported night trains`})),
      ...S.plants.map(p => ({...p, chip: "Plant", col: "--power", t: p.n, sub: `${p.tech}, ${p.mw} MW`})),
      ...S.refs.map(r => ({...r, chip: "Ref", col: "--ink-2", t: r.n, sub: r.note}))];
    pts.forEach(p => { if (within(p.az)) C.push({d: p.d, chip: p.chip, col: p.col, t: p.t, dist: `${fmt(p.d, 1)} km`, sub: p.sub}); });
    C.sort((a, b) => a.d - b.d);

    // verdict
    const sky = skyAt(b), skyDeg = sky ? mrad2deg(sky.m) : null;
    const lines = [];
    const inFan = b >= S.fan[0] && b <= S.fan[1];
    if (anyVisible) lines.push(`<b>US-67 is in view on this bearing.</b> A light moving steadily along it, especially a pair that splits or merges, is most likely a vehicle.`);
    else if (hwyRuns.length) lines.push(`<b>US-67 lies on this bearing but is hidden${Math.abs(K - 0.13) < 1e-9 ? " at standard refraction" : ` at k = ${fmt(K, 2)}`}.</b> Car headlights here need unusual refraction. Check the other sources below.`);
    else lines.push(`<b>US-67 is not on this bearing.</b>${inFan ? "" : " You are pointing outside the 120° viewing fan."}`);
    if (anyRoad) lines.push(`<b>Another road is in view on this bearing</b> (see below). Its traffic can look just like a Marfa Light.`);
    const mEl = elev === null ? null : Math.tan(elev * D2R) * 1000;
    const z = zosAt(b, mEl);
    let rl = null;
    if (RATE) {
      if (mEl !== null) rl = rateAt(b, mEl);
      else { rl = -1; for (let a = b - tol; a <= b + tol + 1e-9; a += 0.25) { const sk = skyAt(norm(a)); if (sk) for (let m = -15; m <= sk.m; m += 0.5) rl = Math.max(rl, rateAt(norm(a), m)); } }
    }
    if (rl !== null && rl >= 0) lines.push(`<span>Ordinary lights expected ${mEl === null ? `somewhere below the skyline within ±${tol}°` : "at this spot"}: <b>${RATE_TXT[rl]}</b> on a clear night (normal refraction up to a strong inversion).</span>`);
    if (z !== null) lines.push(z ? `<span>Inside the <b>Zone of Skepticism</b>: a known light source can appear here. Rule it out first.</span>`
      : `<span>Outside the <b>Zone of Skepticism</b>: no catalogued light source appears here${rl === -1 ? " (fewer than one ordinary light per 100 hours expected)" : ""}. Note the time, bearing and height carefully.</span>`);
    if (elev !== null && skyDeg !== null) {
      lines.push(elev > skyDeg + 0.1
        ? `At ${fmt(elev, 2)}° the light is <b>above the skyline</b> (${fmt(skyDeg, 2)}° here, ridge ${fmt(sky.d, 0)} km away). A ground light can't sit there. Think aircraft, stars or planets, satellites, or the aerostat at ~${fmt(norm(293 - (refMag ? DECL : 0)), 0)}°${refMag ? " magnetic" : " true"}.`
        : `At ${fmt(elev, 2)}° the light is <b>below the skyline</b> (${fmt(skyDeg, 2)}°), seen against terrain. That is consistent with a ground source.`);
    } else if (skyDeg !== null) lines.push(`<span class="muted">The skyline here is ${fmt(skyDeg, 2)}° above level, ${fmt(sky.d, 0)} km away. Add an elevation for a sharper answer.</span>`);
    lines.push(`<span class="muted mono" style="font-size:13px">${fmt(b, 1)}° true · ${fmt(norm(b - DECL), 1)}° magnetic · window ±${tol}°</span>`);
    $("verdict").innerHTML = lines.join("");
    $("cands").innerHTML = C.length ? C.map(c => `<li><span class="chip" style="color:var(${c.col})">${c.chip}</span><span>${c.t}</span><span class="d">${c.dist}</span><span class="sub">${c.sub || ""}</span></li>`).join("")
      : `<li><span></span><span>No catalogued light source on this bearing within ${MAXKM()} km.</span><span></span></li>`;
    last = {b, tol, elev, top: C[0] ? `${C[0].chip}: ${C[0].t} (${C[0].dist})` : "none", visible: anyVisible};
    drawPano();
  }
  const MAXKM = () => 90;

  // ------------------------------------------------------------ phone compass (experimental)
  let lastHeading = null;
  function onOrient(e) {
    let h = null;
    if (typeof e.webkitCompassHeading === "number") h = e.webkitCompassHeading;                 // iOS: magnetic
    else if (e.absolute && typeof e.alpha === "number") h = norm(360 - e.alpha);                   // Android absolute
    if (h === null) return;
    lastHeading = lastHeading === null ? h : norm(lastHeading + 0.25 * angDiff(h, lastHeading));  // smooth
    const bt = norm(lastHeading + DECL);
    $("bearing").value = fmt(norm(refMag ? bt - DECL : bt), 1).replace(",", "");
    identify();
  }
  $("compassBtn").addEventListener("click", async () => {
    if (compassOn) {
      window.removeEventListener("deviceorientation", onOrient); window.removeEventListener("deviceorientationabsolute", onOrient);
      compassOn = false; $("compassBtn").setAttribute("aria-pressed", "false"); $("compassBtn").textContent = "Use phone compass"; return;
    }
    try {
      if (typeof DeviceOrientationEvent !== "undefined" && typeof DeviceOrientationEvent.requestPermission === "function") {
        const r = await DeviceOrientationEvent.requestPermission(); if (r !== "granted") throw new Error("denied");
      }
      window.addEventListener("deviceorientationabsolute", onOrient); window.addEventListener("deviceorientation", onOrient);
      compassOn = true; lastHeading = null; $("compassBtn").setAttribute("aria-pressed", "true"); $("compassBtn").textContent = "Hold reading";
      $("declNote").textContent = "Hold the phone flat, top edge pointing at the light, away from the car and metal railings. Phone compasses are often off by 5–10°, so use the ±5° window.";
    } catch (err) {
      $("declNote").textContent = "This browser didn't allow compass access. Enter the bearing by hand, or tap the map or panorama.";
    }
  });

  // ------------------------------------------------------------ panorama
  let panoZoom = false, showZos = true;
  const PW = 640, PH = 260, PL = 36, PR = 8, PT = 10, PB = 28;
  const svg = $("pano"), NS = "http://www.w3.org/2000/svg";
  const el = (t, a, p) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); p.appendChild(e); return e; };
  let view = {A0: 155, A1: 300, E0: -10.5, E1: 6};
  const px = az => PL + (az - view.A0) / (view.A1 - view.A0) * (PW - PL - PR);
  const py = m => PT + (view.E1 - m) / (view.E1 - view.E0) * (PH - PT - PB);
  function drawPano() {
    const b = trueBearing();
    if (panoZoom && b !== null) view.A0 = Math.max(150, Math.min(282, b - 9)), view.A1 = view.A0 + 18; else view.A0 = 155, view.A1 = 300;
    const inW = az => az >= view.A0 && az <= view.A1;
    const sky = S.sky.filter(s => inW(s[0]));
    // vertical range from what is actually in the window
    const vals = sky.map(s => s[1]).concat(H.filter(p => inW(p.az) && hwyClass(p) !== "h").map(p => p.a), S.towers.filter(t => inW(t.az) && isLit(t) && t.a !== null).map(t => t.a),
      RD.flatMap(r => r.p.filter(p => inW(p.az) && roadClass(p) === "v").map(p => p.a)), S.railpano.filter(r => inW(r[1]) && r[4] <= K).map(r => r[3]));
    const lo = Math.min(...sky.map(s => s[3]), ...vals), hi = Math.max(...vals);
    view.E0 = Math.floor(lo - 0.6); view.E1 = Math.ceil(hi + 1.2);
    svg.innerHTML = "";
    el("rect", {x: PL, y: PT, width: PW - PL - PR, height: PH - PT - PB, fill: "var(--surface-2)"}, svg);
    const d0 = mrad2deg(view.E0), d1 = mrad2deg(view.E1), gst = d1 - d0 > 1.2 ? 0.2 : d1 - d0 > 0.5 ? 0.1 : 0.05;
    for (let dg = Math.ceil(d0 / gst - 1e-9) * gst; dg <= d1 + 1e-9; dg += gst) {
      const e = Math.tan(dg * D2R) * 1000;
      el("line", {x1: PL, x2: PW - PR, y1: py(e), y2: py(e), stroke: "var(--rule)", "stroke-width": .6}, svg);
      el("text", {x: PL - 4, y: py(e) + 3, "text-anchor": "end"}, svg).textContent = fmt(Math.abs(dg) < 1e-9 ? 0 : dg, gst < 0.1 ? 2 : 1);
    }
    // nested terrain silhouettes: far skyline, then ridges within 45, 25 and 10 km
    const layer = (col, op) => el("path", {d: `M${px(sky[0][0])},${py(view.E0)} ` + sky.map(s => `L${px(s[0])},${py(Math.max(view.E0, s[col]))}`).join(" ") + ` L${px(sky[sky.length - 1][0])},${py(view.E0)} Z`, fill: "var(--ink)", "fill-opacity": op}, svg);
    layer(1, .10); layer(5, .09); layer(4, .09); layer(3, .10);
    el("polyline", {points: sky.map(s => `${px(s[0])},${py(s[1])}`).join(" "), fill: "none", stroke: "var(--ink-2)", "stroke-width": 1.3}, svg);
    el("line", {x1: PL, x2: PW - PR, y1: py(0), y2: py(0), stroke: "var(--muted)", "stroke-dasharray": "3 3", "stroke-width": .8}, svg);
    // activity-weighted Zone of Skepticism: expected ordinary lights per hour (clipped to the plot)
    if (RATE && showZos) {
      const cid = "panoclip"; const defs = el("defs", {}, svg); const cp = el("clipPath", {id: cid}, defs);
      el("rect", {x: PL, y: PT, width: PW - PL - PR, height: PH - PT - PB}, cp);
      const g = el("g", {"clip-path": `url(#${cid})`}, svg);
      RATE.levels.forEach((lv, i) => RATES.forEach(Rs => Rs.rate_polys[String(lv)].forEach(r => { if (r.some(q => q[0] >= view.A0 - 1 && q[0] <= view.A1 + 1))
        el("path", {d: "M" + r.map(q => `${px(q[0]).toFixed(1)},${py(q[1]).toFixed(1)}`).join("L") + "Z", fill: `var(--r${i + 1})`, "fill-opacity": .6, "fill-rule": "evenodd"}, g); })));
    }
    S.fan.forEach(a => { if (inW(a)) el("line", {x1: px(a), x2: px(a), y1: PT, y2: PH - PB, stroke: "var(--accent)", "stroke-dasharray": "1 3", "stroke-width": .8}, svg); });
    // US-67
    const col = {v: "var(--vis)", m: "var(--marg)", h: "var(--hid)"};
    ["h", "m", "v"].forEach(c => H.forEach(p => { if (hwyClass(p) === c && inW(p.az) && p.a >= view.E0) el("circle", {cx: px(p.az), cy: py(p.a), r: c === "h" ? 1.1 : 2.3, fill: col[c], "fill-opacity": c === "h" ? .5 : 1}, svg); }));
    // other state roads in view
    RD.forEach(rd => rd.p.forEach(p => { if (roadClass(p) === "v" && inW(p.az) && p.a >= view.E0) el("circle", {cx: px(p.az), cy: py(p.a), r: 2, fill: "var(--road2)"}, svg); }));
    // railroad track in view
    S.railpano.forEach(r => { if (inW(r[1]) && r[4] <= K && r[3] >= view.E0) el("circle", {cx: px(r[1]), cy: py(r[3]), r: 1.8, fill: "var(--rail)"}, svg); });
    // towns
    S.towns.forEach(t => { if (inW(t.az) && t.a !== undefined && !(!panoZoom && t.n.startsWith("Ojinaga"))) {
      const seen = t.kc <= K, sk = skyAt(t.az), y = seen ? Math.max(py(t.a), PT + 10) : Math.max(py(sk ? sk.m : t.a) - 6, PT + 10);
      el("text", {x: px(t.az), y: Math.min(y, PH - PB - 4), "text-anchor": "middle", style: `fill:var(--ink-2);opacity:${seen ? 1 : .55};font-weight:600`}, svg).textContent = (!panoZoom && t.n === "Presidio" ? "Presidio–Ojinaga" : t.n.replace(", Chihuahua", "")) + (seen ? "" : " (glow)");
    }});
    // aerostat: the ground site plus a marker showing it flies higher
    S.fields.filter(f => f.k === "balloon" && inW(f.az)).forEach(f => {
      el("line", {x1: px(f.az), x2: px(f.az), y1: py(view.E1), y2: py(f.a ?? 0), stroke: "var(--cell)", "stroke-dasharray": "2 3", "stroke-width": 1}, svg);
      el("text", {x: px(f.az) - 3, y: PT + 10, "text-anchor": "end", style: "fill:var(--cell)"}, svg).textContent = "aerostat ↑";
    });
    // towers: lit ones as red diamonds, solid if the top light is in view
    S.towers.forEach(t => { if (!inW(t.az) || t.a === null || t.a < view.E0) return;
      const lit = isLit(t), seen = inView(t); if (!lit && !seen) return;
      const x = px(t.az), y = py(t.a), r = lit ? 4.5 : 3;
      el("path", {d: `M${x},${y - r} L${x + r},${y} L${x},${y + r} L${x - r},${y} Z`, fill: lit && seen ? "var(--cell)" : "none", stroke: lit ? "var(--cell)" : "var(--muted)", "stroke-width": 1.3}, svg);
      if (panoZoom && lit) el("text", {x: x + 6, y: y - 5}, svg).textContent = `${fmt(t.h, 0)} m tower${seen ? "" : " (hidden)"}`;
    });
    // axis
    const tick = panoZoom ? 2 : 20;
    for (let a = Math.ceil(view.A0 / tick) * tick; a <= view.A1; a += tick) {
      el("line", {x1: px(a), x2: px(a), y1: PH - PB, y2: PH - PB + 4, stroke: "var(--muted)"}, svg);
      el("text", {x: px(a), y: PH - PB + 14, "text-anchor": "middle"}, svg).textContent = `${fmt(refMag ? norm(a - DECL) : a, 0)}°`;
    }
    el("text", {x: PW - PR, y: PH - 1, "text-anchor": "end"}, svg).textContent = refMag ? "magnetic bearing" : "true bearing";
    el("text", {x: 2, y: PH - 1}, svg).textContent = "elev °";
    if (b !== null && inW(b)) {
      el("line", {x1: px(b), x2: px(b), y1: PT, y2: PH - PB, stroke: "var(--accent)", "stroke-width": 1.6}, svg);
      const e = parseFloat($("elev").value);
      if (!isNaN(e)) el("circle", {cx: px(b), cy: py(Math.tan(e * D2R) * 1000), r: 5, fill: "none", stroke: "var(--accent)", "stroke-width": 2}, svg);
    }
    const hdeg = (view.A1 - view.A0) / (PW - PL - PR), vdeg = mrad2deg(view.E1 - view.E0) / (PH - PT - PB);
    if ($("panoNote")) $("panoNote").textContent = `Height stretched about ${fmt(hdeg / vdeg, 0)}× so the skyline detail is visible. Shaded layers are ridges within 10, 25 and 45 km, then the far skyline. Blue = Zone of Skepticism, shaded by how many ordinary lights pass there per hour on a clear night, from normal refraction up to a strong inversion (lightest 0.01–0.1, then 0.1–1, 1–10, 10+), allowing a ±0.3° bearing error. Unshaded ground: fewer than one per 100 hours from catalogued sources. ◆ red = lit tower (hollow if hidden), purple = railroad in view, magenta = other roads in view.`;
  }
  svg.addEventListener("click", ev => {
    const r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) * (PW / r.width), y = (ev.clientY - r.top) * (PH / r.height);
    if (x < PL || x > PW - PR || y < PT || y > PH - PB) return;
    const az = view.A0 + (x - PL) / (PW - PL - PR) * (view.A1 - view.A0), m = view.E1 - (y - PT) / (PH - PT - PB) * (view.E1 - view.E0);
    setTrueBearing(az, mrad2deg(m));
  });
  if ($("panoFull")) $("panoFull").onclick = () => { panoZoom = false; $("panoFull").setAttribute("aria-pressed", "true"); $("panoZoom").setAttribute("aria-pressed", "false"); drawPano(); };
  if ($("zosBtn")) $("zosBtn").onclick = () => { showZos = !showZos; $("zosBtn").setAttribute("aria-pressed", String(showZos)); drawPano(); };
  if ($("panoZoom")) $("panoZoom").onclick = () => { panoZoom = true; $("panoZoom").setAttribute("aria-pressed", "true"); $("panoFull").setAttribute("aria-pressed", "false"); drawPano(); };

  // ------------------------------------------------------------ field log (this device only)
  let LOG = [];
  try { LOG = JSON.parse(localStorage.getItem("mlfg-log") || "[]"); } catch (e) {}
  const saveLog = () => { try { localStorage.setItem("mlfg-log", JSON.stringify(LOG)); } catch (e) {} renderLog(); };
  function renderLog() {
    $("log").innerHTML = LOG.slice().reverse().map((s, i) => `<li><span><b class="mono">${s.time.slice(5, 16).replace("T", " ")}</b> · ${fmt(s.true_bearing, 1)}° T${s.elev_deg !== "" ? ` · ${s.elev_deg}°` : ""} · ${s.note ? s.note.slice(0, 40) : s.top}</span><button type="button" data-i="${LOG.length - 1 - i}" aria-label="Delete entry">✕</button></li>`).join("");
    $("log").querySelectorAll("button").forEach(bt => bt.onclick = () => { LOG.splice(+bt.dataset.i, 1); saveLog(); });
  }
  $("logBtn").addEventListener("click", () => {
    if (!last) return;
    LOG.push({time: new Date().toISOString(), true_bearing: +last.b.toFixed(2), magnetic_bearing: +norm(last.b - DECL).toFixed(2),
      elev_deg: last.elev === null ? "" : last.elev, window_deg: last.tol, refraction_k: K, us67_in_view: last.visible, top_candidate: last.top, top: last.top, note: $("note").value.trim()});
    $("note").value = ""; saveLog();
  });
  $("csvBtn").addEventListener("click", () => {
    const cols = ["time", "true_bearing", "magnetic_bearing", "elev_deg", "window_deg", "refraction_k", "us67_in_view", "top_candidate", "note"];
    const q = v => `"${String(v).replace(/"/g, '""')}"`;
    const csv = [cols.join(",")].concat(LOG.map(s => cols.map(c => q(s[c] ?? "")).join(","))).join("\n");
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], {type: "text/csv"}));
    a.download = `marfa-sightings-${new Date().toISOString().slice(0, 10)}.csv`; document.body.appendChild(a); a.click(); a.remove();
  });
  renderLog();

  document.addEventListener("themechange", () => { drawStatic(); drawHwy(); identify(); });
  identify();
})();

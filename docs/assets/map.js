/* Marfa Lights Field Guide — interactive map, light identifier, panorama and field log. */
(async function () {
  const S = await fetch("data/site.json").then(r => r.json());
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
  const H = S.hwy.map(p => ({lat: p[0], lon: p[1], az: p[2], d: p[3], z: p[4], kc: p[5], cls: p[6], a: p[7], ch: p[8]}));
  const hwyDistAt = az => {           // distance to the first US-67 crossing on a bearing inside the fan
    const r = S.rays; if (az < r[0][0] || az > r[r.length - 1][0]) return null;
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
    ["fan", "Viewing fan, 0.5° rays", "sw", "--accent", true],
    ["rail", "Railroads", "sw", "--rail", true],
    ["xing", "Rail grade crossings", "swd", "--rail", false],
    ["power", "Power lines ≥ 69 kV", "sw", "--power", false],
    ["air", "Airfields, heliports, TARS", "swd", "--accent", true],
    ["cell", "Cell towers", "swd", "--cell", true],
    ["towns", "Towns", "swd", "--town", true],
  ];
  LAYERS.forEach(([id]) => groups[id] = L.layerGroup());
  const bearingGroup = L.layerGroup().addTo(map);

  function popup(title, rows) { return `<b>${title}</b><br>${rows.filter(Boolean).join("<br>")}`; }
  const azLine = (az, d) => `Bearing ${fmt(az, 1)}° true (${fmt(norm(az - DECL), 1)}° magnetic) · ${fmt(d, 1)} km`;

  function drawStatic() {
    ["fan", "rail", "xing", "power", "air", "cell", "towns"].forEach(id => groups[id].clearLayers());
    const acc = css("--accent");
    // fan wedge + rays
    const e1 = fwd(V[0], V[1], S.fan[0], 45000), e2 = fwd(V[0], V[1], S.fan[1], 45000);
    const arc = []; for (let a = S.fan[0]; a <= S.fan[1] + 1e-6; a += 1) arc.push(fwd(V[0], V[1], a, 45000));
    L.polygon([V, e1, ...arc, e2], {color: acc, weight: 1, opacity: .5, fillOpacity: .05, interactive: false}).addTo(groups.fan);
    S.rays.forEach((r, i) => { if (i % 2 === 0 || i === S.rays.length - 1) L.polyline([V, [r[1], r[2]]], {color: acc, weight: .7, opacity: .22, interactive: false}).addTo(groups.fan); });
    // rail
    const rc = css("--rail");
    S.rail.forEach(ln => L.polyline(ln.c, {color: rc, weight: ln.m ? 3 : 1.6, opacity: .95, dashArray: ln.o === "TXPF" ? "7 5" : null})
      .bindPopup(popup(ln.o === "UP" ? "Union Pacific (Sunset Route)" : "Texas Pacifico (former South Orient)", [
        `${ln.s ? ln.s + " subdivision" : "Siding or yard track"}`, ln.o === "UP" ? "Main line through Marfa; freight and Amtrak" : "Marfa–Presidio line; light traffic",
        "Source: USDOT BTS North American Rail Network"])).addTo(groups.rail));
    S.xing.forEach(x => L.circleMarker([x.lat, x.lon], {radius: 4, color: rc, weight: 1.5, fillColor: css("--surface"), fillOpacity: 1})
      .bindPopup(popup(`Grade crossing ${x.id}`, [`${x.rr} · ${x.road} · ${x.pos}`, `Reported through trains: ${x.day} by day, ${x.night} at night`, azLine(x.az, x.d), "Source: FRA crossing inventory (self-reported)"])).addTo(groups.xing));
    S.tl.forEach(t => L.polyline(t.c, {color: css("--power"), weight: 1.6, dashArray: "2 4", opacity: .9})
      .bindPopup(popup(`${t.kv || "?"} kV transmission line`, [`${t.a} – ${t.b}`, "Unlit structures; they appear in photos, not as lights", "Source: HIFLD-derived transmission lines"])).addTo(groups.power));
    S.fields.forEach(f => {
      const col = f.k === "historic" ? css("--muted") : f.k === "balloon" ? css("--cell") : acc;
      L.circleMarker([f.lat, f.lon], {radius: f.k === "historic" ? 4 : 6, color: col, weight: 2, fillColor: col, fillOpacity: f.k === "historic" ? .2 : .6})
        .bindPopup(popup(f.n, [
          f.k === "historic" ? "Historic WWII Marfa Army Air Field site (closed)" : f.k === "balloon" ? "Tethered aerostat radar site (CBP). The balloon and tether can carry lights well above the terrain." : f.k === "heliport" ? "Heliport" : `Airfield${f.faa ? " · in current FAA records" : ""}`,
          f.elev ? `Elevation ${Number(f.elev).toLocaleString()} ft` : "", azLine(f.az, f.d),
          `<a href="https://ourairports.com/airports/${f.id}/" target="_blank" rel="noopener">OurAirports record</a>`])).addTo(groups.air);
    });
    S.cells.forEach(c => L.circleMarker([c.lat, c.lon], {radius: 5, color: css("--cell"), weight: 2, fillColor: css("--cell"), fillOpacity: .5})
      .bindPopup(popup("Cell site", [c.lic, c.addr, c.h ? `Structure ${fmt(c.h, 0)} m tall` : "", c.asr ? `FCC ASR ${c.asr}` : "", azLine(c.az, c.d), "Tall towers carry red aviation obstruction lights"])).addTo(groups.cell));
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
  function drawHwy() {
    groups.hwy.clearLayers();
    const col = {v: css("--vis"), m: css("--marg"), h: css("--hid")}, w = {v: 5, m: 4, h: 2.2};
    const label = {v: "Visible from the Viewing Area", m: "Marginal: depends on detail finer than the terrain model", h: "Hidden by terrain"};
    let run = [H[0]];
    const flush = () => {
      if (run.length < 2) return; const c = hwyClass(run[0]), a = run[0], b = run[run.length - 1];
      L.polyline(run.map(p => [p.lat, p.lon]), {color: col[c], weight: w[c], opacity: .95, lineCap: "butt"})
        .bindPopup(popup("US-67", [`<span style="color:${col[c]}">■</span> ${label[c]}${Math.abs(K - 0.13) < 1e-9 ? " (standard refraction)" : ` at k = ${fmt(K, 2)}`}`,
          `Road km ${fmt(a.ch, 1)}–${fmt(b.ch, 1)} from Shafter`, `Bearing ${fmt(Math.min(a.az, b.az), 1)}–${fmt(Math.max(a.az, b.az), 1)}° true`,
          `Distance ${fmt(Math.min(a.d, b.d), 1)}–${fmt(Math.max(a.d, b.d), 1)} km · road ${Math.min(a.z, b.z)}–${Math.max(a.z, b.z)} m`])).addTo(groups.hwy);
    };
    for (let i = 1; i < H.length; i++) { run.push(H[i]); if (hwyClass(H[i]) !== hwyClass(run[0]) || i === H.length - 1) { flush(); run = [H[i]]; } }
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
    let anyVisible = false;
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
        dist: `${fmt(dmin, 1)}–${fmt(dmax, 1)} km`, sub: `${fmt(run.length * 0.06, 1)} km of road on this bearing, road km ${fmt(run[0].ch, 1)}–${fmt(run[run.length - 1].ch, 1)} from Shafter${match}`});
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
      C.push({d: p.d, chip: "Rail", col: "--rail", t: p.o === "UP" ? "Union Pacific trains (headlight, ditch lights)" : "Texas Pacifico trains, Marfa–Presidio line",
        dist: `${fmt(p.d, 1)} km`, sub: `${p.m ? "Main track" : "Siding/yard"}${front ? " · in front of US-67 on this bearing" : ""}`});
    });
    const pts = [
      ...S.fields.map(f => ({...f, chip: f.k === "balloon" ? "Aerostat" : f.k === "historic" ? "Historic" : "Air", col: f.k === "balloon" ? "--cell" : "--accent",
        t: f.n, sub: f.k === "balloon" ? "Radar balloon and tether lights can sit high above the skyline" : f.k === "historic" ? "WWII field, closed: no lights expected" : "Runway, beacon or aircraft lights"})),
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
    else lines.push(`<b>US-67 is not on this bearing.</b>${inFan ? "" : " You are pointing outside the viewing fan toward the highway."}`);
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
  const P = {W: 640, H: 250, L: 34, R: 8, T: 10, B: 26, A0: 218, A1: 282, E0: -10.5, E1: 9};
  const px = a => P.L + (a - P.A0) / (P.A1 - P.A0) * (P.W - P.L - P.R), py = e => P.T + (P.E1 - e) / (P.E1 - P.E0) * (P.H - P.T - P.B);
  const svg = $("pano"), NS = "http://www.w3.org/2000/svg";
  const el = (t, a, p) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); p.appendChild(e); return e; };
  function drawPano() {
    svg.innerHTML = "";
    el("rect", {x: P.L, y: P.T, width: P.W - P.L - P.R, height: P.H - P.T - P.B, fill: "var(--surface-2)"}, svg);
    for (let e = -10; e <= 8; e += 2) {
      el("line", {x1: P.L, x2: P.W - P.R, y1: py(e), y2: py(e), stroke: "var(--rule)", "stroke-width": .6}, svg);
      el("text", {x: P.L - 4, y: py(e) + 3, "text-anchor": "end"}, svg).textContent = fmt(mrad2deg(e), 1);
    }
    const sky = S.sky.filter(s => s[0] >= P.A0 && s[0] <= P.A1);
    el("path", {d: `M${px(sky[0][0])},${py(P.E0)} ` + sky.map(s => `L${px(s[0])},${py(Math.max(P.E0, s[1]))}`).join(" ") + ` L${px(sky[sky.length - 1][0])},${py(P.E0)} Z`, fill: "var(--rule)"}, svg);
    el("polyline", {points: sky.map(s => `${px(s[0])},${py(s[1])}`).join(" "), fill: "none", stroke: "var(--ink-2)", "stroke-width": 1.2}, svg);
    el("line", {x1: P.L, x2: P.W - P.R, y1: py(0), y2: py(0), stroke: "var(--muted)", "stroke-dasharray": "3 3", "stroke-width": .8}, svg);
    S.fan.forEach(a => el("line", {x1: px(a), x2: px(a), y1: P.T, y2: P.H - P.B, stroke: "var(--accent)", "stroke-dasharray": "1 3", "stroke-width": .8}, svg));
    const col = {v: "var(--vis)", m: "var(--marg)", h: "var(--hid)"};
    ["h", "m", "v"].forEach(c => H.forEach(p => { if (hwyClass(p) === c && p.a >= P.E0 && p.az >= P.A0 && p.az <= P.A1) el("circle", {cx: px(p.az), cy: py(p.a), r: c === "h" ? 1.2 : 2.2, fill: col[c]}, svg); }));
    for (let a = 220; a <= 280; a += 10) {
      const lab = refMag ? norm(a - DECL) : a;
      el("text", {x: px(a), y: P.H - 12, "text-anchor": "middle"}, svg).textContent = `${fmt(lab, 0)}°`;
    }
    el("text", {x: P.W - P.R, y: P.H - 1, "text-anchor": "end"}, svg).textContent = refMag ? "magnetic bearing" : "true bearing";
    el("text", {x: 2, y: P.T + 8}, svg).textContent = "deg";
    const b = trueBearing();
    if (b !== null && b >= P.A0 && b <= P.A1) {
      el("line", {x1: px(b), x2: px(b), y1: P.T, y2: P.H - P.B, stroke: "var(--accent)", "stroke-width": 1.6}, svg);
      const e = parseFloat($("elev").value);
      if (!isNaN(e)) el("circle", {cx: px(b), cy: py(Math.tan(e * D2R) * 1000), r: 5, fill: "none", stroke: "var(--accent)", "stroke-width": 2}, svg);
    }
  }
  svg.addEventListener("click", ev => {
    const r = svg.getBoundingClientRect(), sx = P.W / r.width, x = (ev.clientX - r.left) * sx, y = (ev.clientY - r.top) * (P.H / r.height);
    if (x < P.L || x > P.W - P.R || y < P.T || y > P.H - P.B) return;
    const az = P.A0 + (x - P.L) / (P.W - P.L - P.R) * (P.A1 - P.A0), m = P.E1 - (y - P.T) / (P.H - P.T - P.B) * (P.E1 - P.E0);
    setTrueBearing(az, mrad2deg(m));
  });

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

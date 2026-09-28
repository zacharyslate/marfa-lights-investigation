/* Marfa Lights Field Guide — interactive map, light identifier, panorama and field log. */
(async function () {
  const S = await fetch("data/site.json?v=3").then(r => r.json());
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
    const FR = 66000, e1 = fwd(V[0], V[1], S.fan[0], FR), e2 = fwd(V[0], V[1], S.fan[1], FR);
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
  function drawHwy() {
    groups.hwy.clearLayers();
    const col = {v: css("--vis"), m: css("--marg"), h: css("--hid")}, w = {v: 6, m: 5, h: 3};
    const label = {v: "Visible from the Viewing Area", m: "Marginal: depends on detail finer than the terrain model", h: "Hidden by terrain"};
    let run = [H[0]];
    const flush = () => {
      if (run.length < 2) return; const c = hwyClass(run[0]), a = run[0], b = run[run.length - 1];
      cased(run.map(p => [p.lat, p.lon]), {color: col[c], weight: w[c], opacity: 1, lineCap: "butt"}, groups.hwy)
        .bindPopup(popup("US-67", [`<span style="color:${col[c]}">■</span> ${label[c]}${Math.abs(K - 0.13) < 1e-9 ? " (standard refraction)" : ` at k = ${fmt(K, 2)}`}`,
          `Road km ${fmt(a.ch, 1)}–${fmt(b.ch, 1)} from Shafter`, `Bearing ${fmt(Math.min(a.az, b.az), 1)}–${fmt(Math.max(a.az, b.az), 1)}° true`,
          `Distance ${fmt(Math.min(a.d, b.d), 1)}–${fmt(Math.max(a.d, b.d), 1)} km · road ${Math.min(a.z, b.z)}–${Math.max(a.z, b.z)} m`]));
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
  let panoZoom = false;
  const PW = 640, PH = 260, PL = 36, PR = 8, PT = 10, PB = 28;
  const svg = $("pano"), NS = "http://www.w3.org/2000/svg";
  const el = (t, a, p) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); p.appendChild(e); return e; };
  let view = {A0: 215, A1: 285, E0: -10.5, E1: 6};
  const px = az => PL + (az - view.A0) / (view.A1 - view.A0) * (PW - PL - PR);
  const py = m => PT + (view.E1 - m) / (view.E1 - view.E0) * (PH - PT - PB);
  function drawPano() {
    const b = trueBearing();
    if (panoZoom && b !== null) view.A0 = Math.max(210, Math.min(274, b - 9)), view.A1 = view.A0 + 18; else view.A0 = 215, view.A1 = 285;
    const inW = az => az >= view.A0 && az <= view.A1;
    const sky = S.sky.filter(s => inW(s[0]));
    // vertical range from what is actually in the window
    const vals = sky.map(s => s[1]).concat(H.filter(p => inW(p.az) && hwyClass(p) !== "h").map(p => p.a), S.towers.filter(t => inW(t.az) && isLit(t) && t.a !== null).map(t => t.a));
    const lo = Math.min(...sky.map(s => s[3]), ...vals), hi = Math.max(...vals);
    view.E0 = Math.floor(lo - 0.6); view.E1 = Math.ceil(hi + 1.2);
    svg.innerHTML = "";
    el("rect", {x: PL, y: PT, width: PW - PL - PR, height: PH - PT - PB, fill: "var(--surface-2)"}, svg);
    const gstep = (view.E1 - view.E0) > 12 ? 2 : 1;
    for (let e = Math.ceil(view.E0); e <= view.E1; e += gstep) {
      el("line", {x1: PL, x2: PW - PR, y1: py(e), y2: py(e), stroke: "var(--rule)", "stroke-width": .6}, svg);
      el("text", {x: PL - 4, y: py(e) + 3, "text-anchor": "end"}, svg).textContent = fmt(mrad2deg(e), 2);
    }
    // nested terrain silhouettes: far skyline, then ridges within 45, 25 and 10 km
    const layer = (col, op) => el("path", {d: `M${px(sky[0][0])},${py(view.E0)} ` + sky.map(s => `L${px(s[0])},${py(Math.max(view.E0, s[col]))}`).join(" ") + ` L${px(sky[sky.length - 1][0])},${py(view.E0)} Z`, fill: "var(--ink)", "fill-opacity": op}, svg);
    layer(1, .10); layer(5, .09); layer(4, .09); layer(3, .10);
    el("polyline", {points: sky.map(s => `${px(s[0])},${py(s[1])}`).join(" "), fill: "none", stroke: "var(--ink-2)", "stroke-width": 1.3}, svg);
    el("line", {x1: PL, x2: PW - PR, y1: py(0), y2: py(0), stroke: "var(--muted)", "stroke-dasharray": "3 3", "stroke-width": .8}, svg);
    S.fan.forEach(a => { if (inW(a)) el("line", {x1: px(a), x2: px(a), y1: PT, y2: PH - PB, stroke: "var(--accent)", "stroke-dasharray": "1 3", "stroke-width": .8}, svg); });
    // US-67
    const col = {v: "var(--vis)", m: "var(--marg)", h: "var(--hid)"};
    ["h", "m", "v"].forEach(c => H.forEach(p => { if (hwyClass(p) === c && inW(p.az) && p.a >= view.E0) el("circle", {cx: px(p.az), cy: py(p.a), r: c === "h" ? 1.1 : 2.3, fill: col[c], "fill-opacity": c === "h" ? .5 : 1}, svg); }));
    // railroad track in view
    S.railpano.forEach(r => { if (inW(r[1]) && r[4] <= K && r[3] >= view.E0) el("circle", {cx: px(r[1]), cy: py(r[3]), r: 1.8, fill: "var(--rail)"}, svg); });
    // towns
    S.towns.forEach(t => { if (inW(t.az) && t.a !== undefined) {
      const seen = t.kc <= K, y = Math.max(py(t.a), PT + 10);
      el("text", {x: px(t.az), y: Math.min(y, PH - PB - 4), "text-anchor": "middle", style: `fill:var(--ink-2);opacity:${seen ? 1 : .55};font-weight:600`}, svg).textContent = t.n.replace(", Chihuahua", "") + (seen ? "" : " (glow)");
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
    const tick = panoZoom ? 2 : 10;
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
    if ($("panoNote")) $("panoNote").textContent = `Height stretched about ${fmt(hdeg / vdeg, 0)}× so the skyline detail is visible. Shaded layers are ridges within 10, 25 and 45 km, then the far skyline. ◆ red = lit tower (hollow if its light is hidden), purple = railroad in view.`;
  }
  svg.addEventListener("click", ev => {
    const r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) * (PW / r.width), y = (ev.clientY - r.top) * (PH / r.height);
    if (x < PL || x > PW - PR || y < PT || y > PH - PB) return;
    const az = view.A0 + (x - PL) / (PW - PL - PR) * (view.A1 - view.A0), m = view.E1 - (y - PT) / (PH - PT - PB) * (view.E1 - view.E0);
    setTrueBearing(az, mrad2deg(m));
  });
  if ($("panoFull")) $("panoFull").onclick = () => { panoZoom = false; $("panoFull").setAttribute("aria-pressed", "true"); $("panoZoom").setAttribute("aria-pressed", "false"); drawPano(); };
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

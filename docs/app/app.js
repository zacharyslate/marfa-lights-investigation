/* Marfa Lights app: Tonight, Identify, Log, Bingo. Works offline once cached by ../sw.js. */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const D2R = Math.PI / 180, R2D = 180 / Math.PI;
  const VIEW = {lat: 30.2751108, lon: -103.8827973, h: 1495};
  let DECL = 6.2;                      // replaced by the value in site.json once it loads
  const TZ = "America/Chicago";
  const norm = a => ((a % 360) + 360) % 360, angDiff = (a, b) => ((a - b + 540) % 360) - 180;
  const fmt = (v, n = 0) => { const s = Number(v).toFixed(n); return /^-0(\.0+)?$/.test(s) ? s.slice(1) : s; };
  const mrad2deg = m => Math.atan(m / 1000) * R2D;
  const tfmt = d => d ? new Intl.DateTimeFormat("en-US", {timeZone: TZ, hour: "numeric", minute: "2-digit"}).format(d instanceof Date ? d : d.date) : "–";
  const store = {get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }};
  const toast = (t, ms = 2600) => { const el = $("toast"); el.textContent = t; el.style.display = "block"; clearTimeout(toast.h); toast.h = setTimeout(() => el.style.display = "none", ms); };

  // ---------------------------------------------------------------- night mode
  function setNight(on) { if (on) document.documentElement.setAttribute("data-night", "1"); else document.documentElement.removeAttribute("data-night");
    $("nightBtn").setAttribute("aria-pressed", String(on)); store.set("mlfg-app-night", on); if (started) drawPano(); }
  let started = false;
  $("nightBtn").onclick = () => setNight(!store.get("mlfg-app-night", false));
  setNight(store.get("mlfg-app-night", false));

  // ---------------------------------------------------------------- tabs
  const TABS = ["tonight", "identify", "log", "bingo", "more"];
  function show(tab) {
    if (!TABS.includes(tab)) tab = "tonight";
    TABS.forEach(t => { $("v-" + t).hidden = t !== tab; });
    document.querySelectorAll(".tabs [data-tab]").forEach(b => { if (b.dataset.tab === tab) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); });
    if (location.hash !== "#" + tab) history.replaceState(null, "", "#" + tab);
    window.scrollTo(0, 0);
    if (tab === "identify") requestAnimationFrame(drawPano);
    if (tab === "log") renderLog();
  }
  document.querySelectorAll(".tabs [data-tab]").forEach(b => b.onclick = () => show(b.dataset.tab));
  document.querySelectorAll("[data-go]").forEach(b => b.onclick = () => { show(b.dataset.go); if (b.dataset.new) $("l-note").focus(); });
  window.addEventListener("hashchange", () => show(location.hash.slice(1)));

  // ---------------------------------------------------------------- sheet
  function sheet(title, html, actions = []) {
    $("sheet-h").textContent = title; $("sheet-b").innerHTML = html;
    $("sheet-a").innerHTML = ""; actions.forEach(([label, fn, cls]) => { const b = document.createElement("button"); b.type = "button"; b.className = cls || "btn"; b.textContent = label; b.onclick = () => { fn(); closeSheet(); }; $("sheet-a").appendChild(b); });
    $("sheet").classList.add("open"); $("sheet-h").focus();
  }
  const closeSheet = () => $("sheet").classList.remove("open");
  document.addEventListener("keydown", e => { if (e.key === "Escape" && $("sheet").classList.contains("open")) closeSheet(); });
  $("sheet-x").onclick = closeSheet; $("sheet").addEventListener("click", e => { if (e.target.id === "sheet") closeSheet(); });

  // ---------------------------------------------------------------- data
  let S = null, ZR = null, MK = null;
  const okJson = r => { if (!r.ok) throw new Error(r.status); return r.json(); };
  const ready = Promise.all([
    fetch("../data/site.json?v=9").then(okJson).then(j => { S = j; if (S.declination) DECL = S.declination.deg; }),
    fetch("../data/zos_rate.json?v=9").then(okJson).then(j => { ZR = j; }).catch(() => {})])
    .then(() => { if (window.MarfaMask && ZR) MK = MarfaMask.build(ZR, null, skyAt); })
    .catch(() => toast("Couldn't load the map data. Open the app once with a connection.", 5000));

  // ================================================================ TONIGHT
  const A = window.Astronomy;
  const OBS = A ? new A.Observer(VIEW.lat, VIEW.lon, VIEW.h) : null;
  const altaz = (body, date) => { const eq = A.Equator(body, date, OBS, true, true); const h = A.Horizon(date, OBS, eq.ra, eq.dec, "normal"); return {alt: h.altitude, az: h.azimuth}; };
  function nightStart(now) {
    const hr = +new Intl.DateTimeFormat("en-US", {timeZone: TZ, hour: "numeric", hourCycle: "h23"}).format(now);
    const shift = hr >= 12 ? -(hr - 12) : hr < 7 ? -(hr + 12) : 12 - hr;
    return new Date(now.getTime() + shift * 3600e3);
  }
  const phaseName = a => a < 22.5 || a >= 337.5 ? "New moon" : a < 67.5 ? "Waxing crescent" : a < 112.5 ? "First quarter" : a < 157.5 ? "Waxing gibbous" :
    a < 202.5 ? "Full moon" : a < 247.5 ? "Waning gibbous" : a < 292.5 ? "Last quarter" : "Waning crescent";
  const compass = az => ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][Math.round(norm(az) / 22.5) % 16];
  let TONIGHT = null;

  function computeTonight() {
    if (!A) { $("t-sum").textContent = "Sky calculations aren't available in this browser."; return; }
    const now = new Date(), start = nightStart(now);
    const sunset = A.SearchRiseSet("Sun", OBS, -1, start, 1), dusk = A.SearchAltitude("Sun", OBS, -1, start, 1, -18);
    const dawn = dusk ? A.SearchAltitude("Sun", OBS, +1, dusk.date, 1, -18) : null, sunrise = A.SearchRiseSet("Sun", OBS, +1, dusk ? dusk.date : start, 1);
    const t0 = sunset.date, t1 = sunrise.date, step = 10 * 60e3, samples = [];
    for (let t = t0.getTime(); t <= t1.getTime(); t += step) {
      const d = new Date(t), sun = altaz("Sun", d), moon = altaz("Moon", d);
      samples.push({d, sun: sun.alt, moon: moon.alt, moonAz: moon.az});
    }
    const illum = A.Illumination("Moon", A.MakeTime(new Date((t0.getTime() + t1.getTime()) / 2))).phase_fraction;
    const phase = A.MoonPhase(new Date((t0.getTime() + t1.getTime()) / 2));
    const moonrise = A.SearchRiseSet("Moon", OBS, +1, t0, 1.2), moonset = A.SearchRiseSet("Moon", OBS, -1, t0, 1.2);
    const upAtSunset = altaz("Moon", t0).alt > 0, before = x => x && x.date.getTime() < t1.getTime();
    const moonTxt = upAtSunset ? (before(moonset) ? `up at sunset, sets ${tfmt(moonset)}` : "up all night")
      : before(moonrise) ? `rises ${tfmt(moonrise)}${moonset && moonset.date > moonrise.date && before(moonset) ? `, sets ${tfmt(moonset)}` : ", up until dawn"}` : "down all night";
    samples.forEach(s => { s.state = s.sun > -6 ? "civil" : s.sun > -18 ? "twi" : (s.moon > 0 && illum > 0.12 ? "moon" : "dark"); });
    const darkMin = samples.filter(s => s.state === "dark").length * 10;
    // planets
    const planets = ["Venus", "Jupiter", "Mars", "Saturn", "Mercury"].map(b => {
      const pts = samples.map(s => ({d: s.d, ...altaz(b, s.d), sun: s.sun}));
      const vis = pts.filter(p => p.alt > 3 && p.sun < -6);
      if (!vis.length) return null;
      const mag = A.Illumination(b, A.MakeTime(vis[0].d)).mag;
      // does it set during the dark part, and where?
      let set = null;
      for (let i = 1; i < pts.length; i++) if (pts[i - 1].alt > 0 && pts[i].alt <= 0 && pts[i].sun < -6) { set = pts[i]; break; }
      return {b, mag, first: vis[0], last: vis[vis.length - 1], set};
    }).filter(Boolean).sort((a, b) => a.mag - b.mag);
    TONIGHT = {start, sunset, dusk, dawn, sunrise, samples, illum, phase, moonrise, moonset, moonTxt, darkMin, planets};
    renderTonight();
  }

  function renderTonight() {
    const T = TONIGHT;
    $("t-date").textContent = new Intl.DateTimeFormat("en-US", {timeZone: TZ, weekday: "long", month: "long", day: "numeric"}).format(T.sunset.date);
    const moonUpAtDark = T.samples.find(s => s.state === "moon");
    $("t-sum").textContent = T.darkMin >= 120 ? `About ${fmt(T.darkMin / 60, 1)} hours of truly dark sky tonight${moonUpAtDark ? ", while the moon is down" : ""}.`
      : T.darkMin > 0 ? `Only about ${T.darkMin} minutes of fully dark sky tonight. The moon is up for most of the night.` : "The moon is up for all of the dark hours tonight, so the sky never gets fully dark. Bright lights are still easy to see.";
    $("t-tiles").innerHTML = [
      ["Sunset", tfmt(T.sunset), "on a flat horizon; the mountains hide the sun a little earlier"],
      ["Fully dark", tfmt(T.dusk), "end of twilight"],
      ["Moon", `${fmt(T.illum * 100)}%`, `${phaseName(T.phase)} · ${T.moonTxt}`],
      ["Dark hours", `${fmt(T.darkMin / 60, 1)} h`, `dawn twilight ${tfmt(T.dawn)}`]]
      .map(([k, b, s]) => `<div class="tile"><span class="k">${k}</span><b>${b}</b><span>${s}</span></div>`).join("");
    // timeline bar
    const t0 = T.samples[0].d.getTime(), t1 = T.samples[T.samples.length - 1].d.getTime(), X = t => (t - t0) / (t1 - t0) * 100;
    const col = {civil: "var(--sky)", twi: "var(--r2)", moon: "var(--r3)", dark: "#05070a"};
    let seg = "", cur = null, from = t0;
    T.samples.forEach((s, i) => { if (s.state !== cur || i === T.samples.length - 1) { if (cur) seg += `<i style="left:${X(from)}%;width:${X(s.d.getTime()) - X(from) + 0.3}%;background:${col[cur]}"></i>`; cur = s.state; from = s.d.getTime(); } });
    const now = Date.now(), nowMark = now > t0 && now < t1 ? `<i style="left:${X(now)}%;width:2px;background:var(--accent)"></i>` : "";
    const hours = []; for (let t = Math.ceil(t0 / 3600e3) * 3600e3; t < t1; t += 2 * 3600e3) hours.push(`<span style="position:absolute;left:${X(t)}%;transform:translateX(-50%)">${new Intl.DateTimeFormat("en-US", {timeZone: TZ, hour: "numeric"}).format(new Date(t))}</span>`);
    $("t-dark").innerHTML = `<h2>When is it dark?</h2><div class="bar" role="img" aria-label="Timeline of tonight from sunset to sunrise">${seg}${nowMark}</div>
      <div style="position:relative;height:16px;font:12px var(--f-mono);color:var(--muted)">${hours.join("")}</div>
      <p class="small dim"><span style="color:var(--r2)">■</span> twilight &nbsp;<span style="color:var(--r3)">■</span> moonlit &nbsp;<span style="color:#05070a;-webkit-text-stroke:1px var(--muted)">■</span> fully dark &nbsp;<span style="color:var(--accent)">|</span> now. The darkest hours are best for faint lights, but bright lights show up any time.</p>`;
    // planets
    $("t-planets").innerHTML = `<h2>Planets tonight</h2>` + (T.planets.length ? `<ul class="plist">${T.planets.map(p => {
      const inFan = p.set && p.set.az >= 150 && p.set.az <= 300;
      return `<li><b>${p.b}</b><span>magnitude ${fmt(p.mag, 1)} · ${p.first.d.getTime() === p.last.d.getTime() ? `low, briefly, around ${tfmt(p.first.d)}` : `visible ${tfmt(p.first.d)}–${tfmt(p.last.d)}`}${p.set ? ` · sets ${tfmt(p.set.d)} in the ${compass(p.set.az)} (${fmt(p.set.az)}° true, ${fmt(norm(p.set.az - DECL))}° compass)` : ""}</span>
        ${inFan ? `<span class="warn">Sets over the flat. Low down it flickers and changes colour, and is often mistaken for a Marfa Light.</span>` : ""}</li>`; }).join("")}</ul>`
      : `<p class="dim">No bright planets are up after dark tonight.</p>`);
    $("t-tip").innerHTML = `<h2>Tip</h2><p>${TIPS[Math.floor((T.sunset.date.getTime() / 864e5)) % TIPS.length]}</p>`;
  }
  const TIPS = [
    "Give your eyes 20–30 minutes in the dark before you judge how bright or dim a light is. One glance at a white phone screen resets the clock.",
    "Before anything else, find the red light of the tower at about 224° on your compass (230° true). It sits right among the US-67 headlights and makes a perfect reference point.",
    "A pair of lights that splits apart and joins again is usually two cars on US-67 passing each other.",
    "Note the time to the second whenever something happens. With a time, a light can be checked against traffic, trains, aircraft and satellites.",
    "If you're with someone, stand a little apart and take your own bearings. Compare afterwards, not during.",
    "A steady light that slowly sinks toward the mountains over half an hour is probably a planet or a bright star setting.",
    "Calibrate the camera sky finder on a tower light or bright star near where you're looking. The phone compass error changes with direction."];

  async function weather() {
    const cache = store.get("mlfg-wx", null);
    const render = w => { const p = w.period; $("t-weather").innerHTML = `<h2>Weather: ${p.name}</h2><p><b>${p.shortForecast}</b>. ${p.temperature}°${p.temperatureUnit}, wind ${p.windSpeed} ${p.windDirection}.</p>
      <p class="small dim">${p.detailedForecast || ""}</p><p class="small dim">National Weather Service forecast for Marfa, updated ${new Date(w.t).toLocaleString()}.</p>`; };
    if (cache) render(cache);
    try {
      const pt = await fetch("https://api.weather.gov/points/30.3095,-104.0206", {headers: {Accept: "application/geo+json"}}).then(r => r.json());
      const fc = await fetch(pt.properties.forecast, {headers: {Accept: "application/geo+json"}}).then(r => r.json());
      const period = fc.properties.periods.find(p => !p.isDaytime) || fc.properties.periods[0];
      const w = {t: Date.now(), period}; store.set("mlfg-wx", w); render(w);
    } catch (e) { if (!cache) $("t-weather").innerHTML = `<h2>Weather</h2><p class="dim">No connection, so no forecast. Look for clear, calm skies: they are the best nights.</p>`; }
  }

  // ---------------------------------------------------------------- refraction forecast
  // The light from US-67 travels a few metres to a few tens of metres above the flat. How much it bends depends on
  // the temperature gradient in that layer (Hirt et al. 2010, eq. 2): k = 503 p / T^2 (0.0343 + dT/dz), p in hPa,
  // T in K, dT/dz in K/m. The gradient here is the forecast difference between 80 m and 2 m above the ground
  // (Open-Meteo, CC BY 4.0). The model's per-point thresholds (site.json hwy kcrit) turn k into km of US-67 in view.
  const kOf = (t2, t80, p) => { const T = 273.15 + (t2 + t80) / 2; return 503 * p / (T * T) * (0.0343 + (t80 - t2) / 78); };
  const RC = ["#6b7480", "#8dbcf0", "#2f6fd0", "#e08a2a"];
  const kClass = k => k < 0.13 ? ["normal", "Normal or weaker", RC[0]] : k < 0.5 ? ["mild", "Mild inversion", RC[1]]
    : k < 1 ? ["strong", "Strong inversion", RC[2]] : ["duct", "Very strong: light can bend with the Earth", RC[3]];
  async function refraction() {
    const box = $("t-refr"), cache = store.get("mlfg-refr", null);
    const render = async F => {
      await ready; if (!TONIGHT || !S) return;
      const t0 = TONIGHT.sunset.date.getTime(), t1 = TONIGHT.sunrise.date.getTime();
      const hrs = F.time.map((t, i) => ({t: t * 1000, k: kOf(F.t2[i], F.t80[i], F.p[i]), dT: F.t80[i] - F.t2[i], w: F.w[i], c: F.c[i]})).filter(h => h.t >= t0 - 1800e3 && h.t <= t1 + 1800e3);
      if (!hrs.length) { box.innerHTML = `<h2>Refraction tonight</h2><p class="dim">The forecast doesn't cover tonight yet.</p>`; return; }
      const kc = S.hwy.map(h => h[5]).filter(v => v !== null), km = k => kc.filter(v => v <= k).length * 0.06;
      const peak = hrs.reduce((a, h) => h.k > a.k ? h : a), base = km(0.13), [, ptxt] = kClass(peak.k);
      const X = t => (t - hrs[0].t) / (hrs[hrs.length - 1].t - hrs[0].t + 3600e3) * 100, w = 100 / (hrs.length);
      const bars = hrs.map(h => { const [, , col] = kClass(h.k); return `<i title="${tfmt(new Date(h.t))}: k = ${fmt(h.k, 2)}" style="left:${X(h.t)}%;width:${w + 0.2}%;background:${col}"></i>`; }).join("");
      const labels = hrs.filter((h, i) => i % 3 === 0).map(h => `<span style="position:absolute;left:${X(h.t)}%">${new Intl.DateTimeFormat("en-US", {timeZone: TZ, hour: "numeric"}).format(new Date(h.t))}</span>`).join("");
      const calm = hrs.filter(h => h.w < 10 && h.c < 30).length;
      box.innerHTML = `<h2>Refraction tonight</h2>
        <p><b>${ptxt}</b> at its peak, around ${tfmt(new Date(peak.t))}: the air at 80 m is forecast ${fmt(Math.abs(peak.dT), 1)} °C ${peak.dT >= 0 ? "warmer" : "cooler"} than at head height, giving a refraction coefficient of about <b>k = ${fmt(peak.k, 2)}</b> (normal is 0.13).</p>
        <div class="bar" role="img" aria-label="Forecast refraction by hour tonight">${bars}</div>
        <div style="position:relative;height:16px;font:12px var(--f-mono);color:var(--muted)">${labels}</div>
        <p class="small dim"><span style="color:${RC[0]}">■</span> normal (k &lt; 0.13) &nbsp;<span style="color:${RC[1]}">■</span> mild &nbsp;<span style="color:${RC[2]}">■</span> strong (k 0.5–1) &nbsp;<span style="color:${RC[3]}">■</span> very strong (k &gt; 1)</p>
        <p class="small">US-67 in view from the platform: <b>${fmt(base, 1)} km</b> at normal refraction${peak.k > 0.13 ? `, about <b>${fmt(km(peak.k), 1)} km</b> at tonight's peak` : ""}. Stronger refraction lifts distant lights a little, brings short extra stretches of road into view, and on the strongest nights makes far lights shimmer, stretch or split, as mirages do.</p>
        <p class="small dim">${calm >= 3 ? "Clear, calm hours are forecast: the best conditions for a ground inversion. " : "Wind or cloud will mix the air near the ground, which weakens inversions. "}A forecast model smooths out the thin, cold layer that forms over the flat on calm nights, so the real inversion is often stronger than shown. Temperatures: Open-Meteo.com model forecast (CC BY 4.0), updated ${new Date(F.at).toLocaleString()}. Formula: Hirt et al. (2010).</p>`;
    };
    if (cache) render(cache);
    try {
      const u = "https://api.open-meteo.com/v1/forecast?latitude=30.2751&longitude=-103.8828&hourly=temperature_2m,temperature_80m,surface_pressure,wind_speed_10m,cloud_cover&wind_speed_unit=kmh&forecast_days=3&timeformat=unixtime&timezone=GMT";
      const j = await fetch(u).then(okJson), H = j.hourly;
      if (!H || !H.temperature_80m) throw new Error("no 80 m temperatures");
      const F = {at: Date.now(), time: H.time, t2: H.temperature_2m, t80: H.temperature_80m, p: H.surface_pressure.map(v => v || 850), w: H.wind_speed_10m, c: H.cloud_cover};
      const ok = F.time.map((_, i) => F.t2[i] !== null && F.t80[i] !== null);
      ["time", "t2", "t80", "p", "w", "c"].forEach(k => { F[k] = F[k].filter((_, i) => ok[i]); });
      store.set("mlfg-refr", F); render(F);
    } catch (e) { if (!cache) box.innerHTML = `<h2>Refraction tonight</h2><p class="dim">No forecast right now. Clear, calm nights after a warm day give the strongest inversions.</p>`; }
  }

  // ================================================================ IDENTIFY
  let refMag = true, heightSel = "", exactM = null, lastCands = [];
  const idB = $("i-b");
  const trueB = () => { const b = parseFloat(idB.value); return isNaN(b) || b < 0 || b > 360 ? null : norm(refMag ? b + DECL : b); };
  $("i-mag").onclick = () => setRef(true); $("i-true").onclick = () => setRef(false);
  function setRef(m) { const b = trueB(); refMag = m; $("i-mag").setAttribute("aria-pressed", m); $("i-true").setAttribute("aria-pressed", !m); if (b !== null) idB.value = fmt(norm(m ? b - DECL : b), 1); identify(); }
  idB.addEventListener("input", () => { exactM = null; identify(); });
  document.querySelectorAll("#i-h-seg button").forEach(b => b.onclick = () => { heightSel = b.dataset.h; exactM = null;
    document.querySelectorAll("#i-h-seg button").forEach(x => x.setAttribute("aria-pressed", x === b)); identify(); });

  // phone compass (magnetic)
  let compassOn = false, head = null, shown = null, queued = false;
  function onOrient(e) { let h = null; if (typeof e.webkitCompassHeading === "number") h = e.webkitCompassHeading; else if (e.absolute && e.alpha !== null) h = norm(360 - e.alpha);
    if (h === null) return; head = head === null ? h : norm(head + 0.25 * angDiff(h, head));
    if (queued || (shown !== null && Math.abs(angDiff(head, shown)) < 0.1)) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; shown = head; const bt = norm(head + DECL); idB.value = fmt(refMag ? norm(bt - DECL) : bt, 1); exactM = null; identify(); }); }
  $("i-compass").onclick = async () => {
    if (compassOn) { window.removeEventListener("deviceorientationabsolute", onOrient); window.removeEventListener("deviceorientation", onOrient); compassOn = false; $("i-compass").textContent = "Use phone compass"; return; }
    try { if (typeof DeviceOrientationEvent !== "undefined" && typeof DeviceOrientationEvent.requestPermission === "function") { if (await DeviceOrientationEvent.requestPermission() !== "granted") throw 0; }
      window.addEventListener("deviceorientationabsolute", onOrient); window.addEventListener("deviceorientation", onOrient); compassOn = true; head = null; shown = null;
      $("i-compass").textContent = "Hold reading"; $("i-cnote").textContent = "Hold the phone flat and point its top edge at the light. Phone compasses are often 5–10° off; the camera sky finder is more accurate.";
      setTimeout(() => { if (compassOn && head === null) $("i-cnote").textContent = "No compass readings yet. This device may not have a compass: type the bearing instead."; }, 2500);
    } catch (err) { $("i-cnote").textContent = "Compass not available. Type the bearing instead."; }
  };

  // noise model helpers
  // rate and fixed-light look-ups come from ../assets/mask.js (MK), built when the data loads
  function skyAt(az) { if (!S) return null; const s = S.sky; if (az < s[0][0] || az > s[s.length - 1][0]) return null; const i = Math.min(s.length - 2, Math.max(0, Math.floor((az - s[0][0]) / 0.1))); const f = (az - s[i][0]) / 0.1; return s[i][1] + f * (s[i + 1][1] - s[i][1]); }
  const RATE_TXT = ["about one every 10–100 hours", "0.1–1 an hour", "1–10 an hour", "10 or more an hour"];
  const HOW = {
    car: "A single white point (a car's two headlamps merge at this distance) that drifts slowly along the road. It brightens when the road turns toward you and blinks out behind rises. Two cars meeting can look like one light splitting in two.",
    tail: "Cars heading away show only dim red tail lights.",
    rail: "One very bright white headlight, often with two smaller flashing ditch lights. Slow, steady movement along the track; you may hear it.",
    tower: "Red light, steady or blinking in a regular rhythm, that never moves. Use it as a reference point.",
    town: "A diffuse glow over the skyline rather than a point of light.",
    aero: "Tethered radar balloon to the west-northwest. Its lights can hang well above the skyline and barely move.",
    planet: "Steady, bright, slowly sinking. Near the horizon it twinkles hard and can flash colours.",
    star: "Twinkles and may flash colours near the horizon. It keeps its place among the other stars.",
    plane: "Blinking red, green or white lights crossing the sky, often with a steady white landing light."};

  function candidates(b, tol) {
    const out = [], within = a => Math.abs(angDiff(a, b)) <= tol;
    if (!S) return out;
    const h67 = S.hwy.filter(p => (p[6] === "v" || p[6] === "m") && within(p[2]));
    if (h67.length) out.push({k: "car", col: "var(--road)", t: "Cars on US-67", d: Math.min(...h67.map(p => p[3])), sub: brightTxt(h67.map(p => ({d: p[3], h: p[10], mL: p[11], mH: p[14], dir: p[9]}))), m: [Math.min(...h67.map(p => p[7])), Math.max(...h67.map(p => p[7]))]});
    S.roads.forEach(r => { const v = r.p.filter(q => q[6] === "v" && within(q[2])); if (v.length) out.push({k: "car", col: "var(--road2)", t: `Cars on ${r.n.replace(" (Pinto Canyon Rd)", " (Pinto Canyon Road)")}`, d: Math.min(...v.map(q => q[3])),
      sub: brightTxt(v.map(q => ({d: q[3], h: q[8], mL: q[9], mH: q[12], dir: q[7]}))), m: [Math.min(...v.map(q => q[4])), Math.max(...v.map(q => q[4]))]}); });
    const rl = S.railpano.filter(r => r[4] <= 0.13 && within(r[1]));
    [...new Set(rl.map(r => r[0]))].forEach(o => { const v = rl.filter(r => r[0] === o); out.push({k: "rail", col: "var(--rail)", t: o === "UP" ? "Union Pacific trains" : "Texas Pacifico trains (rare at night)", d: Math.min(...v.map(r => r[2])), m: [Math.min(...v.map(r => r[3])), Math.max(...v.map(r => r[3]))]}); });
    S.towers.forEach(t => { if (t.light !== "none" && t.kc !== null && t.kc <= 1 && within(t.az)) out.push({k: "tower", col: "var(--tower)", t: `Tower light, ${fmt(t.h)} m tower`, d: t.d, sub: `At ${fmt(t.az, 1)}° true (${fmt(norm(t.az - DECL), 1)}° compass).`, m: [t.a, t.a]}); });
    S.towns.forEach(t => { if (Math.abs(angDiff(t.az, b)) <= tol + 1) out.push({k: "town", col: "var(--muted)", t: `${t.n.replace(", Chihuahua", "")} ${t.kc <= 1 ? "lights" : "skyglow"}`, d: t.d, sky: t.kc > 1}); });
    S.fields.forEach(f => { if (f.k === "balloon" && within(f.az)) out.push({k: "aero", col: "var(--tower)", t: "Tethered radar balloon (aerostat)", d: f.d, sky: true}); });
    // sky objects right now, low in that direction
    if (A) { const now = new Date();
      ["Venus", "Jupiter", "Mars", "Saturn", "Mercury", "Moon"].forEach(p => { const x = altaz(p, now); if (x.alt > -1 && x.alt < 25 && within(x.az)) out.push({k: "planet", col: "var(--accent)", t: p === "Moon" ? "The Moon" : `${p} (planet)`, d: Infinity, sky: true, sub: `Right now at ${fmt(x.az)}° true, ${fmt(x.alt, 1)}° up.`}); }); }
    out.push({k: "plane", col: "var(--muted)", t: "Aircraft", d: Infinity, sky: true, generic: true});
    return out;
  }
  function brightTxt(pts) {
    const f = pts.filter(p => p.mH !== null && p.mH !== undefined); if (!f.length) return "";
    const b = f.reduce((a, p) => p.mH < a.mH ? p : a);
    const cmp = m => m <= -1 ? "as bright as the brightest stars" : m <= 1.5 ? "like a bright star" : m <= 4 ? "like an ordinary star" : "faint";
    return `A car heading ${b.dir === 0 ? "toward Marfa" : "away from Marfa"} can look ${cmp(b.mH)} on high beam here.`;
  }

  function identify() {
    const b = trueB();
    const V = $("i-verdict"), C = $("i-cands");
    const raw = parseFloat(idB.value);
    if (!isNaN(raw) && (raw < 0 || raw > 360)) { V.className = "verdict"; V.innerHTML = `<b class="big-t">Check the bearing</b><span class="dim">Bearings run from 0 to 360°.</span>`; C.innerHTML = ""; drawPano(); return; }
    if (b === null || !S) { V.className = "verdict"; V.innerHTML = `<b class="big-t">Point me at a light</b><span class="dim">Enter a bearing, use the phone compass, or tap the strip.</span>`; C.innerHTML = ""; drawPano(); return; }
    const tol = 2, sk = skyAt(b);
    const above = heightSel === "above" || (exactM !== null && sk !== null && exactM > sk + 1.75);
    const below = heightSel === "below" || heightSel === "on" || (exactM !== null && sk !== null && exactM <= sk + 1.75);
    let cands = candidates(b, tol);
    if (above) cands = cands.filter(c => c.sky || c.k === "tower" && c.m && sk !== null && c.m[1] > sk);
    else if (below) cands = cands.filter(c => !c.sky || c.k === "town");
    if (exactM !== null) cands = cands.filter(c => !c.m || (exactM >= c.m[0] - 1.5 && exactM <= c.m[1] + 1.5));
    // rate
    const DOM = (ZR && ZR.standard.params.az_domain_deg) || [150, 300], outside = b < DOM[0] || b > DOM[1];
    let rl = null, fx = null;
    if (!above && !outside && MK) {
      if (exactM !== null) { rl = MK.rate(b, exactM); fx = MK.fixed(b, exactM); }
      else { const w = MK.window(b, tol); rl = w.rate; fx = w.fixed; }
    }
    const lbl = `${fmt(b, 1)}° true · ${fmt(norm(b - DECL), 1)}° compass`;
    if (above) { V.className = "verdict"; V.innerHTML = `<b class="big-t">Above the skyline</b><span>Usually a plane, satellite, star or planet, or the radar balloon to the west-northwest. Ground lights can't appear here.</span><span class="small dim">${lbl}</span>`; }
    else if (outside) { V.className = "verdict"; V.innerHTML = `<b class="big-t">Outside the mapped view</b><span>This guide works out traffic only toward the Chinati Mountains, from ${fmt(refMag ? norm(DOM[0] - DECL) : DOM[0])}° to ${fmt(refMag ? norm(DOM[1] - DECL) : DOM[1])}° ${refMag ? "on a compass" : "true"} (south to west-northwest). In this direction it can't tell you whether a light is unusual. US-90, the railway and the towns of Alpine and Fort Davis lie to the north and east.</span><span class="small dim">${lbl}</span>`; }
    else if (rl !== null && rl >= 1) { V.className = "verdict busy"; V.innerHTML = `<b class="big-t">Busy spot</b><span>Ordinary lights pass here ${RATE_TXT[rl]} on a clear night. Check the list below first.</span><span class="small dim">${lbl}</span>`; }
    else if (rl === 0) { V.className = "verdict"; V.innerHTML = `<b class="big-t">Occasional traffic</b><span>Ordinary lights pass here ${RATE_TXT[0]}. It could still be one of those, so watch how it moves.</span><span class="small dim">${lbl}</span>`; }
    else if (rl === -1 && fx) { V.className = "verdict"; V.innerHTML = `<b class="big-t">Fixed light here</b><span>Few moving lights are expected, but a tower light, town glow or the radar balloon sits in this direction. Check the list below: a fixed light stays put.</span><span class="small dim">${lbl}</span>`; }
    else if (rl === -1) { V.className = "verdict quiet"; V.innerHTML = `<b class="big-t">Quiet spot</b><span>Fewer than one known ordinary light per 100 hours here. If you see something, note the time and log it.</span><span class="small dim">${lbl}</span>`; }
    else { V.className = "verdict"; V.innerHTML = `<span class="small dim">${lbl}</span>`; }
    lastCands = cands;
    C.innerHTML = cands.map(c => `<li><span class="dot" style="background:${c.col}"></span><b>${c.t}</b><span class="d">${isFinite(c.d) ? fmt(c.d) + " km" : ""}</span><span class="how">${c.sub ? c.sub + " " : ""}${HOW[c.k] || ""}</span></li>`).join("");
    drawPano();
  }

  // mini panorama
  const cv = $("i-pano"), cx = cv.getContext("2d");
  let PV = {a0: 205, a1: 295, e0: -10, e1: 6};
  function drawPano() {
    if (!S || $("v-identify").hidden) return;
    const W = cv.clientWidth, H = cv.clientHeight, dpr = Math.min(2, devicePixelRatio || 1);
    cv.width = W * dpr; cv.height = H * dpr; cx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const b = trueB(); const span = 30;
    if (b !== null) { PV.a0 = b - span / 2; PV.a1 = b + span / 2; } else { PV.a0 = 205; PV.a1 = 295; }
    const sky = S.sky.filter(s => s[0] >= PV.a0 - 0.1 && s[0] <= PV.a1 + 0.1);
    if (!sky.length) { cx.clearRect(0, 0, W, H); cx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--ink-2"); cx.font = "15px system-ui, sans-serif"; cx.textAlign = "center";
      cx.fillText("No skyline drawing in this direction", W / 2, H / 2); $("i-panonote").textContent = ""; return; }
    const vals = sky.map(s => s[1]).concat(S.hwy.filter(p => p[2] >= PV.a0 && p[2] <= PV.a1 && p[6] !== "h").map(p => p[7]));
    PV.e0 = Math.min(...sky.map(s => s[3]), ...vals) - 1; PV.e1 = Math.max(...vals) + 2.5;
    const X = a => (a - PV.a0) / (PV.a1 - PV.a0) * W, Y = m => (PV.e1 - m) / (PV.e1 - PV.e0) * H;
    const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    cx.fillStyle = css("--sky"); cx.fillRect(0, 0, W, H);
    // rate zone
    if (ZR) [css("--r1"), css("--r2"), css("--r3"), css("--r4")].forEach((c, i) => [ZR.standard, ZR.inversion].forEach(Z => Z.rate_polys[String(Z.levels[i])].forEach(r => {
      if (!r.some(q => q[0] >= PV.a0 - 2 && q[0] <= PV.a1 + 2)) return; cx.beginPath(); r.forEach((q, j) => j ? cx.lineTo(X(q[0]), Y(q[1])) : cx.moveTo(X(q[0]), Y(q[1]))); cx.closePath(); cx.globalAlpha = .55; cx.fillStyle = c; cx.fill("evenodd"); cx.globalAlpha = 1; })));
    // terrain layers
    [[1, .45], [5, .6], [4, .78], [3, .95]].forEach(([col, op]) => { cx.beginPath(); cx.moveTo(0, H); sky.forEach(s => cx.lineTo(X(s[0]), Y(s[col]))); cx.lineTo(W, H); cx.closePath(); cx.globalAlpha = op; cx.fillStyle = css("--land"); cx.fill(); cx.globalAlpha = 1; });
    cx.beginPath(); sky.forEach((s, i) => i ? cx.lineTo(X(s[0]), Y(s[1])) : cx.moveTo(X(s[0]), Y(s[1]))); cx.strokeStyle = css("--ink-2"); cx.lineWidth = 1.3; cx.stroke();
    const dot = (a, m, r, c) => { if (a < PV.a0 || a > PV.a1) return; cx.beginPath(); cx.arc(X(a), Y(m), r, 0, 7); cx.fillStyle = c; cx.fill(); };
    S.hwy.forEach(p => { if (p[6] === "v") dot(p[2], p[7], 2, css("--road")); });
    S.roads.forEach(r => r.p.forEach(q => { if (q[6] === "v") dot(q[2], q[4], 1.8, css("--road2")); }));
    S.railpano.forEach(r => { if (r[4] <= 0.13) dot(r[1], r[3], 1.6, css("--rail")); });
    S.towers.forEach(t => { if (t.light !== "none" && t.a !== null && t.kc !== null && t.kc <= 0.13 && t.az >= PV.a0 && t.az <= PV.a1) { const x = X(t.az), y = Y(t.a); cx.beginPath(); cx.moveTo(x, y - 5); cx.lineTo(x + 5, y); cx.lineTo(x, y + 5); cx.lineTo(x - 5, y); cx.closePath(); cx.fillStyle = css("--tower"); cx.fill(); } });
    // ticks
    cx.fillStyle = css("--ink-2"); cx.font = "600 11px 'JetBrains Mono', monospace"; cx.textAlign = "center";
    const tick = (PV.a1 - PV.a0) > 40 ? 10 : 5;
    const t0a = refMag ? DECL : 0;  // label round numbers in the chosen reference
    for (let a = Math.ceil((PV.a0 - t0a) / tick) * tick + t0a; a <= PV.a1; a += tick) { cx.fillRect(X(a), 0, 1, 5); cx.fillText(`${fmt(norm(a - t0a))}°`, X(a), 16); }
    if (b !== null) { cx.fillStyle = css("--accent"); cx.fillRect(X(b) - 1, 0, 2, H); if (exactM !== null) { cx.beginPath(); cx.arc(X(b), Y(exactM), 6, 0, 7); cx.strokeStyle = css("--accent"); cx.lineWidth = 2; cx.stroke(); } }
    $("i-panonote").textContent = `Height is stretched to show detail. Blue shading marks where ordinary lights are expected (darker = busier). ${refMag ? "Compass" : "True"} bearings.`;
  }
  cv.addEventListener("click", e => {
    const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    const a = PV.a0 + x / r.width * (PV.a1 - PV.a0), m = PV.e1 - y / r.height * (PV.e1 - PV.e0);
    idB.value = fmt(refMag ? norm(a - DECL) : norm(a), 1); exactM = m;
    document.querySelectorAll("#i-h-seg button").forEach(x2 => x2.setAttribute("aria-pressed", "false")); heightSel = "";
    identify();
  });
  window.addEventListener("resize", drawPano);

  $("i-log").onclick = () => {
    const b = trueB(); if (b === null) { toast("Enter a bearing first."); return; }
    if (!S) { toast("The map data hasn't loaded, so this light can't be checked. Use Quick log instead."); return; }
    const sk = skyAt(b), el = exactM !== null ? +mrad2deg(exactM).toFixed(3) : "";
    const LOG = store.get("mlfg-log", []);
    LOG.push({time: new Date().toISOString(), true_bearing: +b.toFixed(2), magnetic_bearing: +norm(b - DECL).toFixed(2), elev_deg: el, window_deg: 2, refraction_k: 0.13,
      us67_in_view: lastCands.some(c => c.t === "Cars on US-67"), top_candidate: lastCands[0] ? lastCands[0].t : "none", top: lastCands[0] ? lastCands[0].t : "none",
      source: "app", vs_skyline: heightSel || (exactM !== null && sk !== null ? (exactM > sk + 1.75 ? "above" : "below") : ""), note: ""});
    store.set("mlfg-log", LOG); toast("Saved to your log."); show("log");
  };

  // ================================================================ LOG
  function renderLog() {
    const LOG = store.get("mlfg-log", []);
    const CT = new Intl.DateTimeFormat("en-US", {timeZone: TZ, month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit"});
    const esc = v => String(v).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
    $("l-list").innerHTML = LOG.length ? LOG.map((s, i) => ({s, i})).reverse().map(({s, i}) => `<li><span class="t">${CT.format(new Date(s.time))} CT</span>
      <span class="src">${s.source === "camera" ? "Camera sky finder" : s.source === "app" ? "Identifier" : s.source === "quick" ? "Quick log" : "Map"}</span>
      <div>${s.true_bearing !== "" && s.true_bearing !== undefined ? `<b>${fmt(s.true_bearing, 1)}° true</b> (${fmt(s.magnetic_bearing, 1)}° compass)` : "<b>No bearing</b>"}${s.elev_deg !== "" && s.elev_deg !== undefined ? ` · ${fmt(s.elev_deg, 2)}° up` : ""}</div>
      ${s.top && s.top !== "none" ? `<div class="dim small">Best-matching catalogued source: ${esc(s.top)}</div>` : ""}${s.note ? `<div>${esc(s.note)}</div>` : ""}
      <div class="acts"><a class="pill" href="../report.html?log=${i}">Make a report</a><button type="button" class="pill" data-del="${i}">Delete</button></div></li>`).join("")
      : `<li class="dim">Nothing yet. Use Quick log, or <b>Log this light</b> in Identify, or <b>Record</b> in the camera sky finder.</li>`;
    $("l-list").querySelectorAll("[data-del]").forEach(b => b.onclick = () => sheet("Delete this entry?", "<p class='dim'>This can't be undone.</p>", [["Delete", () => { const L = store.get("mlfg-log", []); L.splice(+b.dataset.del, 1); store.set("mlfg-log", L); renderLog(); }]]));
  }
  $("l-save").onclick = () => {
    const note = $("l-note").value.trim(), b = parseFloat($("l-b").value);
    if (!note && isNaN(b)) { toast("Add a note or a bearing."); return; }
    const LOG = store.get("mlfg-log", []);
    LOG.push({time: new Date().toISOString(), true_bearing: isNaN(b) ? "" : +norm(b + DECL).toFixed(2), magnetic_bearing: isNaN(b) ? "" : +norm(b).toFixed(2), elev_deg: "", window_deg: 5,
      refraction_k: 0.13, us67_in_view: "", top_candidate: "", top: "", source: "quick", note});
    store.set("mlfg-log", LOG); $("l-note").value = ""; $("l-b").value = ""; renderLog(); toast("Saved.");
  };
  const csv = () => { const L = store.get("mlfg-log", []), cols = ["time", "true_bearing", "magnetic_bearing", "elev_deg", "source", "top", "note"];
    return [cols.join(",")].concat(L.map(s => cols.map(c => `"${String(s[c] ?? "").replace(/"/g, '""')}"`).join(","))).join("\n"); };
  $("l-csv").onclick = () => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv()], {type: "text/csv"})); a.download = `marfa-sightings-${new Date().toISOString().slice(0, 10)}.csv`; document.body.appendChild(a); a.click(); a.remove(); };
  $("l-share").onclick = async () => { const text = csv(); try { if (navigator.share) await navigator.share({title: "My Marfa Lights log", text}); else { await navigator.clipboard.writeText(text); toast("Copied to the clipboard."); } } catch (e) {} };

  // ================================================================ BINGO
  const ICON = {
    pair: '<svg viewBox="0 0 44 44"><path d="M2 32 Q12 26 22 30 T42 28" fill="none" stroke="currentColor" stroke-opacity=".4" stroke-width="2"/><circle cx="17" cy="28" r="3.2" fill="#fff5d6"/><circle cx="24" cy="28" r="3.2" fill="#fff5d6"/></svg>',
    flare: '<svg viewBox="0 0 44 44"><path d="M2 34 L42 30" stroke="currentColor" stroke-opacity=".4" stroke-width="2"/><g stroke="#fff5d6" stroke-width="2"><path d="M22 18v18M13 27h18M16 21l12 12M28 21 16 33"/></g><circle cx="22" cy="27" r="4" fill="#fff"/></svg>',
    tail: '<svg viewBox="0 0 44 44"><path d="M2 32 L42 30" stroke="currentColor" stroke-opacity=".4" stroke-width="2"/><circle cx="18" cy="29" r="2.4" fill="#ff4a2c"/><circle cx="25" cy="29" r="2.4" fill="#ff4a2c"/></svg>',
    train: '<svg viewBox="0 0 44 44"><path d="M2 34 L42 34" stroke="currentColor" stroke-opacity=".5" stroke-width="2" stroke-dasharray="3 2"/><circle cx="22" cy="24" r="4.5" fill="#fff"/><circle cx="15" cy="30" r="2" fill="#fff5d6"/><circle cx="29" cy="30" r="2" fill="#fff5d6"/></svg>',
    tower: '<svg viewBox="0 0 44 44"><path d="M22 10 L16 38 M22 10 L28 38 M18 28h8 M19 20h6" stroke="currentColor" stroke-opacity=".6" stroke-width="1.6" fill="none"/><circle cx="22" cy="9" r="3.5" fill="#ff4a2c"/></svg>',
    plane: '<svg viewBox="0 0 44 44"><path d="M8 26 L36 14" stroke="currentColor" stroke-opacity=".35" stroke-dasharray="2 3" stroke-width="2"/><circle cx="30" cy="16.5" r="2.6" fill="#fff"/><circle cx="26" cy="18.5" r="2" fill="#ff4a2c"/><circle cx="34" cy="15" r="2" fill="#45c07a"/></svg>',
    sat: '<svg viewBox="0 0 44 44"><path d="M6 32 L36 10" stroke="currentColor" stroke-opacity=".35" stroke-dasharray="1 4" stroke-width="2"/><circle cx="30" cy="14.5" r="2.4" fill="#fff"/></svg>',
    planet: '<svg viewBox="0 0 44 44"><path d="M2 34 L10 28 L17 31 L26 25 L34 30 L42 27 V44 H2Z" fill="currentColor" fill-opacity=".35"/><circle cx="24" cy="18" r="4" fill="#ffe7a8"/><path d="M24 10v3M24 23v3M16 18h3M29 18h3" stroke="#ffe7a8" stroke-width="1.5"/></svg>',
    ranch: '<svg viewBox="0 0 44 44"><path d="M10 34 V26 L17 21 L24 26 V34Z" fill="currentColor" fill-opacity=".45"/><circle cx="31" cy="25" r="3" fill="#ffd9a0"/><path d="M31 28v6" stroke="currentColor" stroke-opacity=".5"/></svg>'};
  const BINGO = [
    ["pair", "Car pair", "Two headlights close together, moving steadily along US-67 at about 229°–238° true (223°–232° on a compass), just below the mountains. Pairs often split and merge as cars pass each other.",
      [["../img/zw_bingo_carpair-600.webp", "Two cars on US-67, 26 and 27 km away, photographed from the platform at dusk through a 210 mm lens. By eye they are tiny steady points."],
       ["../img/zw_bingo_streak-600.webp", "In a 45-second exposure a car draws the road as it drives."]]],
    ["flare", "Car on a bend", "A light that suddenly brightens, sometimes brighter than any star, then fades. A car on a bend briefly points straight at you. US-67 at about 233° true and RM 2810 at about 255° true do this."],
    ["tail", "Red tail lights", "Dim red points drifting slowly along a road. These are cars driving away from you."],
    ["train", "Train", "A single brilliant white headlight, often with two small flashing ditch lights beside it. Union Pacific trains pass right by the Viewing Area; the Presidio line to the south sees very few."],
    ["tower", "Tower blink", "Red lights that blink or stay steady and never move. Lit towers are in view at about 230°, 256°, 259°, 280° and 284° true."],
    ["plane", "Aircraft", "Blinking red, green and white lights moving across the sky, often with a bright landing light. It moves too fast and too high to be on the ground."],
    ["sat", "Satellite", "A steady point gliding silently across the stars for a few minutes, then fading as it enters Earth's shadow. Best in the first hours after dark."],
    ["planet", "Setting planet", "A bright, steady light low in the west that slowly sinks behind the mountains. Near the horizon it twinkles hard and flashes colours. Tonight's planets are on the Tonight screen."],
    ["ranch", "Ranch light", "A steady yellowish light low on the flat that stays put all night. It is usually a yard or building light on one of the ranches."]];
  const nightKey = () => { const d = nightStart(new Date()); return "mlfg-bingo-" + d.toISOString().slice(0, 10); };
  function renderBingo() {
    const done = store.get(nightKey(), []);
    $("b-grid").innerHTML = BINGO.map(([k, t]) => `<button type="button" data-k="${k}" class="${done.includes(k) ? "done" : ""}" aria-pressed="${done.includes(k)}">${ICON[k]}<span>${t}</span></button>`).join("");
    $("b-grid").querySelectorAll("button").forEach(b => b.onclick = () => {
      const [k, t, how, photos] = BINGO.find(x => x[0] === b.dataset.k); const has = store.get(nightKey(), []).includes(k);
      const ph = (photos || []).map(([src, cap]) => `<figure class="bphoto"><img src="${src}" alt="${cap}" width="600" height="400" loading="lazy"><figcaption>${cap} Photo: Zach Warren.</figcaption></figure>`).join("");
      sheet(t, `<div style="color:var(--ink-2)">${ICON[k].replace("<svg", '<svg style="width:72px;height:72px;float:right;margin-left:10px"')}</div><p>${how}</p>${ph}`,
        [[has ? "Untick" : "I've seen one", () => { const d = store.get(nightKey(), []); const i = d.indexOf(k); if (i >= 0) d.splice(i, 1); else d.push(k); store.set(nightKey(), d); renderBingo(); if (!has) toast(`${t}: spotted!`); }]]);
    });
    const n = done.length;
    $("b-score").textContent = n === 9 ? "Full house! You can tell every ordinary light on the flat." : n >= 5 ? `${n} of 9. You're getting good at this.` : `${n} of 9 spotted tonight`;
  }
  $("b-reset").onclick = () => { store.set(nightKey(), []); renderBingo(); };

  // ================================================================ install / offline
  let deferred = null;
  window.addEventListener("beforeinstallprompt", e => { e.preventDefault(); deferred = e; $("installBtn").hidden = false; });
  $("installBtn").onclick = async () => { if (!deferred) return; deferred.prompt(); await deferred.userChoice; deferred = null; $("installBtn").hidden = true; };
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  $("m-install").innerHTML = ios ? "On iPhone: open this page in Safari, tap the <b>Share</b> button, then <b>Add to Home Screen</b>." :
    "On Android: tap <b>Install</b> at the top, or open the browser menu and choose <b>Install app</b> / <b>Add to Home screen</b>.";
  if ("serviceWorker" in navigator) {
    const hadController = !!navigator.serviceWorker.controller;
    navigator.serviceWorker.addEventListener("controllerchange", () => { if (hadController) toast("A new version is ready. Close and reopen the app to use it.", 6000); });
    navigator.serviceWorker.register("../sw.js", {scope: "../"}).then(() => navigator.serviceWorker.ready).then(() => {
      $("m-offline").textContent = "Ready: this app and the website are saved on your phone for offline use.";
    }).catch(() => { $("m-offline").textContent = "Offline mode isn't available in this browser."; });
  } else $("m-offline").textContent = "Offline mode isn't available in this browser.";

  // ================================================================ start
  started = true;
  show(location.hash.slice(1) || "tonight");
  try { computeTonight(); } catch (e) { $("t-sum").textContent = "Couldn't work out tonight's sky."; console.error(e); }
  weather(); refraction(); renderBingo();
  ready.then(() => { identify(); });
  window.MLAPP = {computeTonight, identify, candidates, show, get tonight() { return TONIGHT; }};
})();

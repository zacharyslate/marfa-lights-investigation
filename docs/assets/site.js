/* Marfa Lights Field Guide — shared header (four grouped menus), footer site map and theme switch. */
(function () {
  // the whole site in four groups; the same list drives the header menus, the phone menu and the footer
  const GROUPS = [
    {id: "visit", t: "Visit", items: [
      ["visit.html", "Plan a night", "When to go, what to bring, how to observe"],
      ["report.html", "Report a sighting", "Check a light against every known source"],
      ["app/", "Pocket app", "Tonight, identify, log. Works offline"]]},
    {id: "tools", t: "Tools", items: [
      ["map.html", "Map and identifier", "What lies along a bearing"],
      ["sky.html", "Sky finder", "Your phone camera as a calibrated pointer"],
      ["photo.html", "Photo checker", "Line up a photo and check each light"],
      ["terrain.html", "3D terrain", "Fly over the land to the Chinatis"]]},
    {id: "learn", t: "Learn", items: [
      ["history.html", "History and folklore", "From campfire tales to cameras"],
      ["sightings.html", "Sightings catalogue", "Every documented sighting and photo, sourced"],
      ["place.html", "The place", "Geology, grassland, dark skies, the border"],
      ["community.html", "Community and dark skies", "Why this project exists, how to take part"]]},
    {id: "science", t: "Science", items: [
      ["science.html", "The science", "What the studies and our model show"],
      ["paper.html", "The paper", "The full study, data and citation"],
      ["sightlines.html", "Sight-line report", "The detailed terrain analysis"]]},
  ];
  const THEMES = ["auto", "light", "dark", "night"];
  const LABEL = {auto: "Auto", light: "Light", dark: "Dark", night: "Night vision"};
  const root = document.documentElement;
  function apply(t) {
    if (t === "auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", t);
    const b = document.getElementById("themeBtn"); if (b) b.lastChild.textContent = LABEL[t];
  }
  let theme = "auto";
  try { theme = localStorage.getItem("mlfg-theme") || "auto"; } catch (e) {}
  apply(theme);

  const here = location.pathname.split("/").pop() || "index.html";
  const isHere = h => h === here;
  const curGroup = GROUPS.find(g => g.items.some(([h]) => isHere(h)));
  const caret = `<svg class="caret" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M1.5 3.5 5 7l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>`;
  const item = ([h, t, d]) => `<a href="${h}"${isHere(h) ? ' aria-current="page"' : ""}><b>${t}</b><span>${d}</span></a>`;
  const bar = document.getElementById("bar");
  if (bar) {
    bar.className = "bar";
    bar.innerHTML = `<div class="bar-in">
      <a class="brand" href="index.html" aria-label="Marfa Lights Field Guide home">
        <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><circle cx="11" cy="11" r="4" fill="var(--accent)"/><circle cx="11" cy="11" r="8.5" fill="none" stroke="var(--accent)" stroke-width="1.2" opacity=".5"/><line x1="0" y1="17.5" x2="22" y2="17.5" stroke="var(--ink)" stroke-width="1.4"/></svg>
        <span>Marfa Lights<span class="bx"> Field Guide</span></span></a>
      <nav class="nav" aria-label="Site">${GROUPS.map(g => `<div class="ng${curGroup === g ? " cur" : ""}">
        <button type="button" class="ng-b" aria-expanded="false" aria-controls="ng-${g.id}">${g.t}${caret}</button>
        <div class="ng-p" id="ng-${g.id}" hidden>${g.items.map(item).join("")}</div></div>`).join("")}</nav>
      <a class="app-btn" href="app/">App</a>
      <button class="menu-btn" type="button" aria-expanded="false" aria-controls="msheet">Menu</button>
      <button class="theme-btn" id="themeBtn" type="button" title="Switch theme. Night vision keeps your eyes dark-adapted."><span class="dot"></span><span>${LABEL[theme]}</span></button>
    </div>
    <div class="msheet" id="msheet" hidden>${GROUPS.map(g => `<div class="mg"><div class="mg-t">${g.t}</div>${g.items.map(item).join("")}</div>`).join("")}</div>`;
    document.getElementById("themeBtn").addEventListener("click", () => {
      theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
      try { localStorage.setItem("mlfg-theme", theme); } catch (e) {}
      apply(theme);
      document.dispatchEvent(new CustomEvent("themechange"));
    });
    // desktop menus: one open at a time; click outside or Escape closes
    const btns = [...bar.querySelectorAll(".ng-b")];
    const close = except => btns.forEach(b => { if (b !== except) { b.setAttribute("aria-expanded", "false"); document.getElementById(b.getAttribute("aria-controls")).hidden = true; } });
    btns.forEach(b => b.addEventListener("click", e => {
      e.stopPropagation(); const open = b.getAttribute("aria-expanded") !== "true"; close(b);
      b.setAttribute("aria-expanded", String(open)); document.getElementById(b.getAttribute("aria-controls")).hidden = !open;
      if (open) document.getElementById(b.getAttribute("aria-controls")).querySelector("a").focus({preventScroll: true});
    }));
    // phone menu: one sheet with every group
    const mb = bar.querySelector(".menu-btn"), ms = document.getElementById("msheet");
    const setSheet = open => { mb.setAttribute("aria-expanded", String(open)); ms.hidden = !open; mb.textContent = open ? "Close" : "Menu"; };
    mb.addEventListener("click", e => { e.stopPropagation(); setSheet(ms.hidden); });
    document.addEventListener("click", e => { if (!bar.contains(e.target)) { close(); setSheet(false); } });
    document.addEventListener("keydown", e => { if (e.key === "Escape") { const o = btns.find(b => b.getAttribute("aria-expanded") === "true"); close(); setSheet(false); if (o) o.focus(); } });
  }
  // offline support: the service worker precaches the whole site and the app
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
    window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
  }
  const foot = document.getElementById("foot");
  if (foot) {
    foot.className = "footer";
    foot.innerHTML = `<div class="page">
      <nav class="fmap" aria-label="Site map">${GROUPS.map(g => `<div><div class="mg-t">${g.t}</div>${g.items.map(([h, t]) => `<a href="${h}">${t}</a>`).join("")}</div>`).join("")}</nav>
      <p>An independent research project by Zach Warren. Analysis, data and code: <a href="https://github.com/zacharyslate/marfa-lights-investigation">github.com/zacharyslate/marfa-lights-investigation</a>. Paper: <a href="https://doi.org/10.5281/zenodo.23046566">doi:10.5281/zenodo.23046566</a>.</p>
      <p>Results are preliminary and not yet field-validated. Map data: USGS The National Map, OpenStreetMap contributors, USDOT BTS, FAA, FRA, FCC, EIA, OurAirports.</p>
      <p>Text, figures and data: <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Code: MIT. Photographs by Zach Warren: all rights reserved. Other images: as credited. <a href="https://github.com/zacharyslate/marfa-lights-investigation/blob/main/LICENSING.md">Licensing details</a>.</p></div>`;
  }
})();

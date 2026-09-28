/* Marfa Lights Field Guide — shared header, footer and theme switch. */
(function () {
  const PAGES = [
    ["map.html", "Map"], ["history.html", "History & Folklore"], ["science.html", "The Science"],
    ["place.html", "The Place"], ["visit.html", "Visiting"], ["sky.html", "Sky finder"], ["community.html", "Community"], ["app/", "Get the app"]
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
  const bar = document.getElementById("bar");
  if (bar) {
    bar.className = "bar";
    bar.innerHTML = `<div class="bar-in">
      <a class="brand" href="index.html" aria-label="Marfa Lights Field Guide home">
        <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><circle cx="11" cy="11" r="4" fill="var(--accent)"/><circle cx="11" cy="11" r="8.5" fill="none" stroke="var(--accent)" stroke-width="1.2" opacity=".5"/><line x1="0" y1="17.5" x2="22" y2="17.5" stroke="var(--ink)" stroke-width="1.4"/></svg>
        Marfa Lights Field Guide</a>
      <nav class="nav" aria-label="Pages">${PAGES.map(([h, t]) => `<a href="${h}"${h === here ? ' aria-current="page"' : ""}>${t}</a>`).join("")}</nav>
      <button class="theme-btn" id="themeBtn" type="button" title="Switch theme. Night vision keeps your eyes dark-adapted."><span class="dot"></span><span>${LABEL[theme]}</span></button>
    </div>`;
    document.getElementById("themeBtn").addEventListener("click", () => {
      theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
      try { localStorage.setItem("mlfg-theme", theme); } catch (e) {}
      apply(theme);
      document.dispatchEvent(new CustomEvent("themechange"));
    });
  }
  // offline support: the service worker precaches the whole site and the app
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
    window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
  }
  const foot = document.getElementById("foot");
  if (foot) {
    foot.className = "footer";
    foot.innerHTML = `<div class="page">
      <p>An independent research project by Zach Warren. Analysis, data and code: <a href="https://github.com/zacharyslate/marfa-lights-investigation">github.com/zacharyslate/marfa-lights-investigation</a>.</p>
      <p>Results are preliminary and not yet field-validated. Map data: USGS The National Map, OpenStreetMap contributors, USDOT BTS, FAA, FRA, FCC, EIA, OurAirports.</p></div>`;
  }
})();

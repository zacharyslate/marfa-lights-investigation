/* Anonymous visit counting with GoatCounter (https://www.goatcounter.com): no cookies, no personal data stored.
   It is off until GC holds the site's GoatCounter code. Elements with a data-stat attribute show the totals. */
(function () {
  const GC = "";   // the GoatCounter site code, e.g. "marfalights" for https://marfalights.goatcounter.com
  if (!GC || !/^https:$/.test(location.protocol)) return;
  const base = `https://${GC}.goatcounter.com`;

  // count this visit
  const s = document.createElement("script");
  s.async = true; s.src = "https://gc.zgo.at/count.js"; s.dataset.goatcounter = base + "/count";
  document.head.appendChild(s);

  // an installed app (home-screen icon) opened for the first time on this device counts once as an install
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  let firstRun = false;
  try { firstRun = standalone && !localStorage.getItem("mlfg-installed"); } catch (e) {}
  if (firstRun) {
    let tries = 0;
    const send = () => {
      if (window.goatcounter && typeof window.goatcounter.count === "function") {
        window.goatcounter.count({path: "app-installed", title: "App installed", event: true});
        try { localStorage.setItem("mlfg-installed", "1"); } catch (e) {}
      } else if (++tries < 40) setTimeout(send, 500);
    };
    send();
  }

  // totals for the footer and the app (the counter is cached by GoatCounter for up to four hours)
  const get = p => fetch(`${base}/counter/${encodeURIComponent(p)}.json`)
    .then(r => (r.ok ? r.json() : null)).then(j => (j && j.count) || null).catch(() => null);
  const show = async () => {
    const els = document.querySelectorAll("[data-stat]");
    if (!els.length) return;
    const [visits, installs] = await Promise.all([get("TOTAL"), get("app-installed")]);
    if (!visits) return;
    const txt = `${visits} visits to the site and app` + (installs ? ` · ${installs} app installs` : "") +
      ". Counted anonymously, with no cookies.";
    els.forEach(el => { el.textContent = txt; el.hidden = false; });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", show); else show();
})();

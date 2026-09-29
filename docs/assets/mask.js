/* Marfa Lights Field Guide: fast look-ups in the known-source mask and the ordinary-light rate map.
 *
 * The mask (data/zos.json, analysis/zone_of_skepticism.py) and the rate map (data/zos_rate.json,
 * analysis/weighted_zone.py) are published as polygons in (true azimuth in degrees, elevation in mrad).
 * Testing a point against every polygon is slow, so on load the polygons are drawn once onto small
 * off-screen rasters (0.05 deg x 0.1 mrad, finer than the observer errors they already include) and
 * every query becomes a table look-up.
 *
 *   const M = MarfaMask.build(ZR, ZOS, skyAt)   // any argument may be null; skyAt(az) -> skyline elevation in mrad
 *   M.rate(az, m)          -> -1 (below 0.01/h), 0..3 (level index), or null (no data / outside the modelled range)
 *   M.fixed(az, m)         -> true if a fixed light (tower, town glow, aerostat) can appear here, null if no data
 *   M.inMask(az, m, tier)  -> tier "A" (photo, +-0.3 deg) or "B" (compass, +-3 deg); null if no data
 *   M.window(az, tol)      -> {rate, fixed} over every elevation below the skyline within +-tol degrees of az
 * Both refraction cases of the rate map (normal, k = 0.13, and a strong inversion, k = 1) are combined:
 * the highest rate either gives.
 */
(function () {
  const DAZ = 0.05, DEL = 0.1, AZ0 = 147, AZ1 = 303, EL0 = -17, EL1 = 15;
  const W = Math.round((AZ1 - AZ0) / DAZ) + 1, H = Math.round((EL1 - EL0) / DEL) + 1;
  const norm = a => ((a % 360) + 360) % 360;

  function raster(rings) {            // even-odd fill of a set of rings -> Uint8Array(W*H) of 0/1
    const out = new Uint8Array(W * H);
    if (!rings || !rings.length) return out;
    const c = document.createElement("canvas"); c.width = W; c.height = H;
    const g = c.getContext("2d");
    g.fillStyle = "#000"; g.beginPath();
    rings.forEach(r => r.forEach(([az, m], i) => {
      const x = (az - AZ0) / DAZ + 0.5, y = (EL1 - m) / DEL + 0.5;
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    }));
    g.fill("evenodd");
    const a = g.getImageData(0, 0, W, H).data;
    for (let i = 0; i < W * H; i++) out[i] = a[4 * i + 3] >= 128 ? 1 : 0;
    return out;
  }
  const idx = (az, m) => {
    const x = Math.round((norm(az) - AZ0) / DAZ), y = Math.round((EL1 - m) / DEL);
    return x < 0 || x >= W || y < 0 || y >= H ? -1 : y * W + x;
  };

  function build(ZR, ZOS, skyAt) {
    let rate = null, fixed = null, tiers = {};
    const domain = (ZR && ZR.standard.params.az_domain_deg) || [150, 300];
    const inDomain = az => norm(az) >= domain[0] && norm(az) <= domain[1];
    if (ZR) {
      rate = new Int8Array(W * H).fill(-1);
      [ZR.standard, ZR.inversion].forEach(Z => Z.levels.forEach((lv, i) => {
        const r = raster(Z.rate_polys[String(lv)]);
        for (let k = 0; k < r.length; k++) if (r[k] && i > rate[k]) rate[k] = i;
      }));
      fixed = new Uint8Array(W * H);
      [ZR.standard, ZR.inversion].forEach(Z => { const r = raster(Z.fixed_polys); for (let k = 0; k < r.length; k++) fixed[k] |= r[k]; });
    }
    if (ZOS) Object.keys(ZOS.tiers).forEach(t => { tiers[t] = raster(ZOS.tiers[t]); });

    // per-column maxima below the skyline (down to -15 mrad), for bearing-only queries
    let colRate = null, colFixed = null;
    if (rate && skyAt) {
      colRate = new Int8Array(W).fill(-1); colFixed = new Uint8Array(W);
      for (let x = 0; x < W; x++) {
        const az = AZ0 + x * DAZ, sk = skyAt(az);
        if (sk === null || sk === undefined) continue;
        const top = Math.max(0, Math.round((EL1 - sk) / DEL)), bot = Math.min(H - 1, Math.round((EL1 + 15) / DEL));
        for (let y = top; y <= bot; y++) { const k = y * W + x; if (rate[k] > colRate[x]) colRate[x] = rate[k]; if (fixed[k]) colFixed[x] = 1; }
      }
    }
    return {
      domain, inDomain,
      rate(az, m) { if (!rate || !inDomain(az)) return null; const k = idx(az, m); return k < 0 ? -1 : rate[k]; },
      fixed(az, m) { if (!fixed || !inDomain(az)) return null; const k = idx(az, m); return k >= 0 && fixed[k] === 1; },
      inMask(az, m, tier) { const t = tiers[tier || "A"]; if (!t || !inDomain(az)) return null; const k = idx(az, m); return k >= 0 && t[k] === 1; },
      window(az, tol) {
        if (!colRate || !inDomain(az)) return {rate: null, fixed: null};
        let r = -1, f = false;
        for (let a = az - tol; a <= az + tol + 1e-9; a += DAZ) {
          const x = Math.round((norm(a) - AZ0) / DAZ); if (x < 0 || x >= W) continue;
          if (colRate[x] > r) r = colRate[x]; if (colFixed[x]) f = true;
        }
        return {rate: r, fixed: f};
      }
    };
  }
  window.MarfaMask = {build};
})();

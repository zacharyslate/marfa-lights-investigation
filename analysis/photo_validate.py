"""Test the line-of-sight model against the registered 2018-11-21 photos (v2 statistics).

What changed from v1 (referee points, publication/notes/09_photo_validation.md):
  * model = v2 engine (analysis/marfa): exact geometry, lidar terrain; road curve = TxDOT centreline;
  * separations are measured to the modelled road CURVE (piecewise-linear between 60 m samples, only
    between consecutive in-view samples), not to the nearest 60 m sample;
  * duplicate detections within a frame (< 0.02 deg apart) are merged;
  * frames taken seconds apart show the same vehicles, so the unit of analysis is a light in a BURST
    (p04+p05, p06+p07, p08, p09, p10); a light seen in both frames of a burst counts once;
  * no post-hoc distance threshold: the test statistic is the median separation of all units, compared with
    a Monte Carlo null (the same number of random positions per burst, drawn uniformly in each frame's
    'ground band' between the 10 km ridge line and the skyline);
  * the 45 s streak in p13 is found without using the model (robust threshold over the whole band below the
    skyline, elongated components), then compared with the model;
  * the contrast vetting rule (peak/median >= 1.20) was chosen after looking at the detections, so the test
    is also reported with no vetting at all.
Limits that remain: the camera pointing is fitted to the modelled skyline (no stars are recorded in these
frames), so the test checks the internal consistency of the terrain model, road geometry and photos, not
the absolute pointing; that needs the star-calibrated camera of experiment E1 (note 12).
Writes data/derived/photos/validation.json."""
import json, math, sys
import numpy as np
from PIL import Image
from scipy import ndimage
sys.path.insert(0, "analysis")
import photo_register as P

R = json.load(open(f"{P.OUT}/registration.json"))
S = P.S
BURSTS = {"B1": ["p04", "p05"], "B2": ["p06", "p07"], "B3": ["p08"], "B4": ["p09"], "B5": ["p10"]}
MERGE_DEG = 0.02
rng = np.random.default_rng(20260928)


def road_curves():
    """Visible road polylines [(name, az, el, chainage_km)], split where the road leaves view."""
    out = []
    F = S["hwy_fields"]
    iaz, ial, icl, ich = F.index("az"), F.index("alpha_mrad"), F.index("cls"), F.index("ch_km")
    pts = [(p[iaz], math.degrees(math.atan(p[ial] / 1000)), p[icl] in ("v", "m"), p[ich]) for p in S["hwy"]]
    out += _split("US-67", pts)
    RF = S["roads_fields"]
    for rd in S["roads"]:
        pts = [(p[RF.index("az")], math.degrees(math.atan(p[RF.index("alpha_mrad")] / 1000)),
                p[RF.index("kcrit")] <= 0.13, float(i)) for i, p in enumerate(rd["p"])]
        out += _split(rd["n"], pts)
    return out


def _split(name, pts):
    segs, cur = [], []
    for a, e, vis, ch in pts:
        if vis:
            cur.append((a, e, ch))
        elif cur:
            segs.append(cur); cur = []
    if cur:
        segs.append(cur)
    return [(name, np.array([s[0] for s in c]), np.array([s[1] for s in c]), np.array([s[2] for s in c])) for c in segs]


CURVES = road_curves()


def sep_curve(az, el):
    """Angular distance (deg) from (az, el) to the nearest visible road curve; also road name and chainage."""
    best = (np.inf, None, None)
    ce = math.cos(math.radians(el))
    for name, A, E, C in CURVES:
        if A.size == 1:
            d = math.hypot((A[0] - az) * ce, E[0] - el)
            if d < best[0]:
                best = (d, name, C[0])
            continue
        x0, y0 = (A[:-1] - az) * ce, E[:-1] - el
        dx, dy = np.diff(A) * ce, np.diff(E)
        L2 = dx * dx + dy * dy
        t = np.clip(-(x0 * dx + y0 * dy) / np.where(L2 > 0, L2, 1), 0, 1)
        d = np.hypot(x0 + t * dx, y0 + t * dy)
        i = int(np.argmin(d))
        if d[i] < best[0]:
            best = (float(d[i]), name, float(C[i] + t[i] * (C[i + 1] - C[i])))
    return best


def vet(name, lights):
    im = np.asarray(Image.open(f"{P.RAW}/{name}.jpg").convert("L")).astype(float)
    for l in lights:
        x, y = int(l["x"]), int(l["y"])
        box = im[max(0, y - 40):y + 40, max(0, x - 60):x + 60]
        peak = im[y - 2:y + 3, x - 2:x + 3].max()
        l["contrast"] = round(float(peak / max(np.median(box), 1)), 2)
        l["accepted"] = bool(l["contrast"] >= 1.20)
    return lights


def band_mask(az, el):
    return (el > P.model_el_deg(az, 3) + 0.01) & (el < P.model_el_deg(az) - 25 / 936)


def _t(n):
    h, m, sec = R[n]["time_camera"][-8:].split(":")
    return int(h) * 3600 + int(m) * 60 + int(sec)


def units(vetted=True, vmax=45.0, slack_km=0.06):
    """Independent sightings. Within a burst, two detections are the same vehicle if they lie on the same road
    and their along-road separation is within what a vehicle at <= vmax m/s covers in the time between the
    frames (+ slack for 1 s timestamp resolution and position error); duplicates in one frame always merge."""
    out = []
    for b, frames in BURSTS.items():
        U = []
        for n in frames:
            for l in R[n]["lights"]:
                if vetted and not l["accepted"]:
                    continue
                d, road, ch = sep_curve(l["az"], l["el"])
                for u in U:
                    dt = abs(_t(n) - _t(u["frames"][-1])) + 1.0
                    same = (n in u["frames"] and math.hypot((u["az"] - l["az"]) * math.cos(math.radians(l["el"])),
                                                            u["el"] - l["el"]) < MERGE_DEG)
                    if road is not None and road == u["road"] and n not in u["frames"]:
                        same = same or abs(ch - u["chainage_km"]) <= vmax * dt / 1000 + slack_km
                    if same:
                        if n not in u["frames"]:
                            u["track"].append((n, round(ch, 3)))
                        u["frames"].append(n); break
                else:
                    U.append(dict(burst=b, frames=[n], az=l["az"], el=l["el"], x=l["x"], y=l["y"],
                                  contrast=l["contrast"], road=road, chainage_km=ch, track=[(n, round(ch, 3))]))
        out += U
    return out


def p_median_within(qs, m_needed):
    """Probability that at least m_needed of independent units with chance probabilities qs fall within the
    observed median separation (Poisson-binomial, exact by convolution)."""
    dist = np.array([1.0])
    for q in qs:
        dist = np.convolve(dist, [1 - q, q])
    return float(dist[m_needed:].sum())


def null_medians(counts, nsim=4000):
    """Median separation of random band positions, same number of units per burst as observed."""
    pools = {}
    for b, frames in BURSTS.items():
        p = [R[frames[0]]["pointing"][k] for k in ("az0", "el0", "roll", "scale")]
        xs, ys = rng.uniform(0, 6000, 60000), rng.uniform(0, 3376, 60000)
        az, el = P.px_to_angles(xs, ys, p)
        ok = band_mask(az, el)
        az, el = az[ok][:3000], el[ok][:3000]
        pools[b] = np.array([sep_curve(a, e)[0] for a, e in zip(az, el)])
    med = np.empty(nsim)
    for i in range(nsim):
        s = np.concatenate([rng.choice(pools[b], counts[b]) for b in BURSTS if counts.get(b, 0)])
        med[i] = np.median(s)
    return med, pools


def streaks(name="p13"):
    """Model-free streak detection below the skyline: robust 7-sigma threshold, elongated components."""
    p = [R[name]["pointing"][k] for k in ("az0", "el0", "roll", "scale")]
    im = np.asarray(Image.open(f"{P.RAW}/{name}.jpg").convert("L")).astype(float)
    H, W = im.shape
    sm = ndimage.uniform_filter(im, 3)
    xs = np.arange(W, dtype=float)
    # skyline row per column from the fitted pointing; search only below it
    azc, _ = P.px_to_angles(xs, np.full(W, H / 2.0), p)
    _, ysky = P.angles_to_px(azc, P.model_el_deg(azc), p)
    rows = np.arange(H)[:, None]
    below = rows > (ysky[None, :] + 12)
    bg = ndimage.median_filter(sm[::4, ::4], size=15)
    bg = np.kron(bg, np.ones((4, 4)))[:H, :W]
    res = sm - bg
    mad = np.median(np.abs(res[below])) * 1.4826
    mask = below & (res > 7 * mad)
    lab, n = ndimage.label(mask)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if w < 60 or w / max(h, 1) < 5:
            continue
        sub = np.where(lab[sl] == i, res[sl], 0)
        cols = np.arange(sl[1].start, sl[1].stop)
        wsum = sub.sum(axis=0)
        ok = wsum > 0
        yc = (sub * np.arange(sl[0].start, sl[0].stop)[:, None]).sum(axis=0)[ok] / wsum[ok]
        az, el = P.px_to_angles(cols[ok].astype(float), yc, p)
        seps = np.array([sep_curve(a, e)[0] for a, e in zip(az, el)])
        out.append(dict(x0=int(sl[1].start), x1=int(sl[1].stop), y=float(np.median(yc)), az0=float(az.min()),
                        az1=float(az.max()), el_med=float(np.median(el)), median_sep_deg=float(np.median(seps)),
                        max_sep_deg=float(seps.max())))
    return out, float(mad)


def main():
    res = {"method": __doc__.split("Writes")[0], "frames": {}, "lights": []}
    for n, r in R.items():
        vet(n, r["lights"])
        for l in r["lights"]:
            d, road, ch = sep_curve(l["az"], l["el"])
            l.update(frame=n, time_camera=r["time_camera"], exposure_s=r["exposure_s"], sep_visible_deg=round(d, 4),
                     road=road, road_km=round(ch, 2) if road == "US-67" and ch is not None else None,
                     chainage_km=round(ch, 3) if road == "US-67" and ch is not None else None)
            res["lights"].append(l)
        res["frames"][n] = {k: r[k] for k in ("time_camera", "exposure_s", "pointing", "skyline_rms_deg", "alt_fits")}
    for vetted in (True, False):
        U = units(vetted)
        for u in U:
            u["sep_deg"] = sep_curve(u["az"], u["el"])[0]
        counts = {b: sum(1 for u in U if u["burst"] == b) for b in BURSTS}
        med_obs = float(np.median([u["sep_deg"] for u in U]))
        med_null, pools = null_medians(counts)
        allpool = np.concatenate(list(pools.values()))
        qs = [float(np.mean(pools[u["burst"]] <= med_obs)) for u in U]
        p_exact = p_median_within(qs, (len(U) + 1) // 2)
        speeds = []
        for u in U:
            if len(u["track"]) > 1:
                (n1, c1), (n2, c2) = u["track"][0], u["track"][-1]
                dt = max(_t(n2) - _t(n1), 1)
                # along-road sensitivity: km of road per degree of image position at this point of the curve
                a, e = u["az"], u["el"]
                c_a = sep_curve(a + 0.005, e)[2]; c_b = sep_curve(a - 0.005, e)[2]
                km_per_deg = abs(c_a - c_b) / 0.01 if (c_a is not None and c_b is not None) else float("nan")
                sig_m = km_per_deg * 0.006 * 1000 * math.sqrt(2)          # 0.006 deg position error per frame
                speeds.append(dict(frames=[n1, n2], dt_s=dt, dt_range_s=[max(dt - 1, 0.5), dt + 1],
                                   d_m=round(abs(c2 - c1) * 1000), sigma_d_m=round(sig_m),
                                   v_ms=round(abs(c2 - c1) * 1000 / dt, 1),
                                   v_range_ms=[round(max(abs(c2 - c1) * 1000 - 2 * sig_m, 0) / (dt + 1), 1),
                                               round((abs(c2 - c1) * 1000 + 2 * sig_m) / max(dt - 1, 0.5), 1)]))
        key = "units_vetted" if vetted else "units_all_detections"
        res[key] = dict(n=len(U), per_burst=counts, median_sep_deg=med_obs,
                        median_sep_px=med_obs * P.F_PX * 0.974 * math.pi / 180,
                        null_median_of_medians_deg=float(np.median(med_null)),
                        p_value_mc=float((np.sum(med_null <= med_obs) + 1) / (med_null.size + 1)),
                        p_value_exact=p_exact, speeds_within_bursts=speeds,
                        band_fraction_within_obs_median=float(np.mean(allpool <= med_obs)),
                        units=[{k: (round(v, 4) if isinstance(v, float) else v) for k, v in u.items()} for u in U])
        print(f"{key}: n={len(U)} median sep {med_obs:.4f} deg; null median {np.median(med_null):.3f} deg; "
              f"p(MC) <= {res[key]['p_value_mc']:.1e}, p(exact) = {p_exact:.1e}; speeds {speeds}; band fraction within {med_obs:.4f} deg = {res[key]['band_fraction_within_obs_median']:.4f}")
    # visible/hidden boundary: share of the in-frame US-67 (60 m samples) the model calls hidden, and where the
    # sightings fall; if visibility had no predictive power, each sighting would land on a hidden sample with
    # probability equal to that share
    F = S["hwy_fields"]
    pts = np.array([[q[F.index("az")], math.degrees(math.atan(q[F.index("alpha_mrad")] / 1000)),
                     q[F.index("cls")] != "h"] for q in S["hwy"]])
    U = res["units_vetted"]["units"]
    bnd, p_all = {}, 1.0
    for b, frames in BURSTS.items():
        pp = [R[frames[0]]["pointing"][k] for k in ("az0", "el0", "roll", "scale")]
        x, y = P.angles_to_px(pts[:, 0], pts[:, 1], pp)
        inside = (x > 0) & (x < 6000) & (y > 0) & (y < 3376)
        f = float(pts[inside, 2].astype(bool).mean())
        n = sum(1 for u in U if u["burst"] == b)
        on_vis = 0
        for u in U:
            if u["burst"] != b:
                continue
            d = np.hypot((pts[:, 0] - u["az"]) * math.cos(math.radians(u["el"])), pts[:, 1] - u["el"])
            on_vis += bool(pts[int(np.argmin(d)), 2])
        bnd[b] = dict(samples_in_frame=int(inside.sum()), visible_fraction=round(f, 3), sightings=n, on_visible=on_vis)
        p_all *= f ** n
    res["boundary_test"] = dict(per_burst=bnd, p_all_on_visible_if_no_predictive_power=p_all)
    print("boundary test:", bnd, "p = %.1e" % p_all)
    st, mad = streaks("p13")
    res["p13_streaks"] = dict(threshold="7 x robust sigma above local background, below the fitted skyline",
                              noise_mad=mad, streaks=st)
    if st:
        m = float(np.median([s["median_sep_deg"] for s in st]))
        res["p13_streak"] = {"n_streaks": len(st), "median_abs_offset_deg": m}
        print("p13 streaks:", [(s["x0"], s["x1"], round(s["median_sep_deg"], 4)) for s in st])
    json.dump(res, open(f"{P.OUT}/validation.json", "w"), indent=1)


if __name__ == "__main__":
    main()

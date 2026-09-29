"""
Marfa Lights investigation: the activity-weighted known-source mask (formerly "Zone of Skepticism").

The binary known-source mask (zone_of_skepticism.py) marks where a catalogued light CAN
appear. This script estimates how OFTEN one does: the expected number of ordinary lights
per hour that pass through each patch of the view from the Viewing Area, on a given night.

For each position (bearing, elevation) the rate is

    lambda = sum over transient sources s of  q_s * P_detect,s        [lights per hour]

  roads   q = AADT * HOURLY_SHARE / 2 per direction (vehicles per hour), from the nearest
          TxDOT count station on the same route (highest of the 2025 AADT and the two previous years).
          P_detect = p_high * [m_high <= m_lim] + (1 - p_high) * [m_low <= m_lim]
          with m from headlight_model.py (photometry v2), corrected to the night's MOR. Cars facing
          away show tail lamps: at the FMVSS No. 108 minimum they are far below the naked-eye limit
          at these ranges (m ~ 8-10), at the regulatory maximum they are near it (m ~ 4.5-6). They are
          not counted in the standard scenario (a lower bound on the rate); the 'tail_max' scenario
          counts them at the regulatory maximum (an upper bound).
  rail    q = night through-trains / 12 h, from the FRA grade-crossing inventory
          (Form FRA F 6180.71 defines night as 6 PM to 6 AM), the highest value reported at
          any crossing of that railroad.
          Track in view counts as detectable (locomotive headlight and ditch lights).

A source contributes where it is in view at the night's refraction k, at its apparent
elevation alpha(k), dilated by the observer's error box (err_az, err_el). A road or a
track contributes its rate once per patch (a car passes a patch once), so rates are the
maximum along one line and the sum across lines.

Permanent lights (lit towers, towns and their skyglow, the aerostat) are not rates. They are
returned as a separate "fixed light" mask: a steady or regularly blinking light there has an
obvious candidate at any time.

Also returned per road sample: the apparent angular speed of a car at SPEED_KMH across
the view, a motion signature to test observed lights against.

ASSUMPTIONS THAT MUST BE REPLACED BY FIELD DATA
  HOURLY_SHARE  fraction of AADT per night hour (both directions). No verified published
                night-hour share was found for these rural roads; 2 % per hour is a working
                value. Rates scale linearly with it. Replace with a traffic count on the night.
  P_HIGH        share of isolated rural drivers on high beam: about 25 % in earlier
                observational work, as summarised by Reagan et al. (2017), who measured
                18 % across all their sites.
  SPEED_KMH     100 km/h nominal.

Usage
    python analysis/weighted_zone.py                          # standard + strong-inversion scenarios
    python analysis/weighted_zone.py --k 0.6 --mor 80 --err-az 0.2 --err-el 0.08 --out night.json
"""
import argparse
import json
import math

import contourpy
import numpy as np
from pyproj import Geod

GEOD = Geod(ellps="WGS84")
R = 6_371_000.0
K0 = 0.13
AZ = (150.0, 300.0, 0.02)
EL = (-16.0, 14.0, 0.04)                 # mrad
D2M = 1000 * math.pi / 180
HOURLY_SHARE = 0.02
P_HIGH = 0.25
SPEED_KMH = 100.0
M_LIM = 5.86                            # Crumey (2014) eq. 54 at mu = 21.0 mag/arcsec^2, F = 2
MOR_REF = json.load(open("data/derived/headlights.json"))["meta"].get("mor_ref_km", 100)
LEVELS = [0.01, 0.1, 1.0, 10.0]         # contour levels, lights per hour
ROUTE = {"US67": "US0067", "RM2810": "RM2810", "US0090": "US0090", "US0067": "US0067", "FM0170": "FM0170",
         "SH0118": "SH0118", "RM0169": "RM0169", "FM1112": "FM1112", "SH0017": "SH0017", "CR18900002": "CR18900002"}
# County roads have no TxDOT count. Nopal Road (CR 189-0002) is given an assumed AADT of 60 vehicles a day, the
# order of the least-travelled count station on RM 2810 (20-52 a day). This is an assumption, stated in the paper.
ASSUMED_AADT = {"CR18900002": 60}


def alpha_at(a013, d_km, k):
    return a013 + d_km * 1000 * (k - K0) / (2 * R) * 1000


def mag_at_mor(m_ref, d_km, mor):
    """Correct a magnitude computed for MOR = MOR_REF km (headlights.json) to another MOR."""
    if m_ref is None:
        return None
    return m_ref + 2.5 * math.log10(math.e) * math.log(20) * d_km * (1 / mor - 1 / MOR_REF)


def load_aadt():
    rows = json.load(open("data/inputs/txdot_aadt.json"))["rows"]
    st = {}
    for r in rows:
        # conservative: the highest of the three most recent annual values (single years can be low outliers)
        vals = [r[f] for f in ("AADT_RPT_QTY", "AADT_RPT_HIST_01_QTY", "AADT_RPT_HIST_02_QTY") if r.get(f) is not None]
        if not vals:
            continue
        st.setdefault(r["ON_ROAD"], []).append((r["LONGITUDE"], r["LATITUDE"], max(vals), r["TRFC_STATN_ID"]))
    return st


def nearest_aadt(stations, lon, lat):
    best = None
    for slon, slat, q, sid in stations:
        d = GEOD.inv(lon, lat, slon, slat)[2]
        if best is None or d < best[0]:
            best = (d, q, sid)
    return best


def sources(k, mor, m_lim, p_high, hourly_share, rail_rates, rear=False):
    """List of lines: dict(kind, label, rate_scale, pts=[(az, el_mrad, km, weight), ...])."""
    lines = []
    hl = json.load(open("data/derived/headlights.json"))
    aadt = load_aadt()
    speed = SPEED_KMH / 3.6
    motion = []
    for rd in hl["roads"]:
        st = aadt.get(ROUTE[rd["key"]], [])
        if not st and rd["key"] in ASSUMED_AADT:
            st = [(rd["lon"][0], rd["lat"][0], ASSUMED_AADT[rd["key"]], "assumed")]
        pts = rd["pts"]
        for dname in ("to_marfa", "from_marfa"):
            seq = []
            for i in range(0, len(pts), 2):
                p = pts[i] if dname == "to_marfa" else pts[i + 1]
                az, km, a, kc, cls = p[0], p[1], p[2], p[3], p[4]
                lat, lon = rd["lat"][i // 2], rd["lon"][i // 2]
                vis = 1.0 if kc <= k else (0.5 if (cls == "m" and k >= K0) else 0.0)
                if vis == 0 or not st or (abs(p[7]) >= 90 and not rear):
                    seq.append(None)
                    continue
                if abs(p[7]) >= 90:          # facing away: tail lamps at the FMVSS No. 108 maximum
                    mT = mag_at_mor(p[16], km, mor)
                    pdet = float(mT is not None and mT <= m_lim)
                else:
                    mL, mH = mag_at_mor(p[9], km, mor), mag_at_mor(p[12], km, mor)
                    pdet = p_high * (mH is not None and mH <= m_lim) + (1 - p_high) * (mL is not None and mL <= m_lim)
                d_st, q, sid = nearest_aadt(st, lon, lat)
                rate = q * hourly_share / 2 * pdet * vis
                seq.append((az, alpha_at(a, km, k), km, rate, sid, q))
                # apparent angular speed: component of velocity across the line of sight
                if dname == "to_marfa":
                    head = p[6]
                    bearing_from_viewer = az
                    cross = abs(math.sin(math.radians(head - bearing_from_viewer)))
                    motion.append((rd["key"], az, km, speed * cross / (km * 1000) * 180 / math.pi * 60))   # deg per minute
            lines.append({"kind": "road", "label": rd["road"], "dir": dname, "pts": seq})
    pl = json.load(open("data/derived/panorama_los.json"))
    for owner in ("UP", "TXPF"):
        seq = []
        for o, lat, lon, az, km, a, kc in sorted((r for r in pl["rail"] if r[0] == owner), key=lambda r: r[3]):
            seq.append((az, alpha_at(a, km, k), km, rail_rates[owner], None, None) if kc <= k else None)
        lines.append({"kind": "rail", "label": "Union Pacific" if owner == "UP" else "Texas Pacifico", "dir": "", "pts": seq})
    return lines, motion


def fixed_segments(k):
    site = json.load(open("docs/data/site.json"))
    sky = np.array(site["sky"])
    out = []
    for t in site["towers"]:
        if t["light"] != "none" and t["kc"] is not None and t["kc"] <= k and t["a"] is not None:
            out.append((t["az"], alpha_at(t["a"], t["d"], k), alpha_at(t["a"], t["d"], k)))
    for t in site["towns"]:
        if not (AZ[0] + 1 <= t["az"] <= AZ[1] - 1):
            continue
        # towns beyond the terrain model (no apparent elevation computed: Presidio, Ojinaga) count as skyglow only
        if "a" in t and t["kc"] is not None and t["kc"] <= k:
            for daz in np.linspace(-0.5, 0.5, 11) * math.degrees(1.5 / t["d"]):
                out.append((t["az"] + daz, alpha_at(t["a"], t["d"], k), alpha_at(t["a"], t["d"], k)))
        else:
            for daz in np.linspace(-1, 1, 21):
                s = float(np.interp(t["az"] + daz, sky[:, 0], sky[:, 1]))
                out.append((t["az"] + daz, s, s + 0.5 * D2M))
    for f in site["fields"]:
        if f["k"] == "balloon":
            out.append((f["az"], EL[0], EL[1]))
    return out


def grids():
    return np.arange(AZ[0], AZ[1] + 1e-9, AZ[2]), np.arange(EL[0], EL[1] + 1e-9, EL[2])


def box(M, az, el, a, lo, hi, daz, de, value=True, how="set"):
    c0, c1 = np.searchsorted(az, a - daz), np.searchsorted(az, a + daz, "right")
    r0, r1 = np.searchsorted(el, min(lo, hi) - de), np.searchsorted(el, max(lo, hi) + de, "right")
    if how == "max":
        np.maximum(M[r0:r1, c0:c1], value, out=M[r0:r1, c0:c1])
    else:
        M[r0:r1, c0:c1] = value


def rate_map(lines, err_az, err_el_mrad):
    az, el = grids()
    total = np.zeros((len(el), len(az)))
    for ln in lines:
        L = np.zeros_like(total)
        pts = ln["pts"]
        for p, q in zip(pts, pts[1:] + [None]):
            if p is None:
                continue
            box(L, az, el, p[0], p[1], p[1], err_az, err_el_mrad, p[3], "max")
            if q is not None:                                        # fill between neighbouring samples
                sep = math.sqrt(p[2] ** 2 + q[2] ** 2 - 2 * p[2] * q[2] * math.cos(math.radians(p[0] - q[0])))
                if sep < 1.0:
                    n = int(abs(p[0] - q[0]) / (AZ[2] * 2))
                    for t in np.linspace(0, 1, n + 2)[1:-1]:
                        box(L, az, el, p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]), p[1] + t * (q[1] - p[1]),
                            err_az, err_el_mrad, min(p[3], q[3]), "max")
        total += L
    return az, el, total


def fixed_map(segs, err_az, err_el_mrad):
    az, el = grids()
    M = np.zeros((len(el), len(az)), bool)
    for a, lo, hi in segs:
        box(M, az, el, a, lo, hi, err_az, err_el_mrad)
    return M


def polygons(az, el, Z, lo, hi=None):
    gen = contourpy.contour_generator(az, el, Z, fill_type=contourpy.FillType.OuterOffset)
    polys, offs = gen.filled(lo, hi if hi is not None else 1e12)
    out = []
    for pts, off in zip(polys, offs):
        for i in range(len(off) - 1):
            ring = pts[off[i]:off[i + 1]]
            keep = [ring[0]]
            for j in range(1, len(ring) - 1):
                a, b, c = keep[-1], ring[j], ring[j + 1]
                if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) > 1e-9:
                    keep.append(b)
            keep.append(ring[-1])
            out.append([[round(float(x), 3), round(float(y), 2)] for x, y in keep])
    return out


def rail_rates_from_fra():
    """Night through-trains per hour by railroad: the HIGHEST value reported at any FRA inventory
    crossing of that railroad within 90 km (night = 6 PM to 6 AM). Conservative on purpose: the
    inventory is self-reported, and Presidio cross-border service may resume in 2026."""
    from collections import Counter
    w = json.load(open("data/inputs/web_layers.json"))
    out, detail = {}, {}
    for rr in ("UP", "TXPF"):
        vals = [x[8] for x in w["xing"] if x[3] == rr and x[8] is not None]
        c = Counter(vals)
        out[rr] = max(vals) / 12.0
        detail[rr] = {"night_thru_trains_max": max(vals), "n_crossings": len(vals), "counts": {str(kk): v for kk, v in c.items()}}
    return out, detail


def run(k=K0, mor=MOR_REF, err_az=0.3, err_el_deg=0.1, m_lim=M_LIM, p_high=P_HIGH, hourly_share=HOURLY_SHARE,
        rail_rates=None, label="night", rear=False):
    rr, rr_detail = rail_rates_from_fra()
    if rail_rates:
        rr.update(rail_rates)
    lines, motion = sources(k, mor, m_lim, p_high, hourly_share, rr, rear=rear)
    az, el, lam = rate_map(lines, err_az, err_el_deg * D2M)
    fixed = fixed_map(fixed_segments(k), err_az, err_el_deg * D2M)
    site = json.load(open("docs/data/site.json"))
    sky = np.array(site["sky"])
    s = np.interp(az, sky[:, 0], sky[:, 1])
    fan = (az >= 157.276) & (az <= 277.276)
    band = (el[:, None] <= s[None, :]) & (el[:, None] >= s[None, :] - 5)
    stats = {}
    for name, sel in (("band_below_skyline_5mrad", band),):
        tot = sel[:, fan].sum()
        quiet = (lam < LEVELS[0]) & ~fixed
        stats[name] = {
            "fixed_light": round(float((fixed & sel)[:, fan].sum() / tot), 3),
            "rate_ge_1_per_h": round(float(((lam >= 1) & sel)[:, fan].sum() / tot), 3),
            "rate_0.1_to_1": round(float(((lam >= 0.1) & (lam < 1) & sel)[:, fan].sum() / tot), 3),
            "rate_0.01_to_0.1": round(float(((lam >= 0.01) & (lam < 0.1) & sel)[:, fan].sum() / tot), 3),
            "quiet_lt_0.01_and_no_fixed": round(float((quiet & sel)[:, fan].sum() / tot), 3)}
    # per-line summary: the peak rate and where
    summary = []
    for ln in lines:
        v = [p for p in ln["pts"] if p is not None and p[3] > 0]
        if v:
            summary.append({"label": ln["label"], "dir": ln["dir"], "n": len(v), "az": [round(min(p[0] for p in v), 1), round(max(p[0] for p in v), 1)],
                            "rate_max_per_h": round(max(p[3] for p in v), 4),
                            "aadt": sorted({(p[4], p[5]) for p in v if p[4]})})
    params = {"az_domain_deg": [AZ[0], AZ[1]], "k": k, "mor_km": mor, "err_az_deg": err_az, "err_el_deg": err_el_deg, "m_lim": m_lim, "p_high": p_high,
              "hourly_share": hourly_share, "rail_trains_per_h": rr, "rail_fra": rr_detail, "speed_kmh": SPEED_KMH}
    out = {"label": label, "params": params, "stats": stats, "summary": summary,
           "levels": LEVELS,
           "rate_polys": {f"{lv:g}": polygons(az, el, lam, lv) for lv in LEVELS},
           "fixed_polys": polygons(az, el, fixed.astype(float), 0.5)}
    return out, (az, el, lam, fixed), motion


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=float)
    ap.add_argument("--mor", type=float, default=MOR_REF)
    ap.add_argument("--err-az", type=float, default=0.3)
    ap.add_argument("--err-el", type=float, default=0.1)
    ap.add_argument("--mlim", type=float, default=M_LIM)
    ap.add_argument("--hourly-share", type=float, default=HOURLY_SHARE)
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.k is not None:
        out, _, _ = run(a.k, a.mor, a.err_az, a.err_el, a.mlim, P_HIGH, a.hourly_share, label="custom night")
        json.dump(out, open(a.out or "night_zone.json", "w"), separators=(",", ":"))
        print(json.dumps(out["stats"], indent=1))
        return
    scenarios = {}
    for name, k, rear, eaz, eel in (("standard", K0, False, 0.3, 0.1), ("inversion", 1.0, False, 0.3, 0.1),
                                    ("tail_max", K0, True, 0.3, 0.1), ("compass", K0, False, 3.0, 0.25)):
        out, grid, motion = run(k=k, label=name, rear=rear, err_az=eaz, err_el_deg=eel)
        scenarios[name] = out
        print(f"\n== {name} (k = {k}) ==")
        print(json.dumps(out["stats"], indent=1))
        for sline in out["summary"]:
            print(f"  {sline['label'][:32]:32s} {sline['dir']:10s} n={sline['n']:4d} az {sline['az']}  max {sline['rate_max_per_h']:.3f}/h  {sline['aadt'][:3]}")
        if name == "standard":
            np.savez_compressed("data/derived/weighted_zone_standard.npz", az=grid[0], el=grid[1], lam=grid[2], fixed=grid[3])
            mot = np.array([(m[1], m[2], m[3]) for m in motion if m[0] == "US67"])
            motion_out = {}
            for key in sorted({m[0] for m in motion}):
                arr = np.array([m[3] for m in motion if m[0] == key])
                motion_out[key] = {"median": round(float(np.median(arr)), 3),
                                   "p10": round(float(np.percentile(arr, 10)), 3), "p90": round(float(np.percentile(arr, 90)), 3)}
            print("apparent speed across the view (degrees per minute) by road:", motion_out)
            scenarios["motion_deg_per_min"] = motion_out
    json.dump(scenarios, open("data/derived/weighted_zone.json", "w"), separators=(",", ":"))
    web = {n: {"params": s["params"], "stats": s["stats"], "levels": s["levels"], "rate_polys": s["rate_polys"],
               "fixed_polys": s["fixed_polys"]} for n, s in scenarios.items() if n in ("standard", "inversion")}
    json.dump(web, open("docs/data/zos_rate.json", "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()

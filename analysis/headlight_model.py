"""
Marfa Lights investigation: how bright would a car look from the Viewing Area? (photometry v2)

For every sampled point of every road in view, and for both directions of travel, this computes where the
Viewing Area sits in the car's own lamp pattern and turns that into an illuminance at the observer's eye and an
apparent magnitude. The physics and the lamp data live in analysis/marfa/photometry.py; this script applies them
to the site's road samples and writes data/derived/headlights.json (schema kept for the site and the figures).

    h   horizontal angle of the observer off the car's heading, + = to the driver's right
    v   vertical angle of the observer above the lamp axis, + = up
        v = eps - theta
        eps   = (E_obs - E_lamp)/d - d(1-k)/(2R)       elevation of the observer seen from the lamp
        theta = atan(road grade along the heading)     vehicle pitch; grade from the 1 m lidar over +-25 m
    I(h,v)  luminous intensity of ONE lamp (cd): market-weighted U.S. beam patterns (UMTRI-2004-23 low beam,
            UMTRI-2001-19 high beam; 25th/50th/75th percentiles), held at the 45 deg value beyond 45 deg
    E   = 2 I(h,v) T / d^2           two lamps, unresolved at these ranges (lux)
    T   = exp(-sigma d),  sigma = ln(20)/MOR    (MOR definition: 5 % transmission)
    m   = -13.99 - 2.5 log10(E / 1 lx)          (Schaefer 1993)
Bands: 'dim' = 25th percentile lamp with the worse of +-AIM_DEG vertical aim; 'bright' = 75th percentile lamp
with the better aim. Rear lamps (cars facing away): FMVSS No. 108 minimum and maximum for two tail lamps, and
for two tail + two stop lamps + the high-mounted stop lamp (braking).

Run from the repository root:  python analysis/headlight_model.py
"""
import json
import math
import os
import sys

import numpy as np
from pyproj import Geod

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from marfa import dem, photometry as P      # noqa: E402

GEOD = Geod(ellps="WGS84")
R = 6_371_000.0
K = 0.13
EYE = 1.6
LAMP = 0.66                              # reference headlamp height (v2 model; see analysis/marfa/export_site.py)
MARFA = (-104.0206, 30.3095)             # courthouse area, used only to name travel direction
AIM_DEG = 0.5                            # assumed aim + load + suspension uncertainty (not a regulatory number)
MOR_KM = (88, 145, 265)                  # NPS Big Bend: ~55 mi on hazy days, ~90 mi average, ~165 mi natural
MOR_REF = MOR_KM[1]
SIRIUS = -1.46
_MOSAIC = None


def mosaic():
    global _MOSAIC
    if _MOSAIC is None:
        _MOSAIC = dem.load("lidar")
    return _MOSAIC


def hwy_class(r):
    """US-67 visibility class from the v2 model (data/derived/los_results.json, field 'cls'):
    v = robustly visible (Monte Carlo P_vis >= 0.95 and still visible under 0.25 m of unresolved grass),
    h = hidden (P_vis <= 0.05), m = marginal (everything else)."""
    return r["cls"]


def magnitude(E_lux):
    with np.errstate(divide="ignore"):
        return -13.99 - 2.5 * np.log10(E_lux)


def transmission(d_m, mor_km):
    return np.exp(-math.log(20) * d_m / (mor_km * 1000))


def wrap(a):
    return (a + 180) % 360 - 180


def road_geometry(lat, lon):
    """Heading (deg, sequence direction) from the neighbouring samples and grade dz/ds from the lidar at +-25 m."""
    n = len(lat)
    hd = np.zeros(n)
    for i in range(n):
        a, b = max(0, i - 1), min(n - 1, i + 1)
        hd[i] = GEOD.inv(lon[a], lat[a], lon[b], lat[b])[0] % 360
    lo1, la1, _ = GEOD.fwd(lon, lat, hd, np.full(n, 25.0))
    lo0, la0, _ = GEOD.fwd(lon, lat, (hd + 180) % 360, np.full(n, 25.0))
    z1, _ = mosaic().sample(np.asarray(lo1), np.asarray(la1), strict=False)
    z0, _ = mosaic().sample(np.asarray(lo0), np.asarray(la0), strict=False)
    grade = np.clip(np.nan_to_num((z1 - z0) / 50.0), -0.08, 0.08)
    return hd, grade


def evaluate(lat, lon, z, obs_z, viewer):
    """Per point, per direction: h, v and magnitudes (MOR_REF) for both beams (central, dim, bright) and rear lamps."""
    lat, lon, z = map(np.asarray, (lat, lon, z))
    hd, grade = road_geometry(lat, lon)
    az_cv, _, d = GEOD.inv(lon, lat, np.full_like(lon, viewer[0]), np.full_like(lat, viewer[1]))
    az_cv %= 360
    eps = np.degrees(((obs_z + EYE) - (z + LAMP)) / d - d * (1 - K) / (2 * R))
    # "toward Marfa" = the sequence direction in which the distance to Marfa shrinks
    dm = GEOD.inv(lon, lat, np.full_like(lon, MARFA[0]), np.full_like(lat, MARFA[1]))[2]
    seq_to_marfa = np.gradient(dm) < 0
    T = P.transmission(d, MOR_REF)
    s = T / d ** 2
    out = {}
    for label, sign in (("to_marfa", 1), ("from_marfa", -1)):
        forward = seq_to_marfa if sign == 1 else ~seq_to_marfa
        head = np.where(forward, hd, (hd + 180) % 360)
        pitch = np.degrees(np.arctan(np.where(forward, grade, -grade)))
        h = wrap(az_cv - head)
        v = eps - pitch
        res = {"heading": head, "h": h, "v": v, "pitch": pitch}
        for bname in ("low", "high"):
            I_c = P.front_intensity(h, v, bname, "p50")
            I_lo = np.min([P.front_intensity(h, v + dv, bname, "p25") for dv in (-AIM_DEG, 0, AIM_DEG)], axis=0)
            I_hi = np.max([P.front_intensity(h, v + dv, bname, "p75") for dv in (-AIM_DEG, 0, AIM_DEG)], axis=0)
            for tag, I in (("", I_c), ("_dim", I_lo), ("_bright", I_hi)):
                res[f"I_{bname}{tag}"] = I
                res[f"m_{bname}{tag}"] = np.where(I > 0, magnitude(I * s), np.inf)
        for w in ("min", "max"):
            It = P.rear_intensity(h, False, w)
            Ib = P.rear_intensity(h, True, w)
            res[f"m_tail_{w}"] = np.where(It > 0, magnitude(It * s), np.inf)
            res[f"m_brake_{w}"] = np.where(Ib > 0, magnitude(Ib * s), np.inf)
        out[label] = res
    return d, eps, out


def main():
    los = json.load(open("data/derived/los_results.json"))
    viewer, z0 = los["meta"]["viewer"], los["meta"]["z0"]
    F = los["hwy_fields"]
    hw = [dict(zip(F, r)) for r in los["hwy"]]
    cls = {round(r["ch_m"] / 1000, 2): hwy_class(r) for r in hw}

    roads = []
    # US-67 Shafter-Marfa: the main 60 m analysis
    lat = np.array([r["lat"] for r in hw]); lon = np.array([r["lon"] for r in hw]); z = np.array([r["zT"] for r in hw])
    d, eps, res = evaluate(lat, lon, z, z0, viewer)
    roads.append(dict(road="US-67 (Shafter–Marfa)", key="US67", lat=lat, lon=lon, z=z, d=d, eps=eps, res=res,
                      az=np.array([r["az"] for r in hw]), kc=np.array([r["kc07"] for r in hw]),
                      a=np.array([r["alpha_mrad_k013_h07"] for r in hw]),
                      cls=[cls.get(round(r["ch_m"] / 1000, 2), "h") for r in hw]))
    # other state roads (TxDOT), 120 m samples
    rl = json.load(open("data/derived/roads_los.json"))
    names = {"RM2810": "RM 2810 (Pinto Canyon Rd)", "US0090": "US-90", "US0067": "US-67/90 near the Viewing Area",
             "FM0170": "FM 170", "SH0118": "SH 118", "RM0169": "RM 169", "FM1112": "FM 1112", "SH0017": "SH 17"}
    for piece in rl["roads"]:
        key = piece["r"].split("-")[0]
        p = np.array(piece["p"], float)
        if key == "US0067":
            p = p[p[:, 2] > 277.5]            # keep only the US-67/90 concurrency near the viewer
        if len(p) < 5:
            continue
        d, eps, res = evaluate(p[:, 0], p[:, 1], p[:, 6], z0, viewer)
        roads.append(dict(road=names.get(key, key), key=key, lat=p[:, 0], lon=p[:, 1], z=p[:, 6], d=d, eps=eps,
                          res=res, az=p[:, 2], kc=p[:, 5], a=p[:, 4],
                          cls=["v" if k <= K else "h" for k in p[:, 5]]))

    # ---------- summary + export
    def r2(x, n=2):
        return [None if not np.isfinite(v) else round(float(v), n) for v in x]

    export = {"meta": {
        "beam_source": "UMTRI market-weighted U.S. headlamp patterns: low beam Schoettle et al. 2004 (UMTRI-2004-23, "
                       "Table 4), high beam Schoettle et al. 2001 (UMTRI-2001-19, Table 6); central = 50th percentile, "
                       "dim/bright = 25th/75th percentile with +-0.5 deg aim; rear lamps FMVSS No. 108 min/max "
                       "(NHTSA TP-108-13)",
        "magnitude": "m = -13.99 - 2.5 log10(E/lx)  (Schaefer 1993, Vistas in Astronomy 36:311)",
        "transmission": f"exp(-ln(20) d / MOR), MOR = {MOR_REF} km (central); MOR definition WMO-No. 8",
        "mor_ref_km": MOR_REF,
        "k": K, "eye_m": EYE, "lamp_m": LAMP, "aim_deg": AIM_DEG, "two_lamps": True,
        "fields": ["az", "km", "a_mrad", "kc", "cls", "dir", "heading", "h", "v",
                   "m_low", "m_low_dim", "m_low_bright", "m_high", "m_high_dim", "m_high_bright",
                   "m_tail_min", "m_tail_max", "m_brake_min", "m_brake_max"]},
        "roads": []}
    print(f"{'road':34s} {'dir':10s} {'n_vis':>5s} {'h range':>14s} {'v range':>12s} {'m_low':>14s} {'m_high':>14s}")
    for rd in roads:
        vis = np.array([c in ("v", "m") for c in rd["cls"]])
        pts = []
        for dname, res in rd["res"].items():
            if vis.any():
                sel = vis
                print(f"{rd['road'][:34]:34s} {dname:10s} {sel.sum():5d} "
                      f"{res['h'][sel].min():6.1f}..{res['h'][sel].max():5.1f} {res['v'][sel].min():5.2f}..{res['v'][sel].max():5.2f} "
                      f"{np.nanmin(res['m_low'][sel]):6.1f}..{np.nanmax(np.where(np.isfinite(res['m_low'][sel]), res['m_low'][sel], np.nan)):5.1f} "
                      f"{np.nanmin(res['m_high'][sel]):6.1f}..{np.nanmax(np.where(np.isfinite(res['m_high'][sel]), res['m_high'][sel], np.nan)):5.1f}")
        for i in range(len(rd["lat"])):
            for dname, res in rd["res"].items():
                pts.append([round(float(rd["az"][i]), 2), round(float(rd["d"][i]) / 1000, 2), round(float(rd["a"][i]), 2),
                            round(float(rd["kc"][i]), 3), rd["cls"][i], dname,
                            round(float(res["heading"][i]), 1), round(float(res["h"][i]), 1), round(float(res["v"][i]), 2)]
                           + r2([res[k][i] for k in ("m_low", "m_low_dim", "m_low_bright",
                                                      "m_high", "m_high_dim", "m_high_bright",
                                                      "m_tail_min", "m_tail_max", "m_brake_min", "m_brake_max")], 1))
        export["roads"].append({"road": rd["road"], "key": rd["key"],
                                "lat": r2(rd["lat"], 5), "lon": r2(rd["lon"], 5), "pts": pts})
    json.dump(export, open("data/derived/headlights.json", "w"), separators=(",", ":"))

    # reference numbers for the notes
    print(f"\nReference: lamp pair straight on (h=v=0), MOR {MOR_REF} km:")
    for km in (10, 20, 30, 40, 50):
        for bname, beam in (("low", P.LOW), ("high", P.HIGH)):
            I = float(beam(0, 0))
            print(f"  {km:3d} km {bname:4s} I={I:8.0f} cd  m={float(magnitude(2 * I * transmission(km * 1000, MOR_REF) / (km * 1000) ** 2)):5.1f}")
    return roads


if __name__ == "__main__":
    main()

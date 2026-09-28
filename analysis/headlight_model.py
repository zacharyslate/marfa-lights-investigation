"""
Marfa Lights investigation: how bright would a car look from the Viewing Area?

For every sampled point of every road in view, and for both directions of travel,
this computes where the Viewing Area sits in the car's own headlamp beam and
turns that into an illuminance at the observer's eye and an apparent magnitude.

    h   horizontal angle of the observer off the car's heading, + = to the driver's right
    v   vertical angle of the observer above the lamp axis, + = up
        v = eps - theta
        eps   = (E_obs - E_lamp)/d - d(1-k)/(2R)       elevation of the observer seen from the lamp
        theta = atan(road grade along the heading)     vehicle pitch on the slope
    I(h,v)  luminous intensity of ONE lamp (cd), from a measured U.S. headlamp pattern
    E   = 2 I(h,v) T / d^2           two lamps, unresolved at these ranges (lux)
    T   = exp(-sigma d),  sigma = ln(20)/MOR    (MOR definition: 5 % transmission)
    m   = -13.99 - 2.5 log10(E / 1 lx)          (Schaefer 1993, converted from foot-candles)

Beam data
---------
NHTSA compliance test report 108-CAN-17-004 (Calcoast-ITL, 30 Nov 2016): 2016 Ford Focus S,
left-hand VOR replaceable-bulb headlamp (H11 low / H1 high), sample LH1, test distance 100 ft.
Upper beam = FMVSS 108 Table XVIII column UB2; lower beam = Table XIX-a column LB2V.
https://static.nhtsa.gov/odi/ctr/2017/TRTR-644737-2017-001.pdf
Values below are the "Measured" column (before any re-aim).

This is ONE production lamp. Other lamps differ, especially in the lower beam near
the cut-off, where 0.5 deg of aim changes intensity several-fold. The model therefore
also reports a band from aim/pitch error of +-AIM_DEG and from the unknown fall-off
beyond the last measured angle. Treat the band, not the central value, as the answer.

Run from the repository root:  python analysis/headlight_model.py
"""
import json
import math

import numpy as np
from pyproj import Geod
from scipy.interpolate import LinearNDInterpolator, RegularGridInterpolator

GEOD = Geod(ellps="WGS84")
R = 6_371_000.0
K = 0.13
EYE = 1.6
LAMP = 0.7
MARFA = (-104.0206, 30.3095)             # courthouse area, used only to name travel direction
AIM_DEG = 0.5                            # assumed aim + load + suspension uncertainty (not a regulatory number)
DECAY = (0.04, 0.07, 0.12)               # dex per degree beyond the last measured |h|: low, central, high
MOR_KM = (50, 100, 200)                  # meteorological optical range cases (km)
SIRIUS = -1.46

# (h deg, + = right; v deg, + = up; candela)  -- report 108-CAN-17-004, sample LH1
UB2 = [(0, 0, 55311.55), (0, 2, 11100.53), (-3, 1, 17174.57), (3, 1, 22281.96),
       (-12, 0, 4373.91), (-9, 0, 7317.46), (-6, 0, 11745.75), (-3, 0, 22738.38),
       (3, 0, 27568.95), (6, 0, 10260.06), (9, 0, 5572.40), (12, 0, 2673.91),
       (-9, -1.5, 11761.32), (0, -1.5, 54966.94), (9, -1.5, 8139.44),
       (-12, -2.5, 7432.08), (0, -2.5, 23416.75), (12, -2.5, 4655.25),
       (0, -4, 7815.57), (0.2, -0.9, 75077.88)]
LB2V = [(0, 0, 5383.66), (-8, 4, 121.47), (8, 4, 96.50), (-4, 2, 248.55),
        (3, 1.5, 314.07), (2, 1.5, 367.76), (-2.2, 1, 549.55), (-1.7, 0.5, 1130.23),
        (2.9, 0.5, 475.73), (1, 0.5, 589.88), (-8, 0, 1998.15), (-4, 0, 3209.13),
        (1.3, -0.6, 21004.14), (-3.5, -0.9, 10314.14), (0, -0.9, 30683.04),
        (2, -1.5, 32466.67), (-15, -2, 5632.36), (-9, -2, 7206.03), (9, -2, 4299.25),
        (15, -2, 2407.33), (-20, -4, 2166.31), (0, -4, 4736.01), (4, -4, 4493.32),
        (20, -4, 1042.98), (0.3, -1.2, 36916.81), (-8, 10, 62.44)]
VSCALE = 4.0      # vertical gradients are much steeper than horizontal: interpolate in (h, 4v)


class Beam:
    """Measured beam on a regular (h, v) grid, interpolated in log10(I).

    Inside the convex hull of the test points: linear interpolation in (h, VSCALE*v).
    Outside it, each row of constant v is continued horizontally from its last in-hull
    value with a log-linear fall-off of `decay` dex per degree, and rows above or below
    the hull copy the nearest in-hull row. The fall-off beyond the measured angles is
    the least constrained part of the model, so it is run at three values (DECAY).
    """

    HG = np.arange(-90, 90.01, 0.25)
    VG = np.arange(-8, 12.01, 0.05)

    def __init__(self, pts, name):
        self.name = name
        p = np.array(pts, float)
        self.pts = p
        lin = LinearNDInterpolator(np.c_[p[:, 0], p[:, 1] * VSCALE], np.log10(p[:, 2]))
        hh, vv = np.meshgrid(self.HG, self.VG)
        self.core = lin(np.c_[hh.ravel(), vv.ravel() * VSCALE]).reshape(hh.shape)   # NaN outside hull
        self.grids = {}

    def grid(self, decay):
        if decay in self.grids:
            return self.grids[decay]
        g = self.core.copy()
        rows = np.where(~np.isnan(g).all(axis=1))[0]
        for i in rows:
            ok = np.where(~np.isnan(g[i]))[0]
            a, b = ok[0], ok[-1]
            g[i, :a] = g[i, a] - decay * (self.HG[a] - self.HG[:a])
            g[i, b + 1:] = g[i, b] - decay * (self.HG[b + 1:] - self.HG[b])
        for i in range(len(self.VG)):
            if np.isnan(g[i]).all():
                g[i] = g[rows[np.argmin(np.abs(rows - i))]]
        f = RegularGridInterpolator((self.VG, self.HG), g, bounds_error=False, fill_value=None)
        self.grids[decay] = f
        return f

    def __call__(self, h, v, decay=DECAY[1]):
        h, v = np.broadcast_arrays(np.asarray(h, float), np.asarray(v, float))
        vc = np.clip(v, self.VG[0], self.VG[-1])
        out = self.grid(decay)(np.c_[vc.ravel(), np.clip(h.ravel(), -90, 90)]).reshape(h.shape)
        out = np.where(np.abs(h) > 90, -np.inf, out)          # observer behind the car: no headlamp light
        return 10 ** out


HIGH, LOW = Beam(UB2, "upper beam (UB2)"), Beam(LB2V, "lower beam (LB2V)")


def hwy_class(kc, kc_far, farclr, k=K):
    """US-67 visibility class, identical to analysis/build_site_data.py:
    v = clearly visible, m = marginal (grazing or blocked only near the car), h = hidden."""
    if kc <= k:
        return "v" if farclr > 5 else "m"
    return "m" if kc_far <= k else "h"


def magnitude(E_lux):
    with np.errstate(divide="ignore"):
        return -13.99 - 2.5 * np.log10(E_lux)


def transmission(d_m, mor_km):
    return np.exp(-math.log(20) * d_m / (mor_km * 1000))


def wrap(a):
    return (a + 180) % 360 - 180


def smooth_series(x, s, half_m):
    """Least-squares slope dz/ds in a window of +-half_m along the road."""
    g = np.full(len(x), np.nan)
    for i in range(len(x)):
        m = np.abs(s - s[i]) <= half_m
        if m.sum() >= 3:
            g[i] = np.polyfit(s[m], x[m], 1)[0]
    return g


def road_geometry(lat, lon, z):
    """Chainage, heading (deg) and grade (dz/ds) in the sequence order of the points."""
    n = len(lat)
    s = np.zeros(n)
    for i in range(1, n):
        s[i] = s[i - 1] + GEOD.inv(lon[i - 1], lat[i - 1], lon[i], lat[i])[2]
    hd = np.zeros(n)
    for i in range(n):
        a, b = max(0, i - 2), min(n - 1, i + 2)
        hd[i] = GEOD.inv(lon[a], lat[a], lon[b], lat[b])[0] % 360
    grade = smooth_series(np.asarray(z, float), s, 250)
    return s, hd, grade


def evaluate(lat, lon, z, obs_z, viewer):
    """Per point, per direction: h, v and magnitudes for both beams (central, dim, bright)."""
    s, hd, grade = road_geometry(lat, lon, z)
    lat, lon, z = map(np.asarray, (lat, lon, z))
    az_cv, _, d = GEOD.inv(lon, lat, np.full_like(lon, viewer[0]), np.full_like(lat, viewer[1]))
    az_cv %= 360
    eps = np.degrees(((obs_z + EYE) - (z + LAMP)) / d - d * (1 - K) / (2 * R))
    # "toward Marfa" = the sequence direction in which the distance to Marfa shrinks
    dm = GEOD.inv(lon, lat, np.full_like(lon, MARFA[0]), np.full_like(lat, MARFA[1]))[2]
    seq_to_marfa = np.gradient(dm) < 0
    out = {}
    for label, sign in (("to_marfa", 1), ("from_marfa", -1)):
        forward = seq_to_marfa if sign == 1 else ~seq_to_marfa
        head = np.where(forward, hd, (hd + 180) % 360)
        pitch = np.degrees(np.arctan(np.where(forward, grade, -grade)))
        h = wrap(az_cv - head)
        v = eps - pitch
        res = {"heading": head, "h": h, "v": v, "pitch": pitch}
        for bname, beam in (("low", LOW), ("high", HIGH)):
            cands = [beam(h, v + dv, dec) for dv in (-AIM_DEG, 0, AIM_DEG) for dec in DECAY]
            I_c = beam(h, v, DECAY[1])
            I_lo, I_hi = np.min(cands, axis=0), np.max(cands, axis=0)
            T = transmission(d, MOR_KM[1])
            for tag, I in (("", I_c), ("_dim", I_lo), ("_bright", I_hi)):
                res[f"I_{bname}{tag}"] = I
                res[f"m_{bname}{tag}"] = magnitude(2 * I * T / d ** 2)
        out[label] = res
    return d, eps, out


def main():
    los = json.load(open("data/derived/los_results.json"))
    viewer, z0 = los["meta"]["viewer"], los["meta"]["z0"]
    F = los["hwy_fields"]
    hw = [dict(zip(F, r)) for r in los["hwy"]]
    nf = json.load(open("data/derived/los_near_far.json"))
    cls = {}
    for r, q in zip(los["hwy"], nf["rows"]):
        r, q = dict(zip(F, r)), dict(zip(nf["fields"], q))
        cls[round(r["ch_m"] / 1000, 2)] = hwy_class(r["kc07"], q["kc07_excl1000"], q["farclr_m_k013"])

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
        "beam_source": "NHTSA compliance report 108-CAN-17-004 (2016 Ford Focus S, LH VOR headlamp, sample LH1), "
                       "https://static.nhtsa.gov/odi/ctr/2017/TRTR-644737-2017-001.pdf",
        "magnitude": "m = -13.99 - 2.5 log10(E/lx)  (Schaefer 1993, Vistas in Astronomy 36:311)",
        "transmission": f"exp(-ln(20) d / MOR), MOR = {MOR_KM[1]} km (central); MOR definition WMO-No. 8",
        "k": K, "eye_m": EYE, "lamp_m": LAMP, "aim_deg": AIM_DEG, "decay_dex_per_deg": DECAY, "two_lamps": True,
        "fields": ["az", "km", "a_mrad", "kc", "cls", "dir", "heading", "h", "v",
                   "m_low", "m_low_dim", "m_low_bright", "m_high", "m_high_dim", "m_high_bright"]},
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
                                                      "m_high", "m_high_dim", "m_high_bright")], 1))
        export["roads"].append({"road": rd["road"], "key": rd["key"],
                                "lat": r2(rd["lat"], 5), "lon": r2(rd["lon"], 5), "pts": pts})
    json.dump(export, open("data/derived/headlights.json", "w"), separators=(",", ":"))

    # reference numbers for the notes
    print("\nReference: lamp pair straight on (h=v=0), MOR 100 km:")
    for km in (10, 20, 30, 40, 50):
        for bname, beam in (("low", LOW), ("high", HIGH)):
            I = float(beam(0, 0))
            print(f"  {km:3d} km {bname:4s} I={I:8.0f} cd  m={float(magnitude(2 * I * transmission(km * 1000, 100) / (km * 1000) ** 2)):5.1f}")
    return roads


if __name__ == "__main__":
    main()

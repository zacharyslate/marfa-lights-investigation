"""What one car on US-67 looks like from the Viewing Area, and how many are in view at once.

Input : data/derived/los2/photometry.npz (run_photometry.py)
Output: data/derived/los2/traffic_us67.json

A car driving US-67 between Shafter and the US-90 junction in Marfa is seen only on the stretches where its lamps
are in view (P_vis >= 0.5 at k = 0.13). Each stretch is a 'window': the light appears at one end, moves across the
view, and vanishes at the other end. For a car at constant speed u the window lasts L/u.

Occupancy: for a one-way flow q (vehicles per hour, Poisson arrivals) the number of cars in view is Poisson with
mean  N = q * L_view / u  (L_view = total in-view length). The fraction of time with at least one car in view is
1 - exp(-N). The number of appearances per hour is q * n_windows.

fwd = increasing TxDOT chainage = southbound on this route; rev = northbound (toward Marfa).
"""
from __future__ import annotations

import json
import os

import numpy as np

from . import dem
from .run_photometry import JUNCTION_LON, MARFA_LAT, SHAFTER_LAT, MOR_REF, MU_REF, F_REF
from . import photometry as P

LOS2 = os.path.join(dem.ROOT, "data", "derived", "los2")
STEP = 60.0
SPEEDS = (25.0, 30.0, 33.5)           # m/s; 30 m/s measured in the photographs (note 09); 33.5 m/s = 75 mph


def windows(chain, view):
    """Contiguous in-view runs along the road; returns list of (i0, i1) index pairs (inclusive) in chain order."""
    out, i0 = [], None
    for i in range(len(chain)):
        if view[i] and i0 is None:
            i0 = i
        gap = i + 1 < len(chain) and chain[i + 1] - chain[i] > 1.5 * STEP
        if i0 is not None and (not view[i] or gap or i == len(chain) - 1):
            i1 = i if view[i] else i - 1
            out.append((i0, i1))
            i0 = None
    return out


def main():
    z = np.load(os.path.join(LOS2, "photometry.npz"), allow_pickle=True)
    sel = (z["route"] == "US0067-KG") & (z["lat"] >= SHAFTER_LAT) & (z["lat"] <= MARFA_LAT) & (z["lon"] < JUNCTION_LON)
    idx = np.where(sel)[0]
    idx = idx[np.argsort(z["chain"][idx])]
    ch = z["chain"][idx] - z["chain"][idx].min()
    ml = float(P.m_lim(MU_REF, F_REF))
    res = dict(m_lim_ref=round(ml, 2), mor_km=MOR_REF, step_m=STEP, speeds_m_s=SPEEDS,
               road_km=round(float(ch.max() / 1000), 2))
    for dname, key, view, lab in (("rev", "low_p50", z["view_head"], "northbound (headlamps, low beam)"),
                                  ("fwd", "tail_max", z["view_rear"], "southbound (tail lamps, FMVSS maximum)")):
        vw = view[idx]
        m = z[f"m_{key}_{dname}_{int(MOR_REF)}"][idx]
        mh = z[f"m_high_p50_{dname}_{int(MOR_REF)}"][idx] if dname == "rev" else z[f"m_brake_min_{dname}_{int(MOR_REF)}"][idx]
        W = windows(ch, vw)
        if dname == "rev":
            W = W[::-1]                                     # northbound drives toward decreasing chainage
        lens = np.array([(b - a + 1) * STEP for a, b in W])
        L = float(lens.sum())
        wins = []
        for (a, b), Lw in zip(W, lens):
            s = slice(a, b + 1)
            wins.append(dict(ch0_km=round(float(ch[a] / 1000), 2), ch1_km=round(float(ch[b] / 1000), 2), L_m=float(Lw),
                             dist_km=round(float(z["dist"][idx][s].mean() / 1000), 2),
                             az=[round(float(z["az"][idx][s].min()), 3), round(float(z["az"][idx][s].max()), 3)],
                             el=[round(float(z["app_el"][idx][s].min()), 3), round(float(z["app_el"][idx][s].max()), 3)],
                             m_median=round(float(np.median(m[s])), 2),
                             m_alt_median=round(float(np.median(mh[s])), 2),
                             detect_frac=round(float(np.mean(m[s] <= ml)), 2)))
        # angular speed across the view while in view (deg/min) at 30 m/s
        az = z["az"][idx]
        daz = np.abs(np.gradient(az, ch))                   # deg per m of road
        w_ang = daz[vw] * 30.0 * 60
        rec = dict(label=lab, n_windows=len(W), L_view_km=round(L / 1000, 2),
                   window_m=dict(median=float(np.median(lens)), p10=float(np.percentile(lens, 10)),
                                 p90=float(np.percentile(lens, 90)), max=float(lens.max()), min=float(lens.min())),
                   first_last_km_along=[wins[0]["ch0_km"], wins[-1]["ch1_km"]] if wins else None,
                   dwell_s={str(u): dict(median=round(float(np.median(lens) / u), 1),
                                         total=round(float(L / u), 0),
                                         span=round(float(abs(ch[W[-1][1]] - ch[W[0][0]]) / u), 0) if W else None)
                            for u in SPEEDS},
                   N_per_10_veh_h={str(u): round(10 / 3600 * L / u, 3) for u in SPEEDS},
                   appearances_per_car=len(W),
                   azimuth_rate_deg_min=dict(median=round(float(np.median(w_ang)), 3),
                                             p90=round(float(np.percentile(w_ang, 90)), 3)),
                   detect_km=round(float(((m <= ml) & vw).sum() * STEP / 1000), 2),
                   windows=wins)
        res[dname] = rec
        print(lab, "windows", len(W), "L", L, "median window", np.median(lens), "dwell@30", L / 30)
    # AADT (TxDOT 2025, stations on this segment; both directions): mean one-way flow
    res["aadt_two_way"] = [1121, 1383]
    res["mean_one_way_veh_h"] = [round(a / 2 / 24, 1) for a in res["aadt_two_way"]]
    json.dump(res, open(os.path.join(LOS2, "traffic_us67.json"), "w"), indent=1)


if __name__ == "__main__":
    main()

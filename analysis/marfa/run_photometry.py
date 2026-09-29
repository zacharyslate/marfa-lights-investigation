"""Photometry v2 run: apparent magnitude and detectability of vehicle lamps on every road point in view.

Input : data/derived/los2/roads_lidar.npz (+ .json)  - v2 line-of-sight batch run for all TxDOT roads (60 m)
Output: data/derived/los2/photometry.npz, photometry.json (summary)

Per road point and direction of travel ('fwd' = increasing TxDOT chainage, 'rev' = opposite):
  h, v              viewing angles at the lamp (photometry.view_angles; vehicle pitch from the lidar grade)
  in view           P_vis >= 0.5 at k = 0.13 for the lamp's own mounting height (headlamp 0.66 m, rear lamps
                    0.86 m, high-mounted stop lamp 1.12 m); class v/m/h as in the site export
  magnitudes        low beam (UMTRI p25/p50/p75; wide-angle 'hold' and 'floor'), high beam (p25/p50/p75),
                    tail lamps and tail+stop+CHMSL (FMVSS 108 min / max), each at MOR 50, 100, 200 km
Detection threshold m_lim (Crumey 2014 eq. 54) on a grid of background mu and field factor F.

Run:  python -m marfa.run_photometry          (from analysis/)
"""
from __future__ import annotations

import json
import math
import os
import time

import numpy as np

from . import dem, geodesy as g, photometry as P

LOS2 = os.path.join(dem.ROOT, "data", "derived", "los2")
K_IDX, K = 1, 0.13
LAMP_HEAD, LAMP_REAR, LAMP_CHMSL = 0.66, 0.86, 1.12
# Meteorological optical range. The NPS Big Bend air profile (nps.gov/articles/airprofiles-bibe.htm) gives standard
# visual range: ~165 mi natural, ~90 mi average with present pollution, below ~55 mi on high-pollution days. Standard
# visual range is the Koschmieder range for a 2 % contrast threshold, SVR = 3.912/b_ext, whereas MOR is defined by 5 %
# transmission, MOR = ln(20)/b_ext = 2.996/b_ext; so MOR = 0.766 SVR: 55, 90, 165 mi -> 68, 111, 203 km.
MOR_FROM_SVR = math.log(20) / 3.912
MORS = tuple(round(mi * 1.609344 * MOR_FROM_SVR) for mi in (55, 90, 165))
MU = (20.5, 21.0, 21.5, 22.0)
F = (1.4, 2.0, 2.4, 4.0)
MU_REF, F_REF, MOR_REF = 21.0, 2.0, MORS[1]
SHAFTER_LAT, MARFA_LAT = 29.8195, 30.3095        # latitude window of US-67 between Shafter and the US-90 junction
JUNCTION_LON = -104.015                           # east of this US-67 runs concurrent with US-90 past the platform


def main():
    t0 = time.time()
    z = np.load(os.path.join(LOS2, "roads_lidar.npz"), allow_pickle=True)
    meta = json.load(open(os.path.join(LOS2, "roads_lidar.json")))
    lamps = meta["lamps"]
    jh, jr, jc = lamps.index(LAMP_HEAD), lamps.index(LAMP_REAR), lamps.index(LAMP_CHMSL)
    lon, lat = z["lon"], z["lat"]
    n = lon.size

    mosaic = dem.load("lidar")
    heading, grade = P.road_heading_grade(lon, lat, z["chain"], z["fid"], mosaic)
    # guard against unrealistic grades from a centreline that leaves the road prism (bridges, cuts)
    grade_raw = grade.copy()
    grade = np.clip(grade, -0.08, 0.08)

    R = g.normal_section_radius(0.5 * (lat + meta["viewer"][1]), z["az"])
    D, geo = z["D"][:, jh], z["geo_el"][:, jh]
    ang = P.view_angles(lon, lat, heading, grade, geo, D, R, k=K)

    pv = z["p_vis"][:, :, K_IDX]
    kcg = z["kc_clutter"][:, :, 0]
    def cls(j):
        p = pv[:, j]
        c = np.full(n, "m")
        c[(p >= 0.95) & (kcg[:, j] <= K)] = "v"
        c[p <= 0.05] = "h"
        c[np.isnan(p)] = "x"
        return c
    view_h, view_r, view_c = pv[:, jh] >= 0.5, pv[:, jr] >= 0.5, pv[:, jc] >= 0.5

    out = dict(lon=lon, lat=lat, route=z["route"], fid=z["fid"], chain=z["chain"], dist=z["dist"], az=z["az"],
               heading=heading, grade=grade, grade_raw=grade_raw, cls_head=cls(jh), cls_rear=cls(jr),
               view_head=view_h, view_rear=view_r, view_chmsl=view_c,
               app_el=z["app_el"][:, jh, K_IDX])
    for d in ("fwd", "rev"):
        h, v = ang[d]
        out[f"h_{d}"], out[f"v_{d}"] = h, v
        for mor in MORS:
            T = P.transmission(D, mor)
            s = T / D ** 2
            tag = f"{d}_{int(mor)}"
            for q in ("p25", "p50", "p75"):
                out[f"m_low_{q}_{tag}"] = P.magnitude(P.front_intensity(h, v, "low", q, "hold") * s)
                out[f"m_high_{q}_{tag}"] = P.magnitude(P.front_intensity(h, v, "high", q, "hold") * s)
            out[f"m_low_floor_{tag}"] = P.magnitude(P.front_intensity(h, v, "low", "p50", "floor") * s)
            for w in ("min", "max"):
                out[f"m_tail_{w}_{tag}"] = P.magnitude(P.rear_intensity(h, False, w) * s)
                # stop + CHMSL; the CHMSL counts only where the 1.12 m lamp is itself in view
                Ist = 2 * P.reg_lamp(P.TAIL, 180 - np.abs(h), w) + 2 * P.reg_lamp(P.STOP, 180 - np.abs(h), w)
                Ich = np.where(view_c, P.reg_lamp(P.CHMSL, 180 - np.abs(h), w), 0.0)
                out[f"m_brake_{w}_{tag}"] = P.magnitude(np.where(np.abs(h) > 90, Ist + Ich, 0.0) * s)
    np.savez_compressed(os.path.join(LOS2, "photometry.npz"), **out)

    # ------------------------------------------------------------------ summaries
    mlim = {f"{mu}_{f}": float(P.m_lim(mu, f)) for mu in MU for f in F}
    ml_ref = float(P.m_lim(MU_REF, F_REF))
    us67 = (z["route"] == "US0067-KG") & (lat >= SHAFTER_LAT) & (lat <= MARFA_LAT) & (lon < JUNCTION_LON)
    step = 60.0
    summ = dict(generated=time.strftime("%Y-%m-%d"), seconds=round(time.time() - t0),
                k=K, lamps=dict(head=LAMP_HEAD, rear=LAMP_REAR, chmsl=LAMP_CHMSL), mor_km=MORS,
                m_lim=mlim, m_lim_ref=dict(mu=MU_REF, F=F_REF, value=ml_ref),
                grade_clipped=int((np.abs(grade_raw) > 0.08).sum()),
                note="fwd = direction of increasing TxDOT chainage (northbound on US-67); lengths in km of road "
                     "(60 m samples) in view (P_vis >= 0.5) and brighter than m_lim")
    rows = {}
    for d in ("fwd", "rev"):
        for key, vw in (("low_p25", view_h), ("low_p50", view_h), ("low_p75", view_h), ("low_floor", view_h),
                        ("high_p50", view_h), ("tail_min", view_r), ("tail_max", view_r),
                        ("brake_min", view_r), ("brake_max", view_r)):
            m = out[f"m_{key}_{d}_{int(MOR_REF)}"]
            sel = us67 & vw & np.isfinite(m) & (m < 30)
            rec = dict(km_in_view=round(float((us67 & vw & ((np.abs(out[f'h_{d}']) <= 90) if key.startswith(('low', 'high'))
                                                          else (np.abs(out[f'h_{d}']) > 90))).sum() * step / 1000), 2),
                       km_detect_ref=round(float((sel & (m <= ml_ref)).sum() * step / 1000), 2),
                       m_median=round(float(np.median(m[sel])), 2) if sel.any() else None,
                       m_min=round(float(np.min(m[sel])), 2) if sel.any() else None,
                       m_max=round(float(np.max(m[sel])), 2) if sel.any() else None)
            # bracket over MOR, background and field factor: [least favourable, most favourable]
            lo = (us67 & vw & (out[f"m_{key}_{d}_{int(MORS[0])}"] <= P.m_lim(20.5, 4.0))).sum() * step / 1000
            hi = (us67 & vw & (out[f"m_{key}_{d}_{int(MORS[-1])}"] <= P.m_lim(22.0, 1.4))).sum() * step / 1000
            rec["km_detect_bracket"] = [round(float(lo), 2), round(float(hi), 2)]
            rows[f"{d}:{key}"] = rec
    summ["us67"] = rows
    hv = us67 & view_h
    summ["us67_angles"] = {d: dict(h_median=round(float(np.median(out[f"h_{d}"][hv])), 1),
                                   h_p5_p95=[round(float(np.percentile(out[f"h_{d}"][hv], q)), 1) for q in (5, 95)],
                                   v_median=round(float(np.median(out[f"v_{d}"][hv])), 2),
                                   v_p5_p95=[round(float(np.percentile(out[f"v_{d}"][hv], q)), 2) for q in (5, 95)])
                           for d in ("fwd", "rev")}
    summ["us67_grade"] = dict(median_abs=round(float(np.median(np.abs(grade[hv]))), 4),
                              p95_abs=round(float(np.percentile(np.abs(grade[hv]), 95)), 4),
                              n_clipped=int((us67 & (np.abs(grade_raw) > 0.08)).sum()))
    summ["us67_dist_km"] = [round(float(z["dist"][hv].min() / 1000), 1), round(float(z["dist"][hv].max() / 1000), 1)]
    json.dump(summ, open(os.path.join(LOS2, "photometry.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1)[:6000])


if __name__ == "__main__":
    main()

"""Write the derived line-of-sight files used by the website, the headlight model and the figures, from the v2
engine (analysis/marfa), in the schemas the downstream scripts already read:

    data/derived/los_results.json     US-67 (Shafter end -> Marfa, 60 m), skyline 215-285 deg, 45 km profiles
    data/derived/los_near_far.json    far-field diagnostics for the same points
    data/derived/panorama_los.json    skyline 140-300 deg, towers, airfields, towns, cell sites, rail
    data/derived/roads_los.json       state roads (TxDOT), 120 m
    data/derived/profiles_fig.json    80 km ground profiles for the figures

Conventions (v2): reference headlamp 0.66 m (field names such as kc07 are kept for compatibility; meta.lamp_m
says which height was used), eye 1.6 m above the lidar surface of the platform, k = 0.13, NAVD88 -> ellipsoid
with GEOID12B, WGS84 geodesics, terrain = USGS 1 m lidar DEM (else 1/3", else 1") plus point-cloud obstructions
('dense') where measured.

US-67 classes (replace the old 'far clearance > 5 m' rule):
    v  robustly visible: Monte Carlo P_vis >= 0.95 AND still visible with 0.25 m of unresolved grass cover
    h  hidden:           P_vis <= 0.05
    m  marginal:         everything else
    python -m marfa.export_site [--skip-sky]
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import time

import numpy as np

from . import dem, geodesy as g, los, targets
from .run_los import OUT as LOS2, observer, mc_params

ROOT = dem.ROOT
DER = os.path.join(ROOT, "data", "derived")
LAMP, LAMP_HI, K = 0.66, 2.5, 0.13
HAND_SOUTH = (-104.306842, 29.817561)     # south end of the old hand-traced US-67 segment (near Shafter)
_G = {}


def _init():
    from .obstruction import ObstructionLayer
    dem.CACHE.max = 1.0e9
    m = dem.load("lidar")
    _G.update(m=m, obs=observer(m), ob=ObstructionLayer("dense"), mc=mc_params(m))


def _hwy_point(args):
    lon, lat = args
    obs, m, ob = _G["obs"], _G["m"], _G["ob"]
    r = los.sightline_multi(obs, m, lon, lat, lamps=(LAMP, LAMP_HI), ks=(K,), clutter=(0.25,), obstruction=ob,
                            mc=_G["mc"], return_profile=True)
    D, R = r["D"][0], r["R"]
    ex = r["y"] - K * r["denom"] / (2 * R)
    i_occ = int(np.argmax(ex * D / r["s"]))
    f = los.sightline_multi(obs, m, lon, lat, lamps=(LAMP,), ks=(K,), skip_tgt=1000.0, obstruction=ob,
                            return_profile=True)
    exf = f["y"] - K * f["denom"] / (2 * R)
    i_f = int(np.argmax(exf * f["D"][0] / f["s"]))
    p, kc_g = float(r["p_vis"][0, 0]), float(r["kc_clutter"][0, 0])
    cls = "v" if (p >= 0.95 and kc_g <= K) else ("h" if p <= 0.05 else "m")
    return dict(zT=r["target_H"], kc07=float(r["k_crit"][0]), kc25=float(r["k_crit"][1]),
                alpha=float(np.radians(r["app_el"][0, 0]) * 1000), clear=-float(r["dL"][0, 0]),
                occ_km=float(r["s"][i_occ] / 1000), kcd_km=float(r["lim_s"][0] / 1000), az=r["az"], dist=r["dist"],
                kc_far=float(f["k_crit"][0]), farclr=-float(f["dL"][0, 0]), far_occ_km=float(f["s"][i_f] / 1000),
                p_vis=p, kc_grass=kc_g, dE=float(r["dE"][0, 0]), cls=cls)


def _point(args):
    """LOS to a light `lamp` m above the ground at lon/lat (towers, towns, airfields, cells, rail)."""
    lon, lat, lamp = args
    try:
        r = los.sightline_multi(_G["obs"], _G["m"], lon, lat, lamps=(lamp,), ks=(K,), obstruction=_G["ob"])
    except ValueError:
        return None
    return dict(az=round(r["az"], 2), d=round(r["dist"] / 1000, 2), zg=round(r["target_H"]),
                a=round(float(np.radians(r["app_el"][0, 0]) * 1000), 2), kc=round(float(r["k_crit"][0]), 3),
                clr=round(-float(r["dL"][0, 0]), 1))


def _sky(az):
    r = los.skyline(_G["obs"], _G["m"], az, dmax=120_000.0, step=30.0, k=K, dmin=30.0, strict=False)
    mr = lambda d: round(float(np.radians(d) * 1000), 2)
    return [round(float(az), 1), mr(r["el"]), round(r["dist"] / 1000, 1),
            mr(r["layers"][10_000]), mr(r["layers"][25_000]), mr(r["layers"][45_000])]


def _profile(args):
    az, dmax, step = args
    s = np.arange(0, dmax + step / 2, step)
    lo, la, _ = g.GEOD.fwd(np.full_like(s, targets.VIEWER[0]), np.full_like(s, targets.VIEWER[1]),
                           np.full_like(s, az), s)
    H, _ = _G["m"].sample(np.asarray(lo), np.asarray(la), strict=False)
    return [None if np.isnan(h) else round(float(h), 1) for h in H]


def hwy_points(spacing=60.0):
    u = targets.us67_south(spacing)
    _, d = g.inv(np.full(u["lon"].size, HAND_SOUTH[0]), np.full(u["lon"].size, HAND_SOUTH[1]), u["lon"], u["lat"])
    i_s = int(np.argmin(d))
    keep = np.arange(0, i_s + 1)[::-1]                  # from the Shafter end north to Marfa
    ch = (u["km_from_marfa"][i_s] - u["km_from_marfa"][keep]) * 1000
    return u["lon"][keep], u["lat"][keep], ch


def entities():
    """Towers (ASR), towns, airfields (OurAirports) and cell sites (FCC ULS) within 90 km, with lamp heights."""
    V = targets.VIEWER
    out = []
    asr = json.load(open(os.path.join(ROOT, "data", "inputs", "fcc_asr.json")))
    for asrn, lat, lon, site_m, agl, *_ in asr["towers"]:
        out.append(("tower", asrn, lon, lat, float(agl)))            # obstruction light at the top
    for name, lat, lon in [("Marfa", 30.31056, -104.02556), ("Alpine", 30.37222, -103.66667),
                           ("Fort Davis", 30.59667, -103.88083), ("Shafter", 29.82028, -104.30333),
                           ("Presidio", 29.56139, -104.36639), ("Ojinaga, Chihuahua", 29.56444, -104.41639)]:
        out.append(("town", name, lon, lat, 8.0))                    # street-light height
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "inputs", "airports.csv"), encoding="utf-8")):
        try:
            lat, lon = float(r["latitude_deg"]), float(r["longitude_deg"])
        except ValueError:
            continue
        if abs(lat - V[1]) > 1 or abs(lon - V[0]) > 1:
            continue
        out.append(("field", r["ident"], lon, lat, 5.0))              # hangar / apron light
    web = json.load(open(os.path.join(ROOT, "data", "inputs", "web_layers.json")))
    seen = set()
    for sid, lic, call, lat, lon, addr, city, asrn, sup, allh, st, ls in web["cell"]:
        key = addr[:20]
        if key in seen:
            continue
        seen.add(key)
        out.append(("cell", key, lon, lat, float(allh or sup or 30.0)))
    res = []
    for k, i, lon, lat, h in out:
        _, d = g.inv(V[0], V[1], lon, lat)
        if d <= 90_000:
            res.append((k, i, lon, lat, h))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-sky", action="store_true")
    ap.add_argument("--procs", type=int, default=2)
    a = ap.parse_args()
    t0 = time.time()
    _init()
    obs = _G["obs"]
    meta_common = dict(engine="analysis/marfa (v2)", dem="USGS 3DEP 1 m lidar (TX_WestTexas_2018_D19), else 1/3\", "
                       "else 1\"; point-cloud obstructions (dense) where measured; see data/dem/MANIFEST.json",
                       geoid="GEOID12B", viewer=list(targets.VIEWER), z0=obs.ground_H, eye=obs.eye, lamp_m=LAMP,
                       kstd=K, sample_step_m="2 m within 3 km of either end, else 5 m", excl_start_m=5,
                       excl_end_m=3, generated=time.strftime("%Y-%m-%d"))
    pool = mp.get_context("fork").Pool(a.procs, initializer=_init)   # each worker opens its own rasters

    # ---- US-67
    lon, lat, ch = hwy_points()
    R = pool.map(_hwy_point, list(zip(lon, lat)), chunksize=8)
    print("hwy", len(R), f"{time.time() - t0:.0f} s", flush=True)
    F = ["ch_m", "lon", "lat", "zT", "kc07", "kc25", "alpha_mrad_k013_h07", "clear_m_k013_h07", "occluder_km_k013",
         "kcd07_km", "az", "dist_m", "p_vis", "kc_grass025", "eye_margin_m", "cls"]
    hwy = [[round(float(c)), round(float(x), 6), round(float(y), 6), round(r["zT"], 2), round(r["kc07"], 4),
            round(r["kc25"], 4), round(r["alpha"], 3), round(r["clear"], 2), round(r["occ_km"], 3),
            round(r["kcd_km"], 3), round(r["az"], 4), round(r["dist"]), round(r["p_vis"], 3), round(r["kc_grass"], 4),
            round(r["dE"], 2), r["cls"]] for c, x, y, r in zip(ch, lon, lat, R)]
    NF = ["ch_m", "kc07_excl60", "kc07_excl1000", "farclr_m_k013", "far_occluder_km", "lon", "lat", "zT", "az",
          "dist_m", "alpha_mrad", "kc25", "clr_all"]
    nf = [[round(float(c)), round(r["kc07"], 4), round(r["kc_far"], 4), round(r["farclr"], 2), round(r["far_occ_km"], 3),
           round(float(x), 6), round(float(y), 6), round(r["zT"], 2), round(r["az"], 4), round(r["dist"]),
           round(r["alpha"], 4), round(r["kc25"], 4), round(r["clear"], 3)] for c, x, y, r in zip(ch, lon, lat, R)]

    # ---- skyline 140-300 deg at 0.1 deg (panorama) and profiles
    sky = []
    if not a.skip_sky:
        sky = pool.map(_sky, list(np.round(np.arange(140.0, 300.05, 0.1), 1)), chunksize=16)
        print("sky", len(sky), f"{time.time() - t0:.0f} s", flush=True)
    prof45 = dict(zip(["235", "240", "250", "260", "270", "277", "229.5", "234"],
                      pool.map(_profile, [(float(z), 45_000.0, 250.0) for z in
                                          ["235", "240", "250", "260", "270", "277", "229.5", "234"]])))
    prof80 = dict(zip(["190", "240", "262", "233.6", "255.6"],
                      pool.map(_profile, [(float(z), 80_000.0, 100.0) for z in ["190", "240", "262", "233.6", "255.6"]])))

    # ---- towers, towns, airfields, cell sites
    ents = entities()
    E = pool.map(_point, [(x, y, h) for _, _, x, y, h in ents], chunksize=4)
    towers, pts = [], []
    for (k, i, x, y, h), r in zip(ents, E):
        row = dict(k=k, id=i, lamp_m=h, **(r or {}))
        (towers if k == "tower" else pts).append(row)
    print("entities", len(ents), f"{time.time() - t0:.0f} s", flush=True)

    # ---- rail (from the batch run: lamps 1.2 and 4.0 m), every 2nd point = 120 m
    rail = []
    rp = os.path.join(LOS2, "rail_lidar.npz")
    if os.path.exists(rp):
        z = np.load(rp, allow_pickle=True)
        for i in range(0, z["lon"].size, 2):
            if np.isnan(z["k_crit"][i, 1]):
                continue
            rail.append([str(z["owner"][i]), round(float(z["lat"][i]), 5), round(float(z["lon"][i]), 5),
                         round(float(z["az"][i]), 2), round(float(z["dist"][i]) / 1000, 2),
                         round(float(np.radians(z["app_el"][i, 1, 1]) * 1000), 2), round(float(z["k_crit"][i, 1]), 3)])

    # ---- state roads (from the batch run), 120 m
    roads = []
    rp = os.path.join(LOS2, "roads_lidar.npz")
    if os.path.exists(rp):
        z = np.load(rp, allow_pickle=True)
        jl = json.load(open(rp[:-4] + ".json"))["lamps"].index(LAMP)
        names = ["RM2810-KG", "FM0170-KG", "SH0118-KG", "US0090-KG", "RM0169-KG", "US0067-KG", "FM1112-KG", "SH0017-KG"]
        for nm in names:
            idx = np.where((z["route"] == nm) & (z["roadbed"] == "Single Roadbed"))[0]
            idx = idx[(z["dist"][idx] >= 300) & (z["dist"][idx] <= 90_000)]
            az = z["az"][idx]
            idx = idx[(az >= 140) & (az <= 300)][::2]
            if not idx.size:
                continue
            roads.append({"r": nm, "p": [[round(float(z["lat"][i]), 5), round(float(z["lon"][i]), 5),
                                          round(float(z["az"][i]), 2), round(float(z["dist"][i]) / 1000, 2),
                                          round(float(np.radians(z["app_el"][i, jl, 1]) * 1000), 2),
                                          round(float(z["k_crit"][i, jl]), 3), round(float(z["target_H"][i]))]
                                         for i in idx if not np.isnan(z["k_crit"][i, jl])]})
    pool.close()

    sky_old = [[s[0], s[1], s[2]] for s in sky if 215 <= s[0] <= 285]
    json.dump(dict(meta=dict(meta_common, hwy_step_m=60, earth_R="WGS84 normal-section radius",
                             classes="v: P_vis>=0.95 and visible with 0.25 m grass; h: P_vis<=0.05; m: otherwise",
                             hwy_note="TxDOT US0067-KG centreline, from the Shafter end (ch 0) north to the US-90 "
                                      "junction in Marfa; clear_m = lamp-height margin (m); eye_margin_m = eye-height "
                                      "change that flips visibility"),
                   hwy_fields=F, hwy=hwy, sky=sky_old, prof=prof45),
              open(os.path.join(DER, "los_results.json"), "w"), separators=(",", ":"))
    json.dump(dict(meta=dict(meta_common, note="kc07_excl60 is now the main k_crit (3 m end exclusion; lidar resolves "
                                                "the road prism); kc07_excl1000 ignores terrain within 1 km of the car"),
                   fields=NF, rows=nf), open(os.path.join(DER, "los_near_far.json"), "w"), separators=(",", ":"))
    json.dump(dict(_meta=dict(meta_common,
                              sky="az 140-300 deg true at 0.1 deg; skyline mrad (k=0.13), distance km, max angle "
                                  "within 10/25/45 km; terrain to 120 km (1\" beyond the lidar)",
                              rail="owner, lat, lon, az, km, apparent mrad, k_crit for a 4 m locomotive headlight",
                              lamps="tower: height AGL of the structure; town 8 m; airfield 5 m; cell: structure height"),
                   sky=sky, towers=towers, pts=pts, rail=rail),
              open(os.path.join(DER, "panorama_los.json"), "w"), separators=(",", ":"))
    json.dump(dict(src="TxDOT Roadways FeatureServer, EXT_DATE 09-01-2026 (data/inputs/txdot_roadways_bigbend.geojson)",
                   fields=["lat", "lon", "az", "km", "a_mrad_k013_h07", "kc_h07", "zg"], roads=roads,
                   meta=dict(meta_common, resample_m=120, note="kc_h07/a_mrad are for the 0.66 m reference lamp")),
              open(os.path.join(DER, "roads_los.json"), "w"), separators=(",", ":"))
    json.dump(dict(meta=dict(step_m=100, z0=obs.ground_H, note="ground elevation (m NAVD88) every 100 m along the "
                             "given true azimuths from the viewer; USGS 1 m lidar, else 1/3\", else 1\""), prof=prof80),
              open(os.path.join(DER, "profiles_fig.json"), "w"), separators=(",", ":"))
    print("done", f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()

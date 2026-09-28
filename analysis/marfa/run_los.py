"""Batch line-of-sight runs: every target point x every lamp height x every refraction coefficient.

    python -m marfa.run_los us67  --dem lidar          # reference run for US-67
    python -m marfa.run_los roads --dem lidar --spacing 60
    python -m marfa.run_los us67  --dem 13s --skip-tgt 60   # comparison with the old configuration

Results go to data/derived/los2/<set>_<dem>[_tag].npz with a JSON sidecar describing every column."""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time

import numpy as np

from . import dem, geodesy as g, los, targets

OUT = os.path.join(dem.ROOT, "data", "derived", "los2")
LAMPS = (0.56, 0.66, 0.86, 1.12, 1.37, 2.5, 4.0)   # FMVSS 108 headlamp limits 0.56-1.37 m; 0.66, 0.86, 1.12 m are mounting heights tested by Akashi et al. 2008 (DOT HS 810 947); 2.5 and 4.0 m truck cab/clearance lamps
KS = (0.0, 0.13, 0.25, 0.5, 1.0)
EYE = 1.6
CLUTTER = (0.25, 0.5, 1.0)          # m of shrubs/fences/signs added to the bare-earth terrain (bounding case)
# terrain error model per DEM source: lidar from the USGS NVA test (RMSEz 5.6 cm, data/dem/lidar_accuracy.txt);
# 1/3" and 1" from their measured differences to the lidar (data/derived/los2/dem_error.json)
ERR = {"1M": (0.056, 20.0), "USGS_13": (0.56, 70.0), "USGS_1_": (2.05, 125.0)}
EYE_SD = 0.15                       # observer eye-height spread (m): people and where they stand on the platform
MC_N = 200

_G = {}


def observer(mosaic, eye=EYE, geoid=None):
    geoid = geoid or g.Geoid(dem.GEOID_GRID)
    H, _ = mosaic.sample(np.array([targets.VIEWER[0]]), np.array([targets.VIEWER[1]]))
    return los.Observer(targets.VIEWER[0], targets.VIEWER[1], float(H[0]), eye=eye, geoid=geoid)


def mc_params(mosaic, n=MC_N, eye_sd=EYE_SD, seed=0):
    sig, cor = [], []
    for name in mosaic.names:
        key = next(k for k in ERR if k in name)
        sig.append(ERR[key][0]); cor.append(ERR[key][1])
    return dict(n=n, sigma=sig, corr=cor, eye_sd=eye_sd, seed=seed)


def _init(level, eye, cache_bytes, use_mc, obstr=None):
    dem.CACHE.max = cache_bytes
    m = dem.load(level)
    ob = None
    if obstr:
        from .obstruction import ObstructionLayer
        ob = ObstructionLayer(obstr)
    _G.update(m=m, obs=observer(m, eye), mc=mc_params(m) if use_mc else None, ob=ob)


def _work(args):
    lon, lat, kw = args
    try:
        return los.sightline_multi(_G["obs"], _G["m"], lon, lat, mc=_G["mc"], obstruction=_G["ob"], **kw)
    except ValueError as e:
        return {"error": str(e)}


def run(lon, lat, level="lidar", lamps=LAMPS, ks=KS, eye=EYE, procs=2, cache_bytes=1.2e9, clutter=CLUTTER,
        use_mc=True, obstruction=None, **kw):
    kw = dict(lamps=tuple(lamps), ks=tuple(ks), clutter=tuple(clutter), **kw)
    n, nL, nK, nC = len(lon), len(lamps), len(ks), len(clutter)
    cols = dict(az=np.full(n, np.nan), dist=np.full(n, np.nan), target_H=np.full(n, np.nan),
                target_src=np.full(n, -1), k_crit=np.full((n, nL), np.nan), lim_s=np.full((n, nL), np.nan),
                lim_src=np.full((n, nL), -1), D=np.full((n, nL), np.nan), geo_el=np.full((n, nL), np.nan),
                clr=np.full((n, nL, nK), np.nan), dL=np.full((n, nL, nK), np.nan),
                dE=np.full((n, nL, nK), np.nan), app_el=np.full((n, nL, nK), np.nan),
                kc_clutter=np.full((n, nL, nC), np.nan), p_vis=np.full((n, nL, nK), np.nan),
                obstruction_max=np.full(n, np.nan))
    t0 = time.time()
    errors = []
    with mp.get_context("fork").Pool(procs, initializer=_init, initargs=(level, eye, cache_bytes, use_mc, obstruction)) as pool:
        for i, r in enumerate(pool.imap(_work, [(lon[i], lat[i], kw) for i in range(n)], chunksize=16)):
            if "error" in r:
                errors.append((i, r["error"]))
                continue
            for k in cols:
                if k in r:
                    cols[k][i] = r[k]
            if i and i % 2000 == 0:
                print(f"  {i}/{n}  {time.time() - t0:.0f} s", flush=True)
    return cols, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("set", choices=["us67", "roads", "rail"])
    ap.add_argument("--dem", default="lidar", choices=["lidar", "13s", "1s"])
    ap.add_argument("--spacing", type=float, default=None)
    ap.add_argument("--skip-tgt", type=float, default=3.0)
    ap.add_argument("--skip-obs", type=float, default=5.0)
    ap.add_argument("--fine", type=float, default=2.0)
    ap.add_argument("--coarse", type=float, default=5.0)
    ap.add_argument("--eye", type=float, default=EYE)
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="only the first N points (testing)")
    ap.add_argument("--tag", default="")
    ap.add_argument("--no-mc", action="store_true")
    ap.add_argument("--obstruction", choices=["dense", "max"], default=None)
    a = ap.parse_args()

    if a.set == "us67":
        t = targets.us67_south(a.spacing or 30.0)
    elif a.set == "roads":
        t = targets.roads(a.spacing or 60.0)
    else:
        t = targets.rail(a.spacing or 60.0)
    lon, lat = t["lon"], t["lat"]
    if a.limit:
        lon, lat = lon[:a.limit], lat[:a.limit]
    lamps = (1.2, 4.0) if a.set == "rail" else LAMPS     # locomotive ditch lights ~1.2 m, headlight ~4 m
    print(f"{a.set}: {len(lon)} points, DEM {a.dem}")
    t0 = time.time()
    cols, errors = run(lon, lat, level=a.dem, lamps=lamps, eye=a.eye, procs=a.procs, skip_tgt=a.skip_tgt,
                       skip_obs=a.skip_obs, fine=a.fine, coarse=a.coarse, use_mc=not a.no_mc, obstruction=a.obstruction)
    os.makedirs(OUT, exist_ok=True)
    name = f"{a.set}_{a.dem}" + (f"_{a.tag}" if a.tag else "")
    extra = {k: v[:len(lon)] for k, v in t.items() if k not in ("lon", "lat") and len(v) >= len(lon)}
    np.savez_compressed(os.path.join(OUT, name + ".npz"), lon=lon, lat=lat, **cols, **extra)
    m = dem.load(a.dem)
    obs = observer(m, a.eye)
    meta = dict(set=a.set, dem=a.dem, dem_sources=m.names, n=len(lon), lamps=list(lamps), ks=list(KS),
                viewer=list(targets.VIEWER), viewer_ground_H=obs.ground_H, eye=a.eye, geoid_N=obs.N,
                skip_obs=a.skip_obs, skip_tgt=a.skip_tgt, fine=a.fine, coarse=a.coarse, fine_zone=3000.0,
                spacing=a.spacing, clutter=list(CLUTTER), obstruction=a.obstruction, mc=None if a.no_mc else mc_params(m),
                seconds=round(time.time() - t0), errors=errors[:50], n_errors=len(errors),
                columns=dict(
                    az="geodesic azimuth viewer->target (deg true)", dist="geodesic distance (m)",
                    target_H="DEM ground height at the target (NAVD88 m)",
                    target_src="index into dem_sources of the raster that supplied target_H",
                    k_crit="[point, lamp] refraction coefficient above which the lamp is visible",
                    lim_s="[point, lamp] distance from the viewer of the limiting terrain sample (m)",
                    lim_src="[point, lamp] DEM source index of the limiting sample",
                    D="[point, lamp] chord length (m)", geo_el="[point, lamp] chord elevation at the eye (deg)",
                    clr="[point, lamp, k] clearance of the ray over the terrain (m, <0 = blocked)",
                    dL="[point, lamp, k] lamp-height change that flips visibility (m; <0: margin to spare)",
                    dE="[point, lamp, k] eye-height change that flips visibility (m; <0: margin to spare)",
                    app_el="[point, lamp, k] apparent elevation (deg)",
                    kc_clutter="[point, lamp, clutter] k_crit with clutter m added to terrain >10 m from both ends",
                    p_vis="[point, lamp, k] Monte Carlo probability of visibility (terrain + eye-height errors)"))
    json.dump(meta, open(os.path.join(OUT, name + ".json"), "w"), indent=1)
    print(f"done in {time.time() - t0:.0f} s, {len(errors)} errors -> {name}")


if __name__ == "__main__":
    main()

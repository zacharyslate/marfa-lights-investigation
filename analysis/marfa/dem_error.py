"""Empirical error model of the 1/3" and 1" DEMs, using the 1 m lidar DEM as reference.

Random points inside the lidar footprints give the bias and standard deviation of (coarse - lidar); pairs of
points along random transects give the semivariogram of the difference, from which a correlation length is
fitted (exponential model gamma(h) = s^2 (1 - exp(-h/L))). These feed the Monte Carlo terrain perturbations."""
from __future__ import annotations

import json
import os

import numpy as np

from . import dem, geodesy as g


def run(n_pts=40000, n_lines=300, line_len=3000.0, step=10.0, seed=0):
    rng = np.random.default_rng(seed)
    lid = dem.load("lidar")
    lidar_only = dem.Mosaic([r for r in lid.rasters if "1M" in r.name])
    m13 = dem.Mosaic([r for r in lid.rasters if "USGS_13" in r.name])
    m1 = dem.Mosaic([r for r in lid.rasters if "USGS_1_" in r.name])
    fps = [r.fp for r in lidar_only.rasters]
    # random points: pick a tile, then a point in it
    t = rng.integers(0, len(fps), n_pts)
    lo = np.array([rng.uniform(fps[i][0], fps[i][2]) for i in t])
    la = np.array([rng.uniform(fps[i][1], fps[i][3]) for i in t])
    zl, _ = lidar_only.sample(lo, la, strict=False)
    z13, _ = m13.sample(lo, la, strict=False)
    z1, _ = m1.sample(lo, la, strict=False)
    ok = ~np.isnan(zl) & ~np.isnan(z13) & ~np.isnan(z1)
    out = {"n_points": int(ok.sum())}
    for name, z in (("13s", z13), ("1s", z1)):
        d = (z - zl)[ok]
        out[name] = dict(bias=float(np.mean(d)), sd=float(np.std(d)), mad_sd=float(1.4826 * np.median(np.abs(d - np.median(d)))),
                         p01=float(np.percentile(d, 1)), p99=float(np.percentile(d, 99)))
    # variogram along random transects
    lags = np.arange(step, 1500 + step, step)
    for name, mm in (("13s", m13), ("1s", m1)):
        acc = np.zeros(lags.size); cnt = np.zeros(lags.size)
        for _ in range(n_lines):
            i = rng.integers(0, len(fps))
            x0, y0 = rng.uniform(fps[i][0], fps[i][2]), rng.uniform(fps[i][1], fps[i][3])
            az = rng.uniform(0, 360)
            s = np.arange(0, line_len, step)
            lo_, la_, _ = g.GEOD.fwd(np.full_like(s, x0), np.full_like(s, y0), np.full_like(s, az), s)
            a, _ = lidar_only.sample(np.asarray(lo_), np.asarray(la_), strict=False)
            b, _ = mm.sample(np.asarray(lo_), np.asarray(la_), strict=False)
            d = b - a
            for j, L in enumerate(lags):
                k = int(L / step)
                e = d[k:] - d[:-k]
                e = e[~np.isnan(e)]
                acc[j] += np.sum(e ** 2) / 2; cnt[j] += e.size
        gam = acc / np.maximum(cnt, 1)
        # fit exponential model by grid search on L with sill = var of point differences
        sill = out[name]["sd"] ** 2
        Ls = np.arange(5, 1000, 5.0)
        err = [np.sum((gam - sill * (1 - np.exp(-lags / L))) ** 2) for L in Ls]
        out[name]["corr_len_m"] = float(Ls[int(np.argmin(err))])
        out[name]["variogram"] = dict(lag_m=lags[::5].tolist(), gamma_m2=gam[::5].round(4).tolist())
    return out


if __name__ == "__main__":
    res = run()
    p = os.path.join(dem.ROOT, "data", "derived", "los2", "dem_error.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(res, open(p, "w"), indent=1)
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "variogram"})
                      for k, v in res.items()}, indent=1))

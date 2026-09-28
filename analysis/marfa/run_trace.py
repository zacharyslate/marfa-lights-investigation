"""Ray tracing US-67 sightlines through night-time temperature profiles (height-dependent refraction).

    python -m marfa.run_trace --every 4        # every 4th US-67 point (120 m spacing)

Scenarios (dT/dz as a function of height above local ground a, in K/m; see raytrace.py):
  neutral      lapse -0.0098 K/m (well-mixed; reproduces constant k = 0.13)
  isothermal   0 K/m
  sbl_weak     exponential SBL, 3 K over e-folding depth 50 m   (windy or partly cloudy night)
  sbl_mod      6 K over 30 m                                    (clear, light wind)
  sbl_strong   10 K over 20 m                                   (clear, calm; surface gradient 0.5 K/m)
  cap_40m      mixed below 40 m, 4 K inversion between 40 and 60 m above ground (elevated inversion)
These are bracketing cases, not a climatology: the near-surface inversion over the Marfa plateau has not been
measured (that is experiment E2). Surface gradients of 0.05-0.5 K/m used here are within the range Hirt et al.
(2010) observed at 1.8 m over grass (up to 1-2 K/m shortly after sunset).
Output: data/derived/los2/trace_us67.npz with, per point and scenario, the number of images, the apparent
elevation of each image (deg; up to 3) and the equivalent constant k of the primary image."""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time

import numpy as np

from . import dem, los, raytrace as rt, targets
from .run_los import OUT, observer

SCEN = {
    "neutral": rt.lapse(-0.0098),
    "isothermal": rt.lapse(0.0),
    "sbl_weak": rt.sbl(3.0, 50.0),
    "sbl_mod": rt.sbl(6.0, 30.0),
    "sbl_strong": rt.sbl(10.0, 20.0),
    "cap_40m": rt.layered([0.0, 40.0, 60.0], [-0.0098, 0.2, -0.0065]),
}
LAMP = 0.66
K_MAX = 2.9          # above the largest local k in any scenario (sbl_strong at the surface: 2.82)
_G = {}


def ref_lamps():
    import json as _j
    return _j.load(open(os.path.join(OUT, "us67_lidar_obs_dense.json")))["lamps"]


def _init(cache):
    from .obstruction import ObstructionLayer
    dem.CACHE.max = cache
    m = dem.load("lidar")
    _G.update(m=m, obs=observer(m), ob=ObstructionLayer("dense"))


def _work(args):
    lon, lat = args
    obs, m = _G["obs"], _G["m"]
    r = los.sightline_multi(obs, m, lon, lat, lamps=(LAMP,), ks=(0.13,), return_profile=True,
                            obstruction=_G["ob"])
    D, R = float(r["D"][0]), r["R"]
    res = {}
    for name, grad in SCEN.items():
        span_hi = 4.0 * D / (2 * R) + 2e-3
        span_lo = -1.0 * D / (2 * R) - 2e-3
        th = np.linspace(span_lo, span_hi, 2401)
        t = rt.trace(r["s"], r["y"], D, R, grad, thetas=th, ds=5.0, eye_agl=obs.eye)
        res[name] = (t["images"], t["k_equiv"])
    return r["geo_el"][0], r["k_crit"][0], D, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=4)
    ap.add_argument("--procs", type=int, default=2)
    a = ap.parse_args()
    t = targets.us67_south(30.0)
    # rays in every scenario have curvature <= K_MAX/R, so the constant-K_MAX arc bounds every ray from above
    # (y'' >= -K_MAX/R with the same end points); points with k_crit > K_MAX cannot be seen in any scenario
    ref = np.load(os.path.join(OUT, "us67_lidar_obs_dense.npz"))
    kc_ref = ref["k_crit"][:, list(ref_lamps()).index(LAMP)]
    idx = np.arange(0, t["lon"].size, a.every)
    idx = idx[kc_ref[idx] <= K_MAX]
    lon, lat = t["lon"][idx], t["lat"][idx]
    n, S = len(idx), list(SCEN)
    nimg = np.zeros((n, len(S)), int)
    el = np.full((n, len(S), 3), np.nan)
    keq = np.full((n, len(S)), np.nan)
    geo = np.full(n, np.nan); kc = np.full(n, np.nan); D = np.full(n, np.nan)
    t0 = time.time()
    with mp.get_context("fork").Pool(a.procs, initializer=_init, initargs=(1.2e9,)) as pool:
        for i, (g_, kc_, D_, res) in enumerate(pool.imap(_work, list(zip(lon, lat)), chunksize=4)):
            geo[i], kc[i], D[i] = g_, kc_, D_
            for j, s in enumerate(S):
                im, ke = res[s]
                nimg[i, j] = len(im)
                if len(im):
                    order = np.argsort(im)[::-1]                # highest image first
                    el[i, j, :min(3, len(im))] = g_ + np.degrees(im[order][:3])
                    keq[i, j] = ke[order][0]
            if i and i % 100 == 0:
                print(f"  {i}/{n} {time.time() - t0:.0f} s", flush=True)
    np.savez_compressed(os.path.join(OUT, "trace_us67.npz"), lon=lon, lat=lat, idx=idx,
                        km_from_marfa=t["km_from_marfa"][idx], geo_el=geo, k_crit=kc, D=D, n_images=nimg,
                        app_el=el, k_equiv=keq)
    json.dump(dict(scenarios=S, lamp=LAMP, every=a.every, spacing_m=30.0 * a.every, k_max_skip=K_MAX,
                   n_total_every=int(np.arange(0, t["lon"].size, a.every).size),
                   note=__doc__, seconds=round(time.time() - t0)),
              open(os.path.join(OUT, "trace_us67.json"), "w"), indent=1)
    print("done", time.time() - t0)


if __name__ == "__main__":
    main()

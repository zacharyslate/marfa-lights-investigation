"""Summaries of the batch line-of-sight runs (data/derived/los2/*.npz) for the methods audit and the paper.

    python -m marfa.summarize us67      -> data/derived/los2/summary_us67.json and a printed table
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

from .run_los import OUT


def load(name):
    z = np.load(os.path.join(OUT, name + ".npz"), allow_pickle=True)
    meta = json.load(open(os.path.join(OUT, name + ".json")))
    return {k: z[k] for k in z.files}, meta


def km(mask, spacing):
    return float(np.sum(mask) * spacing / 1000.0)


def summary(name, spacing=30.0, lamp_ref=0.66, k_ref=0.13):
    d, meta = load(name)
    lamps, ks = meta["lamps"], meta["ks"]
    jl = int(np.argmin(np.abs(np.array(lamps) - lamp_ref)))
    jk = ks.index(k_ref)
    kc = d["k_crit"]
    out = dict(name=name, dem=meta["dem"], n=int(meta["n"]), skip_tgt=meta["skip_tgt"], lamp_ref=lamps[jl],
               viewer_ground_H=meta["viewer_ground_H"])
    out["visible_km"] = {f"lamp {L} m": {f"k={k}": km(kc[:, j] <= k, spacing) for k in ks}
                         for j, L in enumerate(lamps)}
    vis = kc[:, jl] <= k_ref
    lim_from_tgt = d["D"][:, jl] - d["lim_s"][:, jl]
    out["limiting_sample_from_target_m"] = dict(
        median=float(np.median(lim_from_tgt)),
        frac_within_100m=float(np.mean(lim_from_tgt < 100)), frac_within_1km=float(np.mean(lim_from_tgt < 1000)),
        visible_frac_within_100m=float(np.mean(lim_from_tgt[vis] < 100)) if vis.any() else None)
    dL = d["dL"][:, jl, jk]
    out["lamp_margin_m"] = dict(
        visible_but_within_0_5m=km(vis & (dL > -0.5), spacing), hidden_but_within_0_5m=km(~vis & (dL < 0.5), spacing),
        visible_but_within_2m=km(vis & (dL > -2), spacing), hidden_but_within_2m=km(~vis & (dL < 2), spacing))
    if "kc_clutter" in d:
        out["clutter_visible_km"] = {f"{c} m": km(d["kc_clutter"][:, jl, i] <= k_ref, spacing)
                                     for i, c in enumerate(meta.get("clutter", []))}
    if "p_vis" in d and not np.all(np.isnan(d["p_vis"])):
        p = d["p_vis"][:, jl, jk]
        out["mc"] = dict(robust_visible_km=km(p >= 0.95, spacing), robust_hidden_km=km(p <= 0.05, spacing),
                         uncertain_km=km((p > 0.05) & (p < 0.95), spacing), expected_visible_km=float(np.sum(p) * spacing / 1000))
    return out, d, meta


def compare(a, b, lamp=0.66, k=0.13):
    da, ma = load(a)
    db, mb = load(b)
    ja = int(np.argmin(np.abs(np.array(ma["lamps"]) - lamp)))
    jb = int(np.argmin(np.abs(np.array(mb["lamps"]) - lamp)))
    va, vb = da["k_crit"][:, ja] <= k, db["k_crit"][:, jb] <= k
    return dict(a=a, b=b, n=int(va.size), agree=float(np.mean(va == vb)), vis_a_hid_b=int(np.sum(va & ~vb)),
                hid_a_vis_b=int(np.sum(~va & vb)),
                kcrit_diff_median=float(np.nanmedian(db["k_crit"][:, jb] - da["k_crit"][:, ja])))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "us67"
    names = sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(OUT, which + "_*.npz")))
    res = {"runs": [], "comparisons": []}
    for n in names:
        s, _, _ = summary(n)
        res["runs"].append(s)
    ref = f"{which}_lidar"
    for n in names:
        if n != ref and os.path.exists(os.path.join(OUT, ref + ".npz")):
            res["comparisons"].append(compare(ref, n))
    json.dump(res, open(os.path.join(OUT, f"summary_{which}.json"), "w"), indent=1)
    for s in res["runs"]:
        print(f"{s['name']:28s} vis(0.66 m,k=.13)={s['visible_km']['lamp 0.66 m']['k=0.13']:6.2f} km  "
              f"lim<100m={s['limiting_sample_from_target_m']['frac_within_100m']:.2f}  "
              f"mc={s.get('mc')}  clutter={s.get('clutter_visible_km')}")
    for c in res["comparisons"]:
        print(c)

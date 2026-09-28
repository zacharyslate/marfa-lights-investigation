"""Test the line-of-sight model against the registered 2018-11-21 photos.

1. Vet detections: a real light must stand clearly above its surroundings
   (peak / median of a 120 x 80 px box >= 1.20; this agreed with a visual check of all 50 detections). Sensor dust and hair beside bright ground fail.
2. Angular separation of each vetted light from the nearest US-67 point the model says is in view,
   compared with the chance that a random point in the same band lands that close.
3. The 45 s exposure (p13) turns headlights into streaks: compare the streak's centre line with the
   modelled road curve.
4. Speeds from frame pairs, using the chainage of the matched road position.
Writes data/derived/photos/validation.json and publication/figures/fig07_photo_validation.*
"""
import json, math, sys
import numpy as np
from PIL import Image
from scipy import ndimage
sys.path.insert(0, "analysis")
import photo_register as P

R = json.load(open(f"{P.OUT}/registration.json"))
CLOCK = json.load(open(f"{P.OUT}/sun_clock.json"))["clock_offset_min_vs_CST"]
HW = np.array([[p[2], math.degrees(math.atan(p[7] / 1000)), p[3], p[8], {"v": 2, "m": 1, "h": 0}[p[6]]] for p in P.S["hwy"]])  # az, el, km, chainage, class
VIS = HW[HW[:, 4] >= 1]
rng = np.random.default_rng(1)


def sep_to(points, az, el):
    return np.hypot((points[:, 0] - az) * np.cos(np.radians(el)), points[:, 1] - el)


def vet(name, lights):
    im = np.asarray(Image.open(f"{P.RAW}/{name}.jpg").convert("L")).astype(float)
    out = []
    for l in lights:
        x, y = int(l["x"]), int(l["y"])
        box = im[max(0, y - 40):y + 40, max(0, x - 60):x + 60]
        peak = im[y - 2:y + 3, x - 2:x + 3].max()
        l["contrast"] = round(float(peak / max(np.median(box), 1)), 2)
        l["accepted"] = bool(l["contrast"] >= 1.20)
        out.append(l)
    return out


res = {"clock_offset_min_vs_CST": CLOCK, "frames": {}, "lights": []}
for n, r in R.items():
    L = vet(n, r["lights"])
    t_cam = r["time_camera"]
    for l in L:
        s = sep_to(VIS, l["az"], l["el"]); i = int(np.argmin(s))
        sh = sep_to(HW[HW[:, 4] == 0], l["az"], l["el"])
        l.update({"frame": n, "time_camera": t_cam, "exposure_s": r["exposure_s"], "sep_visible_deg": round(float(s[i]), 4),
                  "sep_hidden_deg": round(float(sh.min()), 4), "road_km": round(float(VIS[i, 2]), 2), "chainage_km": round(float(VIS[i, 3]), 3)})
        res["lights"].append(l)
    res["frames"][n] = {k: r[k] for k in ("time_camera", "exposure_s", "pointing", "skyline_rms_deg", "alt_fits")}

acc = [l for l in res["lights"] if l["accepted"]]
pts = [l for l in acc if l["exposure_s"] <= 2]                     # point-like lights (short exposures)
seps = np.array([l["sep_visible_deg"] for l in pts])
thr = float(np.max(seps)) if len(seps) else 0.03

# chance: random points in each frame's band (between the 10 km ridge line and the skyline)
hits = tot = 0
for n, r in R.items():
    p = [r["pointing"][k] for k in ("az0", "el0", "roll", "scale")]
    xs = rng.uniform(0, 6000, 20000); ys = rng.uniform(0, 3376, 20000)
    az, el = P.px_to_angles(xs, ys, p)
    lo, hi = P.model_el_deg(az, 3) + 0.01, P.model_el_deg(az) - 25 / 936
    ok = (el > lo) & (el < hi)
    az, el = az[ok], el[ok]
    for a, e in zip(az[:4000], el[:4000]):
        tot += 1; hits += float(sep_to(VIS, a, e).min()) <= thr
p_chance = hits / tot
res["point_lights"] = {"n": len(pts), "median_sep_deg": float(np.median(seps)), "max_sep_deg": thr,
                       "median_sep_px": float(np.median(seps) * 936 * 0.972), "chance_within_max_sep": p_chance,
                       "p_all_by_chance": p_chance ** len(pts)}
print("vetted lights", len(acc), "of", len(res["lights"]), "| point-like", len(pts))
print("separation from visible US-67: median %.4f deg (%.1f px), max %.4f deg" % (np.median(seps), np.median(seps) * 910, thr))
print("chance a random point in the band is that close: %.3f  -> all %d by chance: %.1e" % (p_chance, len(pts), p_chance ** len(pts)))
print("rejected:", [(l["frame"], l["x"], l["y"], l["contrast"]) for l in res["lights"] if not l["accepted"]])

# streaks in p13
r13 = R["p13"]; p13 = [r13["pointing"][k] for k in ("az0", "el0", "roll", "scale")]
im = np.asarray(Image.open(f"{P.RAW}/p13.jpg").convert("L")).astype(float)
streak = []
for x in range(0, 6000, 4):
    a, _ = P.px_to_angles(np.array([float(x)]), np.array([1700.0]), p13)
    road = VIS[np.abs(VIS[:, 0] - a[0]) < 0.02]
    if not len(road): continue
    _, yr = P.angles_to_px(np.array([a[0]]), np.array([road[:, 1].mean()]), p13)
    y0 = int(yr[0]) - 60; col = ndimage.uniform_filter1d(im[y0:y0 + 120, x], 3)
    bg = np.median(col)
    if col.max() - bg < 25: continue
    yy = y0 + int(np.argmax(col))
    az, el = P.px_to_angles(np.array([float(x)]), np.array([float(yy)]), p13)
    d = el[0] - road[:, 1].mean()
    streak.append((float(az[0]), float(el[0]), float(road[:, 1].mean()), float(d)))
st = np.array(streak)
res["p13_streak"] = {"n_columns": int(len(st)), "az_range": [float(st[:, 0].min()), float(st[:, 0].max())],
                     "mean_offset_deg": float(st[:, 3].mean()), "rms_offset_deg": float(np.sqrt(np.mean(st[:, 3] ** 2))),
                     "median_abs_offset_deg": float(np.median(np.abs(st[:, 3])))}
print("p13 streak columns", len(st), "offset mean %.4f rms %.4f median|.| %.4f deg" % (st[:, 3].mean(), np.sqrt(np.mean(st[:, 3] ** 2)), np.median(np.abs(st[:, 3]))))
json.dump(res, open(f"{P.OUT}/validation.json", "w"), indent=1)
np.save(f"{P.OUT}/p13_streak.npy", st)

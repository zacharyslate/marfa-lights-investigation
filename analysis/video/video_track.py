"""Usage (from the repository root, ZACH-venv):
    python analysis/video/video_track.py VIDEO.mp4 track.json
    python analysis/video/video_render.py VIDEO.mp4 track.json OUTDIR
"""
"""Fit the camera pointing on every video frame (skyline vs the line-of-sight model), detect lights, convert them to
bearing/elevation and match them to the modelled US-67 headlight positions."""
import os, sys, json, math, subprocess, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT + "/analysis")
from photo_overlay import S, m2d
from scipy.ndimage import gaussian_filter, maximum_filter1d, label, find_objects, median_filter, uniform_filter
from scipy.optimize import minimize
VID, OUT = sys.argv[1], sys.argv[2]
W, H = 1920, 1080
SK = np.array([(r[0], m2d(r[1])) for r in S["sky"]])
HW = np.array([(h[2], m2d(h[7]), h[3], h[0], h[1]) for h in S["hwy"] if h[6] != "h"])   # az, el, km, lat, lon
TW = [t for t in S["towers"] if t["light"] != "none" and t.get("kc") is not None and t["kc"] <= 0.13]
RD = []
for rd in S["roads"]:
    for q in rd["p"]:
        if q[6] == "v": RD.append((q[2], m2d(q[4]), rd.get("name", "road")))
def basis(az0, el0, roll):
    a, e, r = map(math.radians, (az0, el0, roll))
    F = np.array([math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)])
    R0 = np.array([math.cos(a), -math.sin(a), 0.0]); U0 = np.cross(R0, F)
    R = math.cos(r) * R0 + math.sin(r) * U0; U = -math.sin(r) * R0 + math.cos(r) * U0
    return F, R, U
def dirs(az, el):
    az, el = np.radians(az), np.radians(el)
    return np.stack([np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)], -1)
def proj(p, az, el):
    F, R, U = basis(*p[:3]); f = p[3]; d = dirs(az, el); z = d @ F
    x = W / 2 + f * (d @ R) / z; y = H / 2 - f * (d @ U) / z
    return x, y, z
def unproj(p, x, y):
    F, R, U = basis(*p[:3]); f = p[3]
    d = F[None] + ((x - W / 2) / f)[:, None] * R[None] + ((H / 2 - y) / f)[:, None] * U[None]
    d /= np.linalg.norm(d, axis=1)[:, None]
    return (np.degrees(np.arctan2(d[:, 0], d[:, 1])) % 360, np.degrees(np.arcsin(d[:, 2])))
def model_y(p, xs):
    half = math.degrees(math.atan(W / 2 / p[3])) + 1
    sel = SK[np.abs(SK[:, 0] - p[0]) < half]
    x, y, z = proj(p, sel[:, 0], sel[:, 1]); o = np.argsort(x)
    return np.interp(xs, x[o], y[o], left=np.nan, right=np.nan)
def skyline(L):
    band = L[250:850]
    ref = maximum_filter1d(band, 60, axis=0, origin=29)        # max over the 60 rows above (approximately)
    fut = maximum_filter1d(band, 25, axis=0, origin=-12)       # max over this row and the 24 below
    cond = (fut < 0.55 * ref) & (ref > 55)
    cond[:12] = False
    has = cond.any(0); y = np.where(has, cond.argmax(0) + 250, np.nan)
    return y
def lights_mask(L):
    bg = uniform_filter(L, 31); return L - bg
def cost(q, xs, yv, wts):
    my = model_y(q, xs); d = my - yv; ok = np.isfinite(d) & (wts > 0)
    if ok.sum() < 0.5 * len(xs): return 1e9
    return float(np.sum(np.minimum(np.abs(d[ok]), 12.0) * wts[ok]) / wts[ok].sum())
def frames():
    cmd = ["ffmpeg", "-v", "error", "-i", VID, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        b = pr.stdout.read(n)
        if len(b) < n: break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
p = np.array([232.2237, 0.2079, -0.001, 8074.13])
res = []
xs = np.arange(20, W - 20, 6)
for i, fr in enumerate(frames()):
    im = fr.astype(np.float32); L = gaussian_filter(im.mean(2), 1.2)
    ys = skyline(L); ys = median_filter(np.nan_to_num(ys, nan=np.nanmedian(ys)), 7)
    # lights: bright compact spots below the detected skyline
    hp = L - uniform_filter(L, 41)
    cand = (hp > 18) & (L > 70)
    lab, n = label(cand); spots = []
    for k, sl in enumerate(find_objects(lab), 1):
        if sl is None: continue
        yy, xx = np.nonzero(lab[sl] == k); area = len(yy)
        if area < 4 or area > 2500: continue
        cy = yy.mean() + sl[0].start; cx = xx.mean() + sl[1].start
        sky_here = ys[int(min(W - 1, max(0, cx)))]
        if not (sky_here - 25 <= cy <= sky_here + 160): continue
        if area > 1500: continue
        rgb = fr[sl][lab[sl] == k].mean(0); w = (L[sl][lab[sl] == k] - 40).clip(0)
        cx = float((xx * w).sum() / w.sum() + sl[1].start); cy = float((yy * w).sum() / w.sum() + sl[0].start)
        spots.append(dict(sky_px=float(sky_here), x=cx, y=cy, area=int(area), r=float(rgb[0]), g=float(rgb[1]), b=float(rgb[2]), peak=float(L[sl].max())))
    # columns near lights don't count for the skyline fit
    wts = np.ones_like(xs, float)
    for s in spots:
        if s["area"] < 800 and s["y"] > s["sky_px"] - 6: wts[np.abs(xs - s["x"]) < 20] = 0
    yv = ys[xs]
    def local(p0):
        return minimize(lambda q: cost(q, xs, yv, wts), p0, method="Nelder-Mead",
                 options={"xatol": 1e-5, "fatol": 1e-4, "maxiter": 4000, "initial_simplex": [p0, p0 + [0.05, 0, 0, 0], p0 + [0, 0.02, 0, 0], p0 + [0, 0, 0.1, 0], p0 + [0, 0, 0, 150]]})
    r = local(p)
    if r.fun > 2.5:
        # global re-seed: bearing x lens grid at the previous roll, offset from the median
        best = (1e9, None)
        for f in np.geomspace(4500, 10000, 18):
            for a0 in np.arange(p[0] - 4, p[0] + 4, 0.08):
                q0 = np.array([a0, 0.0, p[2], f]); my = model_y(q0, xs); d = my - yv; ok = np.isfinite(d) & (wts > 0)
                if ok.sum() < 0.7 * len(xs): continue
                off = np.median(d[ok]); c = np.median(np.abs(d[ok] - off))
                if c < best[0]: best = (c, np.array([a0, -math.degrees(off / f), p[2], f]))
        if best[1] is not None:
            r2 = local(best[1])
            if r2.fun < r.fun: r = r2
    q = r.x
    p = q
    for s in spots:
        a, e = unproj(q, np.array([s["x"]]), np.array([s["y"]])); s["az"] = float(a[0]); s["el"] = float(e[0])
        d = np.hypot((HW[:, 0] - s["az"]) * math.cos(math.radians(s["el"])), HW[:, 1] - s["el"]); j = int(d.argmin())
        s["hwy_sep"] = float(d[j]); s["hwy_az"] = float(HW[j, 0]); s["hwy_el"] = float(HW[j, 1]); s["hwy_km"] = float(HW[j, 2]); s["hwy_lat"] = float(HW[j, 3]); s["hwy_lon"] = float(HW[j, 4])
        tw = [math.hypot(t["az"] - s["az"], m2d(t["a"]) - s["el"]) for t in TW]; s["tower_sep"] = float(min(tw)) if tw else None
        sky_el = float(np.interp(s["az"], SK[:, 0], SK[:, 1])); s["below_sky_deg"] = sky_el - s["el"]
    spots = [s for s in spots if 0.01 < s["below_sky_deg"] < 1.2]
    res.append(dict(i=i, t=i / 30.0, cam=[float(v) for v in q], fit_px=float(r.fun), spots=spots))
    if i % 30 == 0: print(i, [round(v, 4) for v in q], round(r.fun, 2), len(spots), [(round(s["az"], 2), round(s["hwy_sep"], 3)) for s in spots], flush=True)
json.dump(res, open(OUT, "w"))

"""Register the 2018-11-21 Viewing Area photo sequence to the terrain model.

Camera: Sony ILCE-6300 (APS-C, 23.5 mm x 15.6 mm, 6000 px wide), E 55-210 mm at 210 mm.
Pixel pitch 23.5/6000 mm, so the focal length is ~53,600 px and one degree is ~936 px.
Steps:
  1. extract the sky/land boundary in each frame (red-minus-blue drops sharply at the skyline),
  2. find the pointing (azimuth, elevation, roll, small scale change) that best overlays the
     modelled skyline from docs/data/site.json,
  3. find point lights below the skyline and convert them to azimuth / elevation,
  4. compare them with the predicted positions of US-67 and RM 2810 headlights.
Raw photos live in data/photos_raw/ (not in git). Outputs go to data/derived/photos/.
"""
import json, math, sys
import numpy as np
from PIL import Image
from scipy import ndimage, optimize

RAW = "data/photos_raw"
OUT = "data/derived/photos"
S = json.load(open("docs/data/site.json"))
SKY = np.array(S["sky"])                     # az, skyline_mrad, skyline_km, ridge10, ridge25, ridge45
F_PX = 210.0 / (23.5 / 6000.0)               # focal length in pixels (~53,617)


def skyline_px(name, x_step=8):
    im = np.asarray(Image.open(f"{RAW}/{name}.jpg").convert("RGB")).astype(np.float32)
    H, W, _ = im.shape
    d = im[..., 0] - im[..., 2]                   # red minus blue: sky >> 0, hazy land <= ~10
    d = ndimage.uniform_filter(d, size=(9, 9))
    xs = np.arange(4, W - 4, x_step)
    ys = []
    for x in xs:
        col = d[:, x]
        top = np.median(col[200:600])
        land_rows = np.where(col[400:H - 300] < top * 0.45)[0]
        ys.append(400 + land_rows[0] if land_rows.size else np.nan)
    return im, xs, np.array(ys, float)


def model_el_deg(az, col=1):
    """Modelled skyline (or ridge layer) elevation in degrees at true azimuth az (k = 0.13)."""
    return np.degrees(np.arctan(np.interp(az, SKY[:, 0], SKY[:, col]) / 1000.0))


def px_to_angles(x, y, p, W=6000, H=3376):
    """Pixel -> (true az, elevation) for pointing p = (az0, el0, roll_deg, scale)."""
    az0, el0, roll, sc = p
    f = F_PX * sc
    u, v = x - W / 2, (H / 2) - y
    r = math.radians(roll)
    u, v = u * math.cos(r) - v * math.sin(r), u * math.sin(r) + v * math.cos(r)
    # rectilinear camera looking at (az0, el0): ray in camera frame (u, v, f)
    ce, se = math.cos(math.radians(el0)), math.sin(math.radians(el0))
    # world: east, north, up with camera forward at az0
    fwd = np.array([ce * 0, ce, se]); up = np.array([0, -se, ce]); rt = np.array([1, 0, 0])
    d = np.outer(u, rt) + np.outer(v, up) + f * fwd
    E, N, U = d[:, 0], d[:, 1], d[:, 2]
    az = np.degrees(np.arctan2(E, N)) + az0
    el = np.degrees(np.arctan2(U, np.hypot(E, N)))
    return az, el


def angles_to_px(az, el, p, W=6000, H=3376):
    az0, el0, roll, sc = p
    f = F_PX * sc
    a, e = np.radians(np.asarray(az) - az0), np.radians(np.asarray(el))
    E, N, U = np.cos(e) * np.sin(a), np.cos(e) * np.cos(a), np.sin(e)
    ce, se = math.cos(math.radians(el0)), math.sin(math.radians(el0))
    zc = N * ce + U * se                 # forward
    yc = -N * se + U * ce                # up
    xc = E
    u, v = f * xc / zc, f * yc / zc
    r = -math.radians(roll)
    u, v = u * math.cos(r) - v * math.sin(r), u * math.sin(r) + v * math.cos(r)
    return W / 2 + u, H / 2 - v


def fit_pointing(xs, ys, az_range=(200, 290)):
    ok = ~np.isnan(ys); xs, ys = xs[ok], ys[ok]
    def resid(p):
        az, el = px_to_angles(xs, ys, p)
        r = el - model_el_deg(az)
        return r - np.median(r) * 0          # keep absolute
    best = None
    for az0 in np.arange(az_range[0], az_range[1], 0.05):
        az, el = px_to_angles(xs, ys, (az0, 0.0, 0.0, 1.0))
        r = el - model_el_deg(az)
        el0 = -np.median(r)
        az, el = px_to_angles(xs, ys, (az0, el0, 0.0, 1.0))
        rr = el - model_el_deg(az)
        s = np.sqrt(np.mean((rr - np.median(rr)) ** 2))
        if best is None or s < best[0]: best = (s, az0, el0)
    p0 = [best[1], best[2], 0.0, 1.0]
    sol = optimize.least_squares(lambda p: np.clip(resid(p), -0.05, 0.05) + 0 * p[0] + (resid(p) - np.clip(resid(p), -0.05, 0.05)) * 0.1,
                                 p0, x_scale=[0.01, 0.01, 0.1, 0.01], bounds=([p0[0] - 0.5, -3, -3, 0.9], [p0[0] + 0.5, 3, 3, 1.1]))
    r = resid(sol.x)
    return sol.x, best, float(np.sqrt(np.mean(r ** 2))), float(np.median(np.abs(r)))


def score_curve(xs, ys, az_range=(200, 290), step=0.05):
    ok = ~np.isnan(ys); xs, ys = xs[ok], ys[ok]
    out = []
    for az0 in np.arange(az_range[0], az_range[1], step):
        az, el = px_to_angles(xs, ys, (az0, 0.0, 0.0, 0.972))
        r = el - model_el_deg(az)
        out.append((az0, float(np.sqrt(np.mean((r - np.median(r)) ** 2)))))
    return np.array(out)


def find_lights(name, p, sky_margin_px=25, nsig=7.0, el_min=-0.6):
    """Compact bright points between the skyline and the near edge of the flat.
    A detection must beat the local background by nsig robust standard deviations."""
    im = np.asarray(Image.open(f"{RAW}/{name}.jpg").convert("RGB")).astype(np.float32)
    H, W, _ = im.shape
    y0 = max(0, int(angles_to_px(np.array([p[0]]), np.array([0.6]), p)[1][0]))
    y1 = min(H, int(angles_to_px(np.array([p[0]]), np.array([el_min - 0.1]), p)[1][0]))
    band = im[y0:y1].mean(axis=2)
    bg = ndimage.median_filter(band, size=(21, 21))
    hp = band - bg
    sig = 1.4826 * np.median(np.abs(hp - np.median(hp)))
    lab, n = ndimage.label(hp > nsig * sig)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        m = lab[sl] == i
        area = int(m.sum())
        if area < 4 or area > 600: continue
        yy, xx = np.nonzero(m)
        w = hp[sl][m]
        cy = float((yy * w).sum() / w.sum() + sl[0].start + y0); cx = float((xx * w).sum() / w.sum() + sl[1].start)
        if not (20 < cx < W - 20): continue
        az, el = px_to_angles(np.array([cx]), np.array([cy]), p)
        if el[0] > model_el_deg(az[0]) - sky_margin_px / 936 or el[0] < el_min: continue
        # anything farther than 10 km must sit above the highest terrain within 10 km (ridge10 layer)
        if el[0] < model_el_deg(az[0], col=3) + 0.01: continue
        yi, xi = int(round(cy)), int(round(cx))
        rgb = im[yi - 1:yi + 2, xi - 1:xi + 2].reshape(-1, 3).mean(0)
        out.append({"x": round(cx, 1), "y": round(cy, 1), "az": round(float(az[0]), 4), "el": round(float(el[0]), 4),
                    "snr": round(float(w.max() / sig), 1), "area": area, "rgb": [int(c) for c in rgb]})
    return out


def road_points():
    pts = []
    for p in S["hwy"]:
        pts.append(("US-67", p[2], math.degrees(math.atan(p[7] / 1000)), p[3], p[6], p[5]))
    for r in S["roads"]:
        for q in r["p"]:
            pts.append((r["n"].split(" (")[0], q[2], math.degrees(math.atan(q[4] / 1000)), q[3], q[6], q[5]))
    for q in S["railpano"]:
        pts.append((q[0] + " rail", q[1], math.degrees(math.atan(q[3] / 1000)), q[2], "v" if q[4] <= 0.13 else "h", q[4]))
    return pts


def nearest_source(az, el, pts):
    best = None
    for name, a, e, d, cls, kc in pts:
        dd = math.hypot((a - az) * math.cos(math.radians(el)), e - el)
        if best is None or dd < best[0]: best = (dd, name, a, e, d, cls, kc)
    return best


FRAMES = ["p04", "p05", "p06", "p07", "p08", "p09", "p10", "p11", "p12", "p13"]

if __name__ == "__main__":
    from PIL import ExifTags
    pts = road_points()
    res = {}
    for n in FRAMES:
        im, xs, ys = skyline_px(n)
        p, coarse, rms, mad = fit_pointing(xs, ys)
        # uniqueness: best rms among fits started at other local minima
        c = score_curve(xs, ys)
        from scipy.signal import argrelmin
        mins = [c[i] for i in argrelmin(c[:, 1], order=5)[0] if abs(c[i][0] - p[0]) > 1]
        alt = sorted(mins, key=lambda r: r[1])[:3]
        alt_rms = []
        for a0, _ in alt:
            q, _, r2, _ = fit_pointing(xs, ys, az_range=(a0 - 0.3, a0 + 0.3))
            alt_rms.append((round(float(q[0]), 2), round(r2, 4)))
        ex = Image.open(f"{RAW}/{n}.jpg").getexif().get_ifd(0x8769)
        t = ex.get(36867); expo = ex.get(33434)
        L = find_lights(n, p)
        for l in L:
            b = nearest_source(l["az"], l["el"], pts)
            l.update({"nearest": b[1], "sep_deg": round(b[0], 4), "src_az": round(b[2], 3), "src_el": round(b[3], 4), "src_km": round(b[4], 1), "src_cls": b[5]})
        res[n] = {"time_camera": t, "exposure_s": float(expo) if expo else None, "pointing": {"az0": round(float(p[0]), 4), "el0": round(float(p[1]), 4),
                  "roll": round(float(p[2]), 3), "scale": round(float(p[3]), 4)}, "skyline_rms_deg": round(rms, 4), "skyline_med_abs_deg": round(mad, 4),
                  "alt_fits": alt_rms, "lights": L}
        print(n, t, "az0 %.3f el0 %.3f roll %.2f sc %.4f rms %.4f" % tuple(list(p) + [rms]), "alt", alt_rms, "lights", len(L))
        for l in L: print("    ", l["x"], l["y"], "az %.3f el %.3f" % (l["az"], l["el"]), "snr", l["snr"], "area", l["area"], "->", l["nearest"], l["src_cls"], "%.1f km" % l["src_km"], "sep %.3f°" % l["sep_deg"])
    json.dump(res, open(f"{OUT}/registration.json", "w"), indent=1)

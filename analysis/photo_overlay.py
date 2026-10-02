"""Draw the line-of-sight model over a photo, using the camera solution from the photo checker (docs/photo.html).

    python analysis/photo_overlay.py IMAGE AZ EL ROLL F_PX_AT_WIDTH WIDTH OUT.jpg [crop x0 y0 x1 y1] [--lights az,el;az,el]

The projection is the same pinhole model as docs/assets/photo.js: camera at the platform, forward direction from
(AZ, EL), roll about the optical axis, focal length F (pixels at an image width WIDTH; rescaled to IMAGE's width).
Overlays: modelled skyline (cyan), nearest ridge within 10 km (dashed cyan), known-source mask tier A (green),
US-67 headlight positions in view (orange), other roads (pink), lit towers (red rings).
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open(os.path.join(ROOT, "docs/data/site.json")))
Z = json.load(open(os.path.join(ROOT, "docs/data/zos.json")))
m2d = lambda m: math.degrees(math.atan(m / 1000.0))  # noqa: E731


def projector(az0, el0, roll, f, W, H):
    a, e, r = map(math.radians, (az0, el0, roll))
    F = np.array([math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)])
    R0 = np.array([math.cos(a), -math.sin(a), 0.0])
    U0 = np.cross(R0, F)
    R = math.cos(r) * R0 + math.sin(r) * U0
    U = -math.sin(r) * R0 + math.cos(r) * U0

    def P(az, el):
        az, el = math.radians(az), math.radians(el)
        d = np.array([math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)])
        z = d @ F
        if z < 0.05:
            return None
        return (W / 2 + f * (d @ R) / z, H / 2 - f * (d @ U) / z)
    return P


def main():
    a = sys.argv[1:]
    img, az0, el0, roll, f0, w0, out = a[0], float(a[1]), float(a[2]), float(a[3]), float(a[4]), float(a[5]), a[6]
    crop = tuple(map(int, a[8:12])) if len(a) > 7 and a[7] == "crop" else None
    lights = []
    if "--lights" in a:
        lights = [tuple(map(float, p.split(","))) for p in a[a.index("--lights") + 1].split(";") if p]
    im = Image.open(img).convert("RGB")
    W, H = im.size
    f = f0 * W / w0
    P = projector(az0, el0, roll, f, W, H)
    g = ImageDraw.Draw(im, "RGBA")
    lw = max(1, round(W / 1500))
    half = math.degrees(math.atan(W / 2 / f)) + 2
    inf = lambda az: abs(((az - az0 + 540) % 360) - 180) <= half  # noqa: E731

    def line(pts, col, dash=False):
        seg = []
        for i, (az, el) in enumerate(pts):
            p = P(az, el) if inf(az) else None
            if p is None or (dash and (i // 6) % 2):
                if len(seg) > 1:
                    g.line(seg, fill=col, width=lw)
                seg = []
                continue
            seg.append(p)
        if len(seg) > 1:
            g.line(seg, fill=col, width=lw)
    for ring in Z["tiers"]["A"]:
        if not any(inf(az) for az, _ in ring):
            continue
        pts = [P(az, m2d(m)) for az, m in ring]
        pts = [p for p in pts if p]
        if len(pts) > 2:
            g.polygon(pts, fill=(69, 192, 122, 50), outline=(69, 192, 122, 200))
    line([(r[0], m2d(r[1])) for r in S["sky"]], (127, 211, 255, 255))
    line([(r[0], m2d(r[3])) for r in S["sky"]], (127, 211, 255, 150), dash=True)
    rr = 2 * lw
    for h in S["hwy"]:
        if h[6] != "h" and inf(h[2]):
            p = P(h[2], m2d(h[7]))
            if p:
                g.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=(255, 138, 0, 230))
    for rd in S["roads"]:
        for q in rd["p"]:
            if q[6] == "v" and inf(q[2]):
                p = P(q[2], m2d(q[4]))
                if p:
                    g.ellipse([p[0] - lw, p[1] - lw, p[0] + lw, p[1] + lw], fill=(240, 107, 180, 220))
    for t in S["towers"]:
        if t["light"] != "none" and t.get("kc") is not None and t["kc"] <= 0.13 and inf(t["az"]):
            p = P(t["az"], m2d(t["a"]))
            if p:
                g.ellipse([p[0] - 5 * lw, p[1] - 5 * lw, p[0] + 5 * lw, p[1] + 5 * lw], outline=(255, 59, 47, 255), width=lw)
    for az, el in lights:
        p = P(az, el)
        if p:
            g.ellipse([p[0] - 8 * lw, p[1] - 8 * lw, p[0] + 8 * lw, p[1] + 8 * lw], outline=(255, 255, 255, 255), width=lw)
    if crop:
        im = im.crop(crop)
    im.save(out, quality=90)


if __name__ == "__main__":
    main()

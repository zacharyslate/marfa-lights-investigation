"""Table-of-contents graphic (graphical abstract) for the paper.

    python analysis/toc_graphic.py   ->  publication/figures/toc_graphic.{pdf,png,svg}, docs/img/toc_graphic-{900,1800}.webp

Size 3.25 x 1.75 in (the common journal TOC format). All shapes come from the model's own data:
(a) the view from the platform, 200-266 deg true, with the known-source mask (photographic pointing), the positions
where US-67 headlamps can appear, and the lit towers; one hypothetical light outside the mask marks what is left
to study (it is an illustration, not an observation); (b) the terrain cross-section along 233.6 deg true (1 m lidar,
curvature and refraction k = 0.13 applied) with the sight line from the eye to a car 33.8 km away.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open(os.path.join(ROOT, "docs/data/site.json")))
Z = json.load(open(os.path.join(ROOT, "data/derived/zos.json")))
PROF = json.load(open(os.path.join(ROOT, "data/derived/profiles_fig.json")))
R, K, EYE, LAMP = 6_371_000.0, 0.13, 1.6, 0.66
m2d = lambda m: np.degrees(np.arctan(np.asarray(m) / 1000))   # noqa: E731

# palette: the paper's (Okabe-Ito) plus a night scene
SKY_TOP, SKY_LOW = "#1b2a52", "#3a4f86"
LAND = ["#5a5c6b", "#4a4b57", "#3b3c45", "#2c2d34"]
MASK = "#009E73"
CAR = "#E69F00"
TOWER = "#D55E00"
INK, MUTED = "#1a1a1a", "#555555"

A0, A1, E0, E1 = 200.0, 266.0, -0.62, 0.55


def panorama(ax):
    sky = np.array(S["sky"]); sky = sky[(sky[:, 0] >= A0 - 1) & (sky[:, 0] <= A1 + 1)]
    # sky gradient
    grad = np.linspace(0, 1, 256)[:, None]
    ax.imshow(grad, extent=(A0, A1, E0, E1), aspect="auto", origin="upper",
              cmap=matplotlib.colors.LinearSegmentedColormap.from_list("s", [SKY_TOP, SKY_LOW]), zorder=0)
    for col, c in ((1, LAND[0]), (5, LAND[1]), (4, LAND[2]), (3, LAND[3])):
        ax.fill_between(sky[:, 0], E0 - 1, m2d(sky[:, col]), color=c, lw=0, zorder=1)
    ax.plot(sky[:, 0], m2d(sky[:, 1]), color="#9aa0b8", lw=0.5, zorder=2)
    # known-source mask, photographic pointing
    for r in Z["tiers"]["A"]:
        r = np.array(r)
        if r[:, 0].max() < A0 or r[:, 0].min() > A1:
            continue
        ax.add_patch(Polygon(np.c_[r[:, 0], m2d(r[:, 1])], closed=True, fc=MASK, ec=MASK, lw=0.25, alpha=0.42, zorder=3))
    # US-67 headlamp positions in view, other roads, towers
    H = [h for h in S["hwy"] if h[6] == "v" and A0 <= h[2] <= A1]
    ax.scatter([h[2] for h in H], m2d([h[7] for h in H]), s=0.6, color=CAR, lw=0, zorder=4)
    for rd in S["roads"]:
        P = [q for q in rd["p"] if q[6] == "v" and A0 <= q[2] <= A1]
        ax.scatter([q[2] for q in P], m2d([q[4] for q in P]), s=0.4, color="#CC79A7", lw=0, zorder=4)
    for t in S["towers"]:
        if t["light"] != "none" and t.get("a") is not None and t.get("kc") is not None and t["kc"] <= K and A0 <= t["az"] <= A1:
            ax.plot(t["az"], m2d(t["a"]), marker="D", ms=1.8, color=TOWER, mec="none", zorder=5)
    # a hypothetical light outside the mask: what is left to study
    az_q = 245.0
    sk_q = float(np.interp(az_q, sky[:, 0], m2d(sky[:, 1])))
    el_q = sk_q - 0.08
    ax.scatter([az_q], [el_q], s=5, color="white", lw=0, zorder=7)
    ax.scatter([az_q], [el_q], s=40, facecolors="none", edgecolors="white", lw=0.5, zorder=7)
    ax.text(az_q + 1.1, el_q + 0.1, "?", color="white", fontsize=7.5, fontweight="bold", ha="left", va="center", zorder=8)
    ax.text(A0 + 0.8, E1 - 0.06, "Known sources, masked", color="#b9f0dc", fontsize=5.6, va="top", fontweight="bold", zorder=8)
    # key: mark + ink label
    x = A0 + 0.9; yk = E1 - 0.245
    for kind, lab in (("car", "US-67 cars"), ("road", "other roads"), ("tower", "lit towers"), ("mask", "mask")):
        if kind == "car":
            ax.plot(x, yk, "o", ms=1.8, color=CAR, mec="none", zorder=8)
        elif kind == "road":
            ax.plot(x, yk, "o", ms=1.6, color="#CC79A7", mec="none", zorder=8)
        elif kind == "tower":
            ax.plot(x, yk, "D", ms=1.7, color=TOWER, mec="none", zorder=8)
        else:
            ax.add_patch(Polygon([[x - 0.35, yk - 0.035], [x + 0.35, yk - 0.035], [x + 0.35, yk + 0.035], [x - 0.35, yk + 0.035]],
                                 fc=MASK, ec="none", alpha=0.6, zorder=8))
        t = ax.text(x + 0.7, yk, lab, color="#e8e8e8", fontsize=4.5, va="center", zorder=8)
        x += 0.7 + 0.74 * len(lab) + 1.6
    ax.text(az_q, el_q - 0.13, "outside the mask:\nworth a closer look", color="white", fontsize=4.6, ha="center", va="top",
            linespacing=1.1, zorder=8, bbox=dict(boxstyle="round,pad=0.25", fc="#1b2a52", ec="none", alpha=0.75))
    ax.set_xlim(A0, A1); ax.set_ylim(E0, E1)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)


def section(ax):
    z = np.array(PROF["prof"]["233.6"]); z0 = PROF["meta"]["z0"]; step = PROF["meta"]["step_m"]
    d = np.arange(len(z)) * step
    dcar = 33_800.0
    keep = d <= dcar + 1500
    d, z = d[keep], z[keep]
    y = z - z0 - EYE - d ** 2 * (1 - K) / (2 * R)                   # relative to the eye, after curvature and refraction
    ycar = float(np.interp(dcar, d, y)) + LAMP + 1.0                # headlamp just above the road surface
    km = d / 1000
    ax.fill_between(km, y.min() - 30, y, color="#b8b2a3", lw=0, zorder=1)
    ax.plot(km, y, color="#6b6455", lw=0.5, zorder=2)
    ax.plot([0, dcar / 1000], [0, ycar], color=CAR, lw=0.7, ls=(0, (3, 1.5)), zorder=3)
    ax.plot(0, 0, marker="o", ms=2.2, color=INK, zorder=4)
    ax.plot(dcar / 1000, ycar, marker="o", ms=2.6, color=CAR, mec=INK, mew=0.3, zorder=4)
    ax.text(0.4, 6, "eye", fontsize=4.8, color=INK, va="bottom")
    ax.text(dcar / 1000 - 0.6, ycar + 30, "car, 34 km away", fontsize=4.8, color=INK, ha="right", va="bottom")
    # the headlamp beam, pointed back along the sight line
    L = 6.0; ang = np.arctan2(-ycar, -dcar) ; spread = 0.25
    tip = (dcar / 1000, ycar)
    pts = [tip]
    for s_ in (-spread, spread):
        dx = np.cos(ang + s_) * L; dy = np.sin(ang + s_) * L * 1000 / (km.max() * 1000 / (y.max() - y.min() + 60)) * 0.02
        pts.append((tip[0] + dx, tip[1] + np.sign(-ycar) * 0 + (y.max() - y.min()) * 0.12 * (1 if s_ > 0 else -1)))
    ax.add_patch(Polygon(pts, closed=True, fc=CAR, ec="none", alpha=0.28, zorder=3))
    ax.text(0.5, y.min() - 24, "1 m lidar terrain · curvature · refraction", fontsize=4.6, color=MUTED, va="bottom")
    ax.set_xlim(-0.5, dcar / 1000 + 1.6); ax.set_ylim(y.min() - 30, max(y.max(), ycar) + 32)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)


def flow(ax):
    ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    rows = [("Where can it be seen?", "line of sight"), ("How bright does it look?", "headlamp photometry"),
            ("How often, and how does it move?", "traffic and timing")]
    for i, (q, a) in enumerate(rows):
        yy = 0.90 - i * 0.25
        ax.text(0.02, yy, q, fontsize=4.9, color=INK, fontweight="bold", va="center")
        ax.text(0.02, yy - 0.10, a, fontsize=4.4, color=MUTED, va="center")
    ax.text(0.02, 0.08, "= the known-source mask", fontsize=5.2, color=MASK, fontweight="bold", va="center")


def main():
    fig = plt.figure(figsize=(3.25, 1.75), dpi=600)
    fig.patch.set_facecolor("white")
    a = fig.add_axes([0.0, 0.40, 1.0, 0.60]); panorama(a)
    b = fig.add_axes([0.01, 0.01, 0.55, 0.37]); section(b)
    c = fig.add_axes([0.58, 0.01, 0.41, 0.37]); flow(c)
    out = os.path.join(ROOT, "publication/figures/toc_graphic")
    for ext in ("pdf", "svg", "png"):
        fig.savefig(f"{out}.{ext}", dpi=600, facecolor="white")
    from PIL import Image
    im = Image.open(out + ".png").convert("RGB")
    for w in (900, 1800):
        im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save(os.path.join(ROOT, f"docs/img/toc_graphic-{w}.webp"), "WEBP", quality=88)
    print(im.size)


if __name__ == "__main__":
    main()

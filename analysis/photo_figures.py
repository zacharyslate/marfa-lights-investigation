"""Figures from the photo validation: publication fig07 and annotated web images.
Run after photo_register.py, photo_sun_clock.py and photo_validate.py."""
import json, math, sys
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
sys.path.insert(0, "analysis")
import photo_register as P
import pub_figures as PF                      # shared style, save()

REG = json.load(open(f"{P.OUT}/registration.json"))
VAL = json.load(open(f"{P.OUT}/validation.json"))
HW = np.array([[p[2], math.degrees(math.atan(p[7] / 1000)), p[3], {"v": 2, "m": 1, "h": 0}[p[6]]] for p in P.S["hwy"]])
VIS = HW[HW[:, 3] >= 1]
C_MODEL, C_LIGHT = "#F0E442", "#FFFFFF"


def pointing(n):
    q = REG[n]["pointing"]; return [q["az0"], q["el0"], q["roll"], q["scale"]]


def load(n, step=1):
    return np.asarray(Image.open(f"{P.RAW}/{n}.jpg").convert("RGB"))[::step, ::step]


def road_px(n):
    x, y = P.angles_to_px(VIS[:, 0], VIS[:, 1], pointing(n))
    ok = (x > 0) & (x < 6000) & (y > 0) & (y < 3376)
    return x[ok], y[ok], VIS[ok]


def layer_px(n, col):
    az = np.linspace(pointing(n)[0] - 3.4, pointing(n)[0] + 3.4, 400)
    return P.angles_to_px(az, P.model_el_deg(az, col), pointing(n))


def az_ticks(ax, n, y_at, x0, x1, step=1.0, fs=6.5, color="white"):
    p = pointing(n)
    for a in np.arange(math.ceil((p[0] - 3.3) / step) * step, p[0] + 3.3, step):
        x, y = P.angles_to_px(np.array([a]), np.array([P.model_el_deg(a)]), p)
        if x0 < x[0] < x1:
            ax.plot([x[0], x[0]], [y_at - 18, y_at], color=color, lw=0.6)
            ax.text(x[0], y_at - 24, f"{a:.0f}° true", color=color, fontsize=fs, ha="center", va="bottom")


def lights(n, point_only=True):
    return [l for l in VAL["lights"] if l["frame"] == n and l["accepted"]]


# ---------------------------------------------------------------- publication figure 7
def fig07():
    fig = plt.figure(figsize=(PF.W2, PF.W2 * 0.50))
    gs = fig.add_gridspec(2, 3, height_ratios=[0.62, 1.0], hspace=0.12, wspace=0.28)
    # (a) p06 overview with model overlay
    ax = fig.add_subplot(gs[0, :]); n = "p06"
    x0, x1, y0, y1 = 300, 5900, 1250, 2250
    ax.imshow(load(n)[y0:y1, x0:x1], extent=(x0, x1, y1, y0))
    for col, ls, lab in ((1, "-", "modelled skyline"), (3, ":", "10 km ridge line"), (4, "--", "25 km ridge line")):
        x, y = layer_px(n, col); ax.plot(x, y, ls, color="white", lw=0.6, alpha=0.85, label=lab)
    rx, ry, _ = road_px(n); ax.plot(rx, ry, ".", ms=1.2, color=C_MODEL, label="US-67 in view (model)")
    for l in lights(n):
        ax.add_patch(Circle((l["x"], l["y"]), 45, fill=False, ec=C_LIGHT, lw=0.8))
        ax.text(l["x"], l["y"] + 70, f"{l['src_km']:.0f} km", color="white", fontsize=6, ha="center", va="top")
    az_ticks(ax, n, y0 + 150, x0, x1)
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_xticks([]); ax.set_yticks([])
    ax.legend(loc="lower left", fontsize=5.8, labelcolor="white", ncol=4, handlelength=1.6, markerscale=5)
    t = REG[n]["time_camera"][-8:]
    PF.panel(ax, "a", x=-0.02, y=1.0)
    # (b) p13 streak zoom
    ax = fig.add_subplot(gs[1, 0:2]); n = "p13"
    x0, x1, y0, y1 = 4500, 6000, 1650, 1900
    x0, x1, y0, y1 = 4950, 6000, 1690, 1850
    ax.imshow(_stretch(load(n)[y0:y1, x0:x1], 1, 99.9, 0.9), extent=(x0, x1, y1, y0), aspect="auto")
    rx, ry, _ = road_px(n); ok = (rx > x0) & (rx < x1)
    ax.plot(rx[ok], ry[ok], "o", ms=2.2, mfc="none", mec=C_MODEL, mew=0.5, alpha=0.9, label="US-67 (model)")
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_xticks([]); ax.set_yticks([])
    st = max(VAL["p13_streaks"]["streaks"], key=lambda q: q["x1"] - q["x0"])
    ax.text(0.01, 0.04, f"45 s exposure; streak found without the model lies {st['median_sep_deg']:.3f}° (median) from it",
            transform=ax.transAxes, color="white", fontsize=6, va="bottom")
    ax.legend(loc="upper left", fontsize=5.8, labelcolor="white", markerscale=2)
    PF.panel(ax, "b", x=-0.02, y=1.0)
    # (c) separations vs chance
    ax = fig.add_subplot(gs[1, 2])
    U = VAL["units_vetted"]
    obs = np.sort([u["sep_deg"] for u in U["units"]])
    ax.step(obs, np.arange(1, len(obs) + 1) / len(obs), where="post", color=PF.OI["verm"], lw=1.2,
            label=f"independent sightings (n={len(obs)})")
    # chance curve: random positions in each burst's ground band, separation to the modelled road curve
    import photo_validate as PV
    rs = []
    for b, frames in PV.BURSTS.items():
        p = pointing(frames[0]); rng = np.random.default_rng(2)
        xs = rng.uniform(0, 6000, 8000); ys = rng.uniform(0, 3376, 8000)
        az, el = P.px_to_angles(xs, ys, p)
        ok = PV.band_mask(az, el)
        rs += [PV.sep_curve(a, e)[0] for a, e in zip(az[ok][:500], el[ok][:500])]
    rs = np.sort(rs)
    ax.step(rs, np.arange(1, len(rs) + 1) / len(rs), where="post", color=PF.OI["grey"], lw=1.0, label="random points in the same band")
    ax.set_xscale("log"); ax.set_xlim(1e-4, 1); ax.set_ylim(0, 1.02)
    ax.set_xlabel("angular distance to modelled US-67 (°)"); ax.set_ylabel("cumulative fraction")
    ax.text(1.2e-4, 0.62, f"detected\nlights\np = {U['p_value_exact']:.0e}", color=PF.OI["verm"], fontsize=6.5, ha="left", va="center")
    ax.text(0.2, 0.35, "random points\nin the same band", color="#6b6b6b", fontsize=6.5, ha="left", va="center")
    PF.panel(ax, "c", x=-0.28, y=1.0)
    PF.save(fig, "fig07_photo_validation")


# ---------------------------------------------------------------- web images
def _stretch(a, lo=1, hi=99.7, gamma=0.8):
    a = a.astype(float); l, h = np.percentile(a, lo), np.percentile(a, hi)
    return (np.clip((a - l) / max(h - l, 1), 0, 1) ** gamma)


def _composite(n, box, tiles, out_name, labels, stretch=False, model=True):
    """Overview strip (true aspect) plus close-up tiles. Model road: faint dots on the overview only."""
    im = load(n); x0, x1, y0, y1 = box
    W_in = 8.0; ov_h = W_in * (y1 - y0) / (x1 - x0); t_w = W_in / len(tiles); t_h = t_w / 1.5
    H_in = ov_h + t_h + 0.06
    fig = plt.figure(figsize=(W_in, H_in), dpi=200, facecolor="black")
    ax = fig.add_axes([0, (t_h + 0.06) / H_in, 1, ov_h / H_in])
    ov = im[y0:y1, x0:x1]
    ax.imshow(_stretch(ov) if stretch else ov, extent=(x0, x1, y1, y0))
    if model:
        rx, ry, _ = road_px(n); ok = (rx > x0) & (rx < x1)
        ax.plot(rx[ok], ry[ok], ".", ms=1.0, color=C_MODEL, alpha=0.55)
    for k, (cx, cy, hw) in enumerate(tiles, 1):
        hh = hw / 1.5
        ax.add_patch(Rectangle((cx - hw, cy - hh), 2 * hw, 2 * hh, fill=False, ec="white", lw=1.0))
        ax.text(cx, cy - hh - 25, str(k), color="white", fontsize=10, fontweight="bold", ha="center", va="bottom")
    az_ticks(ax, n, y0 + 95, x0, x1, fs=7.5)
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.axis("off")
    for k, (cx, cy, hw) in enumerate(tiles, 1):
        hh = hw / 1.5
        a2 = fig.add_axes([(k - 1) * t_w / W_in + 0.004, 0, t_w / W_in - 0.008, t_h / H_in])
        crop = im[int(cy - hh):int(cy + hh), int(cx - hw):int(cx + hw)]
        a2.imshow(_stretch(crop, 1, 99.9, 0.9) if stretch else crop, extent=(cx - hw, cx + hw, cy + hh, cy - hh))
        a2.set_xlim(cx - hw, cx + hw); a2.set_ylim(cy + hh, cy - hh); a2.axis("off")
        a2.text(0.03, 0.96, f"{k}  {labels[k - 1]}", transform=a2.transAxes, color="white", fontsize=8.5, fontweight="bold", va="top")
    fig.savefig("/tmp/comp.png", dpi=200, facecolor="black"); plt.close(fig)
    out = Image.open("/tmp/comp.png").convert("RGB")
    for w in (900, 1600):
        out.resize((w, round(out.height * w / out.width)), Image.LANCZOS).save(f"docs/img/{out_name}-{w}.webp", "WEBP", quality=84, method=6)


def web_cars():
    L = lights("p06")
    tiles = [(l["x"], l["y"], 150) for l in L]
    _composite("p06", (900, 5900, 1350, 2150), tiles, "zw_cars_twilight", [f"US-67, {l['road_km']:.0f} km" for l in L])


def web_streaks():
    _composite("p13", (900, 5990, 1300, 2100), [(2560, 1640, 300), (5500, 1768, 450)], "zw_car_streaks",
               ["US-67, 32–34 km", "US-67, 25–27 km"], stretch=True, model=False)


def web_small():
    """Unannotated close-ups for the app's bingo cards."""
    for n, (cx, cy), name, st in (("p06", (5000, 1880), "zw_bingo_carpair", False), ("p13", (2600, 1650), "zw_bingo_streak", True)):
        im = np.asarray(Image.open(f"{P.RAW}/{n}.jpg").convert("RGB")); w, h = 900, 600
        c = im[cy - h // 2:cy + h // 2, cx - w // 2:cx + w // 2]
        if st: c = (_stretch(c, 1, 99.9, 0.9) * 255).astype(np.uint8)
        Image.fromarray(c).resize((600, 400), Image.LANCZOS).save(f"docs/img/{name}-600.webp", "WEBP", quality=84, method=6)


if __name__ == "__main__":
    fig07(); web_cars(); web_streaks(); web_small()

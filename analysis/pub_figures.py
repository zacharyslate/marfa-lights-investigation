"""
Publication figures for the Marfa Lights investigation -> publication/figures/

    fig01_study_area        map of the 120 deg viewing fan, roads by visibility, rail, lit towers, towns
    fig02_panorama_zos      panorama from the Viewing Area with every catalogued source and the
                            Zone of Skepticism; (a) 155-300 deg, (b) zoom on the US-67 / RM 2810 sector
    fig03_headlights        measured headlamp beams with the observer's position in each beam, and the
                            predicted brightness of cars facing the Viewing Area
    fig04_sightlines        terrain cross-sections along four bearings with the line of sight
    fig05_refraction        visible road length and apparent-elevation shift versus refraction k

Each figure is written as PDF (vector, fonts embedded as Type 42), SVG, and PNG at 300 dpi.
Colours: Okabe & Ito (2008) colour-blind-safe palette.

Run from the repository root after the analysis chain (see publication/README.md):
    python analysis/pub_figures.py
"""
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LightSource
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon
from pyproj import CRS, Geod, Transformer

OUT = "publication/figures"
GEOD = Geod(ellps="WGS84")
R = 6_371_000.0
K0 = 0.13
M2D = 180 / math.pi / 1000          # mrad -> deg
MM = 1 / 25.4
W2 = 180 * MM                        # double-column width
W1 = 88 * MM                         # single-column width

OI = {"black": "#000000", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
      "yellow": "#F0E442", "blue": "#0072B2", "verm": "#D55E00", "purple": "#CC79A7", "grey": "#9A9A9A"}
C_VIS, C_MARG, C_HID = OI["verm"], OI["orange"], "#C8C8C8"
C_ROAD2 = OI["purple"]
C_RAIL = OI["blue"]
C_ZOS = OI["green"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 7.5, "axes.titlesize": 8, "axes.labelsize": 7.5,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 6.5, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none", "savefig.dpi": 300,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})

S = json.load(open("docs/data/site.json"))
Z = json.load(open("data/derived/zos.json"))
HL = json.load(open("data/derived/headlights.json"))
V = (S["viewer"]["lon"], S["viewer"]["lat"])
Z0 = S["viewer"]["z"]
SKY = np.array(S["sky"])
HW = S["hwy"]
ROADS = S["roads"]


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    meta = {"pdf": {"CreationDate": None, "ModDate": None}, "svg": {"Date": None}, "png": {}}   # reproducible files
    for ext in ("pdf", "svg", "png"):
        fig.savefig(f"{OUT}/{name}.{ext}", bbox_inches="tight", pad_inches=0.02, metadata=meta[ext])
    plt.close(fig)
    print("wrote", name)


def m2deg(x):
    return np.asarray(x, float) * M2D


def panel(ax, letter, x=-0.06, y=1.02):
    ax.text(x, y, letter, transform=ax.transAxes, fontweight="bold", fontsize=9, va="bottom", ha="left")


# ============================================================ figure 1: study area map
def fig01():
    aeqd = CRS.from_proj4(f"+proj=aeqd +lat_0={V[1]} +lon_0={V[0]} +datum=WGS84 +units=km")
    T = Transformer.from_crs("EPSG:4326", aeqd, always_xy=True)
    d = np.load("data/derived/dem_overview.npz")
    z = d["z"].astype(float)
    z[z < 0] = np.nan
    lon = d["lon0"] + np.arange(z.shape[1]) * d["step"]
    lat = d["lat1"] - np.arange(z.shape[0]) * d["step"]
    LO, LA = np.meshgrid(lon, lat)
    X, Y = T.transform(LO, LA)
    ls = LightSource(azdeg=315, altdeg=40)
    dx = float(d["step"]) * 111.0 * 1000 * math.cos(math.radians(30.1))
    hs = ls.hillshade(np.nan_to_num(z, nan=np.nanmin(z)), vert_exag=3, dx=dx, dy=float(d["step"]) * 111000)

    XL, YL = (-84, 30), (-80, 20)
    fig, ax = plt.subplots(figsize=(W2, W2 * 0.82))
    ax.pcolormesh(X, Y, hs, cmap="Greys_r", shading="gouraud", vmin=-0.6, vmax=1.5, rasterized=True, zorder=0, alpha=0.8)
    cs = ax.contour(X, Y, z, levels=np.arange(800, 2600, 200), colors="k", linewidths=0.2, alpha=0.35, zorder=1)
    ax.clabel(cs, levels=[1200, 1600, 2000], fontsize=5, fmt="%d m", inline_spacing=1)

    # fan and rays
    for r in S["rays"]:
        x, y = T.transform(r[2], r[1])
        ax.plot([0, x], [0, y], color="k" if r[4] else "#444", lw=0.18, alpha=0.4 if r[4] else 0.3, zorder=2)
    for az, lab_km in zip(S["fan"], (40, 62)):
        lo, la, _ = GEOD.fwd(V[0], V[1], az, 120_000)
        x, y = T.transform(lo, la)
        ax.plot([0, x], [0, y], color="k", lw=0.9, ls=(0, (4, 2)), zorder=3)
        lo, la, _ = GEOD.fwd(V[0], V[1], az, lab_km * 1000)
        x, y = T.transform(lo, la)
        ax.text(x, y, f"{az:.1f}°", fontsize=6.5, ha="center", va="center",
                bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.85), zorder=9)

    # rail
    for ln in S["rail"]:
        c = np.array(ln["c"])
        x, y = T.transform(c[:, 1], c[:, 0])
        ax.plot(x, y, color="white", lw=2.4 if ln["m"] else 1.4, zorder=3, solid_capstyle="butt")
        ax.plot(x, y, color=C_RAIL, lw=1.3 if ln["m"] else 0.7, zorder=4, ls="-" if ln["o"] == "UP" else (0, (3, 1.2)))

    # roads: casing, then visible/marginal parts on top
    def draw_road(lat, lon, cls, col_vis, lw=1.1):
        x, y = T.transform(lon, lat)
        ax.plot(x, y, color="white", lw=lw + 1.2, zorder=5, solid_capstyle="round")
        ax.plot(x, y, color="#6E6E6E", lw=lw * 0.8, zorder=6)
        for c, col in (("m", C_MARG), ("v", col_vis)):
            m = np.array([q == c for q in cls])
            xs = np.where(m, x, np.nan)
            ax.plot(xs, np.where(m, y, np.nan), color=col, lw=lw + 1.2, zorder=7, solid_capstyle="butt")

    draw_road([p[0] for p in HW], [p[1] for p in HW], [p[6] for p in HW], C_VIS)
    for rd in ROADS:
        p = rd["p"]
        # break the line where samples jump (separate pieces are concatenated in the file)
        la, lo, cl = [], [], []
        for i, q in enumerate(p):
            if i and GEOD.inv(p[i - 1][1], p[i - 1][0], q[1], q[0])[2] > 400:
                draw_road(la, lo, cl, C_ROAD2, 0.8)
                la, lo, cl = [], [], []
            la.append(q[0]); lo.append(q[1]); cl.append(q[6])
        draw_road(la, lo, cl, C_ROAD2, 0.8)

    # towers
    for t in S["towers"]:
        x, y = T.transform(t["lon"], t["lat"])
        if not (XL[0] < x < XL[1] and YL[0] < y < YL[1]):
            continue
        lit = t["light"] != "none"
        seen = t["kc"] is not None and t["kc"] <= K0
        if lit:
            ax.plot(x, y, marker="D", ms=4.2, mfc="k" if seen else "white", mec="k", mew=0.8, zorder=8)
    # towns
    for t in S["towns"]:
        x, y = T.transform(t["lon"], t["lat"])
        if XL[0] < x < XL[1] and YL[0] < y < YL[1]:
            ax.plot(x, y, "s", ms=3, color="k", zorder=8)
            left = t["n"].startswith("Ojinaga")
            ax.text(x + (-1.2 if left else 1.2), y + 1.2, t["n"].replace(", Chihuahua", ""), fontsize=6.5, zorder=9,
                    ha="right" if left else "left", bbox=dict(fc="white", ec="none", pad=0.5, alpha=0.75))
    for f in S["fields"]:
        if f["k"] == "balloon":
            x, y = T.transform(f["lon"], f["lat"])
            y = min(y, YL[1] - 2.5)
            ax.plot(x, y, marker="^", ms=5, mfc="white", mec="k", mew=0.8, zorder=8)
            ax.text(x + 1.2, y - 3.2, "TARS aerostat", fontsize=6.5, zorder=9, bbox=dict(fc="white", ec="none", pad=0.5, alpha=0.75))
    for lab, la, lo, dx_, dy_ in (("Chinati Peak", 29.954, -104.478, 1.5, -1.0), ("US-67 high point", 30.0384, -104.19452, 1.5, 1.0)):
        x, y = T.transform(lo, la)
        ax.plot(x, y, "^", ms=4, color="k", zorder=8)
        ax.text(x + dx_, y + dy_, lab, fontsize=6.5, zorder=9, bbox=dict(fc="white", ec="none", pad=0.5, alpha=0.75))
    ax.plot(0, 0, marker="*", ms=11, mfc=OI["yellow"], mec="k", mew=0.8, zorder=10)
    ax.text(1.8, 1.5, "Viewing Area", fontsize=7, fontweight="bold", zorder=10, bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.8))

    ax.set_xlim(*XL)
    ax.set_ylim(*YL)
    ax.set_aspect("equal")
    ax.set_xlabel("km east of the Viewing Area")
    ax.set_ylabel("km north of the Viewing Area")
    ax.spines[["top", "right"]].set_visible(True)
    # north arrow + scale bar
    ax.annotate("", xy=(22, -22), xytext=(22, -30), arrowprops=dict(arrowstyle="-|>", lw=0.8, color="k"))
    ax.text(22, -21.3, "N", ha="center", fontsize=7, fontweight="bold")
    ax.plot([-78, -58], [-74.5, -74.5], color="k", lw=2, solid_capstyle="butt")
    ax.text(-68, -73.3, "20 km", ha="center", fontsize=6.5)
    handles = [Line2D([], [], color=C_VIS, lw=2.2, label="US-67, visible at k = 0.13"),
               Line2D([], [], color=C_MARG, lw=2.2, label="US-67 / other roads, marginal"),
               Line2D([], [], color=C_ROAD2, lw=2, label="Other state roads, visible"),
               Line2D([], [], color="#6E6E6E", lw=1.0, label="Roads hidden by terrain"),
               Line2D([], [], color=C_RAIL, lw=1.3, label="Union Pacific"),
               Line2D([], [], color=C_RAIL, lw=0.9, ls=(0, (3, 1.2)), label="Texas Pacifico"),
               Line2D([], [], color="k", lw=0.9, ls=(0, (4, 2)), label="Fan bounds (120°)"),
               Line2D([], [], marker="D", ls="", mfc="k", mec="k", ms=4, label="Lit tower, top in view"),
               Line2D([], [], marker="D", ls="", mfc="white", mec="k", ms=4, label="Lit tower, top hidden")]
    ax.legend(handles=handles, loc="lower right", fontsize=6, frameon=True, facecolor="white", edgecolor="none", framealpha=0.85)
    ax.set_title("Viewing fan from the Marfa Lights Viewing Area: 241 rays at 0.5°, 157.3°–277.3° true", loc="left")
    save(fig, "fig01_study_area")


# ============================================================ panorama helpers
def draw_terrain(ax, a0, a1):
    s = SKY[(SKY[:, 0] >= a0) & (SKY[:, 0] <= a1)]
    az = s[:, 0]
    bottom = -2.0
    for col, gray in ((1, "#E4E4E4"), (5, "#D2D2D2"), (4, "#BFBFBF"), (3, "#A9A9A9")):
        ax.fill_between(az, bottom, m2deg(s[:, col]), color=gray, lw=0, zorder=1)
    ax.plot(az, m2deg(s[:, 1]), color="k", lw=0.7, zorder=6)


def draw_zos(ax):
    for ring in Z["tiers"]["B"]:
        r = np.array(ring)
        ax.add_patch(Polygon(np.c_[r[:, 0], m2deg(r[:, 1])], closed=True, fc="none", ec=C_ZOS, lw=0.7,
                             ls=(0, (3, 1.5)), zorder=4))
    for ring in Z["tiers"]["A"]:
        r = np.array(ring)
        ax.add_patch(Polygon(np.c_[r[:, 0], m2deg(r[:, 1])], closed=True, fc=C_ZOS, ec=C_ZOS, lw=0.3, alpha=0.33, zorder=3))


def exaggeration(fig, ax):
    fig.canvas.draw()
    bb = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    return ((x1 - x0) / bb.width) / ((y1 - y0) / bb.height)


def draw_sources(ax, a0, a1, label=True, zoom=False):
    inw = lambda a: a0 <= a <= a1
    # US-67
    for c, col, ms in (("h", C_HID, 0.8), ("m", C_MARG, 1.8), ("v", C_VIS, 2.2)):
        pts = np.array([[p[2], p[7]] for p in HW if p[6] == c and inw(p[2])])
        if len(pts) and c != "h":
            ax.plot(pts[:, 0], m2deg(pts[:, 1]), "o", ms=ms, color=col, mec="none", zorder=7)
    for rd in ROADS:
        pts = np.array([[q[2], q[4]] for q in rd["p"] if q[6] == "v" and inw(q[2])])
        if len(pts):
            ax.plot(pts[:, 0], m2deg(pts[:, 1]), "o", ms=1.7, color=C_ROAD2, mec="none", zorder=7)
    rp = np.array([[r[1], r[3]] for r in S["railpano"] if r[4] <= K0 and inw(r[1])])
    if len(rp):
        ax.plot(rp[:, 0], m2deg(rp[:, 1]), "s", ms=1.4, color=C_RAIL, mec="none", zorder=7)
    for t in S["towers"]:
        if t["light"] == "none" or t["a"] is None or not inw(t["az"]):
            continue
        seen = t["kc"] <= K0
        ax.plot(t["az"], m2deg(t["a"]), marker="D", ms=4 if zoom else 3.4, mfc="k" if seen else "white", mec="k", mew=0.7, zorder=8)
        if label:
            ax.annotate(f"{t['h']:.0f} m tower", (t["az"], m2deg(t["a"])), xytext=(0, 6), textcoords="offset points",
                        ha="center", fontsize=5.8, zorder=9)
    off = {"Presidio": (-9, 0.62, "right"), "Ojinaga, Chihuahua": (-4, 0.80, "left"), "Shafter": (4, 0.36, "left"),
           "Marfa": (-6, 0.62, "right")}
    for t in S["towns"]:
        if inw(t["az"]) and "a" in t:
            dx, dy, ha = off.get(t["n"], (0, 0.3, "center"))
            y = m2deg(float(np.interp(t["az"], SKY[:, 0], SKY[:, 1]))) + dy
            ax.annotate(t["n"].replace(", Chihuahua", "") + (" (in view)" if t["kc"] <= 1 else " skyglow"), (t["az"], y),
                        xytext=(dx, 0), textcoords="offset points", ha=ha, va="bottom", fontsize=5.8, zorder=9,
                        bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.7))
    for f in S["fields"]:
        if f["k"] == "balloon" and inw(f["az"]):
            ax.axvline(f["az"], color="k", lw=0.6, ls=(0, (1, 1.5)), zorder=5)
            ax.annotate("aerostat\n(altitude\nvaries)", (f["az"], 0.80), ha="left", va="top", fontsize=5.8, xytext=(2, 0),
                        textcoords="offset points", bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.7))
    for az in S["fan"]:
        if inw(az):
            ax.axvline(az, color="k", lw=0.6, ls=(0, (4, 2)), zorder=5)


def fig02():
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(W2, W2 * 0.78), gridspec_kw=dict(height_ratios=[1, 1.25], hspace=0.42))
    A0, A1 = 155, 300
    draw_terrain(a1, A0, A1)
    draw_zos(a1)
    draw_sources(a1, A0, A1, label=False)
    a1.axhline(0, color="k", lw=0.4, ls=":", zorder=5)
    a1.set_xlim(A0, A1)
    a1.set_ylim(-0.75, 0.95)
    a1.set_xticks(np.arange(160, 301, 10))
    a1.set_ylabel("Elevation angle (°)")
    a1.set_xlabel("True bearing (°)")
    a1.add_patch(plt.Rectangle((224, -0.72), 38, 0.98, fill=False, lw=0.7, ec="k", ls="-", zorder=9))
    a1.text(224.4, 0.23, "b", fontsize=7, fontweight="bold", va="top", zorder=9)
    for az, lab in ((180, "S"), (202.5, "SSW"), (225, "SW"), (247.5, "WSW"), (270, "W"), (292.5, "WNW")):
        a1.text(az, 0.93, lab, ha="center", va="top", fontsize=6.5, color="#444")
    sec = a1.secondary_xaxis("top", functions=(lambda x: x - 6.2, lambda x: x + 6.2))
    sec.set_xlabel("Magnetic bearing (°), declination 6.2° E", fontsize=6.5)
    sec.tick_params(labelsize=6)
    a1.set_title("(a) Panorama from the Viewing Area, 155°–300° true", loc="left")

    B0, B1 = 224, 262
    draw_terrain(a2, B0, B1)
    draw_zos(a2)
    draw_sources(a2, B0, B1, label=True, zoom=True)
    a2.axhline(0, color="k", lw=0.4, ls=":", zorder=5)
    a2.set_xlim(B0, B1)
    a2.set_ylim(-0.45, 0.32)
    a2.set_xticks(np.arange(B0, B1 + 1, 2))
    a2.set_ylabel("Elevation angle (°)")
    a2.set_xlabel("True bearing (°)")
    a2.text(233.4, -0.30, "US-67", color=C_VIS, fontsize=7, fontweight="bold", ha="center")
    a2.text(258.3, 0.02, "RM 2810", color=C_ROAD2, fontsize=7, fontweight="bold", ha="center")
    a2.text(245.5, 0.27, "above the skyline: aircraft, stars, planets, satellites", fontsize=6, ha="center", color="#333",
            bbox=dict(fc="white", ec="none", pad=0.4, alpha=0.7))
    a2.set_title("(b) The US-67 and RM 2810 sector, 224°–262° true", loc="left")
    e1, e2 = exaggeration(fig, a1), exaggeration(fig, a2)
    a1.set_title(f"vertical ×{e1:.0f}", loc="right", fontsize=6.5)
    a2.set_title(f"vertical ×{e2:.0f}", loc="right", fontsize=6.5)
    handles = [Patch(fc=C_ZOS, alpha=0.33, ec=C_ZOS, lw=0.3, label="Zone of Skepticism, tier A (±0.3° az, ±0.1° el)"),
               Patch(fc="none", ec=C_ZOS, lw=0.7, ls=(0, (3, 1.5)), label="tier B (±3° az, ±0.25° el)"),
               Line2D([], [], marker="o", ls="", color=C_VIS, ms=3, label="US-67 visible (k = 0.13)"),
               Line2D([], [], marker="o", ls="", color=C_MARG, ms=3, label="US-67 marginal"),
               Line2D([], [], marker="o", ls="", color=C_ROAD2, ms=3, label="Other state roads visible"),
               Line2D([], [], marker="s", ls="", color=C_RAIL, ms=2.5, label="Railroad in view (4 m lamp)"),
               Line2D([], [], marker="D", ls="", mfc="k", mec="k", ms=3.5, label="Lit tower, top in view"),
               Line2D([], [], marker="D", ls="", mfc="white", mec="k", ms=3.5, label="Lit tower, top hidden"),
               Line2D([], [], color="k", lw=0.7, label="Skyline (k = 0.13)"),
               Patch(fc="#A9A9A9", label="Ridges ≤10 km"), Patch(fc="#BFBFBF", label="≤25 km"),
               Patch(fc="#D2D2D2", label="≤45 km"), Patch(fc="#E4E4E4", label="beyond")]
    fig.legend(handles=handles, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.075), fontsize=6.0, columnspacing=1.0,
               handletextpad=0.5)
    save(fig, "fig02_panorama_zos")


# ============================================================ figure 3: headlights
def fig03():
    import importlib.util
    spec = importlib.util.spec_from_file_location("hm", "analysis/headlight_model.py")
    hm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hm)
    fig = plt.figure(figsize=(W2, W2 * 0.72))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.05], hspace=0.5, wspace=0.22)
    hh = np.linspace(-40, 40, 321)
    vv = np.linspace(-4.5, 4.5, 181)
    Hg, Vg = np.meshgrid(hh, vv)
    levels = [30, 100, 300, 1000, 3000, 10000, 30000]
    obs = {}
    for rd in HL["roads"]:
        if rd["key"] in ("US67", "RM2810"):
            q = [p for p in rd["pts"] if p[4] in "vm" and abs(p[7]) < 90]
            obs[rd["key"]] = np.array([[p[7], p[8]] for p in q])
    for i, (beam, title, pts) in enumerate(((hm.LOW, "(a) Lower beam (LB2V), one lamp", hm.LB2V),
                                            (hm.HIGH, "(b) Upper beam (UB2), one lamp", hm.UB2))):
        ax = fig.add_subplot(gs[0, i])
        I = beam(Hg, Vg)
        cf = ax.contourf(Hg, Vg, np.log10(I), levels=np.log10([10] + levels + [1e5]), cmap="Greys", alpha=0.9)
        c = ax.contour(Hg, Vg, np.log10(I), levels=np.log10(levels), colors="k", linewidths=0.3)
        ax.clabel(c, fmt=lambda x: f"{10**x:,.0f}", fontsize=5, inline_spacing=1)
        p = np.array(pts)
        ax.plot(p[:, 0], p[:, 1], "+", color=OI["sky"], ms=3.5, mew=0.8, label="measured test point")
        ax.plot(obs["US67"][:, 0], obs["US67"][:, 1], "o", ms=1.8, color=C_VIS, mec="none", alpha=0.8, label="Viewing Area seen from US-67 cars")
        ax.plot(obs["RM2810"][:, 0], obs["RM2810"][:, 1], "o", ms=1.8, color=C_ROAD2, mec="none", alpha=0.8, label="… from RM 2810 cars")
        ax.axhline(0, color="k", lw=0.3)
        ax.axvline(0, color="k", lw=0.3)
        ax.set_xlim(-40, 40)
        ax.set_ylim(-4.5, 4.5)
        ax.set_xlabel("h: angle right of the car's heading (°)")
        if i == 0:
            ax.set_ylabel("v: angle above the lamp axis (°)")
        ax.set_title(title, loc="left")
        edge = 20 if i == 0 else 12
        ax.axvspan(-40, -edge, color="white", alpha=0.45, lw=0)
        ax.axvspan(edge, 40, color="white", alpha=0.45, lw=0)
        ax.text(-39, 4.2, "extrapolated", fontsize=5.6, va="top", style="italic")
        ax.text(39, 4.2, "extrapolated", fontsize=5.6, va="top", ha="right", style="italic")
        if i == 1:
            ax.legend(loc="lower right", fontsize=5.6, frameon=True, facecolor="white", edgecolor="none", framealpha=0.85)
    ax = fig.add_subplot(gs[1, :])
    for key, col, lab in (("US67", C_VIS, "US-67"), ("RM2810", C_ROAD2, "RM 2810")):
        rd = [r for r in HL["roads"] if r["key"] == key][0]
        q = np.array([[p[0], p[9], p[10], p[11], p[12], p[13], p[14]] for p in rd["pts"]
                      if p[4] in "vm" and abs(p[7]) < 90], float)
        q = q[np.argsort(q[:, 0])]
        ax.errorbar(q[:, 0], q[:, 4], yerr=[q[:, 4] - q[:, 6], q[:, 5] - q[:, 4]], fmt="none", ecolor=col, elinewidth=0.4, alpha=0.35)
        ax.plot(q[:, 0], q[:, 4], "^", ms=2.6, color=col, mec="none", label=f"{lab}, high beam")
        ax.plot(q[:, 0], q[:, 1], "o", ms=2.3, mfc="white", mec=col, mew=0.6, label=f"{lab}, low beam")
    ax.axhline(-1.46, color="k", lw=0.5, ls="--")
    ax.text(247, -1.46, "Sirius (−1.46)", fontsize=6, va="bottom", ha="center")
    ax.axhline(6.0, color="k", lw=0.5, ls=":")
    ax.text(247, 6.0, "typical naked-eye limit (≈6)", fontsize=6, va="bottom", ha="center")
    ax.set_xlim(227.5, 263)
    ax.set_ylim(10.5, -3.5)
    ax.set_xlabel("True bearing of the car from the Viewing Area (°)")
    ax.set_ylabel("Apparent magnitude")
    ax.set_title("(c) Predicted brightness of a car facing the Viewing Area (two lamps; MOR 100 km; bars: ±0.5° aim, fall-off range)", loc="left")
    ax.legend(loc="lower center", ncol=2, fontsize=6, bbox_to_anchor=(0.42, 0.03))
    save(fig, "fig03_headlights")


# ============================================================ figure 4: sight-line cross-sections
def fig04():
    P = json.load(open("data/derived/profiles_fig.json"))
    E = Z0 + 1.6
    cases = [("233.6", "233.6° true: US-67 straight, in view", "US67"),
             ("240", "240° true: US-67 behind the Mitchell Flat rise", "US67"),
             ("255.6", "255.6° true: RM 2810 in the Chinati foothills", "RM2810"),
             ("190", "190° true: Texas Pacifico track, no highway", None)]
    fig, axs = plt.subplots(4, 1, figsize=(W2, W2 * 0.95), sharex=True, gridspec_kw=dict(hspace=0.45))
    for ax, (az, title, road) in zip(axs, cases):
        z = np.array([np.nan if v is None else v for v in P["prof"][az]], float)
        d = np.arange(len(z)) * 100.0
        for k, ls in ((K0, "-"), (1.0, "--")):
            y = z - E - d ** 2 * (1 - k) / (2 * R)
            if k == K0:
                ang = np.full_like(d, -np.inf)
                ang[1:] = np.maximum.accumulate(np.nan_to_num(y[1:] / d[1:], nan=-np.inf))
                vis = np.r_[True, y[1:] / d[1:] >= ang[1:] - 1e-12]
                ax.fill_between(d / 1000, -600, y, color="#D9D9D9", lw=0)
                ax.plot(d / 1000, y, color="k", lw=0.6)
                ax.plot(d / 1000, np.where(vis, y, np.nan), color=OI["verm"] if road else OI["blue"], lw=1.6,
                        solid_capstyle="butt")
                j = np.nanargmax(np.where(d > 500, y / np.maximum(d, 1), -np.inf))
                ax.plot([0, 80], [0, 80000 * y[j] / d[j]], color="k", lw=0.5, ls=":")
        # road crossings on this bearing
        a = float(az)
        if road == "US67":
            dd = [p[3] for p in HW if abs(p[2] - a) < 0.08]
        elif road == "RM2810":
            dd = [q[3] for rd in ROADS if rd["k"] == "RM2810" for q in rd["p"] if abs(q[2] - a) < 0.08]
        else:
            dd = [r[2] for r in S["railpano"] if abs(r[1] - a) < 0.6]
        for x in sorted(set(round(v, 1) for v in dd)):
            yi = np.interp(x * 1000, d, z - E - d ** 2 * (1 - K0) / (2 * R))
            ax.plot(x, yi, "v", ms=3.5, color="k", zorder=5)
        ax.set_ylim(-420, 350)
        ax.set_ylabel("m relative to eye")
        ax.set_title(title, loc="left")
        ax.axhline(0, color="k", lw=0.3)
    axs[-1].set_xlabel("Distance from the Viewing Area (km)")
    axs[-1].set_xlim(0, 80)
    handles = [Line2D([], [], color="k", lw=0.6, label="Ground, reduced for curvature and refraction (k = 0.13)"),
               Line2D([], [], color=OI["verm"], lw=1.6, label="Ground in direct view of the eye"),
               Line2D([], [], color="k", lw=0.5, ls=":", label="Steepest sight line (the skyline ray)"),
               Line2D([], [], marker="v", ls="", color="k", ms=3.5, label="Road or track crossing")]
    fig.legend(handles=handles, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.04), fontsize=6.3)
    ex = exaggeration(fig, axs[0]) * 1000      # x in km, y in m
    for ax in axs:
        ax.set_title(f"vertical ×{ex:.0f}", loc="right", fontsize=6.3)
    save(fig, "fig04_sightlines")


# ============================================================ figure 5: refraction sensitivity
def fig05():
    fig, (a, b) = plt.subplots(1, 2, figsize=(W2, W2 * 0.36), gridspec_kw=dict(wspace=0.3))
    ks = np.linspace(-1, 3, 401)
    kc67 = np.array([p[5] for p in HW])
    a.plot(ks, [(kc67 <= k).sum() * 0.06 for k in ks], color=C_VIS, lw=1.3, label="US-67 (Shafter–Marfa, 64.6 km)")
    rm = np.array([q[5] for rd in ROADS if rd["k"] == "RM2810" for q in rd["p"]])
    a.plot(ks, [(rm <= k).sum() * 0.12 for k in ks], color=C_ROAD2, lw=1.3, label="RM 2810 (in the fan)")
    a.axvline(K0, color="k", lw=0.5, ls="--")
    a.text(K0 + 0.05, 46, "k = 0.13", fontsize=6)
    a.set_xlabel("Refraction coefficient k")
    a.set_ylabel("Road length with k_crit ≤ k (km)")
    a.set_title("(a) Road in view versus refraction", loc="left")
    a.legend(loc="upper left", fontsize=6)
    sec = a.secondary_xaxis("top", functions=(lambda k: k / 5.338 - 0.0343, lambda g: (g + 0.0343) * 5.338))
    sec.set_xlabel("dT/dz (K/m) at 850 hPa, 283 K", fontsize=6.3)
    sec.tick_params(labelsize=6)
    d = np.linspace(0, 60, 200)
    for dk, ls in ((0.5, ":"), (1.0, "--"), (2.0, "-")):
        b.plot(d, d * 1000 * dk / (2 * R) * 180 / math.pi, color="k", lw=0.8, ls=ls, label=f"Δk = {dk:g}")
    b.set_xlabel("Distance to the light (km)")
    b.set_ylabel("Rise in apparent elevation (°)")
    b.set_title("(b) Apparent-elevation shift, Δα = dΔk/2R", loc="left")
    b.legend(loc="upper left", fontsize=6)
    save(fig, "fig05_refraction")


# ============================================================ figure 6: activity-weighted zone
SEQ = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]      # one-hue ordinal ramp (validated, light surface)


def draw_rate(ax, WZ, a0, a1):
    s = SKY[(SKY[:, 0] >= a0) & (SKY[:, 0] <= a1)]
    az = s[:, 0]
    for col, gray in ((1, "#EFEFEF"), (5, "#E4E4E4"), (4, "#D9D9D9"), (3, "#CDCDCD")):
        ax.fill_between(az, -2.0, m2deg(s[:, col]), color=gray, lw=0, zorder=1)
    for lv, c in zip(WZ["levels"], SEQ):
        for ring in WZ["rate_polys"][f"{lv:g}"]:
            r = np.array(ring)
            if r[:, 0].max() < a0 - 1 or r[:, 0].min() > a1 + 1:
                continue
            ax.add_patch(Polygon(np.c_[r[:, 0], m2deg(r[:, 1])], closed=True, fc=c, ec="none", zorder=3))
    for ring in WZ["fixed_polys"]:
        r = np.array(ring)
        if r[:, 0].max() < a0 - 1 or r[:, 0].min() > a1 + 1:
            continue
        ax.add_patch(Polygon(np.c_[r[:, 0], m2deg(r[:, 1])], closed=True, fc="none", ec="k", lw=0.5, hatch="////", zorder=4))
    ax.plot(az, m2deg(s[:, 1]), color="k", lw=0.7, zorder=6)
    for a in S["fan"]:
        if a0 <= a <= a1:
            ax.axvline(a, color="k", lw=0.6, ls=(0, (4, 2)), zorder=5)


def fig06():
    WZ = json.load(open("data/derived/weighted_zone.json"))
    st = WZ["standard"]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(W2, W2 * 0.72), gridspec_kw=dict(height_ratios=[1, 1.2], hspace=0.45))
    draw_rate(a1, st, 155, 300)
    a1.set_xlim(155, 300)
    a1.set_ylim(-0.75, 0.6)
    a1.set_xticks(np.arange(160, 301, 10))
    a1.set_ylabel("Elevation angle (°)")
    a1.set_xlabel("True bearing (°)")
    a1.add_patch(plt.Rectangle((224, -0.72), 38, 0.98, fill=False, lw=0.7, ec="k", zorder=9))
    a1.text(224.4, 0.23, "b", fontsize=7, fontweight="bold", va="top", zorder=9)
    lab = dict(fontsize=6, ha="center", zorder=10, bbox=dict(fc="white", ec="none", pad=0.4, alpha=0.8))
    a1.text(186, -0.66, "Texas Pacifico track, ≤ 0.08 trains/h", **lab)
    a1.text(233, -0.62, "US-67", **lab)
    a1.text(249, 0.40, "RM 2810", **lab)
    a1.text(272, 0.40, "US-90, UP, Marfa →", **lab)
    a1.set_title("(a) Expected ordinary lights per hour: standard night, k = 0.13, MOR 100 km, error ±0.3° × ±0.1°", loc="left", fontsize=7.3)
    draw_rate(a2, st, 224, 262)
    a2.set_xlim(224, 262)
    a2.set_ylim(-0.45, 0.32)
    a2.set_xticks(np.arange(224, 263, 2))
    a2.set_ylabel("Elevation angle (°)")
    a2.set_xlabel("True bearing (°)")
    a2.text(233.4, -0.30, "US-67 northbound: up to ~15 cars/h", **lab)
    a2.text(250.5, 0.25, "RM 2810: ≤ 0.5 cars/h", **lab)
    a2.text(245.5, -0.2, "no catalogued source", fontsize=6.5, ha="center", style="italic", color="#333", zorder=10)
    a2.set_title("(b) The US-67 and RM 2810 sector", loc="left")
    e1, e2 = exaggeration(fig, a1), exaggeration(fig, a2)
    for ax, e in ((a1, e1), (a2, e2)):
        ax.text(0.995, 0.97, f"vertical ×{e:.0f}", transform=ax.transAxes, ha="right", va="top", fontsize=6.3, zorder=11,
                bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.8))
    handles = [Patch(fc=c, label=l) for c, l in zip(SEQ, ["0.01–0.1 per hour", "0.1–1", "1–10", "≥ 10"])]
    handles += [Patch(fc="white", ec="k", hatch="////", lw=0.5, label="Permanent light (tower, town, skyglow, aerostat)"),
                Line2D([], [], color="k", lw=0.7, label="Skyline (k = 0.13)")]
    fig.legend(handles=handles, loc="lower center", ncol=6, bbox_to_anchor=(0.5, -0.03), fontsize=6.0, columnspacing=1.0,
               handletextpad=0.5, title="Expected rate of catalogued transient lights (unshaded = < 0.01 per hour)", title_fontsize=6.3)
    save(fig, "fig06_weighted_zone")


if __name__ == "__main__":
    fig01()
    fig02()
    fig03()
    fig04()
    fig05()
    fig06()

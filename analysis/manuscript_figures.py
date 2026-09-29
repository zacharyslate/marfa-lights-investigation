"""Schematic figure for the manuscript (publication/manuscript/): the line-of-sight geometry in the chord frame.

    python analysis/manuscript_figures.py   ->  publication/figures/fig00_geometry.{pdf,svg,png}

Drawn in the frame of the straight eye-lamp chord OQ: the terrain is plotted as its height y(s) relative to the
chord (curvature already included exactly), and a refracted ray with constant coefficient k is an arc that sags
ABOVE the chord by k s (D - s) / 2R. The lamp is visible when the arc clears every terrain sample, i.e. when
k >= k_crit = max_i 2 R y_i / (s_i (D - s_i)). Numbers are illustrative (D = 30 km), not a real profile.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = "publication/figures"
MM = 1 / 25.4
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "pdf.fonttype": 42, "svg.fonttype": "none",
                     "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 300})

R = 6.371e6
D = 30e3
s = np.linspace(0, D, 3001)


def sag(k):
    return k * s * (D - s) / (2 * R)


# illustrative terrain relative to the chord: a ridge near 11 km that rises ~4.5 m above the chord
rng = np.random.default_rng(3)
base = -1.6 * (1 - s / D) - 0.66 * (s / D) - 14 * np.sin(np.pi * s / D)
y = (base + 18.6 * np.exp(-((s - 11e3) / 1.6e3) ** 2) + 9.0 * np.exp(-((s - 24e3) / 1.0e3) ** 2)
     + 0.12 * np.convolve(rng.normal(size=s.size), np.ones(15) / 4, mode="same"))
y[0], y[-1] = -1.6, -0.66
i = np.argmax(np.where((s > 300) & (s < D - 300), y / (s * (D - s) + 1e-9), -np.inf))
kc = 2 * R * y[i] / (s[i] * (D - s[i]))

fig, ax = plt.subplots(figsize=(88 * MM, 88 * MM * 0.62))
ax.fill_between(s / 1e3, y, -30, color="#D9D9D9", lw=0, label="terrain relative to the chord")
ax.plot(s / 1e3, y, color="k", lw=0.7)
ax.plot([0, D / 1e3], [0, 0], color="k", lw=0.8, ls=(0, (4, 2)), label="chord $OQ$")
ax.plot(s / 1e3, sag(0.13), color="#D55E00", lw=1.1, label="ray, $k=0.13$ (blocked)")
ax.plot(s / 1e3, sag(kc), color="#0072B2", lw=1.1, label=f"ray, $k=k_{{crit}}={kc:.2f}$")
ax.plot([s[i] / 1e3] * 2, [0, y[i]], color="k", lw=0.9)
ax.plot(s[i] / 1e3, y[i], "o", ms=2.5, color="k")
ax.annotate("$y_i$", (s[i] / 1e3 + 0.45, y[i] / 2 - 0.3), fontsize=7, bbox=dict(fc="white", ec="none", pad=0.2))
ax.annotate("$s_i$", (s[i] / 1e3 / 2, -2.2), fontsize=7, ha="center")
ax.annotate("", (0, -1.2), (s[i] / 1e3, -1.2), arrowprops=dict(arrowstyle="<->", lw=0.5))
ax.plot(0, 0, "o", ms=4, color="k")
ax.plot(D / 1e3, 0, "*", ms=7, color="#E69F00", mec="k", mew=0.4)
ax.annotate("O (eye)", (0, 0), (1.2, 6.5), fontsize=7, arrowprops=dict(arrowstyle="-", lw=0.4))
ax.annotate("Q (lamp)", (D / 1e3, 0), (27.0, 6.5), fontsize=7, ha="right", arrowprops=dict(arrowstyle="-", lw=0.4))
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), fontsize=5.8, ncol=2, frameon=False)
ax.set_xlim(-0.5, D / 1e3 + 0.5)
ax.set_ylim(-17, 9)
ax.set_xlabel("Distance along the chord from the eye, $s$ (km)")
ax.set_ylabel("Height above the chord (m)")
os.makedirs(OUT, exist_ok=True)
meta = {"pdf": {"CreationDate": None, "ModDate": None}, "svg": {"Date": None}, "png": {}}
for ext in ("pdf", "svg", "png"):
    fig.savefig(f"{OUT}/fig00_geometry.{ext}", bbox_inches="tight", pad_inches=0.02, metadata=meta[ext])
print("k_crit (illustration) =", round(kc, 3))

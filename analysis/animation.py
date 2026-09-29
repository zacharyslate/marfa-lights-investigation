"""Animation: one northbound car on US-67 as seen from the Marfa lights viewing area.

    python analysis/animation.py            ->  docs/media/one_car.mp4, one_car.webm, one_car_poster.jpg

The scene is the US-67 sector of the panorama (Fig. 3b of the paper) at true scale: 228-240 deg true by -0.45 to
+1.0 deg elevation, rendered as at night. A car leaves Shafter northbound at 30 m/s (the speed measured in the
photographs). Its position, whether its headlamps are in view (P_vis >= 0.5 at k = 0.13), and its brightness (low
beam, fleet median, MOR 111 km) come from data/derived/los2/photometry.npz, sampled every 60 m along the road and
interpolated in time. The light is drawn with an area that grows with its brightness and is omitted when it is
fainter than the reference naked-eye limit (m_lim = 5.86). Time is compressed 20 times; the clock shows real time.
The red code beacon on the one lit tower in the scene flashes at a real-time rate (see BEACON_FPM).
"""
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marfa import photometry as PH                                           # noqa: E402
from marfa.run_photometry import JUNCTION_LON, MARFA_LAT, SHAFTER_LAT, MOR_REF, MU_REF, F_REF   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "media")
U = 30.0            # m/s
SPEEDUP = 20.0
FPS = 30
T0, T1 = 15.3, 30.6  # minutes after Shafter
B0, B1, E0, E1 = 228.0, 240.0, -0.45, 1.0
W, H = 1600, 290     # pixels
# Tower top beacon. The one lit tower in the scene (FCC ASR 1053636, 89 m) is registered to FCC lighting
# specification paragraphs 1, 3, 11, 21: paragraph 3 is a red code beacon at the top flashing 12-40 times a minute
# (paragraph 11 adds steady red side lights at mid-height, whose visibility is not modelled here). The actual rate
# is not known; 30 per minute is used. The beacon is animated in REAL time, not compressed, so that it flashes at
# 0.5 Hz on screen (a compressed 10 Hz flicker would be unreadable and above the 3 Hz photosensitivity limit).
BEACON_FPM = 30.0
BEACON_DUTY = 0.5    # fraction of each cycle lit (assumed)
BEACON_RAMP = 0.12   # s, incandescent rise and fall


def load():
    import json
    z = np.load(os.path.join(ROOT, "data/derived/los2/photometry.npz"), allow_pickle=True)
    us = (z["route"] == "US0067-KG") & (z["lat"] >= SHAFTER_LAT) & (z["lat"] <= MARFA_LAT) & (z["lon"] < JUNCTION_LON)
    ch = z["chain"][us]
    o = np.argsort(ch)[::-1]                       # northbound: from the Shafter end (high chainage) toward Marfa
    s = ch.max() - ch[o]                           # metres driven since Shafter
    mor = int(MOR_REF)
    site = json.load(open(os.path.join(ROOT, "docs/data/site.json")))
    return dict(s=s, az=z["az"][us][o], el=z["app_el"][us][o], view=z["view_head"][us][o],
                m=z[f"m_low_p50_rev_{mor}"][us][o], sky=np.array(site["sky"]), towers=site["towers"])


def scene(d):
    """The static night scene (sky, terrain layers, skyline, road locus, lit tower, Moon scale); returns fig, ax."""
    dpi = 100
    fig = plt.figure(figsize=(W / dpi, H / dpi), dpi=dpi)
    ax = fig.add_axes([0.045, 0.2, 0.945, 0.76])
    sk = d["sky"][(d["sky"][:, 0] >= B0 - 0.5) & (d["sky"][:, 0] <= B1 + 0.5)]
    m2d = 180 / np.pi / 1000
    ax.set_facecolor("#2d3f73")
    for col, gray in ((1, "#5a5c6b"), (5, "#4a4b57"), (4, "#3b3c45"), (3, "#2c2d34")):
        ax.fill_between(sk[:, 0], E0 - 1, sk[:, col] * m2d, color=gray, lw=0, zorder=1)
    ax.plot(sk[:, 0], sk[:, 1] * m2d, color="#8a90a8", lw=0.6, zorder=2)
    inv = d["view"] & (d["az"] >= B0) & (d["az"] <= B1)
    ax.plot(d["az"][inv], d["el"][inv], ".", ms=1.2, color="#ffffff", alpha=0.18, zorder=3)    # where a car can appear
    beacons = []
    for t in d["towers"]:
        if t["light"] != "none" and t["a"] is not None and B0 <= t["az"] <= B1 and t["kc"] <= 0.13:
            xy = (t["az"], t["a"] * m2d)
            halo = ax.scatter(*xy, s=90, color="#ff3b30", alpha=0.0, lw=0, zorder=4)
            core = ax.scatter(*xy, s=14, color="#ff5a4f", alpha=0.0, lw=0, zorder=4)
            beacons.append((halo, core))
            ax.text(xy[0], xy[1] - 0.06, "tower", ha="center", va="top", fontsize=8, color="#c8a4a4", zorder=4)
    ax.add_patch(plt.Circle((239.45, 0.70), 0.25, fill=False, ec="#e6e6e6", lw=0.8, zorder=4))
    ax.text(239.1, 0.70, "full Moon", ha="right", va="center", fontsize=9, color="#e6e6e6", zorder=5)
    ax.set_xlim(B0, B1)
    ax.set_ylim(E0, E1)
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(B0, B1 + 0.1, 1))
    ax.set_yticks([-0.4, 0, 0.5, 1.0])
    ax.tick_params(colors="#cccccc", labelsize=10)
    for sp in ax.spines.values():
        sp.set_color("#888888")
    fig.patch.set_facecolor("#111418")
    ax.set_xlabel("True bearing from the viewing area (°)", color="#cccccc", fontsize=10)
    ax.set_ylabel("Elev. (°)", color="#cccccc", fontsize=10)
    fig.beacons = beacons
    return fig, ax


def beacon_level(t_video):
    """Brightness 0..1 of the tower beacon at video time t_video (s), flashing at the real-time rate."""
    period = 60.0 / BEACON_FPM
    x = t_video % period
    on = BEACON_DUTY * period
    if x >= on:
        return 0.0
    return float(min(1.0, x / BEACON_RAMP, (on - x) / BEACON_RAMP))


def set_beacons(fig, t_video, level=None):
    lv = beacon_level(t_video) if level is None else level
    for halo, core in fig.beacons:
        halo.set_alpha(0.25 * lv)
        core.set_alpha(lv)


def encoder(path):
    """An ffmpeg process that takes raw RGBA frames on stdin and writes an H.264 MP4."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow", "-movflags", "+faststart",
           path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def to_webm(mp4, webm):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "36",
                    "-row-mt", "1", webm], check=True)


def main():
    d = load()
    mlim = float(PH.m_lim(MU_REF, F_REF))
    os.makedirs(OUT, exist_ok=True)
    fig, ax = scene(d)
    halo = ax.scatter([], [], s=[], color="#fff1c9", alpha=0.07, lw=0, zorder=6)
    glow = ax.scatter([], [], s=[], color="#fff1c9", alpha=0.18, lw=0, zorder=6)
    core = ax.scatter([], [], s=[], color="#fffaf0", lw=0, zorder=7)
    clock = ax.text(228.15, 0.93, "", fontsize=11, color="#f0f0f0", va="top", family="DejaVu Sans Mono", zorder=8)
    ax.text(236.2, 0.93, f"time ×{SPEEDUP:.0f}", fontsize=10, color="#bbbbbb", va="top", zorder=8)
    status = ax.text(228.15, 0.72, "", fontsize=10, color="#dddddd", va="top", zorder=8)

    n = int((T1 - T0) * 60 / SPEEDUP * FPS)
    tmin = np.linspace(T0, T1, n)
    s_car = tmin * 60 * U
    # sample-and-hold visibility (each 60 m sample stands for +-30 m of road); position and brightness interpolated
    idx = np.clip(np.searchsorted(d["s"], s_car - 30.0), 0, len(d["s"]) - 1)
    vis = d["view"][idx]
    az = np.interp(s_car, d["s"], d["az"])
    el = np.interp(s_car, d["s"], d["el"])
    mm = np.where(np.isfinite(d["m"]), d["m"], 99)
    m = np.interp(s_car, d["s"], mm)

    mp4 = os.path.join(OUT, "one_car.mp4")
    proc = encoder(mp4)
    poster_i = int(np.argmin(np.abs(tmin - 21.05)))
    for i in range(n):
        on = vis[i] and m[i] <= mlim and B0 <= az[i] <= B1
        if on:
            size = np.clip(6.5 - m[i], 0.3, 9.0) ** 1.8 * 2.2
            halo.set_offsets([[az[i], el[i]]]); halo.set_sizes([size * 10])
            glow.set_offsets([[az[i], el[i]]]); glow.set_sizes([size * 3.5])
            core.set_offsets([[az[i], el[i]]]); core.set_sizes([size])
            status.set_text(f"in view   m = {m[i]:+.1f}")
        else:
            halo.set_offsets(np.empty((0, 2))); glow.set_offsets(np.empty((0, 2))); core.set_offsets(np.empty((0, 2)))
            status.set_text("hidden by terrain" if not vis[i] else "too faint to see")
        set_beacons(fig, i / FPS, 1.0 if i == poster_i else None)     # the poster shows the beacon lit
        mins = int(tmin[i]); secs = int(round((tmin[i] - mins) * 60)) % 60
        clock.set_text(f"{mins:02d}:{secs:02d} after leaving Shafter")
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())
        proc.stdin.write(buf.tobytes())
        if i == poster_i:
            plt.imsave(os.path.join(OUT, "one_car_poster.jpg"), buf[:, :, :3])
    proc.stdin.close()
    proc.wait()
    webm = os.path.join(OUT, "one_car.webm")
    to_webm(mp4, webm)
    for f in (mp4, webm):
        print(f, os.path.getsize(f) // 1024, "kB")
    print("frames", n, "duration", n / FPS, "s")


if __name__ == "__main__":
    main()

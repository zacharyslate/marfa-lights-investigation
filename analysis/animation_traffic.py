"""Animation: one simulated hour of random two-way traffic on US-67, as seen from the Marfa lights viewing area.

    python analysis/animation_traffic.py      ->  docs/media/traffic_x20.{mp4,webm}, traffic_realtime.{mp4,webm}
                                                   and a poster frame for each (.jpg), plus traffic_sim.json

Same scene as animation.py (Fig. 3b of the paper, 228-240 deg by -0.45 to +1.0 deg, true scale). Vehicles are
simulated on the 64 km of US-67 between Marfa and Shafter:

  flow        Poisson arrivals, q = 0.02 x AADT / 2 per direction per hour, the night-hour assumption of the paper's
              rate map (Supporting Information S7), with AADT = 1252 veh/day (mean of the two 2025 count stations on
              this stretch, 1121 and 1383) -> q = 12.5 vehicles per hour each way. The night share of traffic has not
              been measured; this is an assumption.
  speed       each vehicle constant, normal with mean 30 m/s (measured in the photographs) and s.d. 2.5 m/s,
              clipped to 25-34 m/s (assumed spread).
  northbound  headlamps face the platform. Fleet-median low beam (UMTRI p50); a random 25% of drivers use high
              beams throughout (high-beam use on isolated rural roads, Reagan et al. 2017). Dipping for oncoming
              traffic is not modelled. In view where the headlamp (0.66 m) has P_vis >= 0.5 at k = 0.13.
  southbound  only the tail lamps face the platform. They are drawn at the FMVSS 108 maximum (18 cd), an upper
              bound: at the minimum (2 cd) no tail lamp on this road is visible. In view for the rear-lamp
              height (0.86 m). Brake lamps are not modelled.
  brightness  MOR 111 km; a lamp is drawn only when brighter than the reference naked-eye limit m_lim = 5.86, with
              an area that grows with brightness. Positions and magnitudes come from
              data/derived/los2/photometry.npz (60 m samples, interpolated; visibility sample-and-hold).
  beacon      the tower's red code beacon flashes 30 times a minute in real time in both videos (animation.py).

Two videos are made from the same simulated hour (21:00-22:00). The random seed is the first (from 1) for which
the number of vehicles that use the road during the hour (entering in [-L/30 m/s, 3600 s]) is within 1 of its
expectation (20) in each direction, with 4-6 on high beam (expectation 5): a typical hour, not a lucky one
(pick_seed; seed 24).
  traffic_x20       the whole hour, time compressed 20 times (3 min);
  traffic_realtime  a 5-minute excerpt in real time: the first 5-minute window whose lamp-seconds in view are closest
                    to the hour's average, i.e. a typical 5 minutes, not the busiest. Statistics: traffic_sim.json.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marfa import photometry as PH                                            # noqa: E402
from marfa.run_photometry import JUNCTION_LON, MARFA_LAT, SHAFTER_LAT, MOR_REF, MU_REF, F_REF   # noqa: E402
import animation as A                                                           # noqa: E402

ROOT = A.ROOT
OUT = A.OUT
AADT = (1121 + 1383) / 2
Q_H = 0.02 * AADT / 2            # vehicles per hour per direction
P_HIGH = 0.25
V_MEAN, V_SD, V_MIN, V_MAX = 30.0, 2.5, 25.0, 34.0
T_HOUR = 3600.0
START_CLOCK = 21 * 3600          # 21:00
RT_LEN = 300.0                   # s, real-time excerpt
HEAD_COL, TAIL_COL = "#fff1c9", "#ff4a3d"


def load():
    z = np.load(os.path.join(ROOT, "data/derived/los2/photometry.npz"), allow_pickle=True)
    us = (z["route"] == "US0067-KG") & (z["lat"] >= SHAFTER_LAT) & (z["lat"] <= MARFA_LAT) & (z["lon"] < JUNCTION_LON)
    o = np.argsort(z["chain"][us])                   # chainage increases from Marfa (x = 0) toward Shafter
    ch = z["chain"][us][o]
    mor = int(MOR_REF)
    g = lambda k: z[k][us][o]                        # noqa: E731
    fin = lambda a: np.where(np.isfinite(a), a, 99.0)  # noqa: E731
    site = json.load(open(os.path.join(ROOT, "docs/data/site.json")))
    return dict(x=ch - ch[0], az=g("az"), el=g("app_el"),
                view=g("view_head"), view_rear=g("view_rear"),
                m_low=fin(g(f"m_low_p50_rev_{mor}")), m_high=fin(g(f"m_high_p50_rev_{mor}")),
                m_tail=fin(g(f"m_tail_max_fwd_{mor}")),
                sky=np.array(site["sky"]), towers=site["towers"])


def simulate(L, rng):
    """Vehicles entering over [-L/V_MIN, T_HOUR] so the road is already in steady state at t = 0."""
    t_first = -L / V_MIN
    cars = []
    for direction in ("N", "S"):
        t = t_first
        while True:
            t += rng.exponential(3600.0 / Q_H)
            if t > T_HOUR:
                break
            v = float(np.clip(rng.normal(V_MEAN, V_SD), V_MIN, V_MAX))
            cars.append(dict(dir=direction, t0=t, v=v, high=bool(direction == "N" and rng.random() < P_HIGH)))
    return cars


def nearest(xs, x):
    """Index of the road sample nearest x: each 60 m sample stands for +-30 m of road (sample-and-hold)."""
    i = int(np.clip(np.searchsorted(xs, x), 1, len(xs) - 1))
    return i if xs[i] - x < x - xs[i - 1] else i - 1


def pick_seed(L):
    w0 = -L / V_MEAN
    expect = Q_H * (T_HOUR - w0) / 3600.0
    for seed in range(1, 1000):
        cars = simulate(L, np.random.default_rng(seed))
        use = [c for c in cars if c["t0"] >= w0]
        nn = sum(c["dir"] == "N" for c in use)
        nh = sum(c["high"] for c in use)
        if abs(nn - expect) <= 1 and abs(len(use) - nn - expect) <= 1 and abs(nh - P_HIGH * expect) <= 1:
            return seed
    raise RuntimeError("no typical seed found")


def lamps_at(d, cars, t, mlim):
    """Visible lamps at time t (s): lists of (az, el, m) for headlamps and for tail lamps."""
    L = d["x"][-1]
    head, tail = [], []
    for c in cars:
        s = (t - c["t0"]) * c["v"]
        if s < 0 or s > L:
            continue
        if c["dir"] == "N":                              # from Shafter (x = L) toward Marfa
            x = L - s
            vis = d["view"][nearest(d["x"], x)]
            m = np.interp(x, d["x"], d["m_high"] if c["high"] else d["m_low"])
            dest = head
        else:                                            # from Marfa (x = 0) toward Shafter
            x = s
            vis = d["view_rear"][nearest(d["x"], x)]
            m = np.interp(x, d["x"], d["m_tail"])
            dest = tail
        az = np.interp(x, d["x"], d["az"])
        if vis and m <= mlim and A.B0 <= az <= A.B1:
            dest.append((az, np.interp(x, d["x"], d["el"]), m))
    return head, tail


def size_of(m):
    return np.clip(6.5 - np.asarray(m), 0.3, 9.0) ** 1.8 * 2.2


def render(d, cars, t0, t1, speedup, name, mlim, label):
    fig, ax = A.scene(dict(view=d["view"], az=d["az"], el=d["el"], sky=d["sky"], towers=d["towers"]))
    dyn = []
    layers = {}
    for key, col in (("head", HEAD_COL), ("tail", TAIL_COL)):
        layers[key] = (ax.scatter([], [], s=[], color=col, alpha=0.07, lw=0, zorder=6, animated=True),
                       ax.scatter([], [], s=[], color=col, alpha=0.18, lw=0, zorder=6, animated=True),
                       ax.scatter([], [], s=[], color="#fffaf0" if key == "head" else "#ff6a5a", lw=0, zorder=7,
                                  animated=True))
        dyn += list(layers[key])
    for halo, core in fig.beacons:
        halo.set_animated(True); core.set_animated(True)
        dyn += [halo, core]
    clock = ax.text(228.15, 0.93, "", fontsize=11, color="#f0f0f0", va="top", family="DejaVu Sans Mono", zorder=8,
                    animated=True)
    status = ax.text(228.15, 0.72, "", fontsize=10, color="#dddddd", va="top", zorder=8, animated=True)
    dyn += [clock, status]
    ax.text(236.2, 0.93, label, fontsize=10, color="#bbbbbb", va="top", zorder=8)
    ax.scatter([231.55], [0.885], s=16, color="#fffaf0", lw=0, zorder=8)
    ax.text(231.65, 0.885, "headlamps (northbound)", fontsize=9, color="#dddddd", va="center", zorder=8)
    ax.scatter([233.75], [0.885], s=16, color="#ff6a5a", lw=0, zorder=8)
    ax.text(233.85, 0.885, "tail lamps (southbound, brightest legal)", fontsize=9, color="#dddddd", va="center",
            zorder=8)
    fig.canvas.draw()
    bg = fig.canvas.copy_from_bbox(fig.bbox)

    n = int(round((t1 - t0) / speedup * A.FPS))
    times = t0 + np.arange(n) * speedup / A.FPS
    counts = [len(lamps_at(d, cars, t, mlim)[0]) + len(lamps_at(d, cars, t, mlim)[1]) for t in times[::A.FPS]]
    poster_i = int(np.argmax(counts)) * A.FPS
    mp4 = os.path.join(OUT, f"{name}.mp4")
    proc = A.encoder(mp4)
    for i, t in enumerate(times):
        head, tail = lamps_at(d, cars, t, mlim)
        for key, lst in (("head", head), ("tail", tail)):
            halo, glow, core = layers[key]
            if lst:
                xy = np.array([(a, e) for a, e, _ in lst])
                sz = size_of([m for *_, m in lst])
                for art, f in ((halo, 10), (glow, 3.5), (core, 1)):
                    art.set_offsets(xy); art.set_sizes(sz * f)
            else:
                for art in (halo, glow, core):
                    art.set_offsets(np.empty((0, 2)))
        A.set_beacons(fig, i / A.FPS, 1.0 if i == poster_i else None)
        c = int(START_CLOCK + t)
        clock.set_text(f"{c // 3600:02d}:{c % 3600 // 60:02d}:{c % 60:02d}")
        on_road = [cc for cc in cars if 0 <= (t - cc["t0"]) * cc["v"] <= d["x"][-1]]
        nb = sum(cc["dir"] == "N" for cc in on_road)
        status.set_text(f"on the 64 km road: {nb} northbound, {len(on_road) - nb} southbound\n"
                        f"lights you could see now: {len(head)} white, {len(tail)} red")
        fig.canvas.restore_region(bg)
        for art in dyn:
            ax.draw_artist(art)
        buf = np.asarray(fig.canvas.buffer_rgba())
        proc.stdin.write(buf.tobytes())
        if i == poster_i:
            import matplotlib.pyplot as plt
            plt.imsave(os.path.join(OUT, f"{name}_poster.jpg"), buf[:, :, :3])
    proc.stdin.close()
    proc.wait()
    webm = os.path.join(OUT, f"{name}.webm")
    A.to_webm(mp4, webm)
    for f in (mp4, webm):
        print(f, os.path.getsize(f) // 1024, "kB")
    print(name, "frames", n, "duration", round(n / A.FPS, 1), "s")


def main():
    d = load()
    mlim = float(PH.m_lim(MU_REF, F_REF))
    seed = pick_seed(d["x"][-1])
    cars = simulate(d["x"][-1], np.random.default_rng(seed))
    # statistics of the simulated hour, per second
    ts = np.arange(0, T_HOUR, 1.0)
    per = np.array([[len(v) for v in lamps_at(d, cars, t, mlim)] for t in ts])
    anyv = per.sum(1) > 0
    win = int(RT_LEN)
    lamp_s = np.convolve(per.sum(1), np.ones(win), "valid")
    t_rt = float(np.argmin(np.abs(lamp_s - per.sum() * RT_LEN / T_HOUR)))
    stats = dict(seed=seed, q_per_h_each_way=Q_H, p_high=P_HIGH, speed=[V_MEAN, V_SD, V_MIN, V_MAX],
                 n_north_using_road=sum(c["dir"] == "N" and c["t0"] >= -d["x"][-1] / V_MEAN for c in cars),
                 n_south_using_road=sum(c["dir"] == "S" and c["t0"] >= -d["x"][-1] / V_MEAN for c in cars),
                 n_high=sum(c["high"] and c["t0"] >= -d["x"][-1] / V_MEAN for c in cars),
                 mean_white_in_view=round(float(per[:, 0].mean()), 2), mean_red_in_view=round(float(per[:, 1].mean()), 2),
                 expected_white_in_view_if_all_detected=round(Q_H * 10.02 / (V_MEAN * 3.6), 2),
                 frac_time_any_light=round(float(anyv.mean()), 3),
                 frac_time_white=round(float((per[:, 0] > 0).mean()), 3),
                 frac_time_red=round(float((per[:, 1] > 0).mean()), 3),
                 max_simultaneous=int(per.sum(1).max()),
                 realtime_excerpt_s=[t_rt, t_rt + RT_LEN],
                 realtime_excerpt_lamp_seconds=int(lamp_s[int(t_rt)]),
                 hour_mean_lamp_seconds_per_5min=round(float(per.sum() * RT_LEN / T_HOUR), 1),
                 m_lim=round(mlim, 2), mor_km=int(MOR_REF))
    os.makedirs(OUT, exist_ok=True)
    json.dump(stats, open(os.path.join(ROOT, "data/derived/los2/traffic_sim.json"), "w"), indent=1, default=float)
    print(json.dumps(stats, default=float))
    which = sys.argv[1:] or ["x20", "realtime"]
    if "x20" in which:
        render(d, cars, 0.0, T_HOUR, 20.0, "traffic_x20", mlim, "time ×20")
    if "realtime" in which:
        render(d, cars, t_rt, t_rt + RT_LEN, 1.0, "traffic_realtime", mlim, "real time")


if __name__ == "__main__":
    main()

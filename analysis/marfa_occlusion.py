"""
Marfa Lights investigation — highway occlusion maps (line of sight from the Viewing Area to US-67).

Input: data/los_results.json, produced by the in-browser LOS run against the USGS 3DEP DEM
(see meta block in that file). Model per highway point (60 m spacing):
  * observer eye 1.6 m above DEM at the Viewing Area; target = headlight 0.7 m (also 2.5 m)
  * terrain sampled every 15 m along the great-circle path, bilinear DEM interpolation
  * curvature + refraction via constant refraction coefficient k (effective radius R/(1-k))
  * closed-form critical coefficient k_crit: target visible iff k >= k_crit
    (validated against brute-force visibility at k_crit +/- 0.01 on 30 points: 0 mismatches)

Outputs:
  Marfa_occlusion_map1_standard.kml   Map 1 — standard atmosphere (k = 0.13)
  Marfa_occlusion_map2_refraction.kml Map 2 — minimum k needed to see each highway point
  Marfa_occlusion_points.csv          per-point table
  data/occlusion_page.json            data for the published page

Refraction coefficient <-> temperature gradient (Hirt et al. 2010, JGR 115, D21102):
    k = 503 * P / T^2 * (0.0343 + dT/dz)      P [hPa], T [K], dT/dz [K/m]
"""
import csv
import json
import math

import numpy as np
from pyproj import Geod

GEOD = Geod(ellps="WGS84")
R = 6371000.0
FAN = (157.276, 277.276)   # 120° fan: right bound from the KML, left bound 120° anticlockwise
BINS = [(-1e9, -1.0, "k1", "Visible under every refraction state (k ≤ −1 still clears)"),
        (-1.0, 0.13, "k2", "Visible at standard refraction (k 0.13); lost under strong sub-refraction"),
        (0.13, 0.5, "k3", "Needs a mild–moderate night inversion (k 0.13–0.5)"),
        (0.5, 1.0, "k4", "Needs a strong inversion (k 0.5–1.0)"),
        (1.0, 3.0, "k5", "Needs an extreme near-surface inversion / ducting (k 1–3)"),
        (3.0, 1e9, "k6", "Not visible under any plausible refraction (k > 3)")]
# ordinal single-hue ramp (validated with dataviz validate_palette.js --ordinal); KML uses the
# dark-surface steps so the lines read over satellite imagery
BIN_COLORS = {"k1": "#cde2fb", "k2": "#9ec5f4", "k3": "#6da7ec", "k4": "#3987e5", "k5": "#1c5cab",
              "k6": "#8d9894"}
MARGIN_M = 5.0   # |clearance| below this is within DEM/geometry uncertainty


def kbin(k):
    for lo, hi, key, _ in BINS:
        if lo < k <= hi:
            return key
    return "k6"


def std_class(r, k=0.13):
    """Map-1 class at standard refraction.
    vis  : headlight clears all modelled terrain AND clears terrain >1 km before the car by > 5 m
    marg : clears it only thinly (<= 5 m), or is blocked only by ground within 1 km of the car
           (road cuts/embankments — below what a 30 m DEM resolves reliably)
    hid  : blocked by terrain more than 1 km before the car"""
    if r["kc07"] <= k:
        return "vis" if r["farclr"] > MARGIN_M else "marg"
    return "marg" if r["kc07_far"] <= k else "hid"


def kml_color(hexrgb, alpha="ff"):
    r, g, b = hexrgb[1:3], hexrgb[3:5], hexrgb[5:7]
    return f"{alpha}{b}{g}{r}"


def runs(rows, key):
    out, cur = [], [rows[0]]
    for r in rows[1:]:
        if key(r) == key(cur[-1]):
            cur.append(r)
        else:
            out.append(cur)
            cur = [cur[-1], r]  # share the vertex so segments join
    out.append(cur)
    return out


def main():
    v = json.load(open("data/derived/los_results.json"))
    meta = v["meta"]
    V = meta["viewer"]
    E = meta["z0"] + meta["eye"]
    F = v["hwy_fields"]
    rows = [dict(zip(F, r)) for r in v["hwy"]]
    nf = json.load(open("data/derived/los_near_far.json"))
    for r, q in zip(rows, nf["rows"]):
        q = dict(zip(nf["fields"], q))
        assert q["ch_m"] == r["ch_m"]
        r.update(kc07_far=q["kc07_excl1000"], farclr=q["farclr_m_k013"], far_occ=q["far_occluder_km"])
        r["bin"] = kbin(r["kc07"])
        r["std"] = std_class(r)
        r["fan"] = FAN[0] <= r["az"] <= FAN[1]

    # ------------------------------------------------ CSV
    with open("outputs/Marfa_occlusion_points.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chainage_km_from_Shafter", "lon", "lat", "road_elev_m", "azimuth_deg", "distance_km",
                    "k_crit_headlight_0.7m", "k_crit_2.5m", "apparent_elev_mrad_k0.13", "apparent_elev_deg_k0.13",
                    "clearance_m_k0.13", "far_clearance_m_k0.13", "standard_class", "refraction_bin", "limiting_terrain_km", "in_fan"])
        for r in rows:
            w.writerow([f"{r['ch_m']/1000:.3f}", r["lon"], r["lat"], r["zT"], r["az"], f"{r['dist_m']/1000:.3f}",
                        r["kc07"], r["kc25"], r["alpha_mrad_k013_h07"], f"{r['alpha_mrad_k013_h07']*0.0572958:.4f}",
                        r["clear_m_k013_h07"], r["farclr"], r["std"], r["bin"], r["occluder_km_k013"], r["fan"]])

    # ------------------------------------------------ KML helpers
    def seg_pm(name, seg, style, desc):
        c = " ".join(f"{p['lon']:.6f},{p['lat']:.6f},0" for p in seg)
        return (f"<Placemark><name>{name}</name><description><![CDATA[{desc}]]></description>"
                f"<styleUrl>#{style}</styleUrl><LineString><tessellate>1</tessellate>"
                f"<altitudeMode>clampToGround</altitudeMode><coordinates>{c}</coordinates></LineString></Placemark>")

    def seg_desc(seg):
        a, b = seg[0], seg[-1]
        return (f"Chainage {a['ch_m']/1000:.2f}–{b['ch_m']/1000:.2f} km from Shafter end<br>"
                f"Azimuth {a['az']:.2f}–{b['az']:.2f}°, distance {a['dist_m']/1000:.1f}–{b['dist_m']/1000:.1f} km<br>"
                f"Road elevation {min(p['zT'] for p in seg):.0f}–{max(p['zT'] for p in seg):.0f} m<br>"
                f"Clearance at k=0.13: {min(p['clear_m_k013_h07'] for p in seg):.1f} to "
                f"{max(p['clear_m_k013_h07'] for p in seg):.1f} m<br>"
                f"k_crit (headlight): {min(p['kc07'] for p in seg):.2f} to {max(p['kc07'] for p in seg):.2f}")

    def fan_edges():
        out = []
        for az in FAN:
            lon, lat, _ = GEOD.fwd(V[0], V[1], az, 45000)
            out.append(f"<Placemark><name>Fan edge {az:.1f}°</name><styleUrl>#edge</styleUrl><LineString>"
                       f"<tessellate>1</tessellate><coordinates>{V[0]},{V[1]},0 {lon:.6f},{lat:.6f},0"
                       f"</coordinates></LineString></Placemark>")
        return "".join(out)

    head = lambda name, desc, styles: f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>{name}</name>
<description><![CDATA[{desc}]]></description>
<Style id="edge"><LineStyle><color>80ffffff</color><width>1.5</width></LineStyle></Style>
<Style id="viewer"><IconStyle><color>ff007cf5</color><scale>1.3</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/star.png</href></Icon></IconStyle></Style>
<Style id="run"><IconStyle><color>ff7ae01f</color><scale>0.8</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/shaded_dot.png</href></Icon></IconStyle><LabelStyle><scale>0.7</scale></LabelStyle></Style>
{styles}
<Placemark><name>Marfa Lights Viewing Area (eye {meta['eye']} m, ground {meta['z0']:.1f} m)</name><styleUrl>#viewer</styleUrl><Point><coordinates>{V[0]},{V[1]},0</coordinates></Point></Placemark>
{fan_edges()}"""

    common = (f"DEM: {meta['dem']}. Eye {meta['eye']} m; headlight target 0.7 m; terrain sampled every "
              f"{meta['sample_step_m']} m; last {meta['excl_end_m']} m before each target excluded "
              f"(road-bed smoothing). 'Marginal' = clears distant terrain by <= {MARGIN_M:.0f} m, or blocked only by "
              f"ground within 1 km of the car, where a 30 m DEM is unreliable.")

    # ------------------------------------------------ Map 1
    s1 = {"vis": ("1f9e7a", 6, "Visible — clears distant terrain by > 5 m"),
          "marg": ("e0b21b", 5, "Marginal — thin clearance, or blocked only within 1 km of the car"),
          "hid": ("8d9894", 3, "Hidden by terrain")}
    styles1 = "".join(f'<Style id="{k}"><LineStyle><color>{kml_color("#"+c)}</color><width>{wd}</width></LineStyle></Style>'
                      for k, (c, wd, _) in s1.items())
    pms1 = {k: [] for k in s1}
    for seg in runs(rows, lambda r: r["std"]):
        k = seg[-1]["std"] if len(seg) > 1 and seg[0]["std"] != seg[-1]["std"] else seg[0]["std"]
        pms1[k].append(seg_pm(s1[k][2], seg, k, seg_desc(seg)))
    vis_runs, cur = [], []
    for r in rows:
        if r["std"] == "vis":
            cur.append(r)
        elif cur:
            vis_runs.append(cur)
            cur = []
    if cur:
        vis_runs.append(cur)
    run_pms = []
    for s in vis_runs:
        m = s[len(s) // 2]
        run_pms.append(f"<Placemark><name>{m['az']:.1f}° · {m['dist_m']/1000:.1f} km</name><styleUrl>#run</styleUrl>"
                       f"<description><![CDATA[{seg_desc(s)}<br>Apparent elevation {m['alpha_mrad_k013_h07']:.2f} mrad "
                       f"({m['alpha_mrad_k013_h07']*0.0572958:.3f}°)]]></description>"
                       f"<Point><coordinates>{m['lon']},{m['lat']},0</coordinates></Point></Placemark>")
    doc1 = head("Map 1 — US-67 visibility, standard atmosphere (k = 0.13)", common, styles1)
    for k in ["vis", "marg", "hid"]:
        doc1 += f"<Folder><name>{s1[k][2]}</name>{''.join(pms1[k])}</Folder>"
    doc1 += f"<Folder><name>Visible stretches (labels)</name>{''.join(run_pms)}</Folder></Document></kml>"
    open("outputs/Marfa_occlusion_map1_standard.kml", "w").write(doc1)

    # ------------------------------------------------ Map 2
    styles2 = "".join(f'<Style id="{key}"><LineStyle><color>{kml_color(BIN_COLORS[key])}</color>'
                      f'<width>{3 if key == "k6" else 6}</width></LineStyle></Style>' for _, _, key, _ in BINS)
    pms2 = {key: [] for _, _, key, _ in BINS}
    labels = {key: lab for _, _, key, lab in BINS}
    for seg in runs(rows, lambda r: r["bin"]):
        key = seg[-1]["bin"] if len(seg) > 1 and seg[0]["bin"] != seg[-1]["bin"] else seg[0]["bin"]
        pms2[key].append(seg_pm(labels[key], seg, key, seg_desc(seg)))
    desc2 = (common + " Colour = minimum refraction coefficient k needed to see a 0.7 m headlight. "
             "k = 503·P/T²·(0.0343 + dT/dz) (Hirt et al. 2010); at P≈850 hPa, T≈283 K: "
             "k 0.13 ≈ standard lapse, k 0.5 ≈ +0.06 K/m, k 1.0 ≈ +0.15 K/m inversion. "
             "Constant-k is an approximation; near-ground gradients vary with height.")
    doc2 = head("Map 2 — US-67 visibility across refraction states", desc2, styles2)
    for _, _, key, lab in BINS:
        doc2 += f"<Folder><name>{lab}</name>{''.join(pms2[key])}</Folder>"
    doc2 += "</Document></kml>"
    open("outputs/Marfa_occlusion_map2_refraction.kml", "w").write(doc2)

    # ------------------------------------------------ page data
    lat0 = V[1]
    kx = 111.32 * math.cos(math.radians(lat0))
    ky = 110.57
    xy = lambda lon, lat: (round((lon - V[0]) * kx, 3), round((lat - V[1]) * ky, 3))
    pts = []
    for r in rows:
        x, y = xy(r["lon"], r["lat"])
        pts.append([x, y, round(r["ch_m"] / 1000, 2), round(r["az"], 2), round(r["dist_m"] / 1000, 2),
                    round(r["zT"], 1), r["kc07"], r["kc25"], r["alpha_mrad_k013_h07"],
                    r["clear_m_k013_h07"], r["farclr"], r["std"], r["bin"]])
    # railroad (TXPF ALPINE sub) for context
    web = json.load(open("data/inputs/web_layers.json"))
    rail = []
    for fid, owner, trk, subdiv, net, tr, lines in web["rail"]:
        if owner == "TXPF" and subdiv == "ALPINE":
            for ln in lines:
                rail.append([xy(lo, la) for lo, la in ln])
    hp = xy(-104.1945191, 30.0383975)
    edges = []
    for az in FAN:
        lon, lat, _ = GEOD.fwd(V[0], V[1], az, 45000)
        edges.append(xy(lon, lat))

    # profiles: apparent height relative to eye at k=0.13 and sight line to the highway
    hits = {}
    for r in csv.DictReader(open("outputs/Marfa_ray_fan_hits.csv")):
        if r["crossing"] == "1":
            hits[float(r["ray_azimuth_deg"])] = (float(r["dist_from_viewer_km"]), float(r["lon"]), float(r["lat"]))
    haz = np.array(sorted(hits))
    hd = np.array([hits[a][0] for a in haz])
    profs = []
    for az_s in ["234", "240", "260"]:
        az = float(az_s)
        dt = float(np.interp(az, haz, hd)) * 1000
        z = v["prof"][az_s]
        d = np.arange(len(z)) * 250.0
        # target elevation: nearest highway point in azimuth among first crossings
        cand = min((r for r in rows if abs(r["az"] - az) < 0.3), key=lambda r: abs(r["dist_m"] - dt))
        zt = cand["zT"]
        out = {"az": az, "dt_km": round(dt / 1000, 2), "zt": zt, "kc": cand["kc07"], "std": cand["std"], "k": {}}
        for k in (0.13, 0.5):
            c = 1 - k
            happ = [None if zz is None else round(zz - E - di * di * c / (2 * R), 2) for zz, di in zip(z, d)]
            tgt = zt + 0.7 - E - dt * dt * c / (2 * R)
            out["k"][str(k)] = {"terrain": happ, "target": round(tgt, 2)}
        out["d_km"] = [round(x / 1000, 2) for x in d]
        profs.append(out)

    page = {"meta": meta, "fan": FAN, "E": E, "pts": pts, "rail": rail, "hp": hp, "edges": edges,
            "sky": v["sky"], "profs": profs, "bins": [[lo, hi, key, lab, BIN_COLORS[key]] for lo, hi, key, lab in BINS]}
    json.dump(page, open("data/derived/occlusion_page.json", "w"), separators=(",", ":"))

    # ------------------------------------------------ summary
    km = lambda sel: sum(1 for r in rows if sel(r)) * meta["hwy_step_m"] / 1000
    print(f"Standard: visible {km(lambda r: r['std']=='vis'):.2f} km, marginal {km(lambda r: r['std']=='marg'):.2f} km, "
          f"hidden {km(lambda r: r['std']=='hid'):.2f} km of {rows[-1]['ch_m']/1000:.2f}")
    for lo, hi, key, lab in BINS:
        print(f"  {key} {lab}: {km(lambda r, k=key: r['bin']==k):.2f} km")
    for kk in (-1, 0, 0.13, 0.25, 0.5, 1.0, 3.0):
        print(f"  visible km at k={kk}: {km(lambda r: r['kc07'] <= kk):.2f}")
    for p in profs:
        print("profile", p["az"], p["dt_km"], p["zt"], p["kc"], p["std"])
    print("visible runs:", len(vis_runs))


if __name__ == "__main__":
    main()

"""
Marfa Lights investigation — infrastructure layer (candidate artificial light sources).

Sources (all public; retrieval date 2026-09-28; see data/web_layers.json "_meta"):
  * Airfields (incl. closed/historic):  OurAirports open data (GitHub: davidmegginson/ourairports-data)
    cross-checked against FAA NASR via USDOT BTS NTAD Aviation Facilities (eff. 2026-09-03)
  * Railroads:            USDOT BTS NTAD North American Rail Network (NARN) lines
  * Grade crossings:      FRA Highway-Rail Crossing Inventory (via NTAD) — includes reported
                          day/night through-train counts
  * Transmission lines:   HIFLD-derived Electric Power Transmission Lines (>= 69 kV only)
  * Cellular towers:      FCC ULS cellular-licence sites (not a complete tower inventory)
  * Power plants:         EIA-860 Power Plants in the US

For every object: geodesic azimuth/distance from the Viewing Area, whether it falls inside the
ray-fan azimuth window, and for line features whether any part lies IN FRONT OF US-67 along
the same line of sight (i.e. could appear superimposed on the highway direction).

Run from the repository root:  python analysis/marfa_infrastructure.py
"""
import csv
import json
import math
from xml.sax.saxutils import escape

import numpy as np
from pyproj import Geod

GEOD = Geod(ellps="WGS84")
VIEWER = (-103.8827973, 30.2751108)
FAN = (228.931, 277.276)
MAX_KM = 80.0
DATA = "data/inputs"
OURAIRPORTS = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/"


# ------------------------------------------------------------------ helpers
def az_dist(lon, lat):
    az, _, d = GEOD.inv(VIEWER[0], VIEWER[1], lon, lat)
    return az % 360, d / 1000.0


def in_fan(az):
    return FAN[0] <= az <= FAN[1]


def load_hwy_profile():
    """Distance to first US-67 crossing as a function of azimuth (from the ray-fan run)."""
    az, d = [], []
    for r in csv.DictReader(open("outputs/Marfa_ray_fan_hits.csv")):
        if r["crossing"] == "1":
            az.append(float(r["ray_azimuth_deg"]))
            d.append(float(r["dist_from_viewer_km"]))
    return np.array(az), np.array(d)


HWY_AZ, HWY_D = load_hwy_profile()


def hwy_dist_at(az):
    return float(np.interp(az, HWY_AZ, HWY_D)) if in_fan(az) else None


def densify(coords, step_km=0.1):
    out = []
    for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
        _, _, d = GEOD.inv(x0, y0, x1, y1)
        n = max(1, int(math.ceil(d / 1000 / step_km)))
        for i in range(n):
            t = i / n
            out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    out.append(coords[-1])
    return out


def line_fan_stats(lines):
    """For a multi-line, return in-fan azimuth span, distance span, and foreground stats."""
    pts = [p for ln in lines for p in densify(ln)]
    ad = [az_dist(*p) for p in pts]
    nearest = min(d for _, d in ad)
    fan = [(a, d) for a, d in ad if in_fan(a)]
    if not fan:
        return dict(nearest_km=nearest, in_fan=False)
    fg = [(a, d) for a, d in fan if d < hwy_dist_at(a)]
    return dict(nearest_km=nearest, in_fan=True,
                fan_az=(min(a for a, _ in fan), max(a for a, _ in fan)),
                fan_km=(min(d for _, d in fan), max(d for _, d in fan)),
                foreground=bool(fg),
                fg_az=(min(a for a, _ in fg), max(a for a, _ in fg)) if fg else None,
                fg_km=(min(d for _, d in fg), max(d for _, d in fg)) if fg else None)


# ------------------------------------------------------------------ loaders
def fetch_ourairports():
    """Download OurAirports CSVs (not stored in the repo; ~17 MB) if missing."""
    import os, urllib.request
    for f in ("airports.csv", "runways.csv"):
        p = f"{DATA}/{f}"
        if not os.path.exists(p):
            urllib.request.urlretrieve(OURAIRPORTS + f, p)


def load_airports(faa_ids):
    fetch_ourairports()
    runways = {}
    for r in csv.DictReader(open(f"{DATA}/runways.csv", encoding="utf-8")):
        runways.setdefault(r["airport_ident"], []).append(r)
    out = []
    for r in csv.DictReader(open(f"{DATA}/airports.csv", encoding="utf-8")):
        try:
            lat, lon = float(r["latitude_deg"]), float(r["longitude_deg"])
        except ValueError:
            continue
        if abs(lat - VIEWER[1]) > 1 or abs(lon - VIEWER[0]) > 1 or "[Duplicate]" in r["name"]:
            continue
        az, d = az_dist(lon, lat)
        if d > MAX_KM:
            continue
        rws = []
        for w in runways.get(r["ident"], []):
            ends = None
            try:
                ends = [(float(w["le_longitude_deg"]), float(w["le_latitude_deg"])),
                        (float(w["he_longitude_deg"]), float(w["he_latitude_deg"]))]
            except ValueError:
                pass
            rws.append(dict(id=f"{w['le_ident']}/{w['he_ident']}", len_ft=w["length_ft"],
                            surface=w["surface"], lighted=w["lighted"], ends=ends))
        local = r["local_code"] or r["ident"]
        out.append(dict(kind=r["type"], ident=r["ident"], name=r["name"], lat=lat, lon=lon,
                        elev_ft=r["elevation_ft"], az=az, km=d, fan=in_fan(az),
                        fg=in_fan(az) and d < hwy_dist_at(az), runways=rws,
                        faa=(local in faa_ids or r["ident"] in faa_ids),
                        src=f"https://ourairports.com/airports/{r['ident']}/"))
    return sorted(out, key=lambda x: x["km"])


def load_web():
    return json.load(open(f"{DATA}/web_layers.json"))


# ------------------------------------------------------------------ KML
def pm_point(name, lon, lat, style, desc):
    return (f"<Placemark><name>{escape(name)}</name><description><![CDATA[{desc}]]></description>"
            f"<styleUrl>#{style}</styleUrl><Point><coordinates>{lon:.6f},{lat:.6f},0"
            f"</coordinates></Point></Placemark>")


def pm_multiline(name, lines, style, desc=""):
    geoms = "".join(
        "<LineString><tessellate>1</tessellate><coordinates>"
        + " ".join(f"{x:.6f},{y:.6f},0" for x, y in ln)
        + "</coordinates></LineString>" for ln in lines)
    return (f"<Placemark><name>{escape(name)}</name><description><![CDATA[{desc}]]></description>"
            f"<styleUrl>#{style}</styleUrl><MultiGeometry>{geoms}</MultiGeometry></Placemark>")


def fan_text(s):
    if not s["in_fan"]:
        return f"Outside fan window (nearest {s['nearest_km']:.1f} km)"
    t = (f"<b>In fan window</b>: az {s['fan_az'][0]:.1f}–{s['fan_az'][1]:.1f}°, "
         f"{s['fan_km'][0]:.1f}–{s['fan_km'][1]:.1f} km")
    if s["foreground"]:
        t += (f"<br><b style='color:#c00'>IN FRONT OF US-67</b> at az {s['fg_az'][0]:.1f}–"
              f"{s['fg_az'][1]:.1f}°, {s['fg_km'][0]:.1f}–{s['fg_km'][1]:.1f} km")
    return t


def pt_fan_text(az, km):
    if not in_fan(az):
        return "Outside fan window"
    h = hwy_dist_at(az)
    rel = "IN FRONT OF US-67" if km < h else "beyond US-67"
    return f"<b>In fan window</b> — {rel} (highway at {h:.1f} km on this bearing)"


STYLES = """
<Style id="apt"><IconStyle><color>ff00d7ff</color><Icon><href>http://maps.google.com/mapfiles/kml/shapes/airports.png</href></Icon></IconStyle><LabelStyle><scale>0.7</scale></LabelStyle></Style>
<Style id="apt_closed"><IconStyle><color>ff9e9e9e</color><scale>0.8</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/airports.png</href></Icon></IconStyle><LabelStyle><scale>0.6</scale></LabelStyle></Style>
<Style id="heli"><IconStyle><color>ff00d7ff</color><Icon><href>http://maps.google.com/mapfiles/kml/shapes/heliport.png</href></Icon></IconStyle></Style>
<Style id="balloon"><IconStyle><color>ff3c14dc</color><scale>1.2</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/triangle.png</href></Icon></IconStyle></Style>
<Style id="runway"><LineStyle><color>ff00d7ff</color><width>3</width></LineStyle></Style>
<Style id="rail_up"><LineStyle><color>ff3030d0</color><width>3.5</width></LineStyle></Style>
<Style id="rail_txpf"><LineStyle><color>ffd06030</color><width>3.5</width></LineStyle></Style>
<Style id="rail_yard"><LineStyle><color>ff909090</color><width>2</width></LineStyle></Style>
<Style id="xing"><IconStyle><color>ffffffff</color><scale>0.6</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_square.png</href></Icon></IconStyle><LabelStyle><scale>0</scale></LabelStyle></Style>
<Style id="tl"><LineStyle><color>ff00ffff</color><width>2</width></LineStyle></Style>
<Style id="cell"><IconStyle><color>ff0000ff</color><Icon><href>http://maps.google.com/mapfiles/kml/shapes/target.png</href></Icon></IconStyle><LabelStyle><scale>0.7</scale></LabelStyle></Style>
<Style id="plant"><IconStyle><color>ff00ff80</color><Icon><href>http://maps.google.com/mapfiles/kml/shapes/square.png</href></Icon></IconStyle></Style>
<Style id="bound"><LineStyle><color>80ffffff</color><width>2</width></LineStyle></Style>
<Style id="viewer"><IconStyle><color>ff007cf5</color><scale>1.3</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/star.png</href></Icon></IconStyle></Style>
"""


def main():
    web = load_web()
    faa_ids = {a[0] for a in web["avia"]}
    airports = load_airports(faa_ids)
    rows = []  # summary table

    # --- airfields
    apt_pms = {"open": [], "closed": []}
    for a in airports:
        style = {"heliport": "heli", "balloonport": "balloon", "closed": "apt_closed"}.get(a["kind"], "apt")
        rw = "<br>".join(f"RWY {w['id']}: {w['len_ft']} ft {w['surface']}, lighted={w['lighted']}"
                         for w in a["runways"]) or "no runway record"
        desc = (f"{a['ident']} · {a['kind']} · elev {a['elev_ft'] or 'n/a'} ft<br>"
                f"In current FAA NASR: {'yes' if a['faa'] else 'no'}<br>"
                f"Az {a['az']:.1f}°, {a['km']:.1f} km<br>{pt_fan_text(a['az'], a['km'])}<br>{rw}<br>"
                f"<a href='{a['src']}'>OurAirports record</a>")
        grp = "closed" if a["kind"] == "closed" else "open"
        apt_pms[grp].append(pm_point(a["name"], a["lon"], a["lat"], style, desc))
        for w in a["runways"]:
            if w["ends"]:
                apt_pms[grp].append(pm_multiline(f"{a['ident']} RWY {w['id']}", [w["ends"]], "runway"))
        lit = "yes" if any(w["lighted"] == "1" for w in a["runways"]) else "no/unknown"
        rows.append(["airfield", a["ident"], a["name"], a["kind"], f"{a['lat']:.5f}", f"{a['lon']:.5f}",
                     f"{a['az']:.2f}", f"{a['km']:.2f}", a["fan"], a["fg"], f"lighted runway: {lit}; FAA-listed: {a['faa']}",
                     a["src"]])

    # --- railroads, grouped by owner + subdivision
    groups = {}
    for fid, owner, trk, subdiv, net, tracks, lines in web["rail"]:
        key = (owner, subdiv or "(siding/yard)", "main" if net == "M" else "siding/yard")
        groups.setdefault(key, []).extend(lines)
    rail_pms, rail_stats = [], {}
    for (owner, subdiv, kind), lines in sorted(groups.items()):
        s = line_fan_stats(lines)
        rail_stats[(owner, subdiv, kind)] = s
        style = "rail_yard" if kind != "main" else ("rail_up" if owner == "UP" else "rail_txpf")
        label = {"UP": "Union Pacific (Sunset Route)", "TXPF": "Texas Pacifico (ex-South Orient)"}.get(owner, owner)
        rail_pms.append(pm_multiline(f"{label} — {subdiv} sub, {kind}", lines, style,
                                     f"Owner {owner}; NARN.<br>{fan_text(s)}"))
        rows.append(["railroad", f"{owner}/{subdiv}", label, kind, "", "", "", f"{s['nearest_km']:.2f}",
                     s["in_fan"], s.get("foreground", False),
                     (f"fan az {s['fan_az'][0]:.1f}-{s['fan_az'][1]:.1f}, {s['fan_km'][0]:.1f}-{s['fan_km'][1]:.1f} km"
                      if s["in_fan"] else ""), web["_meta"]["rail_src"].split(" ")[-3]])

    xing_pms = []
    for cid, lat, lon, rr, road, pos, typ, day, night, spd in web["xing"]:
        az, d = az_dist(lon, lat)
        if d > MAX_KM:
            continue
        xing_pms.append(pm_point(f"Crossing {cid}", lon, lat, "xing",
                                 f"{rr} · {road} · {pos} · {typ}<br>Reported thru trains: day {day}, night {night}; "
                                 f"max {spd} mph<br>Az {az:.1f}°, {d:.1f} km<br>{pt_fan_text(az, d)}<br>"
                                 f"<a href='https://railroads.dot.gov/safety/crossing-safety/crossing-inventory'>FRA crossing inventory</a>"))
        if in_fan(az):
            rows.append(["grade_crossing", cid, f"{rr} x {road}", pos, f"{lat:.5f}", f"{lon:.5f}", f"{az:.2f}",
                         f"{d:.2f}", True, d < hwy_dist_at(az), f"night thru trains {night}", "FRA"])

    # --- transmission lines
    tl_pms = []
    for tid, kv, status, s1, s2, owner, lines in web["tl"]:
        s = line_fan_stats(lines)
        tl_pms.append(pm_multiline(f"{kv or '?'} kV {s1} – {s2}", lines, "tl",
                                   f"ID {tid}; {status}; owner {owner}<br>{fan_text(s)}"))
        rows.append(["transmission_line", tid, f"{kv} kV {s1}-{s2}", status, "", "", "", f"{s['nearest_km']:.2f}",
                     s["in_fan"], s.get("foreground", False),
                     (f"fan az {s['fan_az'][0]:.1f}-{s['fan_az'][1]:.1f}, {s['fan_km'][0]:.1f}-{s['fan_km'][1]:.1f} km"
                      if s["in_fan"] else ""), "HIFLD-derived"])

    # --- cellular sites (dedupe by location)
    seen, cell_pms = set(), []
    for sid, lic, call, lat, lon, addr, city, asr, sup, allh, st, ls in web["cell"]:
        k = (round(lat, 4), round(lon, 4))
        if k in seen:
            continue
        seen.add(k)
        az, d = az_dist(lon, lat)
        if d > MAX_KM:
            continue
        asr_txt = (f"ASR {asr} (<a href='https://wireless2.fcc.gov/UlsApp/AsrSearch/asrRegistration.jsp?regKey={asr}'>FCC</a>)"
                   if asr else "no ASR number listed")
        cell_pms.append(pm_point(f"Cell site {call} ({city})", lon, lat, "cell",
                                 f"{lic}<br>{addr}<br>{asr_txt}<br>Structure height {allh or sup or '?'} m<br>"
                                 f"Az {az:.1f}°, {d:.1f} km<br>{pt_fan_text(az, d)}"))
        rows.append(["cell_site", call, f"{lic} — {addr}", st.strip(), f"{lat:.5f}", f"{lon:.5f}", f"{az:.2f}",
                     f"{d:.2f}", in_fan(az), in_fan(az) and d < hwy_dist_at(az), f"ASR {asr}; height {allh or sup} m",
                     "FCC ULS"])

    plant_pms = []
    for code, name, util, src, tech, mw, lat, lon, city in web["pp"]:
        az, d = az_dist(lon, lat)
        if d > MAX_KM:
            continue
        plant_pms.append(pm_point(name, lon, lat, "plant", f"{tech}, {mw} MW ({util})<br>EIA plant {code}<br>"
                                  f"Az {az:.1f}°, {d:.1f} km<br>{pt_fan_text(az, d)}"))
        rows.append(["power_plant", code, name, tech, f"{lat:.5f}", f"{lon:.5f}", f"{az:.2f}", f"{d:.2f}",
                     in_fan(az), in_fan(az) and d < hwy_dist_at(az), f"{mw} MW", "EIA-860"])

    def fan_edge(az, km=80):
        lon, lat, _ = GEOD.fwd(VIEWER[0], VIEWER[1], az, km * 1000)
        return [VIEWER, (lon, lat)]

    folder = lambda n, items: f"<Folder><name>{n} ({len(items)})</name>{''.join(items)}</Folder>"
    doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<name>Marfa infrastructure layer</name>
<description><![CDATA[Candidate artificial light sources around the Marfa Lights Viewing Area.
Fan window {FAN[0]:.2f}°–{FAN[1]:.2f}° true. "IN FRONT OF US-67" = on the same bearing but closer than the highway.
Sources: OurAirports; FAA NASR (NTAD); USDOT NARN; FRA crossing inventory; HIFLD transmission lines; FCC ULS; EIA-860. Retrieved 2026-09-28.]]></description>
{STYLES}
<Folder><name>Reference</name>
{pm_point('Marfa Lights Viewing Area', VIEWER[0], VIEWER[1], 'viewer', 'Observer position')}
{pm_multiline(f'Fan edge {FAN[0]:.1f}°', [fan_edge(FAN[0])], 'bound')}
{pm_multiline(f'Fan edge {FAN[1]:.1f}°', [fan_edge(FAN[1])], 'bound')}
</Folder>
{folder('Airfields – open', apt_pms['open'])}
{folder('Airfields – closed / historic', apt_pms['closed'])}
{folder('Railroads (NARN)', rail_pms)}
{folder('Rail grade crossings (FRA)', xing_pms)}
{folder('Transmission lines ≥69 kV', tl_pms)}
{folder('Cellular sites (FCC ULS)', cell_pms)}
{folder('Power plants (EIA)', plant_pms)}
</Document></kml>"""
    open("outputs/Marfa_infrastructure.kml", "w", encoding="utf-8").write(doc)

    with open("outputs/Marfa_infrastructure.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", "id", "name", "type_status", "lat", "lon", "azimuth_deg", "distance_km",
                    "inside_fan", "in_front_of_US67", "notes", "source"])
        w.writerows(rows)

    # console summary
    print(f"airfields {len(airports)}, rail groups {len(groups)}, crossings {len(xing_pms)}, "
          f"TL {len(tl_pms)}, cell {len(cell_pms)}, plants {len(plant_pms)}")
    print("\nIN FAN WINDOW:")
    for r in rows:
        if r[8]:
            print(f"  {r[0]:18s} {r[1]:14s} {r[2][:48]:48s} d={r[7]:>6} front_of_US67={r[9]}  {r[10]}")
    print("\nFAA-listed open airfields not in OurAirports within 80 km:",
          sorted(faa_ids - {a['ident'] for a in airports} - {a['ident'].lstrip('K') for a in airports}))


if __name__ == "__main__":
    main()

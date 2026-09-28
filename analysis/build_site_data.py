"""Export every map layer the public website needs into docs/data/site.json.

Run from the repository root after the analysis scripts:
    python analysis/build_site_data.py

Layers
  viewer, fan edges, 0.5° rays (first US-67 crossing), US-67 line-of-sight points,
  skyline panorama, railroads (NARN), grade crossings (FRA), transmission lines,
  cell sites (FCC ULS), power plants (EIA), airfields (OurAirports + FAA NASR cross-check),
  towns, and reference points.

Privacy choice: closed private ranch airstrips are NOT exported to the public site
(they remain in outputs/Marfa_infrastructure.* for research use). Historic WWII
Marfa Army Air Field sites, the TARS aerostat site, and fields in the current FAA NASR
(effective 2026-09-03) are exported; unverified private strips are left out.
"""
import csv
import json

from pyproj import Geod

GEOD = Geod(ellps="WGS84")
VIEWER = (-103.8827973, 30.2751108)
MAX_KM = 90
R5 = lambda v: round(v, 5)


def azd(lon, lat):
    az, _, d = GEOD.inv(VIEWER[0], VIEWER[1], lon, lat)
    return round(az % 360, 2), round(d / 1000, 2)


def main():
    los = json.load(open("data/derived/los_results.json"))
    nf = json.load(open("data/derived/los_near_far.json"))
    web = json.load(open("data/inputs/web_layers.json"))
    meta = los["meta"]
    F = los["hwy_fields"]

    # ---------- US-67 points (same classes as analysis/marfa_occlusion.py)
    hwy = []
    for r, q in zip(los["hwy"], nf["rows"]):
        r = dict(zip(F, r))
        q = dict(zip(nf["fields"], q))
        kc, kcfar, farclr = r["kc07"], q["kc07_excl1000"], q["farclr_m_k013"]
        if kc <= 0.13:
            cls = "v" if farclr > 5 else "m"
        else:
            cls = "m" if kcfar <= 0.13 else "h"
        hwy.append([R5(r["lat"]), R5(r["lon"]), round(r["az"], 2), round(r["dist_m"] / 1000, 2),
                    round(r["zT"]), round(kc, 3), cls, round(r["alpha_mrad_k013_h07"], 2),
                    round(r["ch_m"] / 1000, 2)])

    # ---------- rays
    rays = []
    for row in csv.DictReader(open("outputs/Marfa_ray_fan_hits.csv")):
        if row["crossing"] == "1":
            rays.append([float(row["ray_azimuth_deg"]), R5(float(row["lat"])), R5(float(row["lon"])),
                         float(row["dist_from_viewer_km"])])
    fan = [rays[0][0], rays[-1][0]]

    # ---------- airfields
    faa = {a[0]: a for a in web["avia"]}
    fields = []
    for r in csv.DictReader(open("data/inputs/airports.csv", encoding="utf-8")):
        try:
            lat, lon = float(r["latitude_deg"]), float(r["longitude_deg"])
        except ValueError:
            continue
        if abs(lat - VIEWER[1]) > 1 or abs(lon - VIEWER[0]) > 1 or "[Duplicate]" in r["name"]:
            continue
        az, d = azd(lon, lat)
        if d > MAX_KM:
            continue
        local = r["local_code"] or r["ident"]
        historic = r["type"] == "closed" and ("Army" in r["name"] or r["ident"] in ("US-2971", "US-2976"))
        listed = local in faa or r["ident"] in faa
        keep = historic or r["type"] == "balloonport" or (r["type"] != "closed" and listed)
        if not keep:
            continue
        kind = "historic" if historic else ("balloon" if r["type"] == "balloonport" else
                                            "heliport" if r["type"] == "heliport" else "airfield")
        fields.append({"n": r["name"], "id": r["ident"], "k": kind, "lat": R5(lat), "lon": R5(lon), "az": az, "d": d,
                       "faa": local in faa or r["ident"] in faa, "elev": r["elevation_ft"] or None})

    # ---------- rail
    rail = []
    for fid, owner, trk, subdiv, net, tracks, lines in web["rail"]:
        for ln in lines:
            if any(azd(lo, la)[1] <= MAX_KM for lo, la in ln):
                rail.append({"o": owner, "s": subdiv or "", "m": net == "M",
                             "c": [[R5(la), R5(lo)] for lo, la in ln]})

    xing = []
    for cid, lat, lon, rr, road, pos, typ, day, night, spd in web["xing"]:
        az, d = azd(lon, lat)
        if d <= MAX_KM:
            xing.append({"id": cid, "lat": lat, "lon": lon, "rr": rr, "road": road, "pos": pos, "t": typ,
                         "night": night, "day": day, "az": az, "d": d})

    tl = []
    for tid, kv, status, s1, s2, owner, lines in web["tl"]:
        for ln in lines:
            if any(azd(lo, la)[1] <= MAX_KM for lo, la in ln):
                tl.append({"kv": kv, "a": s1, "b": s2, "c": [[R5(la), R5(lo)] for lo, la in ln]})

    cells, seen = [], set()
    for sid, lic, call, lat, lon, addr, city, asr, sup, allh, st, ls in web["cell"]:
        k = (round(lat, 4), round(lon, 4))
        if k in seen:
            continue
        seen.add(k)
        az, d = azd(lon, lat)
        if d <= MAX_KM:
            cells.append({"lic": lic, "addr": addr, "city": city, "asr": asr or None, "h": allh or sup or None,
                          "lat": lat, "lon": lon, "az": az, "d": d})

    plants = []
    for code, name, util, src, tech, mw, lat, lon, city in web["pp"]:
        az, d = azd(lon, lat)
        if d <= MAX_KM:
            plants.append({"n": name, "tech": tech, "mw": mw, "lat": lat, "lon": lon, "az": az, "d": d})

    # towns: coordinates from each place's Wikipedia infobox (retrieved 2026-09-28)
    towns = []
    for name, lat, lon, note in [
            ("Marfa", 30.31056, -104.02556, "Presidio County seat; street and security lighting"),
            ("Alpine", 30.37222, -103.66667, "Largest town in the area"),
            ("Fort Davis", 30.59667, -103.88083, "Near McDonald Observatory"),
            ("Shafter", 29.82028, -104.30333, "Former silver-mining town; a few families today"),
            ("Presidio", 29.56139, -104.36639, "Border town on the Rio Grande"),
            ("Ojinaga, Chihuahua", 29.56444, -104.41639, "Mexican city across the Rio Grande from Presidio")]:
        az, d = azd(lon, lat)
        towns.append({"n": name, "lat": lat, "lon": lon, "az": az, "d": d, "note": note})

    refs = []
    for name, lat, lon, note in [("US-67 high point (1,650 m)", 30.03840, -104.19452, "Highest point of US-67 on this stretch")]:
        az, d = azd(lon, lat)
        refs.append({"n": name, "lat": lat, "lon": lon, "az": az, "d": d, "note": note})

    site = {
        "generated": "2026-09-28",
        "viewer": {"lat": VIEWER[1], "lon": VIEWER[0], "z": round(meta["z0"], 1), "eye": meta["eye"]},
        "declination": {"deg": 6.2, "model": "WMM2025", "epoch": "2026.7", "annual": -0.08},
        "fan": fan, "rays": rays,
        "hwy_fields": ["lat", "lon", "az", "d_km", "z", "kcrit", "cls", "alpha_mrad", "ch_km"],
        "hwy": hwy, "sky": los["sky"],
        "fields": fields, "rail": rail, "xing": xing, "tl": tl, "cells": cells, "plants": plants,
        "towns": towns, "refs": refs,
    }
    json.dump(site, open("docs/data/site.json", "w"), separators=(",", ":"))
    print("hwy", len(hwy), "rays", len(rays), "fields", len(fields), "rail", len(rail), "xing", len(xing),
          "tl", len(tl), "cells", len(cells), "plants", len(plants))
    for f in fields:
        print("  ", f["k"], f["id"], f["n"], f["d"])


if __name__ == "__main__":
    main()

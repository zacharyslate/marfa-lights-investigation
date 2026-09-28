"""
Marfa Lights investigation — sight-line ray fan from the Viewing Area to US-67.

Reads the Google Earth KML (viewer point, highway LineString, Left/Right bound lines),
casts a geodesic ray every STEP_DEG degrees of azimuth between the two bounds,
intersects each ray with the highway, and writes:

  * <out>.kml              original features + ray fan + highway hit points
  * <out>_hits.csv         one row per ray/highway intersection
  * <out>_profiles.csv     points sampled every SAMPLE_M metres along each ray
                           (attach DEM elevations to this file, then run
                           line_of_sight() to get visible / blocked per point)

Geometry: all intersections are computed in a local azimuthal-equidistant (AEQD)
projection centred on the viewer, so a ray from the centre is a true geodesic and
distances from the viewer are exact. Azimuths are geodesic (WGS84), clockwise from true N.

Run from the repository root:  python analysis/marfa_ray_fan.py
"""
import csv
import math
import sys
import xml.etree.ElementTree as ET

import numpy as np
from pyproj import CRS, Geod, Transformer
from shapely.geometry import LineString, MultiPoint, Point

STEP_DEG = 0.5          # angular spacing of the fan
RAY_LEN_M = 90_000      # rays are cast this far, then trimmed at the highway
SAMPLE_M = 30.0         # profile sampling interval (~1 arc-second DEM cell)
NS = {"k": "http://www.opengis.net/kml/2.2"}
GEOD = Geod(ellps="WGS84")


# ---------------------------------------------------------------- KML parsing
def parse_coords(text):
    pts = []
    for tok in text.split():
        v = [float(x) for x in tok.split(",")]
        pts.append((v[0], v[1], v[2] if len(v) > 2 else 0.0))
    return pts


def read_kml(path):
    root = ET.parse(path).getroot()
    feats = {}
    for pm in root.iter("{%s}Placemark" % NS["k"]):
        name = pm.findtext("k:name", namespaces=NS)
        pt = pm.find(".//k:Point/k:coordinates", NS)
        ls = pm.find(".//k:LineString/k:coordinates", NS)
        feats[name] = parse_coords((pt if pt is not None else ls).text)
    return feats


# ---------------------------------------------------------------- geometry
def build_fan(viewer, highway, left_end, right_end, step=STEP_DEG):
    lon0, lat0 = viewer[0], viewer[1]
    aeqd = CRS.from_proj4(f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +datum=WGS84 +units=m")
    fwd = Transformer.from_crs("EPSG:4326", aeqd, always_xy=True)
    inv = Transformer.from_crs(aeqd, "EPSG:4326", always_xy=True)

    hwy_xy = LineString([fwd.transform(p[0], p[1]) for p in highway])

    az_l, _, d_l = GEOD.inv(lon0, lat0, left_end[0], left_end[1])
    az_r, _, d_r = GEOD.inv(lon0, lat0, right_end[0], right_end[1])
    az_l %= 360
    az_r %= 360
    # sweep clockwise from left bound to right bound (viewer faces west)
    span = (az_r - az_l) % 360
    n = int(math.floor(span / step + 1e-9))
    azimuths = [(az_l + i * step) % 360 for i in range(n + 1)]
    if span - n * step > 1e-6:          # always include the exact right bound
        azimuths.append(az_r)

    rays = []
    for az in azimuths:
        t = math.radians(az)
        end = (RAY_LEN_M * math.sin(t), RAY_LEN_M * math.cos(t))  # AEQD: x=E, y=N
        ray = LineString([(0, 0), end])
        inter = ray.intersection(hwy_xy)
        if inter.is_empty:
            hits = []
        elif isinstance(inter, Point):
            hits = [inter]
        elif isinstance(inter, MultiPoint):
            hits = list(inter.geoms)
        else:  # collinear overlap (unlikely) -> take its vertices
            hits = [Point(c) for c in inter.coords]
        hits = sorted(hits, key=lambda p: p.distance(Point(0, 0)))
        hit_info = []
        for k, h in enumerate(hits):
            lon, lat = inv.transform(h.x, h.y)
            # position along the highway measured from the Shafter end
            s = hwy_xy.project(h)
            hit_info.append(dict(order=k + 1, lon=lon, lat=lat,
                                 dist_m=h.distance(Point(0, 0)),
                                 hwy_chainage_m=s))
        rays.append(dict(az=az, hits=hit_info))

    meta = dict(az_left=az_l, az_right=az_r, span=span,
                d_left=d_l, d_right=d_r, hwy_len_m=hwy_xy.length,
                inv=inv, fwd=fwd)
    return rays, meta


def ray_samples(viewer, az, length_m, step_m=SAMPLE_M):
    """Points along a geodesic from the viewer at azimuth az."""
    n = max(1, int(math.ceil(length_m / step_m)))
    d = np.linspace(0, length_m, n + 1)
    lon, lat, _ = GEOD.fwd(np.full_like(d, viewer[0]), np.full_like(d, viewer[1]),
                           np.full_like(d, az), d)
    return d, lon, lat


# ---------------------------------------------------------------- line of sight
R_EARTH = 6_371_000.0


def line_of_sight(dist_m, ground_m, observer_h=1.7, target_h=1.0, k=0.13):
    """
    Given a terrain profile along one ray (distance from viewer, ground elevation
    AMSL), return for each sample:
      visible  - bool, can a target target_h above ground be seen by an eye
                 observer_h above ground at sample 0
      clearance_m - how far (m) the target sits above(+)/below(-) the
                 limiting sight line
    Earth curvature + standard atmospheric refraction are included via the
    effective radius R/(1-k); k≈0.13 is the usual daytime value, but night-time
    surface inversions over the Marfa plateau can push k well above that.
    """
    d = np.asarray(dist_m, float)
    z = np.asarray(ground_m, float)
    re = R_EARTH / (1.0 - k)
    drop = d ** 2 / (2 * re)                 # apparent drop of the surface
    z_eff = z - drop
    eye = z_eff[0] + observer_h
    # angle (tangent) from eye to each terrain point and to each target point
    with np.errstate(divide="ignore", invalid="ignore"):
        ang_ground = (z_eff - eye) / d
        ang_target = (z_eff + target_h - eye) / d
    ang_ground[0] = -np.inf
    max_before = np.maximum.accumulate(np.concatenate([[-np.inf], ang_ground[:-1]]))
    visible = ang_target >= max_before
    visible[0] = True
    with np.errstate(invalid="ignore"):
        clearance = (ang_target - max_before) * d
    clearance[0] = np.inf
    return visible, clearance


# ---------------------------------------------------------------- KML output
def kml_line(name, coords, style, desc=""):
    c = " ".join(f"{lon:.8f},{lat:.8f},0" for lon, lat in coords)
    return (f"<Placemark><name>{name}</name><description><![CDATA[{desc}]]></description>"
            f"<styleUrl>#{style}</styleUrl><LineString><tessellate>1</tessellate>"
            f"<altitudeMode>clampToGround</altitudeMode><coordinates>{c}</coordinates>"
            f"</LineString></Placemark>")


def kml_point(name, lon, lat, style, desc="", z=0.0, absolute=False):
    mode = "absolute" if absolute else "clampToGround"
    return (f"<Placemark><name>{name}</name><description><![CDATA[{desc}]]></description>"
            f"<styleUrl>#{style}</styleUrl><Point><altitudeMode>{mode}</altitudeMode>"
            f"<coordinates>{lon:.8f},{lat:.8f},{z}</coordinates></Point></Placemark>")


def color_for(frac):
    """KML aabbggrr: gradient blue (left bound) -> orange (right bound)."""
    r = int(40 + frac * (245 - 40))
    g = int(110 + frac * (124 - 110))
    b = int(210 - frac * (210 - 0))
    return f"ff{b:02x}{g:02x}{r:02x}"


def write_kml(path, feats, viewer, highway, rays, meta):
    styles = []
    body_rays, body_hits = [], []
    n = len(rays)
    for i, r in enumerate(rays):
        sid = f"ray{i}"
        styles.append(f'<Style id="{sid}"><LineStyle><color>{color_for(i / max(1, n - 1))}'
                      f'</color><width>1.5</width></LineStyle></Style>')
        if r["hits"]:
            h = r["hits"][0]
            end = (h["lon"], h["lat"])
            desc = (f"Azimuth {r['az']:.2f}° (true)<br>"
                    f"Distance to US-67: {h['dist_m']/1000:.3f} km<br>"
                    f"Highway chainage from Shafter end: {h['hwy_chainage_m']/1000:.2f} km<br>"
                    f"Highway crossings on this ray: {len(r['hits'])}")
        else:
            _, lon, lat = ray_samples(viewer, r["az"], 5000, 5000)
            end = (lon[-1], lat[-1])
            desc = f"Azimuth {r['az']:.2f}° — NO highway intersection"
        # densify so the tessellated line follows the geodesic exactly
        L = r["hits"][0]["dist_m"] if r["hits"] else 5000
        _, lon, lat = ray_samples(viewer, r["az"], L, 1000)
        body_rays.append(kml_line(f"Ray {r['az']:.1f}°", list(zip(lon, lat)), sid, desc))
        for h in r["hits"]:
            body_hits.append(kml_point(
                f"{r['az']:.1f}° · {h['dist_m']/1000:.2f} km", h["lon"], h["lat"], "hit",
                f"Ray azimuth {r['az']:.2f}°, crossing #{h['order']}<br>"
                f"Distance {h['dist_m']/1000:.3f} km<br>"
                f"Chainage {h['hwy_chainage_m']/1000:.2f} km from Shafter end"))

    hp = feats["Highway High-Point"][0]
    az_hp, _, d_hp = GEOD.inv(viewer[0], viewer[1], hp[0], hp[1])

    doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
<name>Marfa ray fan ({STEP_DEG}° steps)</name>
<description><![CDATA[Geodesic sight-line fan from the Marfa Lights Viewing Area to US-67.
{n} rays, azimuth {meta['az_left']:.2f}° to {meta['az_right']:.2f}° (true), step {STEP_DEG}°.
Generated from Investigation_Marfa.kml. Geometry only — no terrain occlusion applied yet.]]></description>
<Style id="viewer"><IconStyle><scale>1.3</scale><color>ff007cf5</color>
<Icon><href>http://maps.google.com/mapfiles/kml/shapes/star.png</href></Icon></IconStyle></Style>
<Style id="hp"><IconStyle><scale>1.3</scale><color>ffa21f7b</color>
<Icon><href>http://maps.google.com/mapfiles/kml/shapes/triangle.png</href></Icon></IconStyle></Style>
<Style id="hit"><IconStyle><scale>0.5</scale><color>ff00ffff</color>
<Icon><href>http://maps.google.com/mapfiles/kml/shapes/shaded_dot.png</href></Icon></IconStyle>
<LabelStyle><scale>0</scale></LabelStyle></Style>
<Style id="hwy"><LineStyle><color>ff2dc0fb</color><width>4</width></LineStyle></Style>
<Style id="bound"><LineStyle><color>ffffffff</color><width>2.5</width></LineStyle></Style>
{''.join(styles)}
<Folder><name>Reference features</name>
{kml_point('Marfa Lights Viewing Area', viewer[0], viewer[1], 'viewer', 'US-90 viewing area (from source KML)')}
{kml_point('Highway High-Point', hp[0], hp[1], 'hp', f'Elevation in source KML: {hp[2]:.1f} m AMSL<br>Azimuth from viewer {az_hp % 360:.2f}°, distance {d_hp/1000:.3f} km', hp[2], True)}
{kml_line('US-67 Shafter to Marfa', [(p[0], p[1]) for p in highway], 'hwy')}
{kml_line('Left bound', [(p[0], p[1]) for p in feats['Left Line']], 'bound')}
{kml_line('Right bound', [(p[0], p[1]) for p in feats['Right Line']], 'bound')}
</Folder>
<Folder><name>Rays ({n})</name>
{''.join(body_rays)}
</Folder>
<Folder><name>Highway intersections</name>
{''.join(body_hits)}
</Folder>
</Document>
</kml>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


# ---------------------------------------------------------------- main
def main(src="data/inputs/Investigation_Marfa.kml", out="outputs/Marfa_ray_fan"):
    feats = read_kml(src)
    viewer = [v for k, v in feats.items() if "Hwy 67/90" in k][0][0]
    highway = feats["Shafer to Marfa"]
    # Left bound: originally the "Left Line" in the KML (the US-67 high point, 228.9°).
    # Extended 2026-09-28 to the Shafter end of the highway trace so the fan covers all of US-67.
    left_end = highway[0]
    right_end = feats["Right Line"][-1]

    rays, meta = build_fan(viewer, highway, left_end, right_end)
    write_kml(f"{out}.kml", feats, viewer, highway, rays, meta)

    with open(f"{out}_hits.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ray_azimuth_deg", "crossing", "n_crossings", "lon", "lat",
                    "dist_from_viewer_km", "hwy_chainage_from_shafter_km"])
        for r in rays:
            for h in r["hits"] or [None]:
                if h is None:
                    w.writerow([f"{r['az']:.3f}", 0, 0, "", "", "", ""])
                else:
                    w.writerow([f"{r['az']:.3f}", h["order"], len(r["hits"]),
                                f"{h['lon']:.7f}", f"{h['lat']:.7f}",
                                f"{h['dist_m']/1000:.4f}", f"{h['hwy_chainage_m']/1000:.4f}"])

    with open(f"{out}_profiles.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ray_azimuth_deg", "dist_m", "lon", "lat", "ground_elev_m"])
        for r in rays:
            L = r["hits"][-1]["dist_m"] if r["hits"] else 0
            if not L:
                continue
            d, lon, lat = ray_samples(viewer, r["az"], L)
            for di, lo, la in zip(d, lon, lat):
                w.writerow([f"{r['az']:.3f}", f"{di:.1f}", f"{lo:.7f}", f"{la:.7f}", ""])

    # console summary
    print(f"Viewer: {viewer[1]:.6f}, {viewer[0]:.6f}")
    print(f"Left bound az {meta['az_left']:.3f}°  ({meta['d_left']/1000:.2f} km)")
    print(f"Right bound az {meta['az_right']:.3f}° ({meta['d_right']/1000:.2f} km)")
    print(f"Span {meta['span']:.3f}°  ->  {len(rays)} rays")
    print(f"Highway polyline length {meta['hwy_len_m']/1000:.2f} km")
    miss = [r for r in rays if not r["hits"]]
    multi = [r for r in rays if len(r["hits"]) > 1]
    print(f"Rays with no hit: {len(miss)}; rays with >1 crossing: {len(multi)}")
    for r in multi:
        print("  multi:", f"{r['az']:.2f}°", [round(h['dist_m']/1000, 2) for h in r["hits"]])
    d = [r["hits"][0]["dist_m"] / 1000 for r in rays if r["hits"]]
    print(f"Nearest-crossing distance range {min(d):.2f} – {max(d):.2f} km")
    zs = {p[2] for p in highway}
    print(f"Distinct altitude values in highway LineString: {sorted(zs)[:5]}")
    return rays, meta


if __name__ == "__main__":
    main(*sys.argv[1:2])

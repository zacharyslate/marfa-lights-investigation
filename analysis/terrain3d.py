"""Terrain for the 3D map (docs/terrain.html).

    python analysis/terrain3d.py            ->  docs/data/terrain/{meta.json, height.bin, relief.webp, creeks.png}

Grid: UTM zone 13N (EPSG:26913, NAD83, NAVD88 heights), 20 m cells, x 540-616 km, y 3294-3364 km
(Marfa and the viewing area in the north-east corner, the Chinati Mountains in the south-west).

Heights: USGS 3DEP 1 m lidar DEM (TX_WestTexas_2018_D19, block-averaged to 20 m) wherever a tile is on disk,
and the USGS 3DEP 1/3 arc-second (about 10 m) DEM everywhere else, reprojected bilinearly. Both are bare-earth.
At 20 m the two agree closely (four lidar tiles checked: median difference +0.01 m, 95% within 1.05 m), so the seam is not visible; the 1 m detail that
matters for the line-of-sight model is far finer than anything a 3D overview can show.

Shading ("enhanced topography"): a hypsometric tint, a multi-directional hillshade with the relief doubled,
slope shading, and a local-relief term (height minus Gaussian-smoothed copies at 120 m and 400 m) that lightens ridges and
darkens valley floors. These exaggerate what is there; they add no features.

Creeks: computed from the heights (pit filling, flat resolution, D8 flow directions, flow accumulation) and drawn
where the upstream area exceeds 1.5 km^2, wider for larger drainages. They are drainage lines, i.e. where water
would run after rain; almost all are dry washes most of the year, and they are not the official NHD lines.

The mesh the browser draws is the same grid averaged to 120 m (height.bin, uint16 decimetres above z0); the
20 m shading is the texture draped on it.
"""
import glob
import json
import os

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling, reproject
from rasterio.transform import from_origin
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs/data/terrain")
CACHE = os.path.join(ROOT, "data/dem/terrain20.npz")
CRS = "EPSG:26913"
X0, X1, Y0, Y1, RES = 540_000, 616_000, 3_294_000, 3_364_000, 20
W, H = (X1 - X0) // RES, (Y1 - Y0) // RES
TR = from_origin(X0, Y1, RES, RES)
MESH = 6                                     # mesh cell = 6 x 20 m = 120 m
CREEK_KM2 = 1.5


def mosaic():
    if os.path.exists(CACHE):
        d = np.load(CACHE)
        return d["z"], d["lidar"]
    z = np.full((H, W), np.nan, np.float32)
    for f in sorted(glob.glob(os.path.join(ROOT, "data/dem/raw/USGS_13_*.tif"))):
        with rasterio.open(f) as s:
            t = np.full((H, W), np.nan, np.float32)
            reproject(rasterio.band(s, 1), t, dst_transform=TR, dst_crs=CRS, dst_nodata=np.nan,
                      resampling=Resampling.bilinear)
        ok = np.isfinite(t) & (t > -100)
        z[ok] = t[ok]
        print("1/3 arcsec", os.path.basename(f), ok.sum())
    lid = np.zeros((H, W), bool)
    diffs = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data/dem/raw/USGS_1M_13_*.tif"))):
        with rasterio.open(f) as s:
            b = s.bounds
            if b.right <= X0 or b.left >= X1 or b.top <= Y0 or b.bottom >= Y1:
                continue
            t = np.full((H, W), np.nan, np.float32)
            reproject(rasterio.band(s, 1), t, dst_transform=TR, dst_crs=CRS, src_nodata=s.nodata, dst_nodata=np.nan,
                      resampling=Resampling.average)
        ok = np.isfinite(t) & (t > -100)
        # trim a 2-cell rim where the 20 m average straddles the tile edge
        ok = ndimage.binary_erosion(ok, iterations=2)
        both = ok & np.isfinite(z)
        if both.any():
            diffs.append(t[both] - z[both])
        z[ok] = t[ok]; lid |= ok
        print("lidar", os.path.basename(f), ok.sum())
    if diffs:
        dd = np.concatenate(diffs)
        print(f"lidar - 1/3 arcsec at 20 m: median {np.median(dd):+.2f} m, 5-95% {np.percentile(dd, 5):+.2f}..{np.percentile(dd, 95):+.2f} m")
    bad = ~np.isfinite(z)
    if bad.any():
        idx = ndimage.distance_transform_edt(bad, return_distances=False, return_indices=True)
        z = z[tuple(idx)]
    np.savez_compressed(CACHE, z=z, lidar=lid)
    return z, lid


def creeks(z):
    import pyproj
    from pysheds.grid import Grid
    from pysheds.sview import Raster, ViewFinder
    if not hasattr(np, "in1d"):                       # pysheds 0.5 still calls np.in1d (removed in NumPy 2.4)
        np.in1d = np.isin
    vf = ViewFinder(affine=TR, shape=z.shape, crs=pyproj.Proj(CRS), nodata=np.nan)
    g = Grid(viewfinder=vf)
    dem = Raster(z.astype(np.float64), viewfinder=vf)
    dem = g.fill_pits(dem); dem = g.fill_depressions(dem); dem = g.resolve_flats(dem)
    fdir = g.flowdir(dem)
    acc = np.asarray(g.accumulation(fdir), dtype=np.float64)
    return acc * RES * RES / 1e6                      # upstream area, km^2


def hillshade(z, az, alt, zf):
    gy, gx = np.gradient(z * zf, RES)
    slope = np.arctan(np.hypot(gx, gy))
    a, e = np.radians(az), np.radians(alt)
    # light from azimuth a (clockwise from north); surface normal from the gradient
    nx, ny, nz = -gx, -gy, np.ones_like(z)
    n = np.sqrt(nx * nx + ny * ny + 1)
    lx, ly, lz = np.sin(a) * np.cos(e), np.cos(a) * np.cos(e), np.sin(e)
    # rows run north -> south, so +row is -y
    return np.clip((nx * lx - ny * ly + nz * lz) / n, 0, 1), slope


def tint(z):
    # hypsometric ramp (m, RGB): grassland plain -> brown foothills -> grey-violet rock -> pale summits
    stops = [(1000, (150, 156, 104)), (1200, (178, 172, 116)), (1350, (204, 192, 134)), (1450, (218, 200, 142)),
             (1520, (208, 182, 126)), (1620, (190, 156, 104)), (1800, (162, 124, 92)), (2000, (140, 114, 104)),
             (2200, (156, 144, 140)), (2400, (196, 190, 182))]
    e = np.array([s[0] for s in stops], float); c = np.array([s[1] for s in stops], float)
    return np.stack([np.interp(z, e, c[:, i]) for i in range(3)], -1)


def overlays(z0):
    """Everything drawn on top of the terrain, in grid metres (x east, y north from the SW corner)."""
    from pyproj import Transformer
    t = Transformer.from_crs(4326, 26913, always_xy=True)
    S = json.load(open(os.path.join(ROOT, "docs/data/site.json")))

    def xy(lat, lon):
        x, y = t.transform(lon, lat)
        return [round(x - X0), round(y - Y0)]

    def inside(p, m=2000):
        return -m <= p[0] <= X1 - X0 + m and -m <= p[1] <= Y1 - Y0 + m

    def simplify(pts, tol=25):
        from shapely.geometry import LineString
        if len(pts) < 3:
            return pts
        return [[round(a), round(b)] for a, b in LineString(pts).simplify(tol).coords]

    roads = []
    G = json.load(open(os.path.join(ROOT, "data/inputs/txdot_roadways_bigbend.geojson")))
    for f in G["features"]:
        c = [xy(la, lo) for lo, la in f["geometry"]["coordinates"]]
        if not any(inside(p, 0) for p in c):
            continue
        p = f["properties"]
        name = {"US": "US-", "SH": "SH ", "FM": "FM ", "RM": "RM ", "IH": "I-"}.get(p["RTE_PRFX"], p["RTE_PRFX"] + " ") + p["RTE_NBR"].lstrip("0")
        roads.append({"n": name, "k": p["RTE_PRFX"], "c": simplify(c)})
    for r in S["roads"]:                                   # county roads used by the model (not on TxDOT's on-system layer)
        if r["k"].startswith("CR"):
            roads.append({"n": r["n"], "k": "CR", "c": simplify([xy(q[0], q[1]) for q in r["p"]])})
    # US-67 where headlamps can be seen from the platform (model class v, normal refraction), as runs of points
    vis, run = [], []
    for h in S["hwy"]:
        if h[6] == "v":
            run.append(xy(h[0], h[1]))
        elif run:
            vis.append(run); run = []
    if run:
        vis.append(run)
    rail = [{"o": r["o"], "c": simplify([xy(a, b) for a, b in r["c"]])} for r in S["rail"]]
    rail = [r for r in rail if any(inside(p, 0) for p in r["c"])]
    tl = [{"kv": r["kv"], "c": simplify([xy(a, b) for a, b in r["c"]])} for r in S["tl"]]
    tl = [r for r in tl if any(inside(p, 0) for p in r["c"])]
    towers = []
    for tw in S["towers"]:
        p = xy(tw["lat"], tw["lon"])
        if inside(p, 0):
            towers.append({"p": p, "h": tw["h"], "lit": tw["light"] in ("lit", "dual"), "o": tw.get("owner") or "",
                           "t": tw["type"], "id": tw["id"]})
    v = S["viewer"]
    places = [{"n": "Marfa Lights Viewing Area", "k": "viewer", "p": xy(v["lat"], v["lon"]), "z": v["z"]}]
    places += [{"n": tw["n"], "k": "town", "p": xy(tw["lat"], tw["lon"])} for tw in S["towns"] if inside(xy(tw["lat"], tw["lon"]), 0)]
    places += [{"n": "Chinati Peak", "k": "peak", "p": xy(29.9532235, -104.4776936), "z": 2354, "src": "GNIS"},
               {"n": "US-67 high point", "k": "ref", "p": xy(30.0384, -104.19452)}]
    places += [{"n": f["n"], "k": "field", "p": xy(f["lat"], f["lon"])} for f in S["fields"] if inside(xy(f["lat"], f["lon"]), 0)]
    out = {"roads": roads, "us67_visible": vis, "rail": rail, "power": tl, "towers": towers, "places": places,
           "grid_convergence_deg": round(float(__import__("pyproj").Proj("EPSG:26913").get_factors(v["lon"], v["lat"]).meridian_convergence), 3)}
    open(os.path.join(OUT, "overlays.json"), "w").write(json.dumps(out, separators=(",", ":")))
    print("overlays", len(roads), "roads,", len(vis), "visible US-67 runs,", len(towers), "towers,", len(places), "places",
          os.path.getsize(os.path.join(OUT, "overlays.json")) // 1024, "KB")


def main():
    os.makedirs(OUT, exist_ok=True)
    z, lid = mosaic()
    print("grid", z.shape, "z", float(z.min()), float(z.max()), "lidar cover", round(lid.mean(), 3))

    # shading
    hs = np.zeros_like(z)
    for az, w in ((315, 0.40), (270, 0.20), (360, 0.20), (225, 0.20)):
        h, slope = hillshade(z, az, 40, 2.5); hs += w * h
    _, slope = hillshade(z, 315, 40, 1.0)             # true slope for the slope term
    tpi = 0.6 * (z - ndimage.gaussian_filter(z, 400 / RES)) + 0.4 * 2.5 * (z - ndimage.gaussian_filter(z, 120 / RES))
    tpi_n = np.tanh(tpi / 15.0)                       # +1 ridge crest ... -1 valley floor (two scales, 120 and 400 m)
    sl = np.degrees(slope)
    col = tint(z)
    shade = 0.30 + 0.85 * hs                          # 0.3 .. 1.15
    shade *= 1 - 0.18 * np.clip(sl / 45, 0, 1)
    shade *= 1 + 0.16 * tpi_n
    rgb = np.clip(col * shade[..., None], 0, 255)
    # valley floors pick up a faint green (where the grass and the water collect)
    vf = np.clip(-tpi_n, 0, 1)[..., None] * 0.18
    rgb = rgb * (1 - vf) + np.array([120, 140, 92]) * vf
    Image.fromarray(rgb.astype(np.uint8)).save(os.path.join(OUT, "relief.webp"), "WEBP", quality=84, method=6)

    # creeks: upstream area >= 1.5 km^2, and either in a real channel (at least 0.3 m below its 120 m
    # surroundings) or draining >= 20 km^2. Without the channel test, the flat-resolution step draws
    # straight parallel "creeks" across the dead-flat parts of the plain that no water would follow.
    ac = os.path.join(ROOT, "data/dem/terrain20_area.npy")
    if os.path.exists(ac):
        area = np.load(ac)
    else:
        area = creeks(z).astype(np.float32); np.save(ac, area)
    tpi120 = z - ndimage.gaussian_filter(z, 120 / RES)
    on = (area >= CREEK_KM2) & ((tpi120 < -0.3) | (area >= 20))
    lab, n = ndimage.label(on, structure=np.ones((3, 3)))
    size = ndimage.sum(on, lab, index=np.arange(1, n + 1))
    on &= np.isin(lab, 1 + np.flatnonzero(size >= 15))          # drop fragments shorter than ~300 m
    lvl = np.clip(np.log10(np.maximum(area, 1e-6) / CREEK_KM2) / np.log10(300 / CREEK_KM2), 0, 1)
    alpha = np.where(on, 150 + 105 * lvl, 0)
    wide = ndimage.binary_dilation(on & (area >= 60))             # main creeks two cells wide
    alpha = np.maximum(alpha, np.where(wide, 200, 0))
    a = np.clip(alpha, 0, 255).astype(np.uint8)
    rgba = np.zeros((H, W, 4), np.uint8); rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3] = 52, 128, 210, a
    Image.fromarray(rgba, "RGBA").save(os.path.join(OUT, "creeks.png"), optimize=True)

    # mesh heights at 120 m (block mean), corner-registered for the browser: (H/6+1) x (W/6+1) vertices
    zm = ndimage.uniform_filter(z, MESH, mode="nearest")
    ys = np.clip(np.arange(0, H + 1, MESH), 0, H - 1); xs = np.clip(np.arange(0, W + 1, MESH), 0, W - 1)
    zv = zm[np.ix_(ys, xs)]
    z0 = float(np.floor(zv.min()))
    q = np.round((zv - z0) * 10).astype("<u2")
    q.tofile(os.path.join(OUT, "height.bin"))

    meta = {
        "crs": "EPSG:26913 (UTM 13N, NAD83); heights NAVD88 metres",
        "x0": X0, "x1": X1, "y0": Y0, "y1": Y1, "tex_res_m": RES, "tex_w": W, "tex_h": H,
        "nx": int(len(xs)), "ny": int(len(ys)), "mesh_m": RES * MESH, "z0": z0, "zscale": 0.1,
        "zmin": round(float(z.min()), 1), "zmax": round(float(z.max()), 1),
        "lidar_fraction": round(float(lid.mean()), 3),
        "creek_min_km2": CREEK_KM2,
        "sources": [
            "USGS 3DEP 1 m lidar DEM, project TX_WestTexas_2018_D19 (block-averaged to 20 m)",
            "USGS 3DEP 1/3 arc-second DEM (outside the lidar tiles)",
        ],
        "notes": "Creeks are computed drainage lines (D8 flow accumulation), not NHD. Flat map: Earth curvature not applied.",
    }
    # check: the highest cell in the Chinati block against GNIS Chinati Peak (29.9532235, -104.4776936; 2,354 m)
    yy, xx = np.unravel_index(np.argmax(np.where((np.arange(W)[None, :] < 1200) & (np.arange(H)[:, None] > 2000), z, -1)), z.shape)
    meta["chinati_check"] = {"dem_max_xy": [X0 + (xx + 0.5) * RES, Y1 - (yy + 0.5) * RES], "dem_max_z": round(float(z[yy, xx]), 1),
                             "gnis_z": 2354}
    with open(os.path.join(OUT, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1, default=float)
    for f in sorted(os.listdir(OUT)):
        print(f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")
    print(meta["chinati_check"])
    overlays(z0)


if __name__ == "__main__":
    main()

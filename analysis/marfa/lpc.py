"""Obstruction heights (shrubs, trees, fences, structures) from the USGS lidar point cloud.

The 1 m DEM is bare earth. Light from a car on US-67 often grazes the ground within a metre, so what stands on
the ground matters. For each 1.5 km LPC tile we rasterise, on the 1 m grid of the DEM (NAD83(2011) UTM 13N):
    hmax   the highest non-noise return above the bare-earth DEM in the cell (m)
    frac   the fraction of all returns in the cell that are more than 0.3 m above the DEM
    n      the number of returns in the cell
Classes used: all except 7 (low noise), 18 (high noise) and withheld points. The project classifies only
ground, water, bridge and noise (Lidar Base Specification 1.3), so vegetation, fences, buildings, vehicles and
wires are all in class 1 ("unclassified").

Two obstruction surfaces are derived (analysis/marfa/dem.py: Obstruction):
    dense  hmax where frac >= 0.25 and n_above >= 2 (solid cover: shrubs, trees, buildings), else 0
    max    hmax everywhere (upper bound: also counts isolated returns from wires, posts and birds)
A thin wire or a fence post is not an opaque wall, so 'dense' is the reference and 'max' the bound.
Output: data/dem/chm/CHM_<tile>.tif, 3 bands (hmax, frac, n), float32, LZW."""
from __future__ import annotations

import glob
import json
import os
import sys

import laspy
import numpy as np
import rasterio
from rasterio.transform import from_origin

from . import dem

CHM_DIR = os.path.join(dem.DEM_DIR, "chm")
LPC_DIR = os.path.join(dem.DEM_DIR, "lpc")
NOISE = (7, 18)
ABOVE = 0.3


def dem_for(x0, y0, x1, y1):
    """Bare-earth 1 m DEM values on the cell grid [x0, x1) x [y0, y1) (cell centres), from the lidar tiles."""
    xs = np.arange(x0, x1) + 0.5
    ys = np.arange(y1, y0, -1) - 0.5
    X, Y = np.meshgrid(xs, ys)
    out = np.full(X.shape, np.nan, "float32")
    for p in sorted(glob.glob(os.path.join(dem.RAW_DIR, "USGS_1M_13_*.tif"))):
        with rasterio.open(p) as src:
            b = src.bounds
            if b.right <= x0 or b.left >= x1 or b.top <= y0 or b.bottom >= y1:
                continue
            win = rasterio.windows.from_bounds(max(x0, b.left), max(y0, b.bottom), min(x1, b.right),
                                               min(y1, b.top), transform=src.transform).round_offsets().round_lengths()
            z = src.read(1, window=win, masked=True).filled(np.nan)
            wt = src.window_transform(win)
            rr, cc = z.shape
            # place z into out: out row i corresponds to y = y1 - i - 0.5; z row j to y = wt.f - j - 0.5
            i0 = int(round(y1 - wt.f))
            j0 = int(round(wt.c - x0))
            ii0, jj0 = max(i0, 0), max(j0, 0)
            ii1, jj1 = min(i0 + rr, out.shape[0]), min(j0 + cc, out.shape[1])
            blk = z[ii0 - i0: ii1 - i0, jj0 - j0: jj1 - j0]
            tgt = out[ii0:ii1, jj0:jj1]
            fill = np.isnan(tgt)
            tgt[fill] = blk[fill]
    return out


def rasterise(laz_path, out_dir=CHM_DIR, chunk=5_000_000):
    os.makedirs(out_dir, exist_ok=True)
    name = os.path.basename(laz_path).replace(".laz", "")
    dst = os.path.join(out_dir, f"CHM_{name}.tif")
    if os.path.exists(dst):
        return dst
    with laspy.open(laz_path) as f:
        h = f.header
        x0, y0 = np.floor(h.mins[0]), np.floor(h.mins[1])
        x1, y1 = np.ceil(h.maxs[0]), np.ceil(h.maxs[1])
        W, H = int(x1 - x0), int(y1 - y0)
        base = dem_for(x0, y0, x1, y1)
        hmax = np.full(H * W, -np.inf, "float32")
        n = np.zeros(H * W, "int32")
        nab = np.zeros(H * W, "int32")
        flat_base = base.ravel()
        for pts in f.chunk_iterator(chunk):
            cls = np.asarray(pts.classification)
            keep = ~np.isin(cls, NOISE)
            try:
                keep &= ~np.asarray(pts.withheld, bool)
            except Exception:
                pass
            x, y, z = np.asarray(pts.x)[keep], np.asarray(pts.y)[keep], np.asarray(pts.z)[keep]
            c = (x - x0).astype(int)
            r = (y1 - y).astype(int)
            ok = (c >= 0) & (c < W) & (r >= 0) & (r < H)
            idx = r[ok] * W + c[ok]
            hag = (z[ok] - flat_base[idx]).astype("float32")
            good = ~np.isnan(hag)
            idx, hag = idx[good], hag[good]
            np.maximum.at(hmax, idx, hag)
            np.add.at(n, idx, 1)
            np.add.at(nab, idx, (hag > ABOVE).astype("int32"))
    hmax[np.isinf(hmax)] = np.nan
    frac = np.where(n > 0, nab / np.maximum(n, 1), np.nan).astype("float32")
    prof = dict(driver="GTiff", width=W, height=H, count=3, dtype="float32", crs="EPSG:26913",
                transform=from_origin(x0, y1, 1.0, 1.0), compress="lzw", nodata=np.nan, tiled=True,
                blockxsize=256, blockysize=256)
    with rasterio.open(dst, "w", **prof) as o:
        o.write(hmax.reshape(H, W), 1)
        o.write(frac.reshape(H, W), 2)
        o.write(n.reshape(H, W).astype("float32"), 3)
        o.update_tags(source=os.path.basename(laz_path), above_threshold_m=ABOVE, noise_classes=str(NOISE),
                      note="band1 hmax above bare-earth 1 m DEM; band2 fraction of returns > 0.3 m; band3 count")
    return dst


if __name__ == "__main__":
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(LPC_DIR, "*.laz")))
    for p in files:
        print(rasterise(p), flush=True)

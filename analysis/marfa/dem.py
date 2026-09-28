"""Archived USGS 3DEP elevation rasters, stacked by priority (finest first), with bilinear sampling.

Every source raster is recorded in data/dem/MANIFEST.json with its USGS URL, product, byte size,
SHA-256, Last-Modified header and retrieval date (see analysis/marfa/fetch_dem.py).

Coordinates passed to sample() are geographic NAD83(2011) longitude/latitude in degrees (EPSG:6318/4269).
Rasters in a projected CRS (the 1 m lidar tiles are NAD83 UTM 13N) are sampled by transforming the query
points into the raster CRS. Heights are NAVD88 orthometric metres.

Sampling rules
  * bilinear interpolation between the four surrounding pixel centres;
  * if any of the four is nodata, the point is NaN in that raster and falls through to the next raster;
  * Mosaic.sample(strict=True) raises if a point has no data in any raster (no silent gaps).

Large rasters are read lazily in their native 512 x 512 blocks through a byte-limited LRU cache, so the
27 lidar tiles (about 11 GB as float32) can be used on a machine with a few GB of memory."""
from __future__ import annotations

import collections
import glob
import json
import os

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.windows import Window, from_bounds

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEM_DIR = os.path.join(ROOT, "data", "dem")
RAW_DIR = os.path.join(DEM_DIR, "raw")
# The 2019 lidar (and the 1/3" and 1" DEMs resampled from it here) give NAVD88 heights computed from ellipsoidal
# heights with GEOID12B (project report, data/dem/meta), so GEOID12B converts them back consistently.
# GEOID18 differs from GEOID12B by -0.06..+0.06 m over the study area (sensitivity only).
GEOID_GRID = os.path.join(ROOT, "data", "geoid", "us_noaa_g2012bu0.tif")
GEOID18_GRID = os.path.join(ROOT, "data", "geoid", "us_noaa_g2018u0.tif")
GEOG = CRS.from_epsg(4269)          # NAD83 geographic; the 3DEP tiles are NAD83(2011) realisations


class _BlockCache:
    """Byte-limited LRU cache of raster blocks, shared by all lazy rasters."""

    def __init__(self, max_bytes=2.5e9):
        self.max = max_bytes
        self.d = collections.OrderedDict()
        self.size = 0

    def get(self, key, loader):
        if key in self.d:
            self.d.move_to_end(key)
            return self.d[key]
        arr = loader()
        self.d[key] = arr
        self.size += arr.nbytes
        while self.size > self.max and len(self.d) > 1:
            _, old = self.d.popitem(last=False)
            self.size -= old.nbytes
        return arr


CACHE = _BlockCache()


class Raster:
    """One elevation raster.  eager: read (a window of) it into memory.  lazy: read 512-px blocks on demand."""

    def __init__(self, path, bounds=None, name=None, lazy=False):
        self.path, self.name, self.lazy = path, name or os.path.basename(path), lazy
        self.src = rasterio.open(path)
        self.crs = CRS.from_user_input(self.src.crs.to_wkt())
        self.geographic = self.crs.is_geographic
        self.to_src = None if self.geographic else Transformer.from_crs(GEOG, self.crs, always_xy=True)
        if lazy:
            self.tr = self.src.transform
            self.shape = (self.src.height, self.src.width)
            self.bw, self.bh = self.src.block_shapes[0][1], self.src.block_shapes[0][0]
            self.z = None
        else:
            if bounds is not None and not self.geographic:
                bounds = self.to_src.transform_bounds(*bounds)
            win = from_bounds(*bounds, transform=self.src.transform) if bounds else None
            if win is not None:
                win = win.round_offsets().round_lengths()
                win = win.intersection(Window(0, 0, self.src.width, self.src.height))
            self.z = self.src.read(1, window=win, masked=True).astype("float32").filled(np.nan)
            self.tr = self.src.window_transform(win) if win is not None else self.src.transform
            self.shape = self.z.shape
            self.src.close()
            self.src = None
        self.res = abs(self.tr.a)
        a, e = self.tr.a, self.tr.e
        h, w = self.shape
        self.bounds_src = (self.tr.c, self.tr.f + h * e, self.tr.c + w * a, self.tr.f)

    # ------------------------------------------------------------------
    def _block(self, bi, bj):
        def load():
            win = Window(bj * self.bw, bi * self.bh, self.bw, self.bh).intersection(
                Window(0, 0, self.shape[1], self.shape[0]))
            z = self.src.read(1, window=win, masked=True).astype("float32").filled(np.nan)
            out = np.full((self.bh, self.bw), np.nan, "float32")
            out[:z.shape[0], :z.shape[1]] = z
            return out
        return CACHE.get((self.path, bi, bj), load)

    def _values(self, r, c):
        """Pixel values at integer rows/cols (all inside the raster)."""
        if not self.lazy:
            return self.z[r, c]
        out = np.empty(r.shape, "float32")
        bi, bj = r // self.bh, c // self.bw
        key = bi * 100000 + bj
        for k in np.unique(key):
            m = key == k
            blk = self._block(int(k // 100000), int(k % 100000))
            out[m] = blk[r[m] - (k // 100000) * self.bh, c[m] - (k % 100000) * self.bw]
        return out

    def sample(self, lon, lat):
        """Bilinear sample at NAD83 lon/lat (deg); NaN outside this raster or where any neighbour is nodata."""
        lon, lat = np.atleast_1d(np.asarray(lon, float)), np.atleast_1d(np.asarray(lat, float))
        x, y = (lon, lat) if self.geographic else self.to_src.transform(lon, lat)
        col = (x - self.tr.c) / self.tr.a - 0.5
        row = (y - self.tr.f) / self.tr.e - 0.5
        c0, r0 = np.floor(col).astype(int), np.floor(row).astype(int)
        h, w = self.shape
        ok = (c0 >= 0) & (r0 >= 0) & (c0 < w - 1) & (r0 < h - 1)
        out = np.full(lon.shape, np.nan, "float64")
        if not ok.any():
            return out
        c, r = c0[ok], r0[ok]
        tx, ty = (col[ok] - c), (row[ok] - r)
        z00, z01 = self._values(r, c), self._values(r, c + 1)
        z10, z11 = self._values(r + 1, c), self._values(r + 1, c + 1)
        out[ok] = z00 * (1 - tx) * (1 - ty) + z01 * tx * (1 - ty) + z10 * (1 - tx) * ty + z11 * tx * ty
        return out

    def footprint_geog(self):
        """Approximate lon/lat bounds of this raster."""
        if self.geographic:
            return self.bounds_src
        inv = Transformer.from_crs(self.crs, GEOG, always_xy=True)
        return inv.transform_bounds(*self.bounds_src)


class Mosaic:
    """Priority stack of rasters: the first raster that has data at a point wins."""

    def __init__(self, rasters, names=None):
        self.rasters = list(rasters)
        self.names = names or [r.name for r in self.rasters]

    def sample(self, lon, lat, strict=True):
        lon, lat = np.atleast_1d(np.asarray(lon, float)), np.atleast_1d(np.asarray(lat, float))
        out = np.full(lon.shape, np.nan)
        src = np.full(lon.shape, -1, int)
        for i, r in enumerate(self.rasters):
            need = np.isnan(out)
            if not need.any():
                break
            idx = np.where(need)[0]
            if hasattr(r, "fp"):     # quick reject by footprint
                x0, y0, x1, y1 = r.fp
                inside = (lon[idx] >= x0) & (lon[idx] <= x1) & (lat[idx] >= y0) & (lat[idx] <= y1)
                idx = idx[inside]
                if idx.size == 0:
                    continue
            v = r.sample(lon[idx], lat[idx])
            good = ~np.isnan(v)
            out[idx[good]] = v[good]
            src[idx[good]] = i
        if strict and np.isnan(out).any():
            bad = np.where(np.isnan(out))[0]
            raise ValueError(f"DEM has no data at {bad.size} points, e.g. "
                             f"{[(float(lon[b]), float(lat[b])) for b in bad[:5]]}")
        return out, src


STUDY_BOUNDS = (-104.75, 29.60, -103.70, 30.55)     # lon0, lat0, lon1, lat1 with margin around the study area


def load(level="lidar", bounds=STUDY_BOUNDS):
    """Standard mosaics.
    level='1s'    : USGS 1 arc-second only
    level='13s'   : 1/3 arc-second, then 1 arc-second
    level='lidar' : 1 m lidar tiles (lazy), then 1/3", then 1"."""
    rs = []
    if level == "lidar":
        for p in sorted(glob.glob(os.path.join(RAW_DIR, "USGS_1M_13_*.tif"))):
            r = Raster(p, lazy=True)
            r.fp = r.footprint_geog()
            rs.append(r)
    if level in ("lidar", "13s"):
        for p in sorted(glob.glob(os.path.join(RAW_DIR, "USGS_13_*.tif"))):
            r = Raster(p, bounds=bounds)
            if r.z.size:
                r.fp = r.footprint_geog()
                rs.append(r)
    for p in sorted(glob.glob(os.path.join(RAW_DIR, "USGS_1_n*.tif"))):
        r = Raster(p, lazy=True)            # 1" tiles are read lazily: they also serve the 120 km skyline
        r.fp = r.footprint_geog()
        rs.append(r)
    return Mosaic(rs)


def manifest():
    p = os.path.join(DEM_DIR, "MANIFEST.json")
    return json.load(open(p)) if os.path.exists(p) else {}

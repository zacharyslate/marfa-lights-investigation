"""Geodesy for the line-of-sight model.

All horizontal geometry uses WGS84 geodesics (pyproj.Geod, Karney's algorithm). Heights from USGS 3DEP are
NAVD88 orthometric heights H; ellipsoidal heights are h = H + N, where N is the geoid undulation. Line-of-sight
geometry is computed exactly in Earth-centred, Earth-fixed (ECEF) coordinates, so no flat-earth or spherical
approximation enters the geometry. Refraction enters separately as a sag of the ray above the chord.
"""
from __future__ import annotations

import numpy as np
from pyproj import Geod, Transformer

GEOD = Geod(ellps="WGS84")
A_WGS84 = 6378137.0
F_WGS84 = 1 / 298.257223563
E2 = F_WGS84 * (2 - F_WGS84)
_TO_ECEF = Transformer.from_crs("EPSG:4979", "EPSG:4978", always_xy=True)


def ecef(lon, lat, h):
    """Geodetic lon/lat (deg) and ellipsoidal height h (m) -> ECEF x, y, z (m)."""
    x, y, z = _TO_ECEF.transform(np.asarray(lon, float), np.asarray(lat, float), np.asarray(h, float))
    return np.stack([x, y, z], axis=-1)


def normal(lon, lat):
    """Unit ellipsoid normal (local 'up') at lon/lat, in ECEF."""
    lo, la = np.radians(lon), np.radians(lat)
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)


def enu_basis(lon, lat):
    """East, north, up unit vectors (ECEF) at a point."""
    lo, la = np.radians(lon), np.radians(lat)
    e = np.array([-np.sin(lo), np.cos(lo), 0.0])
    n = np.array([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)])
    u = np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    return e, n, u


def radii(lat):
    """Meridional (M) and prime-vertical (N) radii of curvature at latitude lat (deg)."""
    s2 = np.sin(np.radians(lat)) ** 2
    w = np.sqrt(1 - E2 * s2)
    return A_WGS84 * (1 - E2) / w ** 3, A_WGS84 / w


def normal_section_radius(lat, az):
    """Radius of curvature of the normal section in azimuth az (deg) at latitude lat (Euler's formula)."""
    m, n = radii(lat)
    a = np.radians(az)
    return 1.0 / (np.cos(a) ** 2 / m + np.sin(a) ** 2 / n)


def inv(lon1, lat1, lon2, lat2):
    """Forward azimuth (deg, 0-360) and geodesic distance (m)."""
    az, _, d = GEOD.inv(lon1, lat1, lon2, lat2)
    return np.mod(az, 360.0), d


def fwd(lon, lat, az, d):
    lo, la, _ = GEOD.fwd(lon, lat, az, d)
    return lo, la


def path(lon1, lat1, lon2, lat2, step):
    """Points along the WGS84 geodesic from (1) to (2) every `step` m, excluding both ends.
    Returns lon, lat, distance-from-start arrays."""
    az, d = inv(lon1, lat1, lon2, lat2)
    n = max(int(np.ceil(d / step)), 2)
    s = np.linspace(0, d, n + 1)[1:-1]
    lo, la, _ = GEOD.fwd(np.full_like(s, lon1), np.full_like(s, lat1), np.full_like(s, az), s)
    return np.asarray(lo), np.asarray(la), s


class Geoid:
    """Geoid undulation N(lon, lat) in metres from a PROJ-style grid (e.g. NOAA GEOID18 us_noaa_g2018u0.tif).
    If no grid is supplied, N is taken as a constant (its absolute value cancels in line-of-sight tests; only
    the difference between points matters)."""

    def __init__(self, grid_path: str | None = None, constant: float = 0.0):
        self.const = constant
        self.src = None
        if grid_path:
            import rasterio
            self.src = rasterio.open(grid_path)
            self.arr = self.src.read(1).astype(float)
            self.tr = self.src.transform

    def __call__(self, lon, lat):
        if self.src is None:
            return np.full(np.shape(lon), self.const, float)
        lon, lat = np.asarray(lon, float), np.asarray(lat, float)
        if self.tr.c >= 0:            # NOAA grids are stored in 0..360 longitude
            lon = np.mod(lon, 360.0)
        # GDAL reports pixel-corner transforms even for AREA_OR_POINT=Point grids, so node i sits at c + (i+0.5)a
        col = (lon - self.tr.c) / self.tr.a - 0.5
        row = (lat - self.tr.f) / self.tr.e - 0.5
        c0, r0 = np.floor(col).astype(int), np.floor(row).astype(int)
        h, w = self.arr.shape
        if np.any((c0 < 0) | (r0 < 0) | (c0 >= w - 1) | (r0 >= h - 1)):
            raise ValueError("point outside geoid grid")
        tx, ty = col - c0, row - r0
        a = self.arr
        v = (a[r0, c0] * (1 - tx) * (1 - ty) + a[r0, c0 + 1] * tx * (1 - ty)
             + a[r0 + 1, c0] * (1 - tx) * ty + a[r0 + 1, c0 + 1] * tx * ty)
        return v

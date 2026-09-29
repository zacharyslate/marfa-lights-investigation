"""Photometry v2: how bright a vehicle on a road in view looks from the Viewing Area, and whether it can be seen.

Geometry (per road sample, per direction of travel)
    h   horizontal angle of the viewer off the vehicle's heading (deg, + = to the driver's right)
    v   vertical angle of the viewer above the lamp's horizontal axis (deg):
            v = eps_T - pitch - aim
        eps_T  elevation of the arriving ray at the lamp above the lamp's local horizontal, from the exact
               chord geometry plus refraction: eps_T = -geo_el - D/R + k D/(2R)   (radians; geo_el = chord
               elevation at the eye, D chord length, R normal-section radius)
        pitch  vehicle pitch = atan(road grade along the heading), grade from the 1 m lidar at +-25 m
        aim    headlamp vertical aim error (0 in the central case; +-0.5 deg sensitivity)
Lamps
  front (|h| <= 90 deg):  two headlamps, low or high beam. Luminous intensity I(h, v) from the market-weighted
      U.S. beam patterns of UMTRI: low beam Schoettle et al. 2004 (UMTRI-2004-23, Table 4), high beam Schoettle
      et al. 2001 (UMTRI-2001-19, Table 6); 25th/50th/75th percentiles on a 0.5-5 deg grid over 45L-45R, 5D-7U,
      interpolated in log I. Beyond 45 deg no data exist: the intensity is held at its 45 deg value (upper case)
      or set to the regulatory floor of the front position (parking) and side-marker lamps (lower case).
  rear (|h| > 90 deg):  two tail lamps; with braking also two stop lamps and the high-mounted stop lamp.
      FMVSS No. 108 photometry (Tables VIII, IX, XV, as reproduced in NHTSA TP-108-13): tail lamp 2.0 cd min /
      18 cd max at H-V (single lighted section), 0.8 cd at 10 deg, 0.3 cd at 20 deg; stop lamp 80 cd min /
      300 cd max at H-V, 40 cd at 10 deg, 10 cd at 20 deg; high-mounted stop lamp 25 cd min / 160 cd max, 16 cd at
      10 deg. Lamps are bracketed between the regulatory minimum and maximum (no market-weighted data were found
      for signal lamps).
Radiometry
    E = sum_i I_i T / D^2  (lux; the lamps are unresolved at these ranges), T = exp(-ln(20) D / MOR)
    m = -13.99 - 2.5 log10(E / 1 lx)          (Schaefer 1993: magnitude of a point source from its illuminance)
Detection (naked eye, point source on a dark background)
    m_lim = 0.3834 mu - 1.4400 - 2.5 log10 F   for 20 < mu < 22 mag/arcsec^2  (Crumey 2014, eq. 54)
    mu = background surface brightness near the horizon, F = observer field factor (Crumey: typically 1.4-2.4)."""
from __future__ import annotations

import json
import math
import os

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from . import dem, geodesy as g

INPUTS = os.path.join(dem.ROOT, "data", "inputs")


def _ang(labels, sign_pos):
    out = []
    for s in labels:
        if s in ("0", "H", "V"):
            out.append(0.0)
        else:
            val = float(s[:-1])
            out.append(val if s[-1] == sign_pos else -val)
    return np.array(out)


class UMTRIBeam:
    """Market-weighted U.S. headlamp beam (one lamp), interpolated in log10(I) over (v, h).
    h + = right of the lamp axis (driver's right), v + = up."""

    def __init__(self, fname):
        d = json.load(open(os.path.join(INPUTS, fname)))
        self.source = d["source"]
        self.h = _ang(d["h"], "R")
        self.v = _ang(d["v"], "U")
        oh, ov = np.argsort(self.h), np.argsort(self.v)
        self.h, self.v = self.h[oh], self.v[ov]
        self.f = {}
        for q in ("p25", "p50", "p75"):
            a = np.log10(np.maximum(np.array(d[q], float), 0.5))[np.ix_(ov, oh)]
            self.f[q] = RegularGridInterpolator((self.v, self.h), a, bounds_error=False, fill_value=None)

    def __call__(self, h, v, q="p50"):
        h, v = np.broadcast_arrays(np.asarray(h, float), np.asarray(v, float))
        hc = np.clip(h, self.h[0], self.h[-1])
        vc = np.clip(v, self.v[0], self.v[-1])
        return 10 ** self.f[q](np.c_[vc.ravel(), hc.ravel()]).reshape(h.shape)


LOW = UMTRIBeam("umtri_2004_23_lowbeam.json")
HIGH = UMTRIBeam("umtri_2001_19_highbeam.json")

# FMVSS 108 regulatory photometry (NHTSA TP-108-13, tables reproduced from FMVSS No. 108):
# minimum luminous intensity (cd) on the horizontal through the lamp axis at the tabulated angles, and maximum.
TAIL = dict(pts=[(0, 2.0), (5, 2.0), (10, 0.8), (20, 0.3)], max=18.0)     # Table VIII, one lighted section
STOP = dict(pts=[(0, 80.0), (5, 80.0), (10, 40.0), (20, 10.0)], max=300.0)  # Table IX, one lighted section
CHMSL = dict(pts=[(0, 25.0), (5, 25.0), (10, 16.0)], max=160.0)            # Table XV (high-mounted stop lamp)
PARKING_MIN_20 = 0.4                                         # Table XIV: 0.4 cd at 20L/20R (5U, 5D)
SIDE_MARKER_AMBER = 0.62                                     # Table X: 0.62 cd at 45L/45R (amber, front)


def reg_lamp(spec, hr, which):
    """Regulatory bracket for a signal lamp seen hr degrees off its axis.
    'min': log-linear between the tabulated minima; beyond the last tabulated angle the requirement ends, so the
           minimum is taken as that last value out to 45 deg (the lamps must be geometrically visible to 45 deg,
           Table V) and zero beyond; 'max': the regulatory cap out to 45 deg, zero beyond."""
    hr = np.abs(np.asarray(hr, float))
    if which == "min":
        a = np.array([p[0] for p in spec["pts"]]); b = np.log10([p[1] for p in spec["pts"]])
        return np.where(hr <= 45, 10 ** np.interp(hr, a, b), 0.0)
    return np.where(hr <= 45, spec["max"], 0.0)


def magnitude(E):
    with np.errstate(divide="ignore"):
        return -13.99 - 2.5 * np.log10(np.maximum(E, 1e-30))


def transmission(D, mor_km):
    return np.exp(-math.log(20) * D / (mor_km * 1000.0))


def m_lim(mu, F):
    """Naked-eye point-source limiting magnitude (Crumey 2014, eq. 54; 20 < mu < 22 mag/arcsec^2)."""
    return 0.3834 * mu - 1.4400 - 2.5 * np.log10(F)


def front_intensity(h, v, beam, q="p50", wide="hold"):
    """Two headlamps. |h| <= 45: UMTRI table. 45 < |h| <= 90: 'hold' = the 45 deg value, 'floor' = parking + marker
    regulatory minima. The two lamps are ~1.5 m apart: at >1 km both are seen at the same (h, v)."""
    B = LOW if beam == "low" else HIGH
    I = 2 * B(h, v, q)
    a = np.abs(h)
    if wide == "floor":
        I = np.where(a > 45, 2 * PARKING_MIN_20 + SIDE_MARKER_AMBER, I)
    return np.where(a > 90, 0.0, I)


def rear_intensity(h, braking=False, which="min"):
    """Rear lamps seen at h (deg off the heading; rear axis at 180)."""
    hr = 180 - np.abs(h)
    I = 2 * reg_lamp(TAIL, hr, which)
    if braking:
        I = I + 2 * reg_lamp(STOP, hr, which) + reg_lamp(CHMSL, hr, which)
    return np.where(np.abs(h) <= 90, 0.0, I)


# ---------------------------------------------------------------- road geometry
def road_heading_grade(lon, lat, chain, fid, mosaic, half=25.0):
    """Heading (deg, direction of increasing chainage) and grade (dz/ds along that heading) from the lidar,
    sampled +-half m along the road."""
    n = lon.size
    hd = np.zeros(n)
    order = np.lexsort((chain, fid))
    for grp in np.split(order, np.where(np.diff(fid[order]) != 0)[0] + 1):
        if grp.size < 2:
            continue
        for k, i in enumerate(grp):
            a, b = grp[max(k - 1, 0)], grp[min(k + 1, grp.size - 1)]
            hd[i] = g.inv(lon[a], lat[a], lon[b], lat[b])[0]
    lo1, la1 = g.fwd(lon, lat, hd, np.full(n, half))
    lo0, la0 = g.fwd(lon, lat, (hd + 180) % 360, np.full(n, half))
    z1, _ = mosaic.sample(np.asarray(lo1), np.asarray(la1), strict=False)
    z0, _ = mosaic.sample(np.asarray(lo0), np.asarray(la0), strict=False)
    grade = (z1 - z0) / (2 * half)
    return hd, np.nan_to_num(grade)


def view_angles(lon, lat, heading, grade, geo_el_deg, D, R, k=0.13, aim=0.0):
    """h, v (deg) for both directions of travel: returns dict dir -> (h, v); dir 'fwd' = direction of increasing
    chainage, 'rev' = the opposite."""
    V = (-103.8827973, 30.2751108)
    az_cv, _ = g.inv(lon, lat, np.full_like(lon, V[0]), np.full_like(lat, V[1]))   # car -> viewer azimuth
    eps = -np.radians(geo_el_deg) - D / R + k * D / (2 * R)
    out = {}
    for name, hdg, gr in (("fwd", heading, grade), ("rev", (heading + 180) % 360, -grade)):
        h = (az_cv - hdg + 180) % 360 - 180
        v = np.degrees(eps) - np.degrees(np.arctan(gr)) - aim
        out[name] = (h, v)
    return out

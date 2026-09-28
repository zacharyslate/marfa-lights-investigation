"""Target points for the line-of-sight model: roads, rail, towers and towns.

Roads come from the TxDOT Roadways layer (archived in data/inputs/txdot_roadways_bigbend.geojson), which carries
every public road (state, county, city, federal, park).  Each polyline is resampled along WGS84 geodesics at a
fixed spacing; every point keeps its route name, roadbed type and chainage along the feature."""
from __future__ import annotations

import json
import os

import numpy as np

from . import geodesy as g
from .dem import ROOT

INPUTS = os.path.join(ROOT, "data", "inputs")
VIEWER = (-103.8827973, 30.2751108)       # Marfa Lights Viewing Center platform (author's GPS/KML point)


def _resample(coords, spacing):
    """Resample a lon/lat polyline every `spacing` m along geodesics. Returns lon, lat, chainage (m)."""
    c = np.asarray(coords, float)
    lo, la, ch = [c[0, 0]], [c[0, 1]], [0.0]
    carry, total = 0.0, 0.0
    for (x0, y0), (x1, y1) in zip(c[:-1], c[1:]):
        az, d = g.inv(x0, y0, x1, y1)
        s = np.arange(spacing - carry, d, spacing)
        if s.size:
            px, py = g.fwd(np.full_like(s, x0), np.full_like(s, y0), np.full_like(s, az), s)
            lo += list(np.atleast_1d(px)); la += list(np.atleast_1d(py)); ch += list(total + s)
            carry = d - s[-1]
        else:
            carry += d
        total += d
    return np.array(lo), np.array(la), np.array(ch)


def roads(spacing=30.0, max_km=90.0, prefixes=None, names=None, roadbeds=("Single Roadbed", "Left Roadbed",
                                                                           "Right Roadbed", "Connector")):
    """All TxDOT road points within max_km of the viewer. Returns a dict of arrays."""
    fc = json.load(open(os.path.join(INPUTS, "txdot_roadways_bigbend.geojson")))
    out = {k: [] for k in ("lon", "lat", "chain", "route", "prefix", "roadbed", "fid", "begin_dfo")}
    for f in fc["features"]:
        p = f["properties"]
        if prefixes and p["RTE_PRFX"] not in prefixes:
            continue
        if names and p["RTE_NM"] not in names:
            continue
        if p["RDBD_TYPE"] not in roadbeds:
            continue
        geom = f["geometry"]
        parts = [geom["coordinates"]] if geom["type"] == "LineString" else geom["coordinates"]
        for part in parts:
            lo, la, ch = _resample(part, spacing)
            _, d = g.inv(np.full_like(lo, VIEWER[0]), np.full_like(la, VIEWER[1]), lo, la)
            m = d <= max_km * 1000
            n = int(m.sum())
            if not n:
                continue
            out["lon"].append(lo[m]); out["lat"].append(la[m]); out["chain"].append(ch[m])
            out["route"] += [p["RTE_NM"]] * n; out["prefix"] += [p["RTE_PRFX"]] * n
            out["roadbed"] += [p["RDBD_TYPE"]] * n; out["fid"] += [p["OBJECTID"]] * n
            out["begin_dfo"] += [p["BEGIN_DFO"]] * n
    for k in ("lon", "lat", "chain"):
        out[k] = np.concatenate(out[k]) if out[k] else np.array([])
    for k in ("route", "prefix", "roadbed", "fid", "begin_dfo"):
        out[k] = np.array(out[k])
    # TxDOT distance-from-origin in miles, useful as a mile-marker-like reference
    out["dfo_mi"] = out["begin_dfo"].astype(float) + out["chain"] / 1609.344
    return out


def us67(spacing=30.0, max_km=90.0):
    """US-67 main roadbed (TxDOT route US0067-KG) between Marfa and Presidio."""
    return roads(spacing, max_km, names={"US0067-KG"}, roadbeds=("Single Roadbed",))


def rail(spacing=60.0, max_km=90.0):
    """Rail lines from the USDOT BTS NTAD layer archived in data/inputs/web_layers.json."""
    w = json.load(open(os.path.join(INPUTS, "web_layers.json")))
    F = w["rail_fields"]
    out = {"lon": [], "lat": [], "owner": []}
    for row in w["rail"]:
        r = dict(zip(F, row))
        for part in r["lines"]:
            if len(part) < 2:
                continue
            lo, la, _ = _resample(part, spacing)
            _, d = g.inv(np.full_like(lo, VIEWER[0]), np.full_like(la, VIEWER[1]), lo, la)
            m = d <= max_km * 1000
            out["lon"].append(lo[m]); out["lat"].append(la[m]); out["owner"] += [r["owner"]] * int(m.sum())
    out["lon"], out["lat"] = np.concatenate(out["lon"]), np.concatenate(out["lat"])
    out["owner"] = np.array(out["owner"])
    return out


MARFA_JCT = (-104.020596, 30.309505)      # US-67 leaves US-90 at Highland Ave, Marfa (end of the author's trace)


def us67_south(spacing=30.0, max_km=90.0):
    """US-67 from the US-90 junction in Marfa south towards Shafter and Presidio."""
    u = us67(spacing, max_km)
    _, d = g.inv(np.full(u["lon"].size, MARFA_JCT[0]), np.full(u["lon"].size, MARFA_JCT[1]), u["lon"], u["lat"])
    dfo0 = u["dfo_mi"][np.argmin(d)]
    keep = u["dfo_mi"] >= dfo0
    out = {k: v[keep] for k, v in u.items()}
    out["km_from_marfa"] = (out["dfo_mi"] - dfo0) * 1.609344
    return out

"""Obstruction heights above the bare-earth DEM from the USGS lidar point cloud (EPT octree on AWS).

The 1 m DEM is bare earth, but light from a car on US-67 grazes the ground within a metre over long stretches,
so shrubs, fences and structures matter. We fetch from the Entwine Point Tile (EPT) copies of the project's work
units (s3://usgs-lidar-public/TX_WestTexas_B3_2018, ..._B7_2018; EPSG:3857 horizontal, NAVD88 vertical) only the
octree nodes that intersect 50 m cells where a US-67 sightline passes within 1.5 m of the bare earth, and
rasterise them on the 1 m UTM grid of the DEM:
    hmax   highest non-noise return above the bare-earth DEM in the cell (m)
    frac   fraction of the cell's returns that are > 0.3 m above the DEM
    n      number of returns
Noise classes 7 and 18 are dropped. Everything that is not ground/water/bridge is in class 1 in this project.

Obstruction surfaces (sampled with ObstructionLayer):
    dense  hmax where frac >= 0.25 and at least 2 returns are > 0.3 m (solid cover)   <- reference
    max    hmax wherever there is any return > 0.3 m (upper bound; includes wires, posts, birds)
Cells without point-cloud coverage return 0 (bare earth)."""
from __future__ import annotations

import glob
import io
import json
import os
import struct

import laspy
import numpy as np
from pyproj import Transformer

from . import dem

OUT = os.path.join(dem.DEM_DIR, "obstruction")
NOISE = (7, 18)
ABOVE = 0.3


def read_packs(paths):
    """Yield (name, bytes) from the pack files written by the browser fetcher."""
    for p in paths:
        with open(p, "rb") as f:
            data = f.read()
        i = 0
        while i < len(data):
            nl, dl = struct.unpack_from("<II", data, i)
            i += 8
            name = data[i:i + nl].decode()
            i += nl
            yield name, data[i:i + dl]
            i += dl


def build(pack_paths, out=OUT):
    os.makedirs(out, exist_ok=True)
    to_utm = Transformer.from_crs(3857, 26913, always_xy=True)
    lid = dem.Mosaic([r for r in dem.load("lidar").rasters if "1M" in r.name])
    to_ll = Transformer.from_crs(26913, 4269, always_xy=True)
    keys_all, hag_all, cls_all = [], [], []
    ground_res = []
    meta = {}
    for name, buf in read_packs(pack_paths):
        if name.endswith("ept.json"):
            meta[name.split("/")[0]] = json.loads(buf.decode())
            continue
        las = laspy.read(io.BytesIO(buf))
        cls = np.asarray(las.classification)
        keep = ~np.isin(cls, NOISE)
        x, y, z = np.asarray(las.x)[keep], np.asarray(las.y)[keep], np.asarray(las.z)[keep]
        cls = cls[keep]
        ux, uy = to_utm.transform(x, y)
        ix, iy = np.floor(ux).astype(np.int64), np.floor(uy).astype(np.int64)
        # bare-earth height at the cell centre (the DEM pixel), from the 1 m DEM
        lo, la = to_ll.transform(ix + 0.5, iy + 0.5)
        zb, _ = lid.sample(lo, la, strict=False)
        hag = z - zb
        ok = ~np.isnan(hag)
        keys_all.append((ix[ok] * 10_000_000 + iy[ok]))
        hag_all.append(hag[ok].astype("float32"))
        cls_all.append(cls[ok])
        g = ok & (cls == 2)
        if g.any():
            # ground returns against the DEM sampled exactly at the point (datum/offset check)
            lo2, la2 = to_ll.transform(ux[g], uy[g])
            zb2, _ = lid.sample(lo2, la2, strict=False)
            ground_res.append((z[g] - zb2)[::10])
    keys = np.concatenate(keys_all)
    hag = np.concatenate(hag_all)
    order = np.argsort(keys, kind="stable")
    keys, hag = keys[order], hag[order]
    uk, start, counts = np.unique(keys, return_index=True, return_counts=True)
    hmax = np.maximum.reduceat(hag, start)
    nab = np.add.reduceat((hag > ABOVE).astype(np.int32), start)
    gr = np.concatenate(ground_res) if ground_res else np.array([])
    gr = gr[~np.isnan(gr)]
    np.savez_compressed(os.path.join(out, "obstruction_cells.npz"), key=uk, hmax=hmax.astype("float32"),
                        n=counts.astype("int32"), n_above=nab.astype("int32"))
    info = dict(n_points=int(hag.size), n_cells=int(uk.size), ground_minus_dem=dict(
                    n=int(gr.size), median=float(np.median(gr)) if gr.size else None,
                    mad_sd=float(1.4826 * np.median(np.abs(gr - np.median(gr)))) if gr.size else None,
                    p05=float(np.percentile(gr, 5)) if gr.size else None,
                    p95=float(np.percentile(gr, 95)) if gr.size else None),
                source="s3://usgs-lidar-public/{" + ",".join(meta) + "} (EPT)", above_m=ABOVE,
                noise_classes=list(NOISE))
    json.dump(info, open(os.path.join(out, "obstruction_info.json"), "w"), indent=1)
    return info


class ObstructionLayer:
    """Sample obstruction height (m above bare earth) at NAD83 lon/lat; 0 where there is no point-cloud cell."""

    def __init__(self, mode="dense", path=os.path.join(OUT, "obstruction_cells.npz"), min_frac=0.25):
        z = np.load(path)
        self.key, hmax, n, nab = z["key"], z["hmax"], z["n"], z["n_above"]
        if mode == "dense":
            self.h = np.where((nab >= 2) & (nab / np.maximum(n, 1) >= min_frac), np.maximum(hmax, 0), 0.0)
        elif mode == "max":
            self.h = np.where(nab >= 1, np.maximum(hmax, 0), 0.0)
        else:
            raise ValueError(mode)
        self.to_utm = Transformer.from_crs(4269, 26913, always_xy=True)
        self.mode = mode

    def sample(self, lon, lat):
        x, y = self.to_utm.transform(np.asarray(lon, float), np.asarray(lat, float))
        k = np.floor(x).astype(np.int64) * 10_000_000 + np.floor(y).astype(np.int64)
        i = np.searchsorted(self.key, k)
        i = np.clip(i, 0, self.key.size - 1)
        hit = self.key[i] == k
        return np.where(hit, self.h[i], 0.0)


if __name__ == "__main__":
    import sys
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(dem.DEM_DIR, "ept", "marfa_ept_pack*.bin")))
    print(json.dumps(build(paths), indent=1))

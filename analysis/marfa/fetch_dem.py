"""Terrain and geoid sources for the line-of-sight model, and the archive manifest.

    python -m marfa.fetch_dem --download   # fetch every source file into data/dem/raw and data/geoid
    python -m marfa.fetch_dem --manifest   # hash the local files and write data/dem/MANIFEST.json
    python -m marfa.fetch_dem --verify     # re-hash the local files and compare with the manifest

The raster files themselves are not committed (about 9 GB); the manifest pins exactly which USGS/NOAA files
were used (URL, byte size, SHA-256, server Last-Modified), so anyone can re-download and verify them.
USGS 3DEP products are public domain; the GEOID18 grid is NOAA/NGS work, public domain, as converted by PROJ."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import urllib.request

from .dem import DEM_DIR, GEOID18_GRID, GEOID_GRID, RAW_DIR, ROOT

S3 = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation"
ONE = ["n30w104", "n30w105", "n30w106", "n31w104", "n31w105", "n31w106",
       # added for the 120 km skyline panorama (az 140-300 deg)
       "n29w103", "n29w104", "n29w105", "n30w103", "n31w103", "n32w104", "n32w105", "n32w106"]
THIRD = ["n30w104", "n30w105", "n31w104", "n31w105"]
LIDAR = [(54, 333), (54, 334), (55, 333), (55, 334), (56, 330), (56, 331), (56, 332), (56, 334), (56, 335),
         (57, 330), (57, 331), (57, 332), (57, 333), (57, 334), (57, 335), (57, 336), (58, 333), (58, 334),
         (58, 335), (58, 336), (59, 334), (59, 335), (59, 336), (60, 335), (60, 336), (61, 335), (61, 336)]
LIDAR_PROJECT = "TX_WestTexas_2018_D19"


def sources():
    out = []
    for t in ONE:
        out.append(dict(file=f"USGS_1_{t}.tif", dir=RAW_DIR, url=f"{S3}/1/TIFF/current/{t}/USGS_1_{t}.tif",
                        product="USGS 3DEP 1 arc-second DEM (current)", crs="EPSG:4269 + NAVD88"))
    for t in THIRD:
        out.append(dict(file=f"USGS_13_{t}.tif", dir=RAW_DIR, url=f"{S3}/13/TIFF/current/{t}/USGS_13_{t}.tif",
                        product="USGS 3DEP 1/3 arc-second DEM (current)", crs="EPSG:4269 + NAVD88"))
    for x, y in LIDAR:
        f = f"USGS_1M_13_x{x}y{y}_{LIDAR_PROJECT}.tif"
        out.append(dict(file=f, dir=RAW_DIR, url=f"{S3}/1m/Projects/{LIDAR_PROJECT}/TIFF/{f}",
                        product=f"USGS 3DEP 1 m DEM, lidar project {LIDAR_PROJECT} (acquired 2019-02-16 to 2019-05-14)",
                        crs="NAD83 UTM 13N + NAVD88"))
    out.append(dict(file="us_noaa_g2012bu0.tif", dir=os.path.dirname(GEOID_GRID),
                    url="https://cdn.proj.org/us_noaa_g2012bu0.tif",
                    product="NOAA NGS GEOID12B (CONUS), PROJ CDN GeoTIFF conversion (used by the 2019 lidar)",
                    crs="EPSG:6319 -> NAVD88"))
    out.append(dict(file="us_noaa_g2018u0.tif", dir=os.path.dirname(GEOID18_GRID),
                    url="https://cdn.proj.org/us_noaa_g2018u0.tif",
                    product="NOAA NGS GEOID18 (CONUS), PROJ CDN GeoTIFF conversion (sensitivity)", crs="EPSG:6319 -> NAVD88"))
    return out


def sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def head(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.headers.get("Last-Modified"), int(r.headers.get("Content-Length", 0))


def download():
    for s in sources():
        dst = os.path.join(s["dir"], s["file"])
        os.makedirs(s["dir"], exist_ok=True)
        if os.path.exists(dst):
            continue
        print("downloading", s["url"])
        urllib.request.urlretrieve(s["url"], dst + ".part")
        os.replace(dst + ".part", dst)


def write_manifest(last_modified=None, retrieved=None):
    last_modified = last_modified or {}
    old = {e["file"]: e for e in json.load(open(os.path.join(DEM_DIR, "MANIFEST.json")))["files"]} \
        if os.path.exists(os.path.join(DEM_DIR, "MANIFEST.json")) else {}
    files = []
    for s in sources():
        p = os.path.join(s["dir"], s["file"])
        if not os.path.exists(p):
            print("missing", p)
            continue
        e = dict(file=s["file"], path=os.path.relpath(p, ROOT), url=s["url"], product=s["product"], crs=s["crs"],
                 bytes=os.path.getsize(p), sha256=sha256(p),
                 last_modified=last_modified.get(s["file"], old.get(s["file"], {}).get("last_modified")),
                 retrieved=retrieved or old.get(s["file"], {}).get("retrieved") or dt.date.today().isoformat())
        files.append(e)
        print(e["file"], e["bytes"], e["sha256"][:12])
    man = dict(description="Terrain and geoid files used by the Marfa line-of-sight model (analysis/marfa).",
               note="Files are not committed; fetch with `python -m marfa.fetch_dem --download` and check with --verify.",
               files=files)
    json.dump(man, open(os.path.join(DEM_DIR, "MANIFEST.json"), "w"), indent=1)


def verify():
    man = json.load(open(os.path.join(DEM_DIR, "MANIFEST.json")))
    bad = 0
    for e in man["files"]:
        p = os.path.join(ROOT, e["path"])
        ok = os.path.exists(p) and os.path.getsize(p) == e["bytes"] and sha256(p) == e["sha256"]
        bad += not ok
        print("ok  " if ok else "BAD ", e["file"])
    print("all files verified" if not bad else f"{bad} files missing or changed")
    return bad == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.download:
        download()
    if a.manifest:
        write_manifest()
    if a.verify:
        verify()

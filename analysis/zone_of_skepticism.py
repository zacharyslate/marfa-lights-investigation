"""
Marfa Lights investigation: the known-source mask (formerly "Zone of Skepticism", ZoS).

The known-source mask is the set of apparent positions (true azimuth, elevation angle) seen
from the Viewing Area where a catalogued, ordinary light source could appear. A light reported
inside the mask has an ordinary candidate and needs that candidate ruled out (by timing,
motion, colour, a second observer) before it can be called unexplained. A light outside it
has no catalogued candidate. That makes it worth attention, not proof of anything.
File and variable names (zos) are kept for compatibility.

Construction
------------
For each source i with range d_i and apparent elevation alpha_i(k) at refraction k:

    alpha_i(k) = alpha_i(0.13) + d_i (k - 0.13) / (2R)          (constant-k, small angle)

A source counts if it is in view somewhere in K_RANGE (k_crit <= K_RANGE[1]); its locus is
the vertical segment [alpha_i(max(k_crit, k_lo)), alpha_i(k_hi)] at its azimuth. The zone
is the union of these segments, each dilated by the observer's measurement error:

    tier A  instrumented   (photo or theodolite, referenced to the skyline):  +-0.3 deg az, +-0.1 deg el
    tier B  hand compass   (plus a skyline-referenced height estimate):        +-3 deg az,   +-0.25 deg el

Sources: US-67 and the other state roads in view (headlamp height 0.7 m), the railroads
(4 m locomotive headlight), lit FCC-registered towers (top light), towns (direct light if
in view, otherwise a skyglow band from the skyline up 0.5 deg), and the tethered aerostat
(a full-height column, because its altitude varies).

NOT in the zone: ranch yard lights, vehicles on private ranch roads, unregistered
structures, aircraft, satellites, stars and planets. Everything above the skyline is sky,
where aircraft and astronomical sources dominate. Beyond K_RANGE (strong mirages, ducting)
the constant-k model does not apply, so the zone should not be read as exhaustive.

Run from the repository root after headlight_model.py:  python analysis/zone_of_skepticism.py
"""
import json
import math

import contourpy
import numpy as np

R = 6_371_000.0
K0 = 0.13
K_RANGE = (0.0, 1.0)
TIERS = {"A": (0.3, 0.1), "B": (3.0, 0.25)}          # (az deg, el deg) half-widths
AZ = (150.0, 300.0, 0.02)
EL = (-16.0, 14.0, 0.04)                               # mrad
D2M = 1000 * math.pi / 180                             # degrees -> mrad


def alpha_at(a013, d_km, k):
    return a013 + d_km * 1000 * (k - K0) / (2 * R) * 1000


def segments():
    """(az, el_lo, el_hi, kind, label) in degrees / mrad for every source in view within K_RANGE."""
    segs = []
    hl = json.load(open("data/derived/headlights.json"))
    for rd in hl["roads"]:
        seen = set()
        for p in rd["pts"]:
            az, km, a, kc, cls = p[0], p[1], p[2], p[3], p[4]
            if (az, km) in seen:
                continue
            seen.add((az, km))
            if cls in ("v", "m") or kc <= K_RANGE[1]:
                k1 = max(min(kc, K0) if cls in ("v", "m") else kc, K_RANGE[0])
                segs.append((az, alpha_at(a, km, k1), alpha_at(a, km, K_RANGE[1]), "road", rd["road"], km))
    pl = json.load(open("data/derived/panorama_los.json"))
    for o, lat, lon, az, km, a, kc in pl["rail"]:
        if kc <= K_RANGE[1]:
            segs.append((az, alpha_at(a, km, max(kc, K_RANGE[0])), alpha_at(a, km, K_RANGE[1]), "rail",
                         "Union Pacific" if o == "UP" else "Texas Pacifico", km))
    site = json.load(open("docs/data/site.json"))
    for t in site["towers"]:
        if t["light"] != "none" and t["kc"] is not None and t["kc"] <= K_RANGE[1] and t["a"] is not None:
            segs.append((t["az"], alpha_at(t["a"], t["d"], max(t["kc"], K_RANGE[0])), alpha_at(t["a"], t["d"], K_RANGE[1]),
                         "tower", f"{t['h']:.0f} m tower at {t['az']:.0f}°"))
    sky = np.array(site["sky"])
    sky_at = lambda az: float(np.interp(az, sky[:, 0], sky[:, 1]))
    for t in site["towns"]:
        if not (AZ[0] + 1 <= t["az"] <= AZ[1] - 1):
            continue
        # towns beyond the terrain model (no apparent elevation computed: Presidio, Ojinaga) count as skyglow only
        if "a" in t and t["kc"] is not None and t["kc"] <= K_RANGE[1]:
            for daz in np.linspace(-0.5, 0.5, 11) * math.degrees(1.5 / t["d"]):     # ~3 km wide town
                segs.append((t["az"] + daz, alpha_at(t["a"], t["d"], max(t["kc"], K_RANGE[0])),
                             alpha_at(t["a"], t["d"], K_RANGE[1]), "town", t["n"]))
        else:
            for daz in np.linspace(-1, 1, 21):
                s = sky_at(t["az"] + daz)
                segs.append((t["az"] + daz, s, s + 0.5 * D2M, "skyglow", t["n"]))
    for f in site["fields"]:
        if f["k"] == "balloon":
            segs.append((f["az"], EL[0], EL[1], "aerostat", "Aerostat (altitude varies)"))
    return segs


def densify(segs):
    """Roads and track are continuous: fill between neighbouring samples of the same line
    that are less than 1 km apart on the ground, so the zone has no gaps between samples."""
    def sep(p, q):
        da = math.radians(p[0] - q[0])
        return math.sqrt(p[5] ** 2 + q[5] ** 2 - 2 * p[5] * q[5] * math.cos(da))

    out = [segs[0]]
    for p, q in zip(segs, segs[1:]):
        if (p[3] == q[3] and p[3] in ("road", "rail") and p[4] == q[4] and p[5] is not None and q[5] is not None
                and sep(p, q) < 1.0):
            n = int(abs(p[0] - q[0]) / (AZ[2] * 2))
            for t in np.linspace(0, 1, n + 2)[1:-1]:
                out.append(tuple(p[j] + t * (q[j] - p[j]) for j in range(3)) + (p[3], p[4], None))
        out.append(q)
    return out


def rasterise(segs, daz, del_mrad):
    segs = densify(segs)
    az = np.arange(AZ[0], AZ[1] + 1e-9, AZ[2])
    el = np.arange(EL[0], EL[1] + 1e-9, EL[2])
    M = np.zeros((len(el), len(az)), bool)
    for a, lo, hi, *_ in segs:
        c0, c1 = np.searchsorted(az, a - daz), np.searchsorted(az, a + daz, "right")
        r0, r1 = np.searchsorted(el, min(lo, hi) - del_mrad), np.searchsorted(el, max(lo, hi) + del_mrad, "right")
        M[r0:r1, c0:c1] = True
    return az, el, M


def polygons(az, el, M, tol=0.05):
    """Filled outlines of the mask as [[az, el_mrad], ...] rings (outer and holes)."""
    gen = contourpy.contour_generator(az, el, M.astype(float), fill_type=contourpy.FillType.OuterOffset)
    polys, offs = gen.filled(0.5, 1.5)
    out = []
    for pts, off in zip(polys, offs):
        for i in range(len(off) - 1):
            ring = pts[off[i]:off[i + 1]]
            ring = simplify(ring, tol)
            out.append([[round(float(x), 3), round(float(y), 2)] for x, y in ring])
    return out


def simplify(ring, tol):
    """Drop collinear points on the axis-aligned staircase outline."""
    keep = [ring[0]]
    for i in range(1, len(ring) - 1):
        a, b, c = keep[-1], ring[i], ring[i + 1]
        if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) > 1e-9:
            keep.append(b)
    keep.append(ring[-1])
    return np.array(keep)


def main():
    segs = segments()
    out = {"meta": {"k_range": K_RANGE, "tiers_deg": TIERS, "units": "az deg true, el mrad",
                    "definition": __doc__.split("Construction")[0].strip()}, "tiers": {}, "sources": []}
    for tier, (daz, dele) in TIERS.items():
        az, el, M = rasterise(segs, daz, dele * D2M)
        out["tiers"][tier] = polygons(az, el, M)
        # fraction of the below-skyline field of view (fan only) covered by the zone
        site = json.load(open("docs/data/site.json"))
        sky = np.array(site["sky"])
        s = np.interp(az, sky[:, 0], sky[:, 1])
        fan = (az >= 157.276) & (az <= 277.276)
        below = (el[:, None] <= s[None, :]) & (el[:, None] >= -12)
        band = (el[:, None] <= s[None, :]) & (el[:, None] >= s[None, :] - 5)
        cov = (M & below)[:, fan].sum() / below[:, fan].sum()
        covb = (M & band)[:, fan].sum() / band[:, fan].sum()
        out["meta"][f"coverage_{tier}"] = round(float(cov), 3)
        out["meta"][f"coverage_{tier}_skyline5"] = round(float(covb), 3)
        print(f"tier {tier}: {len(out['tiers'][tier])} rings; inside the 157-277 deg fan it covers {cov:.1%} of the view "
              f"from -12 mrad up to the skyline, and {covb:.1%} of the 5 mrad band just below the skyline")
    kinds = {}
    for a, lo, hi, kind, label, *_ in segs:
        kinds.setdefault((kind, label), []).append((a, lo, hi))
    for (kind, label), v in sorted(kinds.items()):
        a = np.array(v)
        if a[:, 0].max() < AZ[0] or a[:, 0].min() > AZ[1]:
            continue
        out["sources"].append({"kind": kind, "label": label, "az": [round(a[:, 0].min(), 2), round(a[:, 0].max(), 2)],
                               "el": [round(a[:, 1].min(), 2), round(a[:, 2].max(), 2)], "n": len(v)})
        print(f"  {kind:9s} {label:32s} az {a[:,0].min():6.1f}–{a[:,0].max():6.1f}  el {a[:,1].min():6.1f}…{a[:,2].max():6.1f} mrad  n={len(v)}")
    json.dump(out, open("data/derived/zos.json", "w"), separators=(",", ":"))
    web = {"k_range": K_RANGE, "tiers_deg": TIERS, "tiers": out["tiers"], "sources": out["sources"],
           "coverage": {t: out["meta"][f"coverage_{t}"] for t in TIERS}}
    json.dump(web, open("docs/data/zos.json", "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()

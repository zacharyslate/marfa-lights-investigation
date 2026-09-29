"""Exact-geometry line of sight with refraction.

Geometry. Observer O (eye) and target T (lamp) and every terrain sample P_i along the WGS84 geodesic O->T are
placed in ECEF using ellipsoidal heights h = H + N. Let u be the unit chord O->T and w the unit vector
perpendicular to u in the plane spanned by u and the mean ellipsoid normal ("up" of the chord). For each P_i:
    s_i = (P_i - O).u      distance along the chord
    y_i = (P_i - O).w      height of the terrain sample above the chord (signed, m)

Refraction. With a constant refraction coefficient k the ray is a circular arc of radius R/k, concave toward the
Earth, so between O and T it lies above the chord by the sag
    sag_i(k) = k s_i (D - s_i) / (2 R)      (D = |OT|, R = normal-section radius of the WGS84 ellipsoid)
(parabolic approximation of the arc; relative error < (D/R)^2 ~ 1e-5 here).

Visibility. T is visible iff y_i <= sag_i(k) for every i, i.e. iff k >= k_crit with
    k_crit = max_i  2 R y_i / ( s_i (D - s_i) ).
Clearance at k:  c(k) = min_i [ sag_i(k) - y_i ]  (m, measured perpendicular to the chord).

Apparent elevation of T at the eye: geometric elevation of the chord above the observer's horizon (plane normal
to the ellipsoid normal at O) plus the refraction angle k D / (2 R).
"""
from __future__ import annotations

import numpy as np

from . import geodesy as g


class Observer:
    def __init__(self, lon, lat, ground_H, eye=1.6, geoid=None):
        self.lon, self.lat, self.ground_H, self.eye = lon, lat, ground_H, eye
        self.geoid = geoid or g.Geoid()
        self.N = float(self.geoid(np.array([lon]), np.array([lat]))[0])
        self.h = ground_H + eye + self.N
        self.X = g.ecef(lon, lat, self.h)
        self.up = g.normal(lon, lat)


def sightline(obs: Observer, mosaic, lon_t, lat_t, lamp=0.7, step=5.0, skip_obs=5.0, skip_tgt=5.0,
              target_H=None, return_profile=False):
    """Line of sight from obs to a lamp `lamp` m above the ground at (lon_t, lat_t).

    Returns dict with az (deg), D (m, chord), dist (m, geodesic), k_crit, the limiting sample (distance from the
    observer, from the target), clearance at k=0.13, geometric and apparent elevation (deg) at k=0.13, and the
    source raster of the target height."""
    az, dist = g.inv(obs.lon, obs.lat, lon_t, lat_t)
    lo, la, s_geo = g.path(obs.lon, obs.lat, lon_t, lat_t, step)
    keep = (s_geo >= skip_obs) & (s_geo <= dist - skip_tgt)
    lo, la, s_geo = lo[keep], la[keep], s_geo[keep]
    Hp, _ = mosaic.sample(lo, la)
    if target_H is None:
        tH, tsrc = mosaic.sample(np.array([lon_t]), np.array([lat_t]))
        target_H, tsrc = float(tH[0]), int(tsrc[0])
    else:
        tsrc = -1
    Np = obs.geoid(lo, la)
    Nt = float(obs.geoid(np.array([lon_t]), np.array([lat_t]))[0])
    P = g.ecef(lo, la, Hp + Np)
    T = g.ecef(lon_t, lat_t, target_H + lamp + Nt)
    O = obs.X
    OT = T - O
    D = float(np.linalg.norm(OT))
    u = OT / D
    up = obs.up + g.normal(lon_t, lat_t)
    w = up - np.dot(up, u) * u
    w /= np.linalg.norm(w)
    rel = P - O
    s = rel @ u
    y = rel @ w
    R = float(g.normal_section_radius(0.5 * (obs.lat + lat_t), az))
    denom = s * (D - s)
    kc_i = 2 * R * y / denom
    i = int(np.argmax(kc_i))
    k_crit = float(kc_i[i])
    sag013 = 0.13 * denom / (2 * R)
    clr = sag013 - y
    j = int(np.argmin(clr))
    # geometric elevation of the chord at the eye
    geo_el = float(np.degrees(np.arcsin(np.dot(u, obs.up))))
    out = dict(az=float(az), dist=float(dist), D=D, R=R, target_H=target_H, target_src=tsrc,
               k_crit=k_crit, lim_from_obs=float(s[i]), lim_from_tgt=float(D - s[i]),
               clr013=float(clr[j]), clr_at_from_tgt=float(D - s[j]),
               geo_el=geo_el, app_el013=geo_el + float(np.degrees(0.13 * D / (2 * R))))
    if return_profile:
        out.update(s=s, y=y, kc_i=kc_i, H=Hp, denom=denom)
    return out


def sample_distances(dist, skip_obs, skip_tgt, fine=2.0, coarse=5.0, fine_zone=3000.0):
    """Distances along the geodesic at which terrain is sampled: `fine` spacing within `fine_zone` of either end
    (where the 1 m lidar resolves road prisms, ditches and the platform), `coarse` spacing in between."""
    end = dist - skip_tgt
    if end <= skip_obs:
        return np.array([0.5 * dist])
    near_o = np.arange(skip_obs, min(fine_zone, end), fine)
    near_t = end - np.arange(0.0, min(fine_zone, end - skip_obs), fine)          # anchored on the target end
    mid = np.arange(fine_zone, dist - fine_zone, coarse) if dist > 2 * fine_zone else np.array([])
    s = np.unique(np.concatenate([near_o, mid, near_t]))
    return s[(s >= skip_obs) & (s <= end)]


def correlated_errors(s, sigma, corr, n, rng, grid=None):
    """n realisations of a zero-mean Gaussian error field along the samples s (m), with a point-wise standard
    deviation sigma[i] and an exponential correlation length corr[i].

    For each distinct correlation length L a unit-variance first-order autoregressive process (phi = exp(-g/L))
    is generated on a uniform grid of spacing g = min(L/4, 5 m) with scipy.signal.lfilter and linearly
    interpolated to s; each sample takes the field of its own class, scaled by its sigma. (Errors of different
    DEM sources are independent of each other, as they should be.)  Linear interpolation of an AR(1) field
    lowers its variance midway between grid nodes to (1+phi)/2, i.e. 0.89 at g = L/4 (standard deviation -6 %);
    the field is rescaled to unit variance at every sample to remove this."""
    from scipy.signal import lfilter
    s = np.asarray(s, float)
    sigma, corr = np.asarray(sigma, float), np.asarray(corr, float)
    e = np.zeros((n, s.size))
    for L in np.unique(corr):
        m = corr == L
        if not np.any(sigma[m] > 0):
            continue
        g = min(L / 4.0, 5.0)
        x = np.arange(s[m].min() - g, s[m].max() + 2 * g, g)
        phi = np.exp(-g / L)
        z = rng.standard_normal((n, x.size)) * np.sqrt(1 - phi ** 2)
        z[:, 0] = rng.standard_normal(n)
        f = lfilter([1.0], [1.0, -phi], z, axis=1)
        pos = (s[m] - x[0]) / g
        i0 = np.floor(pos).astype(int)
        t = pos - i0
        v = f[:, i0] * (1 - t) + f[:, i0 + 1] * t
        # variance of the interpolated field: (1-t)^2 + t^2 + 2 t (1-t) phi
        v /= np.sqrt((1 - t) ** 2 + t ** 2 + 2 * t * (1 - t) * phi)
        e[:, m] = v * sigma[m]
    return e


def sightline_multi(obs: Observer, mosaic, lon_t, lat_t, lamps=(0.7,), ks=(0.13,), skip_obs=5.0, skip_tgt=3.0,
                    fine=2.0, coarse=5.0, fine_zone=3000.0, target_H=None, return_profile=False,
                    clutter=(), clutter_skip=10.0, mc=None, obstruction=None):
    """Line of sight from `obs` to lamps at several heights above the ground at (lon_t, lat_t).

    For each lamp height L (array index j) returns
      k_crit[j]            refraction coefficient above which the lamp is visible
      lim_s[j]             distance from the observer of the limiting terrain sample (m)
      clr[j, m]            clearance min_i(sag_i(k_m) - y_i) for each k in ks (m, perpendicular to the chord)
      dL[j, m]             lamp-height margin: the smallest change in lamp height that flips visibility at k_m
                           (negative = lamp could be that much lower and still be seen; positive = it must be
                           raised by that much to be seen)
      dE[j, m]             the same margin expressed as a change in observer eye height
      geo_el[j], app_el[j, m]  chord elevation and apparent elevation (deg)
      kc_clutter[j, c]     k_crit when every terrain sample more than `clutter_skip` m from both ends is raised
                           by clutter[c] m (a bound for shrubs, fences and signs absent from a bare-earth DEM)
      obstruction          optional layer with .sample(lon, lat) -> height above bare earth (m) of shrubs,
                           structures etc. (marfa.obstruction.ObstructionLayer); added to every terrain sample
                           more than `clutter_skip` m from both ends
      p_vis[j, m]          (if mc) fraction of Monte Carlo realisations in which the lamp is visible at k_m;
                           mc = dict(n, sigma=[per DEM source], corr=[per source], eye_sd, seed): correlated
                           terrain errors plus a Gaussian eye-height error
    plus az, dist (geodesic, m), D (chord, m), R, target_H, target_src and the DEM source index of the
    limiting sample for the first lamp and first k."""
    az, dist = g.inv(obs.lon, obs.lat, lon_t, lat_t)
    s_geo = sample_distances(dist, skip_obs, skip_tgt, fine, coarse, fine_zone)
    lo, la, _ = g.GEOD.fwd(np.full_like(s_geo, obs.lon), np.full_like(s_geo, obs.lat),
                           np.full_like(s_geo, az), s_geo)
    lo, la = np.asarray(lo), np.asarray(la)
    Hp, src = mosaic.sample(lo, la)
    if target_H is None:
        tH, tsrc = mosaic.sample(np.array([lon_t]), np.array([lat_t]))
        target_H, tsrc = float(tH[0]), int(tsrc[0])
    else:
        tsrc = -1
    P = g.ecef(lo, la, Hp + obs.geoid(lo, la))
    Nt = float(obs.geoid(np.array([lon_t]), np.array([lat_t]))[0])
    R = float(g.normal_section_radius(0.5 * (obs.lat + lat_t), az))
    O = obs.X
    upT = g.normal(lon_t, lat_t)
    ks = np.asarray(ks, float)
    nL, nK = len(lamps), len(ks)
    out = dict(az=float(az), dist=float(dist), R=R, target_H=target_H, target_src=tsrc,
               k_crit=np.empty(nL), lim_s=np.empty(nL), lim_src=np.empty(nL, int),
               clr=np.empty((nL, nK)), dL=np.empty((nL, nK)), dE=np.empty((nL, nK)),
               geo_el=np.empty(nL), app_el=np.empty((nL, nK)), D=np.empty(nL),
               kc_clutter=np.empty((nL, len(clutter))), p_vis=np.full((nL, nK), np.nan))
    far = (s_geo > clutter_skip) & (s_geo < dist - clutter_skip)
    if obstruction is not None:
        ob = obstruction.sample(lo, la) * far
        if ob.any():
            P = g.ecef(lo, la, Hp + ob + obs.geoid(lo, la))
        out["obstruction_max"] = float(ob.max())
    rel = P - O
    if mc:
        rng = np.random.default_rng(mc.get("seed", 0) + int(abs(lon_t * 1e6 + lat_t * 1e7)) % 1_000_000)
        sig = np.asarray(mc["sigma"], float)[src]
        cor = np.asarray(mc["corr"], float)[src]
        eye_sd = mc.get("eye_sd", 0.0)
        dEye = rng.standard_normal(mc["n"]) * eye_sd
        excesses = {}
    for j, L in enumerate(lamps):
        T = g.ecef(lon_t, lat_t, target_H + L + Nt)
        OT = T - O
        D = float(np.linalg.norm(OT))
        u = OT / D
        up = obs.up + upT
        w = up - np.dot(up, u) * u
        w /= np.linalg.norm(w)
        s = rel @ u
        y = rel @ w
        denom = s * (D - s)
        kc_i = 2 * R * y / denom
        i = int(np.argmax(kc_i))
        out["k_crit"][j], out["lim_s"][j], out["lim_src"][j] = kc_i[i], s[i], src[i]
        geo = float(np.degrees(np.arcsin(np.dot(u, obs.up))))
        out["geo_el"][j], out["D"][j] = geo, D
        # the chord height at s changes by dL*s/D when the lamp moves by dL (and by dE*(D-s)/D for the eye);
        # visibility flips when the worst sample just touches the ray
        cos_t = float(np.dot(upT, w))            # lamp moves along local vertical; project onto w
        cos_o = float(np.dot(obs.up, w))
        for m, k in enumerate(ks):
            excess = y - k * denom / (2 * R)       # >0: terrain above the ray
            out["clr"][j, m] = float(-excess.max())
            out["dL"][j, m] = float(np.max(excess * D / s) / cos_t)
            out["dE"][j, m] = float(np.max(excess * D / (D - s)) / cos_o)
            out["app_el"][j, m] = geo + float(np.degrees(k * D / (2 * R)))
            if mc:
                excesses[(j, m)] = (excess, (D - s) / D)
        for c, v in enumerate(clutter):
            yc = y + np.where(far, v, 0.0)
            out["kc_clutter"][j, c] = float(np.max(2 * R * yc / denom))
        if return_profile and j == 0:
            out.update(s=s, y=y, H=Hp, src=src, lon=lo, lat=la, denom=denom)
    if mc:
        # linearised Monte Carlo: a terrain error e raises y by e (w ~ vertical); an eye-height error dE lowers
        # the chord by dE (D - s)/D. Only samples that can reach the ray within 6 standard deviations matter.
        reach = 6 * sig
        cand = np.zeros(s_geo.size, bool)
        todo = {}
        for (j, m), (ex, fo) in excesses.items():
            lo_ = ex - reach - 6 * eye_sd * fo
            if lo_.max() > 0:                 # terrain above the ray by > 6 sigma somewhere: hidden in every draw
                out["p_vis"][j, m] = 0.0
                continue
            c = ex + reach + 6 * eye_sd * fo > 0
            if not c.any():                   # ray above every sample by > 6 sigma: visible in every draw
                out["p_vis"][j, m] = 1.0
                continue
            todo[(j, m)] = c
            cand |= c
        if todo:
            idx = np.where(cand)[0]
            pos = np.full(s_geo.size, -1)
            pos[idx] = np.arange(idx.size)
            E = correlated_errors(s_geo[idx], sig[idx], cor[idx], mc["n"], rng)
            for (j, m), c in todo.items():
                ex, fo = excesses[(j, m)]
                cols = pos[c]
                tot = ex[c][None, :] + E[:, cols] - dEye[:, None] * fo[c][None, :]
                out["p_vis"][j, m] = float(np.mean(tot.max(axis=1) <= 0))
    return out


def apparent_elevation(geo_el_deg, D, R, k):
    """Apparent elevation (deg) of a point whose chord elevation is geo_el_deg, for refraction k."""
    return geo_el_deg + np.degrees(k * D / (2 * R))


def skyline(obs: Observer, mosaic, az, dmax=160_000.0, step=30.0, k=0.13, dmin=60.0, strict=False):
    """Apparent elevation (deg) of the skyline at azimuth az, the distance of the skyline point, and the
    maximum apparent elevation of terrain within 10, 25 and 45 km (ridge layers)."""
    s = np.arange(dmin, dmax, step)
    lo, la, _ = g.GEOD.fwd(np.full_like(s, obs.lon), np.full_like(s, obs.lat), np.full_like(s, az), s)
    H, _ = mosaic.sample(np.asarray(lo), np.asarray(la), strict=strict)
    ok = ~np.isnan(H)
    s, lo, la, H = s[ok], np.asarray(lo)[ok], np.asarray(la)[ok], H[ok]
    P = g.ecef(lo, la, H + obs.geoid(lo, la))
    rel = P - obs.X
    dist = np.linalg.norm(rel, axis=1)
    R = float(g.normal_section_radius(obs.lat, az))
    el = np.degrees(np.arcsin((rel @ obs.up) / dist)) + np.degrees(k * dist / (2 * R))
    i = int(np.argmax(el))
    layers = {}
    for lim in (10_000, 25_000, 45_000):
        m = s <= lim
        layers[lim] = float(el[m].max()) if m.any() else np.nan
    return dict(az=float(az), el=float(el[i]), dist=float(s[i]), layers=layers)

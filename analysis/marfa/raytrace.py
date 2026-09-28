"""Height-dependent refraction: ray tracing through a temperature profile that follows the terrain.

Frame. We work in the chord frame of los.sightline_multi: s = distance along the straight chord from the eye O
to the lamp T (length D), y = height perpendicular to the chord in the vertical plane (positive away from the
Earth). Terrain samples (s_i, y_i) already contain the Earth's curvature exactly.

Ray equation. A light ray in a horizontally stratified atmosphere with refractive index n(z) has curvature
    kappa = -(1/n) (dn/dz) cos(e)  ~  -dn/dz            (elevation angles here are < 1 deg, cos e = 1 - 1e-4)
toward the Earth. Writing kappa = k/R defines the local refraction coefficient k. With n - 1 = c P / T
(c = 79.0e-6 K/hPa at visible wavelengths) and hydrostatic pressure, one gets the standard relation
(Hirt et al. 2010, J. Geophys. Res. 115, D21102, eq. 2; doi:10.1029/2010JD014067):
    k = 503 * P / T^2 * (0.0343 + dT/dz)          (P in hPa, T in K, dT/dz in K/m)
Hirt et al. measured k from -4 to +16 at 1.8 m above grassland, with gradients up to 1-2 K/m shortly after
sunset, so near-ground rays at night are not described by a single k in 0..1.
In the chord frame the ray obeys (small-angle, paraxial; error O(theta^2) ~ 1e-4 relative)
    y''(s) = -k(s, y) / R,        y(0) = 0 (eye),   y'(0) = theta  (launch angle above the chord).
For constant k this gives y = theta s - k s^2/(2R); the ray through T (y(D) = 0) has theta = k D/(2R) and
y = k s (D - s)/(2R), which is exactly the sag used by the constant-k model (tested).

Atmosphere. k depends on height above the local ground a = y - y_ground(s) through a temperature profile.
Profiles (each returns dT/dz as a function of a, in K/m):
  lapse(g)                 constant gradient g (neutral: g = -0.0098; standard k = 0.13 at 850 hPa, 283 K)
  sbl(dT, h, g_top)        nocturnal stable boundary layer, T(a) = T0 + dT (1 - exp(-a/h)) + g_top a;
                           dT/dz = (dT/h) exp(-a/h) + g_top   (e.g. Stull 1988, ch. 12, exponential SBL form)
  layered(zs, gs)          piecewise-constant gradients between heights zs (for measured profiles)

Images. We launch a fan of rays with angles theta over [theta_min, theta_max], integrate each to s = D, drop
rays that go below the terrain anywhere on the way (outside the end exclusions), and find the roots of
y(D; theta) = 0 by linear interpolation between neighbouring rays. Each root is an image of the lamp with
apparent elevation geo_el + theta. More than one root = a mirage (superior or inferior); none = hidden.
"""
from __future__ import annotations

import numpy as np

C_OPT = 79.0e-6          # optical refractivity constant (K/hPa), visible light
G_RD = 9.80665 / 287.05  # g / R_dry = 0.03416 K/m (autoconvective lapse rate)


def k_from_gradient(dTdz, P=850.0, T=283.0):
    """Local refraction coefficient for temperature gradient dT/dz (K/m) at pressure P (hPa), temperature T (K)."""
    R = 6371000.0
    return R * C_OPT * P / T ** 2 * (G_RD + np.asarray(dTdz, float))


def lapse(g=-0.0098):
    return lambda a: np.full(np.shape(a), g, float)


def sbl(dT=6.0, h=30.0, g_top=-0.0065):
    """Exponential stable boundary layer: inversion strength dT (K) with e-folding depth h (m)."""
    return lambda a: (dT / h) * np.exp(-np.clip(a, 0, None) / h) + g_top


def layered(zs, gs):
    zs, gs = np.asarray(zs, float), np.asarray(gs, float)
    return lambda a: gs[np.clip(np.searchsorted(zs, a, side="right") - 1, 0, len(gs) - 1)]


def trace(s, y_ground, D, R, grad, P=850.0, T=283.0, thetas=None, ds=5.0, n_theta=4001,
          skip_obs=5.0, skip_tgt=3.0, eye_agl=1.6):
    """Fan of rays from the eye through the atmosphere `grad` (dT/dz as a function of height above ground).

    s, y_ground: terrain profile in the chord frame (from los.sightline_multi(return_profile=True)).
    Returns dict: thetas (rad), yD (height of each ray at s = D, m), blocked (bool), images (list of launch
    angles, rad, of rays that reach the lamp), and the constant-k equivalent of each image, 2*theta*R/D."""
    order = np.argsort(s)
    s, y_ground = np.asarray(s)[order], np.asarray(y_ground)[order]
    if thetas is None:
        span = 3.0 * D / (2 * R) + 4e-3
        thetas = np.linspace(-span, span, n_theta)
    grid = np.arange(0.0, D + ds / 2, ds)
    grid[-1] = D
    # ground under the ray; inside the end exclusions the nearest sample is used (for the profile only)
    yg = np.interp(grid, s, y_ground)
    yg[0] = -eye_agl
    check = (grid >= skip_obs) & (grid <= D - skip_tgt)
    th = np.asarray(thetas, float)
    y = np.zeros_like(th)
    v = th.copy()
    blocked = np.zeros(th.shape, bool)
    kfac = C_OPT * P / T ** 2                  # k / R = kfac * (g/R_d + dT/dz)
    agl = lambda yy, g_: np.maximum(yy - g_, 0.05)
    for i in range(1, grid.size):
        h = grid[i] - grid[i - 1]
        acc0 = -kfac * (G_RD + grad(agl(y, yg[i - 1])))
        y_mid = y + v * h / 2 + acc0 * h * h / 8
        acc_mid = -kfac * (G_RD + grad(agl(y_mid, 0.5 * (yg[i - 1] + yg[i]))))
        y = y + v * h + acc_mid * h * h / 2         # midpoint rule, second order in h
        v = v + acc_mid * h
        if check[i]:
            blocked |= y < yg[i]
    yD = y
    images = []
    ok = ~blocked
    for j in range(th.size - 1):
        if ok[j] and ok[j + 1] and (yD[j] == 0 or np.sign(yD[j]) != np.sign(yD[j + 1])):
            f = yD[j] / (yD[j] - yD[j + 1])
            images.append(th[j] + f * (th[j + 1] - th[j]))
    images = np.array(images)
    return dict(thetas=th, yD=yD, blocked=blocked, images=images, k_equiv=2 * images * R / D)

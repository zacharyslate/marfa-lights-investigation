"""Independent checks of every equation used in the manuscript (publication/manuscript/marfa_ajp.tex) and its
supplementary material. Each test derives or simulates the relation from first principles, without using the
production code, and then checks that the production code implements the same relation.

Numbering follows the manuscript: Eq. (1) curvature drop, (2) sag, (3) k_crit, (4) Hirt relation, (5) ray equation,
(6) view angles, (7) illuminance and transmission, (8) magnitude, (9) Crumey threshold, (10) occupancy."""
import math

import numpy as np
import pytest

from marfa import geodesy as g, photometry as P, raytrace as RT

R = 6_371_000.0


# ---------------------------------------------------------------- Eq. (1): curvature drop and horizon
def test_eq1_drop_exact_sphere():
    """Exact drop of a sea-level point below the observer's horizontal plane, R(sec(d/R) - 1), and the effect of a
    ray of curvature k/R, against (1-k) d^2 / 2R."""
    for d in (5e3, 30e3, 60e3):
        th = d / R
        drop_exact = R * (1 / math.cos(th) - 1)                  # geometric, along the vertical at the point
        ray_lift = k_lift = 0.13 * d ** 2 / (2 * R)               # refracted ray lies above the tangent by k d^2/2R
        assert abs(drop_exact - d ** 2 / (2 * R)) / (d ** 2 / (2 * R)) < 2e-4
        assert abs((drop_exact - k_lift) - (1 - 0.13) * d ** 2 / (2 * R)) < 0.02 * (d / 30e3) ** 4 + 1e-6
    assert abs((1 - 0.13) * 30e3 ** 2 / (2 * R) - 61.45) < 0.01                   # value quoted in the text
    assert abs(math.sqrt(2 * R * 1.6 / (1 - 0.13)) - 4840) < 5                    # horizon for a 1.6 m eye
    assert abs(0.13 * 30e3 ** 2 / (8 * R) - 2.30) < 0.005                         # midpoint sag at 30 km


# ---------------------------------------------------------------- Eq. (2) and App. A: the refracted arc
def test_eq2_sag_is_the_circular_arc():
    """The exact circle of radius R/k through O and T lies above the chord by k s (D-s)/2R to O((D/R)^2)."""
    k, D = 0.5, 40e3
    rho = R / k
    s = np.linspace(0, D, 401)
    x = s - D / 2
    h0 = math.sqrt(rho ** 2 - (D / 2) ** 2)                      # centre below the chord
    y_exact = np.sqrt(rho ** 2 - x ** 2) - h0
    y_par = k * s * (D - s) / (2 * R)
    assert np.max(np.abs(y_exact - y_par)) / np.max(y_par) < (D / R) ** 2
    # launch angle theta = kD/2R and the apparent-elevation shift D dk / 2R
    assert abs(math.atan(D / 2 / h0) - k * D / (2 * R)) < 1e-9


# ---------------------------------------------------------------- Eq. (3): k_crit is the visibility threshold
def test_eq3_kcrit_threshold_bruteforce():
    rng = np.random.default_rng(1)
    D = 30e3
    s = np.linspace(50, D - 50, 600)
    for _ in range(50):
        y = rng.normal(-5, 3, s.size)
        kc = np.max(2 * R * y / (s * (D - s)))
        for k in (kc - 1e-6, kc + 1e-6):
            visible = np.all(y <= k * s * (D - s) / (2 * R))
            assert visible == (k >= kc)


# ---------------------------------------------------------------- Eq. (4): Hirt relation from first principles
def test_eq4_hirt_relation_derivation():
    c, P0, T0 = 79.0e-6, 850.0, 283.0                             # n - 1 = c P / T (P in hPa)
    g0, Rd = 9.80665, 287.05

    def n_of_z(z, dTdz):
        T = T0 + dTdz * z
        # hydrostatic pressure for a linear temperature profile
        if abs(dTdz) < 1e-12:
            Pz = P0 * np.exp(-g0 * z / (Rd * T0))
        else:
            Pz = P0 * (T / T0) ** (-g0 / (Rd * dTdz))
        return 1 + c * Pz / T

    for dTdz in (-0.0098, 0.0, 0.05, 0.5, 1.0):
        hstep = 1e-3
        dndz = (n_of_z(hstep, dTdz) - n_of_z(-hstep, dTdz)) / (2 * hstep)
        k_num = -R * dndz / n_of_z(0, dTdz)
        k_hirt = 503 * P0 / T0 ** 2 * (0.0343 + dTdz)
        assert abs(k_num - k_hirt) < 0.004 * max(1, abs(k_hirt)), (dTdz, k_num, k_hirt)
        assert abs(RT.k_from_gradient(dTdz) - k_num) < 1e-3 * max(1, abs(k_num))
    assert abs(R * c - 503.3) < 0.1
    assert abs(g0 / Rd - 0.03416) < 1e-5                           # Hirt et al. round this to 0.0343
    assert abs(503 * 850 / 283 ** 2 * (0.0343 - 0.0098) - 0.131) < 0.001
    assert abs(503 * 850 / 283 ** 2 * 0.0343 - 0.183) < 0.001


# ---------------------------------------------------------------- Eq. (5) and the k_max bound
def test_eq5_comparison_bound():
    """If k(a) <= k_max everywhere, every ray from O that reaches T lies below the constant-k_max arc."""
    rng = np.random.default_rng(4)
    D, n = 25e3, 2501
    s = np.linspace(0, D, n)
    ds = s[1] - s[0]
    kmax = 2.0
    for _ in range(20):
        kk = rng.uniform(-1, kmax, n)                              # arbitrary k along the path, below k_max
        # ray with y(0)=0 and y(D)=0 for this k(s): y = -int int k/R, fixed by the end condition
        yp = np.r_[0, np.cumsum(-(kk[1:] + kk[:-1]) / 2 * ds / R)]      # trapezoid rule, y'(0) = 0
        y = np.r_[0, np.cumsum((yp[1:] + yp[:-1]) / 2 * ds)]
        y -= s / D * y[-1]                                          # linear term = launch angle that reaches T
        arc = kmax * s * (D - s) / (2 * R)
        assert np.all(y <= arc + 1e-6)


# ---------------------------------------------------------------- Eq. (6): vertical angle at the lamp
def _ecef_sphere(lat, lon, h):
    la, lo = np.radians(lat), np.radians(lon)
    r = R + h
    return np.array([r * np.cos(la) * np.cos(lo), r * np.cos(la) * np.sin(lo), r * np.sin(la)])


def test_eq6_elevation_at_lamp_matches_3d_geometry():
    rng = np.random.default_rng(7)
    for _ in range(50):
        latO, lonO, hO = 30.0, -104.0, 1500.0 + rng.uniform(-50, 50)
        d = rng.uniform(5e3, 50e3)
        az = rng.uniform(0, 360)
        dlat = d / R * math.cos(math.radians(az))
        dlon = d / R * math.sin(math.radians(az)) / math.cos(math.radians(latO))
        latT, lonT, hT = latO + math.degrees(dlat), lonO + math.degrees(dlon), 1400.0 + rng.uniform(-100, 100)
        O, T = _ecef_sphere(latO, lonO, hO), _ecef_sphere(latT, lonT, hT)
        upO, upT = O / np.linalg.norm(O), T / np.linalg.norm(T)
        u = (T - O) / np.linalg.norm(T - O)
        D = np.linalg.norm(T - O)
        eO = math.asin(np.dot(u, upO))                              # chord elevation at the eye
        eT = math.asin(np.dot(-u, upT))                             # chord elevation (toward the eye) at the lamp
        gamma = math.acos(np.clip(np.dot(upO, upT), -1, 1))         # angle between the verticals
        assert abs(eT - (-eO - gamma)) < 1e-9
        assert abs(gamma - D / R) < 5e-6                            # D/R stands in for the central angle (< 1")
        k = 0.13
        eps_formula = -eO - D / R + k * D / (2 * R)
        assert abs(eps_formula - (eT + k * D / (2 * R))) < 5e-6       # < 1 arcsecond
        # production code
        h, v = P.view_angles(np.array([lonT]), np.array([latT]), np.array([0.0]), np.array([0.0]),
                             np.array([math.degrees(eO)]), np.array([D]), np.array(R), k=k)["fwd"]
        assert abs(math.radians(v[0]) - eps_formula) < 1e-12


def test_eq6_pitch_sign():
    """Driving uphill tilts the lamp axis up, so the viewer is lower in the beam: v decreases by atan(grade)."""
    base = P.view_angles(np.array([-104.1]), np.array([30.1]), np.array([10.0]), np.array([0.0]),
                         np.array([-0.2]), np.array([30e3]), np.array(R))["fwd"][1][0]
    up = P.view_angles(np.array([-104.1]), np.array([30.1]), np.array([10.0]), np.array([0.03]),
                       np.array([-0.2]), np.array([30e3]), np.array(R))["fwd"][1][0]
    assert abs((base - up) - math.degrees(math.atan(0.03))) < 1e-9


# ---------------------------------------------------------------- Eq. (7): transmission and visual range
def test_eq7_transmission_and_visual_range():
    V = 111e3
    assert abs(math.exp(-V * math.log(20) / V) - 0.05) < 1e-15                    # MOR definition
    # standard visual range: contrast 2 %  ->  3.912 / b ; MOR: 5 % transmission -> ln 20 / b
    assert abs(math.log(50) - 3.912) < 1e-3 and abs(math.log(20) - 2.996) < 1e-3
    for mi, km in ((55, 68), (90, 111), (165, 203)):
        assert round(mi * 1.609344 * math.log(20) / math.log(50)) == km
    assert abs(P.transmission(30e3, 111) - math.exp(-math.log(20) * 30 / 111)) < 1e-15


# ---------------------------------------------------------------- Eq. (8): magnitude scale
def test_eq8_magnitude_constant():
    # Schaefer (1993): m = -16.57 - 2.5 log10(E / foot-candle); 1 fc = 10.7639 lx
    assert abs((-16.57 + 2.5 * math.log10(10.7639)) - (-13.99)) < 0.005
    # sanity: the Sun (V = -26.74) gives about 1.3e5 lx at the top of the atmosphere
    assert 1.0e5 < 10 ** (-(-26.74 + 13.99) / 2.5) < 1.5e5
    # m = 0 corresponds to 2.5e-6 lx
    assert abs(10 ** (-13.99 / 2.5) - 2.54e-6) < 0.02e-6
    # worked example in the text: 2 x 300 cd at 30 km, V = 111 km
    E = 600 * P.transmission(30e3, 111) / 30e3 ** 2
    assert abs(E - 2.97e-7) < 0.01e-7 and abs(P.magnitude(E) - 2.33) < 0.01


# ---------------------------------------------------------------- Eq. (9): Crumey threshold
def test_eq9_crumey_values():
    assert abs(P.m_lim(21.0, 2.0) - 5.86) < 0.005
    assert abs(P.m_lim(20.5, 4.0) - 4.91) < 0.005
    assert abs(P.m_lim(22.0, 1.4) - 6.63) < 0.005
    # larger field factor = less sensitive observer
    assert P.m_lim(21.0, 4.0) < P.m_lim(21.0, 1.4)


# ---------------------------------------------------------------- Eq. (10): occupancy
def test_eq10_occupancy_poisson_simulation():
    rng = np.random.default_rng(3)
    q, L, u = 25 / 3600.0, 10.0e3, 30.0                            # vehicles/s, m, m/s
    Tsim = 3.0e6
    arrivals = np.cumsum(rng.exponential(1 / q, int(q * Tsim * 1.2)))
    arrivals = arrivals[arrivals < Tsim]
    tt = rng.uniform(L / u, Tsim, 20000)                           # random observation instants
    idx = np.searchsorted(arrivals, tt)
    lo = np.searchsorted(arrivals, tt - L / u)
    counts = idx - lo                                               # vehicles that entered within the last L/u
    N = q * L / u
    assert abs(counts.mean() - N) < 0.05 * N
    assert abs(counts.var() - N) < 0.1 * N                          # Poisson: variance = mean
    assert abs(np.mean(counts > 0) - (1 - math.exp(-N))) < 0.02
    assert abs(10 / 3600 * 10.02e3 / 30 - 0.928) < 0.001            # value in the text


# ---------------------------------------------------------------- angular drift of a car across the view
def test_angular_rate_formula():
    """omega = u |sin(h)| / d for a car at distance d moving at u with the viewer h off its heading."""
    d, u, h = 30e3, 30.0, math.radians(14.0)
    car = np.array([0.0, d])                                        # viewer at the origin, car due "north"
    vel = u * np.array([math.sin(math.pi + h), math.cos(math.pi + h)])   # heading 180 + h (toward the viewer, h off)
    dt = 1e-3
    b0 = math.atan2(car[0], car[1])
    b1 = math.atan2(*(car + vel * dt))
    assert abs(abs(b1 - b0) / dt - u * abs(math.sin(h)) / d) < 1e-6 * u / d
    assert abs(math.degrees(u * abs(math.sin(h)) / d) * 60 - 0.83) < 0.01


# ---------------------------------------------------------------- SI: Euler radius, AR(1) field, median test
def test_si_euler_radius():
    lat = 30.2751
    M, N = g.radii(lat)
    for az in (0, 45, 90, 233.7):
        a = math.radians(az)
        assert abs(1 / g.normal_section_radius(lat, az) - (math.cos(a) ** 2 / M + math.sin(a) ** 2 / N)) < 1e-18


def test_si_ar1_correlation_and_interpolation_loss():
    L, gstep = 20.0, 5.0
    phi = math.exp(-gstep / L)
    # correlation of the AR(1) sequence at lag m*g is phi^m = exp(-m g / L)
    assert abs(phi ** 3 - math.exp(-15 / L)) < 1e-12
    # variance of linear interpolation midway between nodes: (1 + phi)/2 -> standard deviation loss <= 6 %
    var_mid = 0.25 + 0.25 + 2 * 0.25 * phi
    assert abs(var_mid - (1 + phi) / 2) < 1e-12
    assert 0.88 < var_mid < 0.89 and 1 - math.sqrt(var_mid) < 0.06


def test_si_median_test_is_conservative():
    """For 8 values, median <= x implies at least 4 values <= x, so P(median <= x) <= P(#<=x >= 4)."""
    rng = np.random.default_rng(0)
    x = rng.uniform(size=(20000, 8))
    thr = 0.3
    med = np.median(x, axis=1)
    atleast4 = (x <= thr).sum(axis=1) >= 4
    assert np.all(atleast4[med <= thr])
    assert np.mean(med <= thr) <= np.mean(atleast4)

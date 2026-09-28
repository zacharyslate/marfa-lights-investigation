"""Unit tests for the exact-geometry line-of-sight engine (run: pytest analysis/tests)."""
import sys, os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from marfa import geodesy as g, los

V = (-103.8827973, 30.2751108)


class FnMosaic:
    """Synthetic terrain H(lon, lat) for tests."""
    def __init__(self, fn):
        self.fn = fn

    def sample(self, lon, lat, strict=True):
        z = self.fn(np.asarray(lon, float), np.asarray(lat, float))
        if strict and np.isnan(z).any():
            raise ValueError("no data")
        return z, np.zeros(np.shape(z), int)


def dist_from_viewer(lon, lat):
    _, d = g.inv(np.full_like(lon, V[0]), np.full_like(lat, V[1]), lon, lat)
    return d


def test_radius_matches_euler_formula():
    m, n = g.radii(30.0)
    assert g.normal_section_radius(30.0, 0) == pytest.approx(m)
    assert g.normal_section_radius(30.0, 90) == pytest.approx(n)
    assert m < g.normal_section_radius(30.0, 225) < n


@pytest.mark.parametrize("k", [0.0, 0.13, 0.5])
def test_horizon_over_smooth_earth(k):
    """Bare ellipsoid (H = 0): eye h1 and lamp h2 are just visible at d = sqrt(2R'h1) + sqrt(2R'h2), R' = R/(1-k)."""
    flat = FnMosaic(lambda lo, la: np.zeros_like(lo))
    obs = los.Observer(V[0], V[1], ground_H=0.0, eye=10.0)
    az = 225.0
    R = g.normal_section_radius(V[1], az) / (1 - k)
    d_h = np.sqrt(2 * R * 10.0) + np.sqrt(2 * R * 2.0)
    for f, vis in ((0.97, True), (1.03, False)):
        lo, la = g.fwd(V[0], V[1], az, f * d_h)
        r = los.sightline(obs, flat, lo, la, lamp=2.0, step=20.0)
        assert (r["k_crit"] <= k) == vis, (k, f, r["k_crit"])


def test_kcrit_matches_bruteforce_on_random_terrain():
    rng = np.random.default_rng(3)
    for trial in range(20):
        amp, wl, ph = rng.uniform(5, 40), rng.uniform(2000, 9000), rng.uniform(0, 6)
        terr = FnMosaic(lambda lo, la: 1400 + amp * np.sin(dist_from_viewer(lo, la) / wl + ph))
        obs = los.Observer(V[0], V[1], ground_H=1400.0, eye=1.6)
        lo, la = g.fwd(V[0], V[1], rng.uniform(200, 260), rng.uniform(8000, 40000))
        r = los.sightline(obs, terr, lo, la, lamp=0.7, step=10.0, return_profile=True)
        R, D = r["R"], r["D"]
        for k in (r["k_crit"] - 0.01, r["k_crit"] + 0.01):
            sag = k * r["denom"] / (2 * R)
            visible = np.all(r["y"] <= sag)
            assert visible == (k >= r["k_crit"])


def test_isolated_ridge_kcrit_analytic():
    """A 30 m ridge on a flat plain: compare k_crit with the small-angle textbook formula."""
    d_ridge, d_t = 12000.0, 30000.0
    def fn(lo, la):
        d = dist_from_viewer(lo, la)
        return 1400 + 30.0 * np.exp(-((d - d_ridge) / 150.0) ** 2)
    obs = los.Observer(V[0], V[1], ground_H=1400.0, eye=1.6)
    az = 230.0
    lo, la = g.fwd(V[0], V[1], az, d_t)
    r = los.sightline(obs, FnMosaic(fn), lo, la, lamp=0.7, step=5.0)
    R = g.normal_section_radius(V[1], az)
    E, zt, zi = 1401.6, 1400.7, 1430.0
    # textbook: 1 - k_crit = 2R [ (zt-E)/dt - (zi-E)/di ] / (dt - di)   (heights reduced to the sphere)
    kc_text = 1 - 2 * R * ((zt - E) / d_t - (zi - E) / d_ridge) / (d_t - d_ridge)
    assert r["k_crit"] == pytest.approx(kc_text, abs=0.02)


def test_dip_of_sea_level_horizon():
    """Apparent elevation of a point at eye level at distance d is -(1-k) d / (2R) (rad)."""
    flat = FnMosaic(lambda lo, la: np.zeros_like(lo))
    obs = los.Observer(V[0], V[1], ground_H=0.0, eye=0.0)
    az, d = 240.0, 20000.0
    lo, la = g.fwd(V[0], V[1], az, d)
    r = los.sightline(obs, flat, lo, la, lamp=0.0, step=50.0)
    R = g.normal_section_radius(V[1], az)
    assert r["app_el013"] == pytest.approx(-np.degrees((1 - 0.13) * d / (2 * R)), abs=2e-5)


def test_missing_dem_raises():
    holey = FnMosaic(lambda lo, la: np.where(dist_from_viewer(lo, la) > 5000, np.nan, 1400.0))
    obs = los.Observer(V[0], V[1], ground_H=1400.0)
    lo, la = g.fwd(V[0], V[1], 230.0, 20000.0)
    with pytest.raises(ValueError):
        los.sightline(obs, holey, lo, la)


def _h0(terr):
    return float(terr.sample(np.array([V[0]]), np.array([V[1]]))[0][0])


def _ridge_terrain(rng):
    amp, wl, ph = rng.uniform(5, 40), rng.uniform(2000, 9000), rng.uniform(0, 6)
    return FnMosaic(lambda lo, la: 1400 + amp * np.sin(dist_from_viewer(lo, la) / wl + ph))


def test_multi_agrees_with_single_lamp_engine():
    rng = np.random.default_rng(7)
    for _ in range(10):
        terr = _ridge_terrain(rng)
        obs = los.Observer(V[0], V[1], ground_H=_h0(terr), eye=1.6)
        lo, la = g.fwd(V[0], V[1], rng.uniform(200, 260), rng.uniform(8000, 40000))
        a = los.sightline(obs, terr, lo, la, lamp=0.7, step=5.0, skip_tgt=5.0)
        b = los.sightline_multi(obs, terr, lo, la, lamps=(0.7,), fine=5.0, coarse=5.0, skip_tgt=5.0)
        assert b["k_crit"][0] == pytest.approx(a["k_crit"], abs=2e-3)
        assert b["clr"][0, 0] == pytest.approx(a["clr013"], abs=0.02)


def test_lamp_and_eye_margins_flip_visibility():
    """Moving the lamp by dL (or the eye by dE) must put the ray exactly on the terrain: k_crit -> k."""
    rng = np.random.default_rng(11)
    for _ in range(10):
        terr = _ridge_terrain(rng)
        obs = los.Observer(V[0], V[1], ground_H=_h0(terr), eye=1.6)
        lo, la = g.fwd(V[0], V[1], rng.uniform(200, 260), rng.uniform(8000, 40000))
        k = 0.13
        r = los.sightline_multi(obs, terr, lo, la, lamps=(0.7,), ks=(k,))
        L2 = 0.7 + r["dL"][0, 0]
        r2 = los.sightline_multi(obs, terr, lo, la, lamps=(L2,), ks=(k,))
        assert r2["k_crit"][0] == pytest.approx(k, abs=2e-3)
        obs2 = los.Observer(V[0], V[1], ground_H=_h0(terr), eye=1.6 + r["dE"][0, 0])
        r3 = los.sightline_multi(obs2, terr, lo, la, lamps=(0.7,), ks=(k,))
        assert r3["k_crit"][0] == pytest.approx(k, abs=2e-3)


def test_sampling_is_fine_near_both_ends():
    s = los.sample_distances(20000.0, 5.0, 3.0)
    assert s[0] == 5.0 and s[-1] == pytest.approx(19997.0)
    assert np.all(np.diff(s[s < 3000]) <= 2.0 + 1e-9) and np.all(np.diff(s[s > 17000]) <= 2.0 + 1e-9)
    assert np.diff(s).max() <= 5.0 + 1e-9
    short = los.sample_distances(1000.0, 5.0, 3.0)
    assert np.diff(short).max() <= 2.0 + 1e-9


def test_correlated_errors_statistics():
    rng = np.random.default_rng(0)
    s = np.concatenate([np.arange(0, 1000, 2.0), np.arange(1000, 5000, 5.0)])
    sig = np.where(s < 1000, 0.1, 0.5)
    cor = np.where(s < 1000, 20.0, 70.0)
    e = los.correlated_errors(s, sig, cor, 4000, rng)
    assert e[:, 100].std() == pytest.approx(0.1, rel=0.05)
    assert e[:, -1].std() == pytest.approx(0.5, rel=0.05)
    i = np.searchsorted(s, 3000.0)
    j = np.searchsorted(s, 3070.0)
    assert np.corrcoef(e[:, i], e[:, j])[0, 1] == pytest.approx(np.exp(-1), abs=0.05)


def test_mc_without_errors_is_deterministic():
    rng = np.random.default_rng(5)
    terr = _ridge_terrain(rng)
    obs = los.Observer(V[0], V[1], ground_H=_h0(terr), eye=1.6)
    lo, la = g.fwd(V[0], V[1], 230.0, 15000.0)
    r = los.sightline_multi(obs, terr, lo, la, lamps=(0.7, 3.0), ks=(0.0, 0.13, 0.5, 1.0),
                            mc=dict(n=50, sigma=[0.0], corr=[10.0], eye_sd=0.0))
    for j in range(2):
        for m, k in enumerate((0.0, 0.13, 0.5, 1.0)):
            assert r["p_vis"][j, m] == float(r["k_crit"][j] <= k)


def test_clutter_raises_kcrit():
    rng = np.random.default_rng(9)
    terr = _ridge_terrain(rng)
    obs = los.Observer(V[0], V[1], ground_H=_h0(terr), eye=1.6)
    lo, la = g.fwd(V[0], V[1], 230.0, 15000.0)
    r = los.sightline_multi(obs, terr, lo, la, lamps=(0.7,), clutter=(0.0, 0.5, 1.0))
    kc = r["kc_clutter"][0]
    assert kc[0] == pytest.approx(r["k_crit"][0])
    assert kc[0] < kc[1] < kc[2]


def test_mc_eye_only_matches_analytic_probability():
    """With terrain errors off, visibility requires eye error >= the eye-height margin dE: p = 1 - Phi(dE/sd)."""
    from scipy.stats import norm
    rng = np.random.default_rng(21)
    checked = 0
    for _ in range(30):
        terr = _ridge_terrain(rng)
        obs = los.Observer(V[0], V[1], ground_H=_h0(terr), eye=1.6)
        lo, la = g.fwd(V[0], V[1], rng.uniform(200, 260), rng.uniform(8000, 40000))
        sd = 1.0
        r = los.sightline_multi(obs, terr, lo, la, lamps=(0.7,), ks=(0.13,),
                                mc=dict(n=4000, sigma=[0.0], corr=[10.0], eye_sd=sd))
        dE = r["dE"][0, 0]
        if abs(dE) > 2.5:
            continue
        p = 1 - norm.cdf(dE / sd)
        assert r["p_vis"][0, 0] == pytest.approx(p, abs=0.04)
        checked += 1
    assert checked >= 5

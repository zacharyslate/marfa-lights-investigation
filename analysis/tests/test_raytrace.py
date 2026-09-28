"""Tests for the height-dependent refraction ray tracer."""
import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from marfa import raytrace as rt

R = 6.37e6
EYE, LAMP = 1.6, 0.7


def flat(D, ds=5.0):
    """Bare smooth Earth in the chord frame: ground bulges above the eye-lamp chord."""
    s = np.arange(0, D, ds)
    return s, -(EYE * (D - s) + LAMP * s) / D + s * (D - s) / (2 * R)


def test_hirt_relation_standard_value():
    assert rt.k_from_gradient(-0.0098) == pytest.approx(0.130, abs=0.002)
    assert rt.k_from_gradient(0.0) == pytest.approx(503.3 * 850 / 283 ** 2 * 0.03416, rel=1e-3)


@pytest.mark.parametrize("g", [-0.0098, 0.0, 0.05])
def test_constant_gradient_reproduces_constant_k(g):
    D = 6000.0
    s, yg = flat(D)
    r = rt.trace(s, yg, D, R, rt.lapse(g), n_theta=4001)
    k = rt.C_OPT * 850 / 283 ** 2 * (rt.G_RD + g) * R
    assert len(r["images"]) == 1
    assert r["k_equiv"][0] == pytest.approx(k, abs=2e-3)


@pytest.mark.parametrize("g,vis", [(-0.0098, False), (0.03, True)])
def test_horizon_matches_constant_k_horizon(g, vis):
    """Target just beyond the k=0.13 horizon: hidden with the neutral lapse, visible with k ~ 0.35."""
    k013 = 0.13
    Rp = R / (1 - k013)
    d_h = np.sqrt(2 * Rp * EYE) + np.sqrt(2 * Rp * LAMP)
    D = 1.05 * d_h
    s, yg = flat(D)
    r = rt.trace(s, yg, D, R, rt.lapse(g), n_theta=6001)
    assert (len(r["images"]) > 0) == vis


def test_surface_duct_reach_is_analytic():
    """Uniform k>1 inside a duct of depth H: max reach to the lamp = sqrt(2R'(H-eye)) + sqrt(2R'(H-lamp)),
    R' = R/(k-1); beyond it no ray from the eye reaches the lamp (rays leaving the duct never return)."""
    H, g = 3.0, 1.0
    k = rt.C_OPT * 850 / 283 ** 2 * (rt.G_RD + g) * R
    Rp = R / (k - 1)
    reach = np.sqrt(2 * Rp * (H - EYE)) + np.sqrt(2 * Rp * (H - LAMP))
    duct = rt.layered([0, H], [g, -0.0065])
    for f, vis in ((0.9, True), (1.1, False)):
        D = f * reach
        s, yg = flat(D, 2.0)
        r = rt.trace(s, yg, D, R, duct, ds=2.0, n_theta=8001)
        assert (len(r["images"]) > 0) == vis, (f, reach)

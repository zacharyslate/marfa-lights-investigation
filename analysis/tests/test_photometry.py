import numpy as np

from marfa import geodesy as g, photometry as P

V = (-103.8827973, 30.2751108)


def test_umtri_grid_values():
    assert abs(P.LOW(0, 0) - 8830) < 1e-6          # UMTRI-2004-23 Table 4, H-V median
    assert abs(P.LOW(-45, 0) - 23) < 1e-6          # 45L
    assert abs(P.LOW(45, 0) - 4) < 1e-6            # 45R
    assert abs(P.HIGH(0, 0) - 37005) < 1e-3        # UMTRI-2001-19 Table 6, H-V median
    assert np.all(P.LOW(np.linspace(-45, 45, 91), 0, "p25") <= P.LOW(np.linspace(-45, 45, 91), 0, "p75") + 1e-9)


def test_magnitude_scale():
    # Schaefer 1993: m = -13.99 - 2.5 log10(E/lx); a 1 cd source at 1 km with no extinction -> E = 1e-6 lx
    assert abs(P.magnitude(1e-6) - 1.01) < 1e-9
    assert abs(P.magnitude(1e-4) - P.magnitude(1e-6) + 5.0) < 1e-9


def test_transmission_definition():
    # MOR is the distance at which transmission falls to 5 %
    assert abs(P.transmission(100e3, 100.0) - 0.05) < 1e-12


def test_crumey_threshold():
    assert abs(P.m_lim(21.0, 1.0) - (0.3834 * 21 - 1.44)) < 1e-12


def test_heading_straight_at_viewer_gives_h0_and_rear_opposite():
    lon, lat = np.array([-104.10]), np.array([30.10])
    az_cv, d = g.inv(lon, lat, np.array([V[0]]), np.array([V[1]]))
    ang = P.view_angles(lon, lat, az_cv, np.zeros(1), np.array([-0.3]), d, np.array(6.37e6))
    assert abs(ang["fwd"][0][0]) < 1e-9
    assert abs(abs(ang["rev"][0][0]) - 180) < 1e-9


def test_viewer_to_the_right_is_positive_h():
    lon, lat = np.array([-104.10]), np.array([30.10])
    az_cv, d = g.inv(lon, lat, np.array([V[0]]), np.array([V[1]]))
    ang = P.view_angles(lon, lat, az_cv - 30.0, np.zeros(1), np.array([-0.3]), d, np.array(6.37e6))
    assert abs(ang["fwd"][0][0] - 30.0) < 1e-9     # heading 30 deg left of the viewer -> viewer 30 deg to the right


def test_vertical_angle_level_ground_symmetric():
    # eye and lamp at equal ellipsoidal height, no refraction: the chord makes equal angles -D/2R at both ends
    D, R = 30e3, 6.37e6
    geo = -np.degrees(D / (2 * R))
    ang = P.view_angles(np.array([-104.1]), np.array([30.1]), np.array([0.0]), np.zeros(1), np.array([geo]),
                        np.array([D]), np.array(R), k=0.0)
    assert abs(ang["fwd"][1][0] - geo) < 1e-9
    # uphill pitch of 2 % tilts the lamp axis up, so the viewer is lower in the beam
    ang2 = P.view_angles(np.array([-104.1]), np.array([30.1]), np.array([0.0]), np.array([0.02]), np.array([geo]),
                         np.array([D]), np.array(R), k=0.0)
    assert abs(ang2["fwd"][1][0] - (geo - np.degrees(np.arctan(0.02)))) < 1e-9
    assert abs(ang2["rev"][1][0] - (geo + np.degrees(np.arctan(0.02)))) < 1e-9


def test_rear_brackets():
    assert P.rear_intensity(np.array(0.0)) == 0.0                    # front view: no rear lamps
    assert abs(P.rear_intensity(np.array(180.0)) - 4.0) < 1e-12      # 2 x 2.0 cd at H-V (min)
    assert abs(P.rear_intensity(np.array(180.0), True, "max") - (36 + 600 + 160)) < 1e-9
    assert P.rear_intensity(np.array(120.0)) == 0.0                  # 60 deg off the rear axis

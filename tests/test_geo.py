import numpy as np
import pytest

from app.geo import from_local_km, haversine_km, pairwise_km, to_local_km


def test_one_degree_on_equator():
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.195, abs=1e-3)


def test_zero_and_symmetric():
    assert haversine_km(-1.2, 116.9, -1.2, 116.9) == 0
    a = haversine_km(-0.15, 109.4, 3.33, 117.57)
    assert a == pytest.approx(haversine_km(3.33, 117.57, -0.15, 109.4))


def test_known_distance_pontianak_balikpapan():
    # ~830 km great-circle; check against an independent spherical law of cosines
    lat1, lon1, lat2, lon2 = np.radians([-0.15071, 109.404, -1.26827, 116.894])
    c = np.arccos(np.sin(lat1) * np.sin(lat2) + np.cos(lat1) * np.cos(lat2) * np.cos(lon2 - lon1))
    assert haversine_km(-0.15071, 109.404, -1.26827, 116.894) == pytest.approx(6371.0088 * c)


def test_pairwise_shape():
    d = pairwise_km([(0, 0), (1, 1)], [(0, 0), (0, 1), (2, 2)])
    assert d.shape == (2, 3)
    assert d[0, 0] == 0


def test_local_projection_round_trip_and_scale():
    pts = np.array([(-1.0, 110.0), (0.5, 112.3)])
    xy = to_local_km(pts, -0.5, 111.0)
    assert np.allclose(from_local_km(xy, -0.5, 111.0), pts)
    # short distances close to great-circle
    a, b = np.array([(-0.5, 111.0)]), np.array([(-0.4, 111.1)])
    planar = np.linalg.norm(to_local_km(b, -0.5, 111.0) - to_local_km(a, -0.5, 111.0))
    assert planar == pytest.approx(pairwise_km(a, b)[0, 0], rel=1e-3)

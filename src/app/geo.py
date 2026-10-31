"""Great-circle distances and a local planar km projection."""

import numpy as np

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Accepts scalars or broadcastable arrays (degrees)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def pairwise_km(a, b):
    """Matrix of great-circle km between point sets a (n, 2) and b (m, 2), columns (lat, lon)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return haversine_km(a[:, None, 0], a[:, None, 1], b[None, :, 0], b[None, :, 1])


def to_local_km(points, ref_lat, ref_lon):
    """Equirectangular projection around (ref_lat, ref_lon): (lat, lon) -> (x_east, y_north) km."""
    p = np.asarray(points, float)
    k = np.radians(1.0) * EARTH_RADIUS_KM
    x = (p[..., 1] - ref_lon) * k * np.cos(np.radians(ref_lat))
    y = (p[..., 0] - ref_lat) * k
    return np.stack([x, y], axis=-1)


def from_local_km(xy, ref_lat, ref_lon):
    """Inverse of to_local_km."""
    q = np.asarray(xy, float)
    k = np.radians(1.0) * EARTH_RADIUS_KM
    lat = ref_lat + q[..., 1] / k
    lon = ref_lon + q[..., 0] / (k * np.cos(np.radians(ref_lat)))
    return np.stack([lat, lon], axis=-1)

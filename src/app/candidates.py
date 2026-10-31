"""Candidate cells for refinery + depot hubs: farm sites plus a sieved Hanan grid."""

import numpy as np

from app.geo import pairwise_km


def hanan_grid(points) -> np.ndarray:
    """All (lat, lon) combinations of the given points' latitudes and longitudes."""
    p = np.asarray(points, float)
    lats, lons = np.unique(p[:, 0]), np.unique(p[:, 1])
    la, lo = np.meshgrid(lats, lons, indexing="ij")
    return np.column_stack([la.ravel(), lo.ravel()])


def in_bbox(points, bbox) -> np.ndarray:
    lat_min, lon_min, lat_max, lon_max = bbox
    p = np.asarray(points, float)
    return (p[:, 0] >= lat_min) & (p[:, 0] <= lat_max) & (p[:, 1] >= lon_min) & (p[:, 1] <= lon_max)


def near_any(points, anchors, max_km: float) -> np.ndarray:
    return pairwise_km(points, anchors).min(axis=1) <= max_km


def dedupe(points, min_km: float) -> np.ndarray:
    """Greedy: keep a point unless it is within min_km of one already kept (order matters)."""
    p = np.asarray(points, float)
    if len(p) == 0:
        return p.reshape(0, 2)
    d = pairwise_km(p, p)
    keep = np.ones(len(p), bool)
    for i in range(len(p)):
        if keep[i]:
            close = d[i] < min_km
            close[: i + 1] = False
            keep &= ~close
    return p[keep]


def build_candidates(farm_pts, airport_pts, cfg: dict) -> np.ndarray:
    """Farm sites first (so they survive dedupe), then sieved Hanan points. (n, 2) lat/lon."""
    farm_pts = np.asarray(farm_pts, float)
    parts = []
    if cfg.get("include_farm_sites", True):
        parts.append(farm_pts)
    if cfg.get("hanan", True):
        grid = hanan_grid(np.vstack([farm_pts, np.asarray(airport_pts, float)]))
        mask = near_any(grid, farm_pts, float(cfg.get("max_km_to_farm", 150)))
        if "bbox" in cfg:
            mask &= in_bbox(grid, cfg["bbox"])
        parts.append(grid[mask])
    if not parts:
        raise ValueError("candidates: enable include_farm_sites and/or hanan")
    return dedupe(np.vstack(parts), float(cfg.get("dedupe_km", 1.0)))

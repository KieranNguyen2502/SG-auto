"""Road-distance matrices (great-circle x road factor) and arc pruning."""

import numpy as np

from app.geo import pairwise_km


def road_km(a, b, road_factor: float) -> np.ndarray:
    return pairwise_km(a, b) * road_factor


def farm_cell_arcs(d_fc: np.ndarray, max_km: float | None) -> list[tuple[int, int]]:
    """(farm, cell) index pairs whose road distance is within max_km (all pairs if None)."""
    if max_km is None:
        js, cs = np.indices(d_fc.shape).reshape(2, -1)
    else:
        js, cs = np.nonzero(d_fc <= max_km)
    return list(zip(js.tolist(), cs.tolist(), strict=True))

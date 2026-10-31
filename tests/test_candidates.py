import numpy as np

from app.candidates import build_candidates, dedupe, hanan_grid, in_bbox


def test_hanan_grid():
    g = hanan_grid([(0, 10), (1, 11), (1, 12)])
    assert len(g) == 2 * 3
    assert {tuple(p) for p in g} >= {(0, 12), (1, 10)}


def test_dedupe_keeps_first():
    pts = [(0, 0), (0, 0.001), (0, 1)]  # second is ~0.1 km from first
    out = dedupe(pts, 1.0)
    assert np.array_equal(out, [(0, 0), (0, 1)])


def test_bbox():
    assert in_bbox([(0, 110), (5, 110)], [-1, 109, 1, 111]).tolist() == [True, False]


def test_build_candidates_sieves_far_points():
    farms = [(0, 110), (0.1, 110.1)]
    airports = [(3, 117)]
    c = build_candidates(farms, airports, {"max_km_to_farm": 50, "dedupe_km": 1})
    # farms kept first; Hanan points with lat 3 or lon 117 are >50 km away
    assert np.array_equal(c[:2], farms)
    assert len(c) == 4
    assert (c[:, 0] < 1).all() and (c[:, 1] < 111).all()


def test_real_instance_size(base_cfg):
    from app.pipeline import build_instance

    inst = build_instance(base_cfg)
    assert 80 <= len(inst.cells) <= 84 * 84
    assert inst.d_fc.shape == (80, len(inst.cells))
    # every farm has at least one arc (its own site)
    assert {j for j, _ in inst.arcs} == set(range(80))

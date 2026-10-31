import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "standalone"))
import weiszfeld_refine as W  # noqa: E402


def test_symmetric_points_give_centre():
    # Four equal weights at +-0.1 deg around (0, 110): optimum is the centre.
    anchors = [(0.1, 110, 1), (-0.1, 110, 1), (0, 110.1, 1), (0, 109.9, 1)]
    (lat, lon), _ = W.weiszfeld((0.05, 110.03), anchors)
    assert lat == pytest.approx(0, abs=1e-5)
    assert lon == pytest.approx(110, abs=1e-5)


def test_dominant_anchor_keeps_hub_on_it():
    # Vardi-Zhang: weight 10 at the start point beats the pull of 1 + 1 elsewhere.
    anchors = [(0, 110, 10), (0.2, 110, 1), (0, 110.2, 1)]
    (lat, lon), _ = W.weiszfeld((0, 110), anchors)
    assert (lat, lon) == (0, 110)


def test_leaves_light_anchor():
    # Start on a light anchor; two heavy ones pull it away, to a cheaper point.
    anchors = [(0, 110, 0.1), (0.2, 110, 5), (-0.2, 110, 5)]
    (lat, lon), _ = W.weiszfeld((0, 110.1), anchors)
    assert W.hub_cost((lat, lon), anchors) < W.hub_cost((0, 110.1), anchors)


def test_result_is_local_minimum():
    anchors = [(0.0, 110.0, 3), (0.3, 110.4, 1), (-0.2, 110.5, 2), (0.1, 109.8, 1.5)]
    p, _ = W.weiszfeld((0.0, 110.2), anchors)
    base = W.hub_cost(p, anchors)
    for k in range(16):
        t = k * math.pi / 8
        q = (p[0] + 0.005 * math.sin(t), p[1] + 0.005 * math.cos(t))
        assert W.hub_cost(q, anchors) >= base - 1e-9

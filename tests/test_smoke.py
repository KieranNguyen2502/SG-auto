import csv
import json

import pytest

from app import __version__
from app.data import Airport, Farm
from app.model import Instance, solve
from app.report import trips, write_report
from app.validate import validate


def test_version():
    assert __version__


def test_trips():
    assert trips(0, 9) == 0
    assert trips(0.009, 9) == 1
    assert trips(0.0091, 9) == 2
    assert trips(100, 32) == 3125


def test_report_files(params, tmp_path):
    pytest.importorskip("gurobipy")
    farms = [Farm("F1", "P", "D", 400, 0, 0), Farm("F2", "P", "D", 400, 0, 0.5)]
    airports = [Airport("AAA", "A", 0, 0.2, 60), Airport("TRK", "T", 0.3, 0.3, 40, barge=True)]
    inst = Instance(farms, [(0, 0), (0, 0.5)], airports, params)
    sol = solve(inst)
    write_report(inst, sol, validate(inst, sol), tmp_path, {"run_id": "t"})
    names = {p.name for p in tmp_path.iterdir()}
    assert names == {
        "facilities.csv",
        "flows_farm_depot.csv",
        "flows_depot_refinery.csv",
        "flows_refinery_airport.csv",
        "unused_farms.csv",
        "costs.json",
    }
    out = _rows(tmp_path / "flows_refinery_airport.csv")
    barge = [r for r in out if r["airport"] == "TRK"]
    assert barge and all(r["mode"] == "barge" and r["trips_small"] == "" for r in barge)
    s = json.loads((tmp_path / "costs.json").read_text())
    assert s["costs_usd"]["total"] == pytest.approx(sol.objective_musd * 1e6, rel=1e-6)
    assert s["biomass_used_kt"] == pytest.approx(500)
    unused = _rows(tmp_path / "unused_farms.csv")
    assert sum(float(r["unused_kt"]) for r in unused) == pytest.approx(300)


def _rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_apply_override():
    from app.main import apply_override

    cfg = {"model": {"max_haul_km": 400}}
    apply_override(cfg, "model.max_haul_km=250")
    apply_override(cfg, "model.n_refineries={ Large = 6 }")
    apply_override(cfg, "candidates.hanan=false")
    apply_override(cfg, "output.dir=elsewhere")
    assert cfg["model"] == {"max_haul_km": 250, "n_refineries": {"Large": 6}}
    assert cfg["candidates"]["hanan"] is False
    assert cfg["output"]["dir"] == "elsewhere"

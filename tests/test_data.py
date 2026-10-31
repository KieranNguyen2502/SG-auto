from pathlib import Path

import pytest

from app.data import DataError, load_airports, load_farms, load_params

ROOT = Path(__file__).resolve().parents[1]


def test_farms(base_cfg):
    farms = load_farms(base_cfg["data"]["farms_csv"])
    assert len(farms) == 80
    assert sum(f.supply_kt for f in farms) == pytest.approx(6800)
    assert all(20 <= f.supply_kt <= 100 for f in farms)


def test_airports_by_iata(base_cfg):
    ap = load_airports(base_cfg["data"]["airports_dat"], base_cfg["airports"]["demand_kt"], ["TRK"])
    assert [a.iata for a in ap] == ["PNK", "PKN", "BPN", "TRK"]
    pkn = ap[1]
    assert pkn.lat == pytest.approx(-2.7052, abs=1e-4)  # Pangkalan Bun, not Banda Aceh
    assert pkn.lon == pytest.approx(111.673, abs=1e-3)
    assert [a.barge for a in ap] == [False, False, False, True]
    assert sum(a.demand_kt for a in ap) == 1200


def test_missing_airport_errors(base_cfg):
    with pytest.raises(DataError, match="XXX"):
        load_airports(base_cfg["data"]["airports_dat"], {"PNK": 1, "XXX": 1})


def test_bad_farm_file(tmp_path):
    p = tmp_path / "f.csv"
    p.write_text("location_id,latitude\nA,1\n")
    with pytest.raises(DataError, match="missing columns"):
        load_farms(p)


def test_params_annualised(params):
    assert params.annual_fixed_usd(params.refineries["Large"]) == pytest.approx(76.5e6)
    assert params.annual_fixed_usd(params.refineries["Small"]) == pytest.approx(48e6)
    assert params.annual_fixed_usd(params.depots["Large"]) == pytest.approx(450_000)
    assert params.annual_fixed_usd(params.depots["Small"]) == pytest.approx(225_000)


def test_params_match_organiser_workbook(params):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(ROOT / "data" / "challenge3_parameters.xlsx", data_only=True)
    fac = [r for r in wb["facilities"].iter_rows(values_only=True) if _num(r[2])]
    for kind, size, capex, cap, fixed_opex, var_opex, annual_capex in fac:
        f = (params.depots if kind == "Depot" else params.refineries)[size]
        assert (f.capex_usd, f.capacity_kt, f.var_opex_usd_per_t) == (capex, cap, var_opex)
        assert params.fixed_opex_frac * capex == pytest.approx(fixed_opex)
        assert capex / params.capex_years == pytest.approx(annual_capex)
    legs = ["farm_depot", "depot_refinery", "refinery_airport"]
    rows = [r for r in wb["transport"].iter_rows(values_only=True) if _num(r[2])]
    for name, (_, _, cost, small, large) in zip(legs, rows, strict=True):
        leg = params.legs[name]
        assert (leg.cost_usd_per_tkm, leg.small_truck_t, leg.large_truck_t) == (cost, small, large)


def test_bad_yield(base_cfg):
    cfg = {**base_cfg, "process": {**base_cfg["process"], "yield": 0}}
    with pytest.raises(DataError):
        load_params(cfg)


def _num(v):
    return isinstance(v, int | float)

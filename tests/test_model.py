"""Tiny instances (well under the size-limited Gurobi licence)."""

from dataclasses import replace

import pytest

from app.data import Airport, Farm
from app.geo import haversine_km
from app.model import InfeasibleError, Instance, SolveOptions, solve
from app.validate import check, validate

pytest.importorskip("gurobipy")


def farm(i, kt, lat, lon):
    return Farm(f"F{i}", "P", "D", kt, lat, lon)


def tiny(params, demand=100.0, supply=(400.0, 400.0)):
    farms = [farm(1, supply[0], 0, 0), farm(2, supply[1], 0, 0.5)]
    airports = [Airport("AAA", "A", 0, 0, demand)]
    return Instance(farms, [(0, 0), (0, 0.5)], airports, params)


def test_hand_solved(params):
    # 100 kt SAF -> 500 kt biomass. Best: Small refinery at cell 0 (airport + F1 there),
    # 400 kt from F1 at 0 km + 100 kt from F2, 2 Large depots (cheaper than 1L+2S).
    inst = tiny(params)
    sol = solve(inst)
    d = haversine_km(0, 0, 0, 0.5) * 1.3
    expected = 48 + 0.060 * 500 + (2 * 0.45 + 0.004 * 500) + 1e-4 * 100 * d
    assert sol.objective_musd == pytest.approx(expected, rel=1e-6)
    assert sol.refineries == {0: ("Small", pytest.approx(500))}
    assert sol.depots[0]["Large"][0] == 2
    assert "Small" not in sol.depots[0]
    assert sol.farm_flows[(0, 0)] == pytest.approx(400)
    assert sol.farm_flows[(1, 0)] == pytest.approx(100)


def test_validate_matches_objective(params):
    inst = tiny(params)
    sol = solve(inst)
    costs = validate(inst, sol)
    assert costs["total"] == pytest.approx(sol.objective_musd * 1e6, rel=1e-6)
    assert costs["transport_depot_refinery"] == 0


def test_validate_catches_tampering(params):
    inst = tiny(params)
    sol = solve(inst)
    sol.saf_flows = {k: v * 0.5 for k, v in sol.saf_flows.items()}
    assert any("airport" in e for e in check(inst, sol))


def test_infeasible_supply_errors_clearly(params):
    with pytest.raises(InfeasibleError, match="Need 1,000.0 kt"):
        solve(tiny(params, demand=200, supply=(400, 400)))


def test_infeasible_capacity_reports_iis(params):
    # Enough supply but only one Small refinery allowed: 1000 kt intake > 500 capacity.
    with pytest.raises(InfeasibleError) as e:
        solve(
            tiny(params, demand=200, supply=(600, 600)),
            SolveOptions(n_refineries={"Small": 1, "Large": 0}),
        )
    assert e.value.reasons


def test_capacity_off_collapses_to_one_refinery(params):
    big = replace(params.refineries["Large"], capacity_kt=1e6)
    p = replace(
        params,
        refineries={"Large": big},
        depots={"Large": replace(params.depots["Large"], capacity_kt=1e6)},
    )
    farms = [farm(i, 300, 0.3 * i, 110 + 0.3 * i) for i in range(6)]
    airports = [Airport("AAA", "A", 0, 110, 150), Airport("BBB", "B", 1.5, 111.5, 150)]
    inst = Instance(farms, [(f.lat, f.lon) for f in farms], airports, p)
    sol = solve(inst)
    assert len(sol.refineries) == 1
    validate(inst, sol)


def test_forced_counts_and_fixed_sites(params):
    inst = tiny(params)
    sol = solve(inst, SolveOptions(n_refineries={"Large": 1, "Small": 0}))
    assert [s for s, _ in sol.refineries.values()] == ["Large"]
    sol = solve(inst, SolveOptions(fixed_sites={1: "Small"}))
    assert set(sol.refineries) == {1}
    validate(inst, sol)


def test_demand_ge_mode(params):
    inst = tiny(params)
    sol = solve(inst, SolveOptions(demand="ge"))
    assert check(inst, sol, demand="ge") == []

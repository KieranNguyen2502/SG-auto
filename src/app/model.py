"""SAF network MILP (gurobipy). Units: kt and US$M. See docs/PLAN.md "Model spec".

Depots are co-located with refineries (docs/DECISIONS.md), so each candidate cell is a hub:
at most one refinery plus an integer number of depots per size; depot->refinery is 0 km.
Only this module imports gurobipy, so another solver can replace it behind solve().
"""

import math
from dataclasses import dataclass, field

import numpy as np

from app.data import Airport, Farm, Params
from app.distances import farm_cell_arcs, road_km

USD_PER_MUSD = 1e6
T_PER_KT = 1e3


class InfeasibleError(RuntimeError):
    """No plan meets demand. `reasons` lists the IIS constraint names when available."""

    def __init__(self, msg: str, reasons: list[str] | None = None):
        super().__init__(msg)
        self.reasons = reasons or []


class SolverError(RuntimeError):
    """Solver failed without a usable solution (licence, time limit, ...)."""


@dataclass
class Instance:
    farms: list[Farm]
    cells: np.ndarray  # (n_cells, 2) lat, lon
    airports: list[Airport]
    params: Params
    max_haul_km: float | None = None
    d_fc: np.ndarray = field(init=False)  # road km farm -> cell
    d_ca: np.ndarray = field(init=False)  # road km cell -> airport (barge uses the same distance)
    arcs: list[tuple[int, int]] = field(init=False)

    def __post_init__(self):
        self.cells = np.asarray(self.cells, float).reshape(-1, 2)
        rf = self.params.road_factor
        farm_pts = [(f.lat, f.lon) for f in self.farms]
        ap_pts = [(a.lat, a.lon) for a in self.airports]
        self.d_fc = road_km(farm_pts, self.cells, rf)
        self.d_ca = road_km(self.cells, ap_pts, rf)
        self.arcs = farm_cell_arcs(self.d_fc, self.max_haul_km)


@dataclass
class SolveOptions:
    demand: str = "eq"  # "eq" or "ge"
    n_refineries: dict[str, int] | None = None  # force counts per size
    fixed_sites: dict[int, str] | None = None  # cell -> refinery size; only these cells are used
    mip_gap: float = 1e-4
    time_limit_s: float = 900
    log_file: str | None = None
    verbose: bool = False
    gurobi_params: dict | None = None  # passed through, e.g. {"Threads": 8, "MIPFocus": 2}


@dataclass
class Solution:
    status: str
    objective_musd: float
    mip_gap: float
    runtime_s: float
    refineries: dict[int, tuple[str, float]]  # cell -> (size, intake kt)
    depots: dict[int, dict[str, tuple[int, float]]]  # cell -> size -> (count, throughput kt)
    farm_flows: dict[tuple[int, int], float]  # (farm, cell) -> kt biomass
    saf_flows: dict[tuple[int, int], float]  # (cell, airport) -> kt SAF


def _pre_check(inst: Instance) -> None:
    p = inst.params
    need = sum(a.demand_kt for a in inst.airports) / p.yield_
    reachable = {j for j, _ in inst.arcs}
    have = sum(inst.farms[j].supply_kt for j in reachable)
    if have + 1e-9 < need:
        raise InfeasibleError(
            f"Need {need:,.1f} kt biomass for demand but only {have:,.1f} kt is reachable "
            f"(total supply {sum(f.supply_kt for f in inst.farms):,.1f} kt)."
        )


def solve(inst: Instance, opts: SolveOptions | None = None) -> Solution:
    import gurobipy as gp
    from gurobipy import GRB

    opts = opts or SolveOptions()
    if opts.demand not in ("eq", "ge"):
        raise ValueError("demand must be 'eq' or 'ge'")
    _pre_check(inst)
    p = inst.params
    na = len(inst.airports)
    if opts.fixed_sites is not None:
        unknown = set(opts.fixed_sites.values()) - set(p.refineries)
        if unknown:
            raise ValueError(f"unknown refinery sizes {unknown}")
        cells = sorted(opts.fixed_sites)
    else:
        cells = list(range(len(inst.cells)))
    cell_set = set(cells)
    arcs = [(j, i) for j, i in inst.arcs if i in cell_set]
    rsz, dsz = list(p.refineries), list(p.depots)

    c_in = p.legs["farm_depot"].cost_usd_per_tkm * T_PER_KT / USD_PER_MUSD
    c_out = p.legs["refinery_airport"].cost_usd_per_tkm * T_PER_KT / USD_PER_MUSD

    def fixed(f):
        return p.annual_fixed_usd(f) / USD_PER_MUSD

    def var(f):
        return f.var_opex_usd_per_t * T_PER_KT / USD_PER_MUSD

    env = gp.Env(empty=True)
    env.setParam("OutputFlag", 1 if (opts.verbose or opts.log_file) else 0)
    env.setParam("LogToConsole", 1 if opts.verbose else 0)
    if opts.log_file:
        env.setParam("LogFile", opts.log_file)
    try:
        env.start()
    except gp.GurobiError as e:
        raise SolverError(f"Gurobi could not start: {e}") from e

    with env, gp.Model("saf", env=env) as m:
        x = m.addVars(arcs, name="x")
        y = m.addVars(cells, range(na), name="y")
        R = m.addVars(cells, rsz, vtype=GRB.BINARY, name="R")
        q = m.addVars(cells, rsz, name="q")
        N = m.addVars(cells, dsz, vtype=GRB.INTEGER, name="N")
        P = m.addVars(cells, dsz, name="P")
        for i in cells:
            for s in dsz:
                N[i, s].UB = p.depots[s].max_per_cell

        into: dict[int, list[int]] = {i: [] for i in cells}
        out_of: dict[int, list[int]] = {}
        for j, i in arcs:
            into[i].append(j)
            out_of.setdefault(j, []).append(i)

        for j, cs in out_of.items():
            m.addConstr(
                gp.quicksum(x[j, i] for i in cs) <= inst.farms[j].supply_kt,
                name=f"supply[{inst.farms[j].id}]",
            )
        for i in cells:
            intake = gp.quicksum(x[j, i] for j in into[i])
            m.addConstr(intake == q.sum(i, "*"), name=f"refinery_in[{i}]")
            m.addConstr(intake == P.sum(i, "*"), name=f"depot_in[{i}]")
            m.addConstr(y.sum(i, "*") == p.yield_ * intake, name=f"yield[{i}]")
            m.addConstr(R.sum(i, "*") <= 1, name=f"one_refinery[{i}]")
            for s in rsz:
                m.addConstr(q[i, s] <= p.refineries[s].capacity_kt * R[i, s], name=f"rcap[{i},{s}]")
            for s in dsz:
                m.addConstr(P[i, s] <= p.depots[s].capacity_kt * N[i, s], name=f"dcap[{i},{s}]")
            open_i = R.sum(i, "*")
            for j in into[i]:  # strengthening cut
                m.addConstr(x[j, i] <= inst.farms[j].supply_kt * open_i, name=f"cut[{j},{i}]")
        for a, ap in enumerate(inst.airports):
            lhs = y.sum("*", a)
            if opts.demand == "eq":
                m.addConstr(lhs == ap.demand_kt, name=f"demand[{ap.iata}]")
            else:
                m.addConstr(lhs >= ap.demand_kt, name=f"demand[{ap.iata}]")
        # Valid cut: each refinery takes at most the largest capacity.
        need = sum(a.demand_kt for a in inst.airports) / p.yield_
        max_cap = max(f.capacity_kt for f in p.refineries.values())
        m.addConstr(R.sum() >= math.ceil(need / max_cap - 1e-9), name="min_refineries")
        if opts.n_refineries:
            for s, n in opts.n_refineries.items():
                m.addConstr(R.sum("*", s) == n, name=f"count[{s}]")
        if opts.fixed_sites is not None:
            for i, s in opts.fixed_sites.items():
                R[i, s].LB = 1

        m.setObjective(
            gp.quicksum(c_in * inst.d_fc[j, i] * x[j, i] for j, i in arcs)
            + gp.quicksum(c_out * inst.d_ca[i, a] * y[i, a] for i in cells for a in range(na))
            + gp.quicksum(
                fixed(p.refineries[s]) * R[i, s] + var(p.refineries[s]) * q[i, s]
                for i in cells
                for s in rsz
            )
            + gp.quicksum(
                fixed(p.depots[s]) * N[i, s] + var(p.depots[s]) * P[i, s]
                for i in cells
                for s in dsz
            ),
            GRB.MINIMIZE,
        )
        m.Params.MIPGap = opts.mip_gap
        m.Params.TimeLimit = opts.time_limit_s
        for k, v in (opts.gurobi_params or {}).items():
            m.setParam(k, v)

        try:
            m.optimize()
        except gp.GurobiError as e:
            hint = (
                " (size-limited pip licence: install an academic licence)"
                if e.errno == 10010
                else ""
            )
            raise SolverError(f"Gurobi error {e.errno}: {e}{hint}") from e

        if m.Status in (GRB.INFEASIBLE, GRB.INF_OR_UNBD):
            m.computeIIS()
            reasons = [c.ConstrName for c in m.getConstrs() if c.IISConstr]
            raise InfeasibleError("Model is infeasible; IIS: " + ", ".join(reasons[:20]), reasons)
        if m.SolCount == 0:
            raise SolverError(f"No solution found (Gurobi status {m.Status})")

        status = {GRB.OPTIMAL: "optimal", GRB.TIME_LIMIT: "time_limit"}.get(m.Status, str(m.Status))
        eps = 1e-7
        refineries = {}
        depots = {}
        for i in cells:
            for s in rsz:
                if R[i, s].X > 0.5:
                    refineries[i] = (s, q.sum(i, "*").getValue())
            per = {s: (round(N[i, s].X), P[i, s].X) for s in dsz if round(N[i, s].X) > 0}
            if per:
                depots[i] = per
        return Solution(
            status=status,
            objective_musd=m.ObjVal,
            mip_gap=m.MIPGap,
            runtime_s=m.Runtime,
            refineries=refineries,
            depots=depots,
            farm_flows={k: v.X for k, v in x.items() if eps < v.X},
            saf_flows={k: v.X for k, v in y.items() if eps < v.X},
        )

"""Recompute constraints and the yearly cost from a solution, independently of the solver."""

from collections import defaultdict

from app.model import USD_PER_MUSD, Instance, Solution

TOL_KT = 1e-4


class ValidationError(AssertionError):
    pass


def cost_breakdown(inst: Instance, sol: Solution) -> dict[str, float]:
    """Yearly cost in USD by component. Depot->refinery is 0 km (co-located), so it costs 0."""
    p = inst.params
    years, frac = p.capex_years, p.fixed_opex_frac
    c = defaultdict(float)
    for size, intake_kt in sol.refineries.values():
        f = p.refineries[size]
        c["refinery_capex"] += f.capex_usd / years
        c["refinery_fixed_opex"] += frac * f.capex_usd
        c["refinery_var_opex"] += f.var_opex_usd_per_t * intake_kt * 1e3
    for per in sol.depots.values():
        for size, (n, thru_kt) in per.items():
            f = p.depots[size]
            c["depot_capex"] += n * f.capex_usd / years
            c["depot_fixed_opex"] += n * frac * f.capex_usd
            c["depot_var_opex"] += f.var_opex_usd_per_t * thru_kt * 1e3
    leg_in = p.legs["farm_depot"].cost_usd_per_tkm
    leg_out = p.legs["refinery_airport"].cost_usd_per_tkm
    for (j, i), kt in sol.farm_flows.items():
        c["transport_farm_depot"] += leg_in * kt * 1e3 * inst.d_fc[j, i]
    c["transport_depot_refinery"] += 0.0
    for (i, a), kt in sol.saf_flows.items():
        c["transport_refinery_airport"] += leg_out * kt * 1e3 * inst.d_ca[i, a]
    out = dict(c)
    out["total"] = sum(c.values())
    return out


def check(inst: Instance, sol: Solution, demand: str = "eq") -> list[str]:
    """Return a list of violated constraints (empty if the plan is feasible)."""
    p = inst.params
    errs = []
    arcs = set(inst.arcs)
    used = defaultdict(float)
    intake = defaultdict(float)
    for (j, i), kt in sol.farm_flows.items():
        if (j, i) not in arcs:
            errs.append(f"flow on pruned arc farm {inst.farms[j].id} -> cell {i}")
        if kt < -TOL_KT:
            errs.append(f"negative flow farm {j} -> cell {i}")
        used[j] += kt
        intake[i] += kt
    for j, kt in used.items():
        if kt > inst.farms[j].supply_kt + TOL_KT:
            errs.append(
                f"farm {inst.farms[j].id} ships {kt:.3f} > supply {inst.farms[j].supply_kt}"
            )
    saf_out = defaultdict(float)
    saf_in = defaultdict(float)
    for (i, a), kt in sol.saf_flows.items():
        saf_out[i] += kt
        saf_in[a] += kt
    for i in set(intake) | set(saf_out) | set(sol.refineries) | set(sol.depots):
        kt = intake.get(i, 0.0)
        if kt > TOL_KT and i not in sol.refineries:
            errs.append(f"cell {i} receives {kt:.3f} kt but has no refinery")
        if i in sol.refineries:
            size, q = sol.refineries[i]
            if abs(q - kt) > TOL_KT:
                errs.append(f"cell {i} refinery intake {q:.3f} != inflow {kt:.3f}")
            if q > p.refineries[size].capacity_kt + TOL_KT:
                errs.append(
                    f"cell {i} refinery over capacity: {q:.3f} > {p.refineries[size].capacity_kt}"
                )
        per = sol.depots.get(i, {})
        thru = sum(t for _, t in per.values())
        if abs(thru - kt) > TOL_KT:
            errs.append(f"cell {i} depot throughput {thru:.3f} != inflow {kt:.3f}")
        for size, (n, t) in per.items():
            f = p.depots[size]
            if n > f.max_per_cell or t > n * f.capacity_kt + TOL_KT:
                errs.append(f"cell {i} depots {size}: {n} units, {t:.3f} kt over limit")
        if abs(saf_out.get(i, 0.0) - p.yield_ * kt) > TOL_KT:
            errs.append(f"cell {i} SAF out {saf_out.get(i, 0.0):.3f} != yield x {kt:.3f}")
    for a, ap in enumerate(inst.airports):
        got = saf_in.get(a, 0.0)
        short = got < ap.demand_kt - TOL_KT
        over = demand == "eq" and got > ap.demand_kt + TOL_KT
        if short or over:
            errs.append(f"airport {ap.iata} receives {got:.3f} kt SAF, demand {ap.demand_kt}")
    return errs


def validate(inst: Instance, sol: Solution, demand: str = "eq", rel_tol: float = 1e-6) -> dict:
    """Raise ValidationError on any violation or cost mismatch; return the USD cost breakdown."""
    errs = check(inst, sol, demand)
    costs = cost_breakdown(inst, sol)
    obj_usd = sol.objective_musd * USD_PER_MUSD
    if abs(costs["total"] - obj_usd) > max(rel_tol * abs(obj_usd), 1e3):
        errs.append(f"recomputed cost {costs['total']:,.0f} USD != objective {obj_usd:,.0f} USD")
    if errs:
        raise ValidationError("; ".join(errs))
    return costs

"""Independent test runner for the baseline equations; not a deliverable."""

import argparse
import importlib.util
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("baseline", ROOT / "saf_baseline.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def run(args):
    farms, airports = b.load_farms(), b.load_airports()
    cells = b.build_candidates(farms, airports, args.farms_only)
    d_fc = {
        (j, i): b.haversine_km(f["lat"], f["lon"], *p) * b.ROAD_FACTOR
        for j, f in enumerate(farms)
        for i, p in enumerate(cells)
        if b.haversine_km(f["lat"], f["lon"], *p) * b.ROAD_FACTOR <= args.max_haul_km
    }
    d_ca = {
        (i, a): b.haversine_km(*p, ap["lat"], ap["lon"]) * b.ROAD_FACTOR
        for i, p in enumerate(cells)
        for a, ap in enumerate(airports)
    }
    cost, upper, integer = [], [], []
    names = []

    def variable(name, c=0, ub=math.inf, is_int=0):
        k = len(cost)
        names.append(name)
        cost.append(c)
        upper.append(ub)
        integer.append(is_int)
        return k

    x = {k: variable(("x", *k), b.LEGS["farm_depot"][0] * 0.001 * d) for k, d in d_fc.items()}
    y = {k: variable(("y", *k), b.LEGS["refinery_airport"][0] * 0.001 * d) for k, d in d_ca.items()}
    R, q, N, P = {}, {}, {}, {}
    for i in range(len(cells)):
        for s, (capex, _cap, var, _mx) in b.REFINERIES.items():
            R[i, s] = variable(("R", i, s), b.annual_fixed_usd(capex) / 1e6, 1, 1)
            q[i, s] = variable(("q", i, s), var * 0.001)
        for s, (capex, _cap, var, mx) in b.DEPOTS.items():
            N[i, s] = variable(("N", i, s), b.annual_fixed_usd(capex) / 1e6, mx, 1)
            P[i, s] = variable(("P", i, s), var * 0.001)

    rr, cc, vv, lo, hi, row_names = [], [], [], [], [], []

    def row(name, terms, lower=-math.inf, upper=math.inf):
        k = len(lo)
        row_names.append(name)
        for col, value in terms:
            rr.append(k)
            cc.append(col)
            vv.append(value)
        lo.append(lower)
        hi.append(upper)

    into, from_farm = defaultdict(list), defaultdict(list)
    for j, i in x:
        into[i].append(j)
        from_farm[j].append(i)
    for j, f in enumerate(farms):
        row(("supply", j), [(x[j, i], 1) for i in from_farm[j]], upper=f["kt"])
    for i in range(len(cells)):
        incoming = [(x[j, i], 1) for j in into[i]]
        row(("refinery_in", i), incoming + [(q[i, s], -1) for s in b.REFINERIES], 0, 0)
        row(("depot_in", i), incoming + [(P[i, s], -1) for s in b.DEPOTS], 0, 0)
        row(
            ("yield", i),
            [(y[i, a], 1) for a in range(len(airports))] + [(x[j, i], -b.YIELD) for j in into[i]],
            0,
            0,
        )
        row(("one_refinery", i), [(R[i, s], 1) for s in b.REFINERIES], upper=1)
        for s, (_, cap, _, _) in b.REFINERIES.items():
            row(("rcap", i, s), [(q[i, s], 1), (R[i, s], -cap)], upper=0)
        for s, (_, cap, _, _) in b.DEPOTS.items():
            row(("dcap", i, s), [(P[i, s], 1), (N[i, s], -cap)], upper=0)
        for j in into[i]:
            row(
                ("cut", j, i),
                [(x[j, i], 1)] + [(R[i, s], -farms[j]["kt"]) for s in b.REFINERIES],
                upper=0,
            )
    for a, ap in enumerate(airports):
        row(("demand", a), [(y[i, a], 1) for i in range(len(cells))], ap["demand"], ap["demand"])
    need = sum(ap["demand"] for ap in airports) / b.YIELD
    row("min_refineries", [(col, 1) for col in R.values()], math.ceil(need / 1087 - 1e-9))
    if args.n_large is not None:
        row("count_L", [(R[i, "Large"], 1) for i in range(len(cells))], args.n_large, args.n_large)
    if args.n_small is not None:
        row("count_S", [(R[i, "Small"], 1) for i in range(len(cells))], args.n_small, args.n_small)
    mat = coo_array(
        (vv, (np.asarray(rr, dtype=np.int32), np.asarray(cc, dtype=np.int32))),
        shape=(len(lo), len(cost)),
    ).tocsc()
    print(f"{len(cells)} cells, {len(x)} arcs, {len(cost)} variables, {len(lo)} rows", flush=True)
    t0 = time.perf_counter()
    res = milp(
        np.asarray(cost),
        integrality=np.asarray(integer),
        bounds=Bounds(np.zeros(len(cost)), np.asarray(upper)),
        constraints=LinearConstraint(mat, np.asarray(lo), np.asarray(hi)),
        options={"time_limit": args.time_limit, "mip_rel_gap": args.mip_gap, "disp": True},
    )
    elapsed = time.perf_counter() - t0
    print(res.message, flush=True)
    if res.x is None:
        raise RuntimeError("No incumbent")
    values = res.x
    # Independently verify the full original matrix, bounds, and integer variables.
    acts = mat @ values
    residual = max(0.0, float(np.max(np.asarray(lo) - acts)), float(np.max(acts - np.asarray(hi))))
    violation = max(0.0, float(np.max(-values)), float(np.max(values - np.asarray(upper))))
    int_error = max(abs(values[k] - round(values[k])) for k, flag in enumerate(integer) if flag)
    ok = residual <= 1e-4 and violation <= 1e-4 and int_error <= 1e-5
    assert ok, (residual, violation, int_error)
    sol = {
        "status": "optimal" if res.status == 0 else "time_limit",
        "objective_musd": float(res.fun),
        "best_bound_musd": float(res.mip_dual_bound),
        "absolute_gap_musd": max(0.0, float(res.fun - res.mip_dual_bound)),
        "mip_gap": float(res.mip_gap),
        "runtime_s": elapsed,
        "solver": "SciPy/HiGHS",
        "solver_version": f"SciPy {scipy.__version__}; HiGHS version in the solver log",
        "node_count": int(res.mip_node_count),
        "n_variables": len(cost),
        "n_constraints": len(lo),
        "refineries": {},
        "depots": {},
        "farm_flows": {k: float(values[col]) for k, col in x.items() if values[col] > 1e-7},
        "saf_flows": {k: float(values[col]) for k, col in y.items() if values[col] > 1e-7},
    }
    for i in range(len(cells)):
        for s in b.REFINERIES:
            if values[R[i, s]] > 0.5:
                sol["refineries"][i] = (s, float(sum(values[q[i, z]] for z in b.REFINERIES)))
        per = {
            s: (round(values[N[i, s]]), float(values[P[i, s]]))
            for s in b.DEPOTS
            if values[N[i, s]] > 0.5
        }
        if per:
            sol["depots"][i] = per
    costs, errors = b.cost_and_check(farms, airports, sol, d_fc, d_ca)
    assert not errors, errors
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = b.write_report(
        farms,
        airports,
        cells,
        sol,
        d_fc,
        d_ca,
        costs,
        out,
        {
            "args": vars(args),
            "n_cells": len(cells),
            "n_arcs": len(x),
            "test_matrix_max_residual": residual,
            "test_bounds_max_violation": violation,
            "test_integrality_max_error": int_error,
        },
    )
    (out / "raw_solution.json").write_text(
        json.dumps(
            {
                "cells": cells,
                "sol": {k: list(v.items()) if isinstance(v, dict) else v for k, v in sol.items()},
            },
            indent=2,
        )
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--farms-only", action="store_true")
    ap.add_argument("--max-haul-km", type=float, default=400)
    ap.add_argument("--time-limit", type=float, default=900)
    ap.add_argument("--mip-gap", type=float, default=0.0001)
    ap.add_argument("--n-large", type=int)
    ap.add_argument("--n-small", type=int)
    ap.add_argument("--out", default=str(ROOT / "tmp/baseline_highs"))
    run(ap.parse_args())

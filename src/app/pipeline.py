"""End-to-end run: config -> data -> candidates -> MILP -> validate -> report."""

import time
from dataclasses import dataclass
from pathlib import Path

from app.candidates import build_candidates
from app.data import load_airports, load_config, load_farms, load_params
from app.model import Instance, Solution, SolveOptions, solve
from app.report import write_report
from app.validate import validate


@dataclass
class RunResult:
    instance: Instance
    solution: Solution
    costs: dict
    out_dir: Path


def build_instance(cfg: dict) -> Instance:
    params = load_params(cfg)
    farms = load_farms(cfg["data"]["farms_csv"])
    ap_cfg = cfg["airports"]
    airports = load_airports(
        cfg["data"]["airports_dat"], ap_cfg["demand_kt"], ap_cfg.get("barge", [])
    )
    cells = build_candidates(
        [(f.lat, f.lon) for f in farms],
        [(a.lat, a.lon) for a in airports],
        cfg.get("candidates", {}),
    )
    return Instance(farms, cells, airports, params, cfg.get("model", {}).get("max_haul_km"))


def solve_options(cfg: dict, log_file: str | None = None, verbose: bool = False) -> SolveOptions:
    m = cfg.get("model", {})
    return SolveOptions(
        demand=m.get("demand", "eq"),
        n_refineries=m.get("n_refineries"),
        mip_gap=float(m.get("mip_gap", 1e-4)),
        time_limit_s=float(m.get("time_limit_s", 900)),
        log_file=log_file,
        verbose=verbose,
        gurobi_params=m.get("gurobi"),
    )


def run(cfg: dict | str | Path, run_id: str | None = None, verbose: bool = False) -> RunResult:
    if not isinstance(cfg, dict):
        cfg = load_config(cfg)
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = Path(cfg.get("output", {}).get("dir", "outputs")) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    inst = build_instance(cfg)
    if verbose:
        print(
            f"{len(inst.farms)} farms, {len(inst.cells)} candidate cells, "
            f"{len(inst.arcs)} farm->cell arcs, {len(inst.airports)} airports"
        )
    opts = solve_options(cfg, log_file=str(out_dir / "gurobi.log"), verbose=verbose)
    sol = solve(inst, opts)
    costs = validate(inst, sol, opts.demand)
    meta = {
        "run_id": run_id,
        "n_farms": len(inst.farms),
        "n_cells": len(inst.cells),
        "n_arcs": len(inst.arcs),
    }
    write_report(inst, sol, costs, out_dir, meta)
    return RunResult(inst, sol, costs, out_dir)

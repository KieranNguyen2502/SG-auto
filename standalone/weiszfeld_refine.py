#!/usr/bin/env python3
"""Weiszfeld refinement of an existing saf_solve.py result (experiment, not part of the main solve).

Starts from a solved plan (default outputs/full-hanan-900s/), keeps the number of hubs, and
alternates two steps until the yearly cost stops falling:

  A. move   - with each hub's farms/airports fixed, move the hub to the point minimising its
              transport cost  sum_k w_k * d(hub, p_k)  (weighted Fermat-Weber), solved by
              Weiszfeld iteration with the Vardi-Zhang fix for landing on a point.
              Weights: farm  w = 0.10 USD/t-km x 1.3 x tonnes in,
                       airport w = 0.08 USD/t-km x 1.3 x tonnes SAF out.
  B. re-solve - with the hub coordinates fixed, re-optimise flows, refinery sizes and depot
              counts (saf_solve's MILP on just these sites; ~560 variables, fits the pip licence).

Round 0 re-solves B at the *original* sites first, so the report separates "better flows on the
same sites" from "better sites". A move is kept only if the exact cost (great-circle x 1.3)
drops. Facility costs do not depend on location, so all of the change is transport.

    python standalone/weiszfeld_refine.py
    python standalone/weiszfeld_refine.py --base outputs/full-hanan-900s --out outputs/wz

Needs gurobipy and saf_solve.py in the same folder. No land mask: moved hubs report
nearest_farm_km; check them.
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saf_solve as S  # noqa: E402

KM_PER_DEG = math.radians(1.0) * S.EARTH_RADIUS_KM


# ----------------------------------------------------------------------------- plan I/O
def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_plan(base: Path, farms, airports):
    """Hubs in H1..Hn order and their flows, from a saf_solve output folder."""
    fac = read_csv(base / "facilities.csv")
    hubs = [
        (r["hub"], float(r["lat"]), float(r["lon"])) for r in fac if r["facility"] == "refinery"
    ]
    hubs.sort(key=lambda h: int(h[0][1:]))
    hub_ix = {h[0]: i for i, h in enumerate(hubs)}
    farm_ix = {f["id"]: j for j, f in enumerate(farms)}
    ap_ix = {a["iata"]: k for k, a in enumerate(airports)}
    farm_flows = {
        (farm_ix[r["farm_id"]], hub_ix[r["hub"]]): float(r["kt"])
        for r in read_csv(base / "flows_farm_depot.csv")
    }
    saf_flows = {
        (hub_ix[r["refinery_unit"][:-2]], ap_ix[r["airport"]]): float(r["kt_saf"])
        for r in read_csv(base / "flows_refinery_airport.csv")
    }
    costs = json.loads((base / "costs.json").read_text(encoding="utf-8"))
    return [(la, lo) for _, la, lo in hubs], farm_flows, saf_flows, costs


# ----------------------------------------------------------------------------- costs
def road_km(a, b):
    return S.haversine_km(a[0], a[1], b[0], b[1]) * S.ROAD_FACTOR


def transport_usd(cells, farms, airports, farm_flows, saf_flows):
    c_in, c_out = S.LEGS["farm_depot"][0], S.LEGS["refinery_airport"][0]
    t_in = sum(
        c_in * kt * 1e3 * road_km((farms[j]["lat"], farms[j]["lon"]), cells[i])
        for (j, i), kt in farm_flows.items()
    )
    t_out = sum(
        c_out * kt * 1e3 * road_km(cells[i], (airports[a]["lat"], airports[a]["lon"]))
        for (i, a), kt in saf_flows.items()
    )
    return t_in, t_out


def hub_anchors(i, farms, airports, farm_flows, saf_flows):
    """(lat, lon, weight in USD per great-circle km) for every farm and airport hub i serves."""
    c_in, c_out = S.LEGS["farm_depot"][0], S.LEGS["refinery_airport"][0]
    pts = [
        (farms[j]["lat"], farms[j]["lon"], c_in * kt * 1e3 * S.ROAD_FACTOR)
        for (j, h), kt in farm_flows.items()
        if h == i
    ]
    pts += [
        (airports[a]["lat"], airports[a]["lon"], c_out * kt * 1e3 * S.ROAD_FACTOR)
        for (h, a), kt in saf_flows.items()
        if h == i
    ]
    return pts


def hub_cost(pt, anchors):
    return sum(w * S.haversine_km(pt[0], pt[1], la, lo) for la, lo, w in anchors)


# ----------------------------------------------------------------------------- Weiszfeld
def weiszfeld(start, anchors, tol_km=1e-4, max_iter=2000):
    """Weighted Fermat-Weber point. Iterates in a local km plane re-centred on the current point
    (keeps projection error negligible), with Vardi-Zhang when the point sits on an anchor."""
    lat, lon = start
    for it in range(max_iter):
        k_lon = KM_PER_DEG * math.cos(math.radians(lat))
        xy = [((lo - lon) * k_lon, (la - lat) * KM_PER_DEG, w) for la, lo, w in anchors]
        num_x = num_y = den = 0.0
        on_anchor_w = 0.0
        for x, y, w in xy:
            d = math.hypot(x, y)
            if d < 1e-9:
                on_anchor_w += w
                continue
            num_x += w * x / d
            num_y += w * y / d
            den += w / d
        if den == 0.0:
            break
        tx, ty = num_x / den, num_y / den  # Weiszfeld step from current point (origin)
        if on_anchor_w > 0.0:  # Vardi-Zhang: stay if the anchor's weight beats the pull
            r = math.hypot(num_x, num_y)
            if r <= on_anchor_w:
                break
            f = 1.0 - on_anchor_w / r
            tx, ty = f * tx, f * ty
        lat, lon = lat + ty / KM_PER_DEG, lon + tx / k_lon
        if math.hypot(tx, ty) < tol_km:
            return (lat, lon), it + 1
    return (lat, lon), it + 1


def move_hubs(cells, farms, airports, farm_flows, saf_flows):
    """Step A. Returns new cells (each kept only if its exact cost drops) and km moved."""
    new, moved = [], []
    for i, c in enumerate(cells):
        anchors = hub_anchors(i, farms, airports, farm_flows, saf_flows)
        cand, _ = weiszfeld(c, anchors)
        if hub_cost(cand, anchors) < hub_cost(c, anchors) - 1e-6:
            new.append(cand)
            moved.append(S.haversine_km(c[0], c[1], cand[0], cand[1]))
        else:
            new.append(c)
            moved.append(0.0)
    return new, moved


# ----------------------------------------------------------------------------- re-solve
def resolve(cells, farms, airports, out: Path, max_haul_km):
    """Step B: saf_solve's MILP with the candidate set = these hub coordinates only."""
    import gurobipy as gp

    gp.setParam("LogToConsole", 0)
    args = SimpleNamespace(
        max_haul_km=max_haul_km,
        mip_gap=1e-6,
        time_limit=300,
        out=str(out),
        threads=0,
        mipfocus=None,
        demand="eq",
        n_large=None,
        n_small=None,
    )
    sol, d_fc, d_ca = S.solve(farms, airports, cells, args)
    costs, errs = S.cost_and_check(farms, airports, sol, d_fc, d_ca)
    if errs:
        sys.exit("VALIDATION FAILED: " + "; ".join(errs))
    return sol, d_fc, d_ca, costs


def flows_of(sol):
    return dict(sol["farm_flows"]), dict(sol["saf_flows"])


# ----------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", default="outputs/full-hanan-900s", help="saf_solve output folder")
    ap.add_argument("--out", default="outputs/weiszfeld-refined", help="output folder")
    ap.add_argument("--rounds", type=int, default=20, help="max move/re-solve rounds")
    ap.add_argument("--max-haul-km", type=float, default=400, help="same pruning as the base run")
    args = ap.parse_args(argv)

    base, out = Path(args.base), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    farms, airports = S.load_farms(), S.load_airports()
    cells0, ff0, sf0, base_costs = load_plan(base, farms, airports)
    base_total = base_costs["costs_usd"]["total"]
    fixed_usd = (
        base_total
        - base_costs["costs_usd"]["transport_farm_depot"]
        - base_costs["costs_usd"]["transport_refinery_airport"]
    )

    # Sanity: recomputing the base plan's transport from its CSVs must match costs.json.
    t_in, t_out = transport_usd(cells0, farms, airports, ff0, sf0)
    drift = abs(
        t_in
        + t_out
        - base_costs["costs_usd"]["transport_farm_depot"]
        - base_costs["costs_usd"]["transport_refinery_airport"]
    )
    print(
        f"base {base}: total ${base_total / 1e6:,.3f}M, transport recomputed "
        f"${(t_in + t_out) / 1e6:,.3f}M (drift ${drift:,.0f} from CSV rounding)"
    )

    log = [
        {
            "round": "base",
            "step": "time-limited MILP",
            "total_usd": base_total,
            "transport_usd": t_in + t_out,
            "facility_usd": fixed_usd,
            "max_move_km": 0.0,
        }
    ]

    # Round 0: best flows/sizes/depots on the ORIGINAL sites.
    sol, d_fc, d_ca, costs = resolve(cells0, farms, airports, out, args.max_haul_km)
    best = {"cells": cells0, "sol": sol, "d_fc": d_fc, "d_ca": d_ca, "costs": costs}
    log.append(
        {
            "round": 0,
            "step": "re-solve flows, same sites",
            "total_usd": costs["total"],
            "transport_usd": costs["transport_farm_depot"] + costs["transport_refinery_airport"],
            "facility_usd": costs["total"]
            - costs["transport_farm_depot"]
            - costs["transport_refinery_airport"],
            "max_move_km": 0.0,
        }
    )
    resolved_same_sites = costs["total"]

    cells = cells0
    for rnd in range(1, args.rounds + 1):
        ff, sf = flows_of(best["sol"])
        moved_cells, moved = move_hubs(cells, farms, airports, ff, sf)
        t_in, t_out = transport_usd(moved_cells, farms, airports, ff, sf)
        fac_usd = (
            best["costs"]["total"]
            - best["costs"]["transport_farm_depot"]
            - best["costs"]["transport_refinery_airport"]
        )
        log.append(
            {
                "round": rnd,
                "step": "A: Weiszfeld move, flows fixed",
                "total_usd": fac_usd + t_in + t_out,
                "transport_usd": t_in + t_out,
                "facility_usd": fac_usd,
                "max_move_km": max(moved),
            }
        )
        sol, d_fc, d_ca, costs = resolve(moved_cells, farms, airports, out, args.max_haul_km)
        log.append(
            {
                "round": rnd,
                "step": "B: re-solve flows, new sites",
                "total_usd": costs["total"],
                "transport_usd": costs["transport_farm_depot"]
                + costs["transport_refinery_airport"],
                "facility_usd": costs["total"]
                - costs["transport_farm_depot"]
                - costs["transport_refinery_airport"],
                "max_move_km": max(moved),
            }
        )
        gain = best["costs"]["total"] - costs["total"]
        print(
            f"round {rnd}: ${costs['total'] / 1e6:,.4f}M  (gain ${gain / 1e6:,.4f}M, "
            f"max hub move {max(moved):.2f} km)"
        )
        if gain <= 1.0:  # USD; converged
            if gain > 0:
                best = {
                    "cells": moved_cells,
                    "sol": sol,
                    "d_fc": d_fc,
                    "d_ca": d_ca,
                    "costs": costs,
                }
            break
        cells = moved_cells
        best = {"cells": moved_cells, "sol": sol, "d_fc": d_fc, "d_ca": d_ca, "costs": costs}

    # Outputs: same files as saf_solve, plus the comparison.
    meta = {"refined_from": str(base), "rounds": rnd, "max_haul_km": args.max_haul_km}
    S.write_report(
        farms,
        airports,
        best["cells"],
        best["sol"],
        best["d_fc"],
        best["d_ca"],
        best["costs"],
        out,
        meta,
    )
    with open(out / "refine_log.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(log[0]))
        w.writeheader()
        w.writerows(log)

    hubs = []
    for k, (c0, c1) in enumerate(zip(cells0, best["cells"], strict=True), start=1):
        near = min(S.haversine_km(c1[0], c1[1], f["lat"], f["lon"]) for f in farms)
        hubs.append(
            {
                "hub": f"H{k}",
                "lat_before": c0[0],
                "lon_before": c0[1],
                "lat_after": round(c1[0], 5),
                "lon_after": round(c1[1], 5),
                "moved_km": round(S.haversine_km(c0[0], c0[1], c1[0], c1[1]), 2),
                "nearest_farm_km_after": round(near, 1),
            }
        )
    final = best["costs"]
    comparison = {
        "base_total_usd": base_total,
        "resolved_same_sites_usd": resolved_same_sites,
        "refined_total_usd": final["total"],
        "gain_from_reflow_usd": base_total - resolved_same_sites,
        "gain_from_weiszfeld_usd": resolved_same_sites - final["total"],
        "gain_total_usd": base_total - final["total"],
        "gain_total_pct": (base_total - final["total"]) / base_total * 100,
        "transport_before_usd": base_costs["costs_usd"]["transport_farm_depot"]
        + base_costs["costs_usd"]["transport_refinery_airport"],
        "transport_after_usd": final["transport_farm_depot"] + final["transport_refinery_airport"],
        "hubs": hubs,
    }
    (out / "refine_summary.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")

    m = 1e6
    print(f"\n{'':<34}{'$M / yr':>12}")
    print(f"{'base (time-limited MILP)':<34}{base_total / m:>12,.3f}")
    print(f"{'re-solved flows, same sites':<34}{resolved_same_sites / m:>12,.3f}")
    print(f"{'Weiszfeld-refined sites':<34}{final['total'] / m:>12,.3f}")
    print(f"{'  gain from re-flow':<34}{comparison['gain_from_reflow_usd'] / m:>12,.3f}")
    print(f"{'  gain from Weiszfeld':<34}{comparison['gain_from_weiszfeld_usd'] / m:>12,.3f}")
    print(
        f"{'  total gain':<34}{comparison['gain_total_usd'] / m:>12,.3f}"
        f"  ({comparison['gain_total_pct']:.3f}%)"
    )
    print(
        f"transport ${comparison['transport_before_usd'] / m:,.3f}M -> "
        f"${comparison['transport_after_usd'] / m:,.3f}M"
    )
    for h in hubs:
        flag = "  <- check land" if h["nearest_farm_km_after"] > 30 else ""
        print(
            f"  {h['hub']}: ({h['lat_before']:.4f}, {h['lon_before']:.4f}) -> "
            f"({h['lat_after']:.4f}, {h['lon_after']:.4f})  moved {h['moved_km']:.2f} km, "
            f"nearest farm {h['nearest_farm_km_after']:.1f} km{flag}"
        )
    print(f"outputs: {out.resolve()}")


if __name__ == "__main__":
    main()

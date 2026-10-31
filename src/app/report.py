"""Write a run's outputs: facilities, flows per leg (with trip counts), unused farms, costs."""

import csv
import json
import math
from pathlib import Path

from app.geo import pairwise_km
from app.model import Instance, Solution


def trips(kt: float, truck_t: float) -> int:
    """Truck trips per year to move kt (one-way, full loads)."""
    return math.ceil(round(kt * 1e3 / truck_t, 6)) if kt > 0 else 0


def site_ids(sol: Solution) -> dict[int, str]:
    """Stable hub names H1, H2, ... ordered by cell index."""
    return {i: f"H{k}" for k, i in enumerate(sorted(sol.refineries), start=1)}


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _r(v: float, nd: int = 3) -> float:
    return round(float(v), nd)


def write_report(inst: Instance, sol: Solution, costs: dict, out_dir: Path, meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = inst.params
    ids = site_ids(sol)
    farm_pts = [(f.lat, f.lon) for f in inst.farms]
    nearest_farm = pairwise_km(inst.cells[sorted(ids)], farm_pts).min(axis=1) if ids else []
    near = dict(zip(sorted(ids), nearest_farm, strict=True))

    rows = []
    for i, hub in ids.items():
        lat, lon = inst.cells[i]
        size, q = sol.refineries[i]
        cap = p.refineries[size].capacity_kt
        rows.append(
            [
                hub,
                "refinery",
                f"{hub}-R",
                size,
                _r(lat, 5),
                _r(lon, 5),
                _r(q),
                cap,
                _r(q / cap, 4),
                _r(near[i], 1),
            ]
        )
        for dsize, (n, thru) in sorted(sol.depots.get(i, {}).items()):
            dcap = p.depots[dsize].capacity_kt
            for k in range(1, n + 1):
                rows.append(
                    [
                        hub,
                        "depot",
                        f"{hub}-D{dsize[0]}{k}",
                        dsize,
                        _r(lat, 5),
                        _r(lon, 5),
                        _r(thru / n),
                        dcap,
                        _r(thru / n / dcap, 4),
                        _r(near[i], 1),
                    ]
                )
    _write(
        out_dir / "facilities.csv",
        [
            "hub",
            "facility",
            "unit_id",
            "size",
            "lat",
            "lon",
            "intake_kt",
            "capacity_kt",
            "utilisation",
            "nearest_farm_km",
        ],
        rows,
    )

    leg = p.legs["farm_depot"]
    rows = []
    for (j, i), kt in sorted(sol.farm_flows.items()):
        f, d = inst.farms[j], inst.d_fc[j, i]
        rows.append(
            [
                f.id,
                ids[i],
                _r(kt),
                _r(d, 2),
                _r(kt * 1e3 * d, 0),
                _r(kt * 1e3 * d * leg.cost_usd_per_tkm, 0),
                trips(kt, leg.small_truck_t),
                trips(kt, leg.large_truck_t),
            ]
        )
    _write(
        out_dir / "flows_farm_depot.csv",
        ["farm_id", "hub", "kt", "road_km", "t_km", "cost_usd", "trips_small", "trips_large"],
        rows,
    )

    leg = p.legs["depot_refinery"]
    rows = []
    for i, per in sorted(sol.depots.items()):
        for dsize, (n, thru) in sorted(per.items()):
            for k in range(1, n + 1):
                kt = thru / n
                rows.append(
                    [
                        f"{ids[i]}-D{dsize[0]}{k}",
                        f"{ids[i]}-R",
                        _r(kt),
                        0.0,
                        0,
                        0,
                        trips(kt, leg.small_truck_t),
                        trips(kt, leg.large_truck_t),
                    ]
                )
    _write(
        out_dir / "flows_depot_refinery.csv",
        [
            "depot_unit",
            "refinery_unit",
            "kt",
            "road_km",
            "t_km",
            "cost_usd",
            "trips_small",
            "trips_large",
        ],
        rows,
    )

    leg = p.legs["refinery_airport"]
    rows = []
    for (i, a), kt in sorted(sol.saf_flows.items()):
        ap, d = inst.airports[a], inst.d_ca[i, a]
        mode = "barge" if ap.barge else "truck"
        ts = "" if ap.barge else trips(kt, leg.small_truck_t)
        tl = "" if ap.barge else trips(kt, leg.large_truck_t)
        rows.append(
            [
                f"{ids[i]}-R",
                ap.iata,
                mode,
                _r(kt),
                _r(d, 2),
                _r(kt * 1e3 * d, 0),
                _r(kt * 1e3 * d * leg.cost_usd_per_tkm, 0),
                ts,
                tl,
            ]
        )
    _write(
        out_dir / "flows_refinery_airport.csv",
        [
            "refinery_unit",
            "airport",
            "mode",
            "kt_saf",
            "km",
            "t_km",
            "cost_usd",
            "trips_small",
            "trips_large",
        ],
        rows,
    )

    used = {j: 0.0 for j in range(len(inst.farms))}
    for (j, _), kt in sol.farm_flows.items():
        used[j] += kt
    rows = [
        [f.id, f.province, f.district, f.supply_kt, _r(used[j]), _r(f.supply_kt - used[j])]
        for j, f in enumerate(inst.farms)
        if f.supply_kt - used[j] > 1e-3
    ]
    _write(
        out_dir / "unused_farms.csv",
        ["farm_id", "province", "district", "supply_kt", "used_kt", "unused_kt"],
        rows,
    )

    total_used = sum(used.values())
    summary = {
        **meta,
        "status": sol.status,
        "objective_musd": sol.objective_musd,
        "mip_gap": sol.mip_gap,
        "runtime_s": sol.runtime_s,
        "costs_usd": {k: round(v, 2) for k, v in costs.items()},
        "refineries": {
            s: sum(1 for z, _ in sol.refineries.values() if z == s) for s in p.refineries
        },
        "depots": {s: sum(per[s][0] for per in sol.depots.values() if s in per) for s in p.depots},
        "biomass_used_kt": round(total_used, 3),
        "biomass_unused_kt": round(sum(f.supply_kt for f in inst.farms) - total_used, 3),
    }
    (out_dir / "costs.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def summary_text(summary_path: Path) -> str:
    s = json.loads(summary_path.read_text(encoding="utf-8"))
    c = s["costs_usd"]
    lines = [
        f"status {s['status']}  gap {s['mip_gap']:.2e}  runtime {s['runtime_s']:.1f}s",
        f"total ${c['total'] / 1e6:,.2f}M/yr",
        *(f"  {k:<28} ${v / 1e6:>10,.2f}M" for k, v in c.items() if k != "total"),
        f"refineries {s['refineries']}  depots {s['depots']}",
        f"biomass used {s['biomass_used_kt']:,.1f} kt, unused {s['biomass_unused_kt']:,.1f} kt",
    ]
    return "\n".join(lines)

#!/usr/bin/env python3
"""Self-contained SAF supply-chain optimiser for Kalimantan (Challenge #3).

Single file, only needs `gurobipy` (unrestricted/academic licence for the full model).
All data and parameters are embedded. Same model as the repo's `src/app/` package.

    pip install gurobipy
    python saf_solve.py                                   # full model -> saf_out/
    python saf_solve.py --threads 16 --time-limit 1800
    python saf_solve.py --n-large 6 --n-small 0 --out saf_out_6L
    python saf_solve.py --no-hanan --max-haul-km 80       # tiny; fits the pip licence

Model (yearly, units kt and US$M): each candidate cell is a hub with at most one refinery
(Small/Large) and an integer number of co-located depots (depot->refinery is 0 km, which is never
worse because depots lose no mass and 0.12 > 0.10 USD/t-km). Farms ship biomass to hubs
(great-circle x 1.3, arcs <= max_haul_km), hubs ship SAF (yield 0.20) to the 4 airports;
TRK's leg is a barge at the same rate. Minimise annualised CapEx + fixed OpEx + variable OpEx
+ transport. Candidates = farm sites + Hanan grid of farm/airport coordinates within
max_km_to_farm of a farm (no land mask: check `nearest_farm_km` in facilities.csv).
"""

import argparse
import csv
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

# ----------------------------------------------------------------------------- data
# location_id, province, district, production_kt, lat, lon
# (kalimantan_80_locations_6800kt_full_range.csv)
FARMS_CSV = """\
KAL_SUP_01,West Kalimantan,Ketapang,90.12,-1.9635,110.1136
KAL_SUP_02,Central Kalimantan,Kotawaringin Barat,96.6,-2.1083,111.5801
KAL_SUP_03,West Kalimantan,Ketapang,96.44,-2.0515,109.9553
KAL_SUP_04,East Kalimantan,Paser,99.22,-1.6149,116.3117
KAL_SUP_05,Central Kalimantan,Kotawaringin Timur,90.46,-2.085,113.235
KAL_SUP_06,West Kalimantan,Ketapang,87.91,-1.847,110.0258
KAL_SUP_07,West Kalimantan,Ketapang,89.06,-2.0294,110.3472
KAL_SUP_08,West Kalimantan,Sanggau,94.0,0.2911,110.6932
KAL_SUP_09,Central Kalimantan,Kotawaringin Barat,26.33,-2.264,111.7926
KAL_SUP_10,East Kalimantan,Kutai Kartanegara,99.51,-0.6682,116.8524
KAL_SUP_11,East Kalimantan,Kutai Kartanegara,92.16,-0.664,117.3125
KAL_SUP_12,Central Kalimantan,Kotawaringin Timur,93.8,-2.7613,112.8714
KAL_SUP_13,East Kalimantan,Kutai Kartanegara,92.81,-0.3066,116.8705
KAL_SUP_14,West Kalimantan,Ketapang,29.34,-2.1397,110.2164
KAL_SUP_15,West Kalimantan,Ketapang,88.32,-1.682,110.4027
KAL_SUP_16,Central Kalimantan,Kotawaringin Timur,98.25,-2.5858,112.7929
KAL_SUP_17,East Kalimantan,Kutai Kartanegara,88.27,-0.3747,116.804
KAL_SUP_18,North Kalimantan,Bulungan,92.89,2.61,117.2423
KAL_SUP_19,Central Kalimantan,Kotawaringin Timur,99.71,-2.5394,112.8334
KAL_SUP_20,Central Kalimantan,Kotawaringin Barat,34.1,-2.9999,111.9992
KAL_SUP_21,East Kalimantan,Paser,90.65,-2.1934,115.7592
KAL_SUP_22,West Kalimantan,Ketapang,89.0,-1.5194,109.602
KAL_SUP_23,West Kalimantan,Sanggau,92.52,-0.0962,110.4256
KAL_SUP_24,East Kalimantan,Paser,96.52,-1.8548,116.1854
KAL_SUP_25,West Kalimantan,Sanggau,88.0,0.3297,110.817
KAL_SUP_26,South Kalimantan,Tanah Laut,93.86,-4.0801,114.8675
KAL_SUP_27,Central Kalimantan,Kotawaringin Barat,93.25,-1.9857,111.856
KAL_SUP_28,Central Kalimantan,Kotawaringin Barat,88.6,-2.3295,111.9558
KAL_SUP_29,West Kalimantan,Ketapang,88.41,-1.6332,110.1275
KAL_SUP_30,East Kalimantan,Kutai Kartanegara,99.81,-0.3435,117.0175
KAL_SUP_31,West Kalimantan,Ketapang,96.65,-1.6977,109.6352
KAL_SUP_32,West Kalimantan,Ketapang,92.04,-1.6782,109.7887
KAL_SUP_33,Central Kalimantan,Kotawaringin Timur,96.69,-2.6368,112.6695
KAL_SUP_34,West Kalimantan,Sanggau,87.84,0.2514,110.2592
KAL_SUP_35,West Kalimantan,Ketapang,99.9,-1.6283,110.2045
KAL_SUP_36,Central Kalimantan,Kotawaringin Timur,91.25,-2.5737,112.6033
KAL_SUP_37,West Kalimantan,Ketapang,97.19,-2.0081,109.8869
KAL_SUP_38,East Kalimantan,Kutai Kartanegara,23.62,-0.3295,117.0183
KAL_SUP_39,West Kalimantan,Sanggau,95.76,0.2131,110.645
KAL_SUP_40,West Kalimantan,Sanggau,22.84,-0.2488,110.4914
KAL_SUP_41,West Kalimantan,Ketapang,91.08,-1.7119,110.0077
KAL_SUP_42,West Kalimantan,Sanggau,88.76,0.133,110.3271
KAL_SUP_43,West Kalimantan,Ketapang,87.96,-1.6746,109.7672
KAL_SUP_44,East Kalimantan,Kutai Kartanegara,91.87,-0.3668,116.8975
KAL_SUP_45,Central Kalimantan,Kotawaringin Timur,94.55,-2.0425,113.0427
KAL_SUP_46,West Kalimantan,Sanggau,96.19,0.2625,110.7212
KAL_SUP_47,Central Kalimantan,Kotawaringin Timur,88.6,-2.4623,113.0832
KAL_SUP_48,West Kalimantan,Ketapang,88.95,-1.6378,110.0902
KAL_SUP_49,Central Kalimantan,Kotawaringin Barat,94.09,-2.6715,111.589
KAL_SUP_50,West Kalimantan,Ketapang,90.03,-2.1621,109.9169
KAL_SUP_51,West Kalimantan,Ketapang,93.01,-1.9542,110.0706
KAL_SUP_52,East Kalimantan,Paser,90.57,-1.5392,115.8861
KAL_SUP_53,West Kalimantan,Sanggau,91.7,0.2589,110.3311
KAL_SUP_54,East Kalimantan,Kutai Kartanegara,92.83,-0.712,116.982
KAL_SUP_55,East Kalimantan,Kutai Kartanegara,89.76,-0.4098,116.5264
KAL_SUP_56,East Kalimantan,Paser,89.47,-2.2348,115.7677
KAL_SUP_57,East Kalimantan,Kutai Kartanegara,25.07,-0.0881,116.8219
KAL_SUP_58,West Kalimantan,Ketapang,96.97,-1.8634,109.8828
KAL_SUP_59,South Kalimantan,Tanah Laut,87.72,-3.9454,114.676
KAL_SUP_60,South Kalimantan,Tanah Laut,93.13,-3.5655,114.8385
KAL_SUP_61,East Kalimantan,Paser,89.76,-2.0292,116.2806
KAL_SUP_62,West Kalimantan,Ketapang,96.05,-1.6347,109.7354
KAL_SUP_63,West Kalimantan,Sanggau,92.73,0.4711,110.978
KAL_SUP_64,Central Kalimantan,Kotawaringin Barat,89.4,-2.6729,112.0284
KAL_SUP_65,Central Kalimantan,Kotawaringin Barat,88.1,-2.5395,111.7025
KAL_SUP_66,East Kalimantan,Kutai Kartanegara,98.64,-0.3758,117.121
KAL_SUP_67,Central Kalimantan,Kotawaringin Barat,89.3,-2.6718,111.704
KAL_SUP_68,Central Kalimantan,Kotawaringin Barat,35.94,-2.7388,111.3012
KAL_SUP_69,West Kalimantan,Ketapang,30.99,-2.1443,110.0022
KAL_SUP_70,North Kalimantan,Bulungan,96.08,2.8936,117.2919
KAL_SUP_71,Central Kalimantan,Kotawaringin Timur,93.87,-2.4114,112.9518
KAL_SUP_72,Central Kalimantan,Kotawaringin Timur,99.42,-2.2989,113.0191
KAL_SUP_73,West Kalimantan,Sanggau,99.03,-0.2772,110.5956
KAL_SUP_74,West Kalimantan,Sanggau,99.61,0.2713,111.0006
KAL_SUP_75,West Kalimantan,Sanggau,93.87,0.1668,110.9547
KAL_SUP_76,Central Kalimantan,Kotawaringin Barat,27.79,-2.214,111.9176
KAL_SUP_77,East Kalimantan,Kutai Kartanegara,91.32,-0.7849,117.0677
KAL_SUP_78,Central Kalimantan,Kotawaringin Barat,97.14,-2.3248,111.4876
KAL_SUP_79,Central Kalimantan,Kotawaringin Barat,32.55,-2.5115,112.0284
KAL_SUP_80,West Kalimantan,Ketapang,92.4,-2.1498,109.7591
"""

# iata, name, lat, lon, SAF demand kt/yr, barge (OpenFlights airports.dat, matched by IATA)
AIRPORTS = [
    ("PNK", "Supadio Intl, Pontianak", -0.15071099996566772, 109.40399932861328, 300.0, False),
    ("PKN", "Iskandar, Pangkalan Bun", -2.70519995689, 111.672996521, 300.0, False),
    (
        "BPN",
        "Sultan Aji Muhammad Sulaiman Sepinggan Intl, Balikpapan",
        -1.26827001572,
        116.893997192,
        300.0,
        False,
    ),
    ("TRK", "Juwata Intl, Tarakan", 3.326667, 117.569444, 300.0, True),
]

YIELD = 0.20
ROAD_FACTOR = 1.3
CAPEX_YEARS = 20
FIXED_OPEX_FRAC = 0.05
# size: (capex USD, capacity kt biomass in/yr, variable OpEx USD/t in, max units per hub)
DEPOTS = {"Small": (2_250_000, 150, 5, 2), "Large": (4_500_000, 300, 4, 4)}
REFINERIES = {"Small": (480_000_000, 500, 60, 1), "Large": (765_000_000, 1087, 55, 1)}
# leg: (USD per t-km, small truck t, large truck t)
LEGS = {
    "farm_depot": (0.10, 3, 9),
    "depot_refinery": (0.12, 18, 30),
    "refinery_airport": (0.08, 16, 32),
}
BBOX = (-4.5, 108.5, 4.5, 119.5)  # lat_min, lon_min, lat_max, lon_max
EARTH_RADIUS_KM = 6371.0088


def annual_fixed_usd(capex):
    return capex / CAPEX_YEARS + FIXED_OPEX_FRAC * capex


def load_farms():
    farms = []
    for r in csv.reader(FARMS_CSV.strip().splitlines()):
        farms.append(
            {
                "id": r[0],
                "province": r[1],
                "district": r[2],
                "kt": float(r[3]),
                "lat": float(r[4]),
                "lon": float(r[5]),
            }
        )
    assert len(farms) == 80 and abs(sum(f["kt"] for f in farms) - 6800) < 1e-6
    return farms


def load_airports():
    return [
        {"iata": a, "name": n, "lat": la, "lon": lo, "demand": d, "barge": b}
        for a, n, la, lo, d, b in AIRPORTS
    ]


# ----------------------------------------------------------------------------- geometry
def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, max(0.0, a))))


def dedupe(points, min_km):
    """Greedy in order: drop a point within min_km of one already kept (grid-bucketed)."""
    if min_km <= 0:
        return list(points)
    step = min_km / 110.0  # degrees; a bucket is >= min_km wide at Kalimantan latitudes
    buckets = defaultdict(list)
    kept = []
    for lat, lon in points:
        bi, bj = math.floor(lat / step), math.floor(lon / step)
        close = any(
            haversine_km(lat, lon, *buckets_pt) < min_km
            for di in (-1, 0, 1)
            for dj in (-1, 0, 1)
            for buckets_pt in buckets[(bi + di, bj + dj)]
        )
        if not close:
            kept.append((lat, lon))
            buckets[(bi, bj)].append((lat, lon))
    return kept


def build_candidates(farms, airports, hanan=True, max_km_to_farm=150.0, dedupe_km=1.0):
    """Farm sites first, then Hanan grid points (lat-major, sorted) near a farm and in BBOX."""
    pts = [(f["lat"], f["lon"]) for f in farms]
    if hanan:
        coords = pts + [(a["lat"], a["lon"]) for a in airports]
        lats = sorted({c[0] for c in coords})
        lons = sorted({c[1] for c in coords})
        lat_min, lon_min, lat_max, lon_max = BBOX
        for la in lats:
            for lo in lons:
                if not (lat_min <= la <= lat_max and lon_min <= lo <= lon_max):
                    continue
                if any(haversine_km(la, lo, f["lat"], f["lon"]) <= max_km_to_farm for f in farms):
                    pts.append((la, lo))
    return dedupe(pts, dedupe_km)


# ----------------------------------------------------------------------------- model
def solve(farms, airports, cells, args):
    import gurobipy as gp
    from gurobipy import GRB

    nc, na = len(cells), len(airports)
    d_fc = {}
    for j, f in enumerate(farms):
        for i, (la, lo) in enumerate(cells):
            d = haversine_km(f["lat"], f["lon"], la, lo) * ROAD_FACTOR
            if args.max_haul_km is None or d <= args.max_haul_km:
                d_fc[j, i] = d
    d_ca = {
        (i, a): haversine_km(la, lo, ap["lat"], ap["lon"]) * ROAD_FACTOR
        for i, (la, lo) in enumerate(cells)
        for a, ap in enumerate(airports)
    }
    arcs = list(d_fc)
    print(f"{len(farms)} farms, {nc} candidate cells, {len(arcs)} farm->cell arcs, {na} airports")

    need = sum(a["demand"] for a in airports) / YIELD
    reachable = sum(farms[j]["kt"] for j in {j for j, _ in arcs})
    if reachable + 1e-9 < need:
        sys.exit(f"infeasible: need {need:,.1f} kt biomass, only {reachable:,.1f} kt reachable")

    c_in = LEGS["farm_depot"][0] * 1e-3  # $M per kt-km
    c_out = LEGS["refinery_airport"][0] * 1e-3
    rsz, dsz = list(REFINERIES), list(DEPOTS)
    cells_i = range(nc)

    m = gp.Model("saf")
    m.Params.MIPGap = args.mip_gap
    m.Params.TimeLimit = args.time_limit
    m.Params.LogFile = str(Path(args.out) / "gurobi.log")
    if args.threads:
        m.Params.Threads = args.threads
    if args.mipfocus is not None:
        m.Params.MIPFocus = args.mipfocus

    x = m.addVars(arcs, name="x")
    y = m.addVars(cells_i, range(na), name="y")
    R = m.addVars(cells_i, rsz, vtype=GRB.BINARY, name="R")
    q = m.addVars(cells_i, rsz, name="q")
    N = m.addVars(cells_i, dsz, vtype=GRB.INTEGER, name="N")
    P = m.addVars(cells_i, dsz, name="P")
    for i in cells_i:
        for s in dsz:
            N[i, s].UB = DEPOTS[s][3]

    into, out_of = defaultdict(list), defaultdict(list)
    for j, i in arcs:
        into[i].append(j)
        out_of[j].append(i)
    for j, cs in out_of.items():
        m.addConstr(gp.quicksum(x[j, i] for i in cs) <= farms[j]["kt"], name=f"supply[{j}]")
    for i in cells_i:
        intake = gp.quicksum(x[j, i] for j in into[i])
        m.addConstr(intake == q.sum(i, "*"), name=f"refinery_in[{i}]")
        m.addConstr(intake == P.sum(i, "*"), name=f"depot_in[{i}]")
        m.addConstr(y.sum(i, "*") == YIELD * intake, name=f"yield[{i}]")
        m.addConstr(R.sum(i, "*") <= 1, name=f"one_refinery[{i}]")
        for s in rsz:
            m.addConstr(q[i, s] <= REFINERIES[s][1] * R[i, s], name=f"rcap[{i},{s}]")
        for s in dsz:
            m.addConstr(P[i, s] <= DEPOTS[s][1] * N[i, s], name=f"dcap[{i},{s}]")
        open_i = R.sum(i, "*")
        for j in into[i]:  # strengthening cut
            m.addConstr(x[j, i] <= farms[j]["kt"] * open_i, name=f"cut[{j},{i}]")
    for a, ap in enumerate(airports):
        if args.demand == "eq":
            m.addConstr(y.sum("*", a) == ap["demand"], name=f"demand[{ap['iata']}]")
        else:
            m.addConstr(y.sum("*", a) >= ap["demand"], name=f"demand[{ap['iata']}]")
    max_cap = max(v[1] for v in REFINERIES.values())
    m.addConstr(R.sum() >= math.ceil(need / max_cap - 1e-9), name="min_refineries")
    if args.n_large is not None:
        m.addConstr(R.sum("*", "Large") == args.n_large, name="count[Large]")
    if args.n_small is not None:
        m.addConstr(R.sum("*", "Small") == args.n_small, name="count[Small]")

    m.setObjective(
        gp.quicksum(c_in * d_fc[k] * x[k] for k in arcs)
        + gp.quicksum(c_out * d_ca[k] * y[k] for k in d_ca)
        + gp.quicksum(
            annual_fixed_usd(REFINERIES[s][0]) / 1e6 * R[i, s] + REFINERIES[s][2] * 1e-3 * q[i, s]
            for i in cells_i
            for s in rsz
        )
        + gp.quicksum(
            annual_fixed_usd(DEPOTS[s][0]) / 1e6 * N[i, s] + DEPOTS[s][2] * 1e-3 * P[i, s]
            for i in cells_i
            for s in dsz
        ),
        GRB.MINIMIZE,
    )
    m.optimize()

    if m.Status in (GRB.INFEASIBLE, GRB.INF_OR_UNBD):
        m.computeIIS()
        names = [c.ConstrName for c in m.getConstrs() if c.IISConstr]
        sys.exit("infeasible; IIS: " + ", ".join(names[:20]))
    if m.SolCount == 0:
        sys.exit(f"no solution found (Gurobi status {m.Status})")

    min_flow = 1e-7
    status_names = {GRB.OPTIMAL: "optimal", GRB.TIME_LIMIT: "time_limit"}
    sol = {
        "status": status_names.get(m.Status, str(m.Status)),
        "objective_musd": m.ObjVal,
        "mip_gap": m.MIPGap,
        "runtime_s": m.Runtime,
        "refineries": {},
        "depots": {},
        "farm_flows": {k: v.X for k, v in x.items() if v.X > min_flow},  # noqa: SIM300
        "saf_flows": {k: v.X for k, v in y.items() if v.X > min_flow},  # noqa: SIM300
    }
    for i in cells_i:
        for s in rsz:
            if R[i, s].X > 0.5:
                sol["refineries"][i] = (s, q.sum(i, "*").getValue())
        per = {s: (round(N[i, s].X), P[i, s].X) for s in dsz if round(N[i, s].X) > 0}
        if per:
            sol["depots"][i] = per
    return sol, d_fc, d_ca


# ----------------------------------------------------------------------------- validate
def cost_and_check(farms, airports, sol, d_fc, d_ca, demand="eq", tol=1e-4):
    """Recompute constraints and yearly cost (USD) from the flows, independently of Gurobi."""
    errs, c = [], defaultdict(float)
    used, intake, saf_out, saf_in = (defaultdict(float) for _ in range(4))
    for (j, i), kt in sol["farm_flows"].items():
        used[j] += kt
        intake[i] += kt
        c["transport_farm_depot"] += LEGS["farm_depot"][0] * kt * 1e3 * d_fc[j, i]
    for (i, a), kt in sol["saf_flows"].items():
        saf_out[i] += kt
        saf_in[a] += kt
        c["transport_refinery_airport"] += LEGS["refinery_airport"][0] * kt * 1e3 * d_ca[i, a]
    c["transport_depot_refinery"] += 0.0  # co-located: 0 km
    for j, kt in used.items():
        if kt > farms[j]["kt"] + tol:
            errs.append(f"farm {farms[j]['id']} over supply")
    for i in set(intake) | set(sol["refineries"]) | set(sol["depots"]):
        kt = intake.get(i, 0.0)
        if i in sol["refineries"]:
            s, qv = sol["refineries"][i]
            capex, cap, var, _ = REFINERIES[s]
            c["refinery_capex"] += capex / CAPEX_YEARS
            c["refinery_fixed_opex"] += FIXED_OPEX_FRAC * capex
            c["refinery_var_opex"] += var * qv * 1e3
            if abs(qv - kt) > tol or qv > cap + tol:
                errs.append(f"cell {i} refinery intake/capacity")
        elif kt > tol:
            errs.append(f"cell {i} receives biomass without a refinery")
        thru = 0.0
        for s, (n, t) in sol["depots"].get(i, {}).items():
            capex, cap, var, mx = DEPOTS[s]
            c["depot_capex"] += n * capex / CAPEX_YEARS
            c["depot_fixed_opex"] += n * FIXED_OPEX_FRAC * capex
            c["depot_var_opex"] += var * t * 1e3
            thru += t
            if n > mx or t > n * cap + tol:
                errs.append(f"cell {i} depot {s} over capacity")
        if abs(thru - kt) > tol:
            errs.append(f"cell {i} depot throughput != intake")
        if abs(saf_out.get(i, 0.0) - YIELD * kt) > tol:
            errs.append(f"cell {i} yield")
    for a, ap in enumerate(airports):
        got = saf_in.get(a, 0.0)
        if got < ap["demand"] - tol or (demand == "eq" and got > ap["demand"] + tol):
            errs.append(f"airport {ap['iata']} gets {got:.3f} kt")
    costs = dict(c)
    costs["total"] = sum(c.values())
    obj = sol["objective_musd"] * 1e6
    if abs(costs["total"] - obj) > max(1e-6 * abs(obj), 1e3):
        errs.append(f"recomputed cost {costs['total']:,.0f} != objective {obj:,.0f}")
    return costs, errs


# ----------------------------------------------------------------------------- report
def trips(kt, truck_t):
    return math.ceil(round(kt * 1e3 / truck_t, 6)) if kt > 0 else 0


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def write_report(farms, airports, cells, sol, d_fc, d_ca, costs, out, meta):
    ids = {i: f"H{k}" for k, i in enumerate(sorted(sol["refineries"]), start=1)}
    r3 = lambda v: round(float(v), 3)  # noqa: E731

    rows = []
    for i, hub in ids.items():
        lat, lon = cells[i]
        near = min(haversine_km(lat, lon, f["lat"], f["lon"]) for f in farms)
        s, qv = sol["refineries"][i]
        cap = REFINERIES[s][1]
        rows.append(
            [
                hub,
                "refinery",
                f"{hub}-R",
                s,
                round(lat, 5),
                round(lon, 5),
                r3(qv),
                cap,
                round(qv / cap, 4),
                round(near, 1),
            ]
        )
        for ds, (n, t) in sorted(sol["depots"].get(i, {}).items()):
            dcap = DEPOTS[ds][1]
            for k in range(1, n + 1):
                rows.append(
                    [
                        hub,
                        "depot",
                        f"{hub}-D{ds[0]}{k}",
                        ds,
                        round(lat, 5),
                        round(lon, 5),
                        r3(t / n),
                        dcap,
                        round(t / n / dcap, 4),
                        round(near, 1),
                    ]
                )
    write_csv(
        out / "facilities.csv",
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

    cost, small, large = LEGS["farm_depot"]
    rows = [
        [
            farms[j]["id"],
            ids[i],
            r3(kt),
            round(d_fc[j, i], 2),
            round(kt * 1e3 * d_fc[j, i]),
            round(kt * 1e3 * d_fc[j, i] * cost),
            trips(kt, small),
            trips(kt, large),
        ]
        for (j, i), kt in sorted(sol["farm_flows"].items())
    ]
    write_csv(
        out / "flows_farm_depot.csv",
        ["farm_id", "hub", "kt", "road_km", "t_km", "cost_usd", "trips_small", "trips_large"],
        rows,
    )

    _, small, large = LEGS["depot_refinery"]
    rows = []
    for i, per in sorted(sol["depots"].items()):
        for ds, (n, t) in sorted(per.items()):
            for k in range(1, n + 1):
                rows.append(
                    [
                        f"{ids[i]}-D{ds[0]}{k}",
                        f"{ids[i]}-R",
                        r3(t / n),
                        0.0,
                        0,
                        0,
                        trips(t / n, small),
                        trips(t / n, large),
                    ]
                )
    write_csv(
        out / "flows_depot_refinery.csv",
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

    cost, small, large = LEGS["refinery_airport"]
    rows = []
    for (i, a), kt in sorted(sol["saf_flows"].items()):
        ap, d = airports[a], d_ca[i, a]
        barge = ap["barge"]
        rows.append(
            [
                f"{ids[i]}-R",
                ap["iata"],
                "barge" if barge else "truck",
                r3(kt),
                round(d, 2),
                round(kt * 1e3 * d),
                round(kt * 1e3 * d * cost),
                "" if barge else trips(kt, small),
                "" if barge else trips(kt, large),
            ]
        )
    write_csv(
        out / "flows_refinery_airport.csv",
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

    used = defaultdict(float)
    for (j, _), kt in sol["farm_flows"].items():
        used[j] += kt
    rows = [
        [f["id"], f["province"], f["district"], f["kt"], r3(used[j]), r3(f["kt"] - used[j])]
        for j, f in enumerate(farms)
        if f["kt"] - used[j] > 1e-3
    ]
    write_csv(
        out / "unused_farms.csv",
        ["farm_id", "province", "district", "supply_kt", "used_kt", "unused_kt"],
        rows,
    )

    total_used = sum(used.values())
    summary = {
        **meta,
        "status": sol["status"],
        "objective_musd": sol["objective_musd"],
        "mip_gap": sol["mip_gap"],
        "runtime_s": sol["runtime_s"],
        "costs_usd": {k: round(v, 2) for k, v in costs.items()},
        "refineries": {
            s: sum(1 for z, _ in sol["refineries"].values() if z == s) for s in REFINERIES
        },
        "depots": {s: sum(p[s][0] for p in sol["depots"].values() if s in p) for s in DEPOTS},
        "biomass_used_kt": round(total_used, 3),
        "biomass_unused_kt": round(sum(f["kt"] for f in farms) - total_used, 3),
    }
    (out / "costs.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


# ----------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="saf_out", help="output folder (default saf_out)")
    ap.add_argument("--time-limit", type=float, default=900, help="seconds (default 900)")
    ap.add_argument("--mip-gap", type=float, default=1e-4)
    ap.add_argument("--threads", type=int, default=0, help="0 = Gurobi default")
    ap.add_argument("--mipfocus", type=int, default=None, help="Gurobi MIPFocus (e.g. 2 = bound)")
    ap.add_argument("--max-haul-km", type=float, default=400, help="road km farm->hub (400)")
    ap.add_argument(
        "--max-km-to-farm",
        type=float,
        default=150,
        help="great-circle km a Hanan candidate may be from a farm (default 150)",
    )
    ap.add_argument("--no-hanan", action="store_true", help="candidates = farm sites only")
    ap.add_argument("--n-large", type=int, default=None, help="force number of Large refineries")
    ap.add_argument("--n-small", type=int, default=None, help="force number of Small refineries")
    ap.add_argument("--demand", choices=["eq", "ge"], default="eq")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    farms, airports = load_farms(), load_airports()
    cells = build_candidates(farms, airports, not args.no_hanan, args.max_km_to_farm)
    sol, d_fc, d_ca = solve(farms, airports, cells, args)
    costs, errs = cost_and_check(farms, airports, sol, d_fc, d_ca, args.demand)
    if errs:
        sys.exit("VALIDATION FAILED: " + "; ".join(errs))
    meta = {"args": vars(args), "n_cells": len(cells), "n_arcs": len(d_fc)}
    s = write_report(farms, airports, cells, sol, d_fc, d_ca, costs, out, meta)

    print(
        f"\nstatus {s['status']}  gap {s['mip_gap']:.2e}  solve {s['runtime_s']:.1f}s  "
        f"wall {time.time() - t0:.1f}s"
    )
    print(f"total ${costs['total'] / 1e6:,.2f}M/yr (validated against Gurobi objective)")
    for k, v in costs.items():
        if k != "total":
            print(f"  {k:<28} ${v / 1e6:>10,.2f}M")
    print(f"refineries {s['refineries']}  depots {s['depots']}")
    print(f"biomass used {s['biomass_used_kt']:,.1f} kt, unused {s['biomass_unused_kt']:,.1f} kt")
    print(f"outputs: {out.resolve()}")


if __name__ == "__main__":
    main()

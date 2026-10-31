# Plan

> Generated at kickoff. Keep checkboxes current.

## Model spec (yearly, units kt and $M)
Sets: farms j (supply s_j), candidate cells i, airports a (demand 300 kt SAF).
Variables: x[j,i] ≥ 0 biomass farm→cell (only arcs ≤ max_haul_km, e.g. 400); y[i,a] ≥ 0 SAF cell→airport; S[i], L[i] binary; qS[i], qL[i] ≥ 0 refinery intake by size; nS[i] ≤ 2, nL[i] ≤ 4 integer depots; pS[i], pL[i] ≥ 0 depot throughput by size.
Minimise: Σ 1e-4·d·x + Σ 8e-5·d·y + Σ_i (48·S + 76.5·L + 0.060·qS + 0.055·qL + 0.225·nS + 0.45·nL + 0.005·pS + 0.004·pL)
Subject to:
- Σ_i x[j,i] ≤ s_j  (each farm)
- Σ_j x[j,i] = qS[i] + qL[i] = pS[i] + pL[i]  (each cell)
- qS ≤ 500·S, qL ≤ 1087·L, S + L ≤ 1
- pS ≤ 150·nS, pL ≤ 300·nL
- Σ_a y[i,a] = 0.20·Σ_j x[j,i]  (yield)
- Σ_i y[i,a] = 300  (each airport)
- Strengthening cut: x[j,i] ≤ s_j·(S[i] + L[i])  (most important for solve speed)
Gurobi: MIPGap 1e-4, TimeLimit ~900 s, LogFile per run, MIP starts on re-solves, computeIIS on infeasible. One builder with two modes: "full" and "fixed-sites" (chosen cells only, sizes fixed — used by refinement).

## MVP slice
- [x] Full-size run on the academic-licence machine: time-limited (900 s, 12 threads), $890.29M/yr, 3.04% gap (bound $863.22M) → `outputs/full-hanan-900s/`
- [x] Approve and add dependencies (see DECISIONS)
- [x] Copy data files into `data/`; parameters in `config/base.toml` (cross-check with challenge3_parameters.xlsx)
- [x] `app/data.py` — load + validate farms, airports (by IATA), params
- [x] `app/geo.py` — haversine, local km projection (+ tests)
- [x] `app/candidates.py` — sieved Hanan grid (bounding-box sieve first) + farm sites, dedupe < 1 km
- [x] `app/distances.py` — farm→cell and cell→airport matrices × 1.3, arc pruning
- [x] `app/model.py` — gurobipy MILP (spec above), config switches: fixed refinery counts, demand = / ≥
- [x] `app/validate.py` — recompute constraints and cost from flows; compare to Gurobi objective
- [x] `app/report.py` — facilities.csv, flows_*.csv (tonnes, km, trips per truck size; barge for TRK), unused_farms.csv, costs.json
- [x] `app/main.py` — `python -m app.main --config config/base.toml` → `outputs/<run_id>/`
- [x] Tests: tiny hand-solved instance; infeasible instance errors clearly; capacity-off collapses to one refinery; validate cost == objective

## Stretch
- [ ] Land mask (GADM IDN level 1, 5 Kalimantan provinces) + `snap_to_land`
- [ ] `app/refine.py` — Weiszfeld (planar km, Vardi–Zhang step near anchors) + fixed-sites re-solve loop; accept only if great-circle cost drops; add refined cells, re-solve full MILP (≤3 rounds); report km moved per refinery
- [ ] Folium map (line width ∝ tonnes)
- [ ] Scenarios: fixed 6 Large; sensitivity (yield 0.15–0.25, demand ±20%/uneven, refinery CapEx ±20%, road factor 1.1–1.5); Hanan vs uniform grid; Gurobi solution pool for alternative plans
- [ ] Comparison run: depots forced to farm clusters (shows the co-location saving)
- [ ] Streamlit front end over `pipeline.run(config)`

## Non-goals
- Real road-network routing (the brief fixes great-circle × 1.3)
- Integer truck-trip costs (cost is per t-km; trips are reported only)
- Multi-year dynamics, interest, discounting

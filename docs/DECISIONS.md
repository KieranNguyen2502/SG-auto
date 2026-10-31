# Decisions

Short log of choices so the team (and agents) don't re-argue them. Newest first.

## 2026-10-31 — Result: full Hanan run, 900 s, $890.29M/yr at 3.04% gap
Full instance (4,503 candidate cells, max haul 400 km, standalone solver, 12 threads, 900 s time limit) stopped at the time limit: best plan $890.29M/yr, proven lower bound $863.22M on this candidate grid, gap 3.04%. Plan: 6 Large refineries, 0 Small; 21 Large + 1 Small depots co-located; 6,000 kt biomass used, 800 kt unused. Cost: refineries $459.0M fixed + $330.0M variable; depots $33.74M; transport farm→hub $27.89M, hub→airport (incl. TRK barge) $39.66M. Validated: constraints and cost recomputed from flows match the Gurobi objective. Matches the expected-answer sanity check (6 Large, ~21 Large depots, ~$900M); logistics is 7.6% of cost (estimate was ~10%). Refinery cost is at its theoretical minimum ($789M) and depots are within $0.74M of theirs (20 Large = $33.0M), so the remaining gap is essentially transport. Location check: all 6 refineries within 7.1 km of a farm (H1, H2 on farm sites; H3–H6 on grid points 2.2–7.1 km away); none > 30 km. The 800 kt unused is all in Paser, Bulungan (nearest biomass to TRK) and Tanah Laut: moving biomass per t SAF costs 6.25× moving SAF, so refineries sit in the west/central clusters. Next: longer run with `--n-large 6 --n-small 0 --mipfocus 2`, then Weiszfeld refinement.

## 2026-10-31 — Config in TOML, data in `data/`, full runs on another machine
Config is `config/base.toml` (stdlib `tomllib`, no pyyaml); override any key with `--set section.key=value`. Data copied from `data and ideas/` into `data/` (workbook renamed `challenge3_parameters.xlsx`; `challenge3_airports_4.csv` was not provided — airports come from `airports.dat` by IATA and match the workbook). Installed: gurobipy 13.0.3, numpy, openpyxl (dev/test only). The local Gurobi licence is size-limited (2,000 vars), so full runs (~4,500 cells, ~167k arcs, ~221k vars) happen on the team's academic-licence machine; tests use tiny instances. Added a valid cut Σ R ≥ ⌈need / max refinery capacity⌉ (cut solve time ~35% on a reduced real instance, same optimum).

## 2026-10-31 — Stack: gurobipy + scientific Python (proposed, NOT installed — ask first)
Add: gurobipy (MILP), numpy, pandas, openpyxl (read challenge3_parameters.xlsx), shapely + geopandas (land mask, snapping), folium (map). Optional later: highspy (fallback solver), streamlit (UI).
Why: Gurobi is fastest for this MILP; the rest is standard geo/data tooling.
Risks: pip Gurobi licence is size-limited → get an academic licence. `.venv` is Python 3.14 — check gurobipy has a 3.14 wheel, else use a 3.12/3.13 venv. Keep the solver behind a thin interface so HiGHS can replace it.

## 2026-10-31 — Model: one tier, depots co-located with refineries
Depots lose no mass and depot→refinery (0.12) costs more than farm→depot (0.10). By the triangle inequality, 0.10·d(f,R) ≤ 0.10·d(f,D)+0.10·d(D,R) < 0.10·d(f,D)+0.12·d(D,R), so a depot at the refinery site is never worse. Depot→refinery leg = 0 km; depots become a per-site cost of intake. Present this as a finding, with a comparison run where depots are forced to farm clusters.

## 2026-10-31 — Refineries: at most one per candidate cell
Binary S_i, L_i with S_i + L_i ≤ 1. Large clusters (Ketapang 1,812 kt) split across neighbouring cells. Depot counts per cell are integers nS_i, nL_i.

## 2026-10-31 — Candidates: sieved Hanan grid, refined with Weiszfeld
Hanan grid = all (lat, lon) pairs from the 80 farm + 4 airport coordinates (≤7,056), sieved to land in Kalimantan and within ~150 km of a farm, plus the 80 farm sites. Not exact under great-circle distance (it is exact only for Manhattan; worst case √2 on logistics), so refine: Weiszfeld location step with allocation fixed → re-solve flows → repeat; then add refined points as new cells and re-solve the full MILP.

## 2026-10-31 — Units and assumptions
Model units: kt and US$M (well-scaled coefficients). Distances: haversine (R = 6371.0088 km) × 1.3 on every leg, including the TRK barge (assumption — confirm). Demand met exactly (=). Objective is yearly cost.

## 2026-10-31 — Expected answer (sanity check, not a target)
6 Large refineries ($789M/yr vs $811M/yr for the next option, 5L+2S); ~21 Large depots + 0–1 Small, co-located (Large depots are $1/t cheaper to run); ~6,000 kt used, ~800 kt of remote sites dropped; total ≈ $900M/yr, logistics ≈ 10%. Supply is west/central-heavy, demand is half east → refineries near biomass, SAF shipped east.

## 2026-10-31 — Baseline: Python 3.11+, src layout, pytest, ruff
Placeholder until the problem statement is out. Revisit at kickoff.

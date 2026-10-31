# SAF Supply Chain Optimiser — Kalimantan

Challenge #3, Autonomous SG 2026 (AI & Aerospace track), Acacia Hackathon Society, NUS — 31 Oct 2026.

**Result:** a supply chain that delivers 1,200 kt of Sustainable Aviation Fuel a year to Kalimantan's four airports for **$890.3M a year ($742 per tonne of SAF)**. Gurobi proves no plan on our candidate network costs less than **$863.2M**, so ours is within **3.04%** of the optimum for that network. Every constraint and every dollar was re-checked independently of the solver.

> **Main open limitation:** refinery coordinates are not yet checked against a land mask. All six are within 7.1 km of a biomass site (two sit exactly on one), so the risk is low. See [Limitations](#limitations).

## Solution versions

| Version | Role | Candidate hub sites | Cost, $M / yr | Status |
|---|---|---|---|---|
| **Baseline**: existing locations | Comparison: tests whether the Hanan grid adds value | 84 (80 farm sites + 4 airports) | 890.354 | Independent HiGHS run, 900 s, gap 2.52%; plan re-validated by our checker; [`outputs/baseline-existing-sites/`](outputs/baseline-existing-sites/) |
| **Hanan grid** (default) | **Our solution** | 4,503 (farm sites + Hanan grid; contains all 84 baseline sites) | **890.291** | Gurobi, 900 s, gap 3.04%; [`outputs/full-hanan-900s/`](outputs/full-hanan-900s/) |
| **Hanan + Weiszfeld** | Improvement on the default: hubs moved off-grid | 6 refined positions | 890.183 | Converged, validated, reproduced by an independent implementation; [`outputs/weiszfeld-refined/`](outputs/weiszfeld-refined/) |

All three use the same costs, constraints and 400 km haul limit, and all build 6 Large refineries with 21 Large + 1 Small depots. The Hanan plan is $0.063M / yr below the baseline, and Weiszfeld takes a further $0.108M off, for $0.171M / yr (0.019%) below the baseline in total. Because the Hanan candidate set contains every baseline site, its true optimum can be no worse than the baseline's.

**What the baseline shows.** The baseline puts all six refineries on existing farm sites (KAL_SUP_32, 44, 46, 51, 65, 71), and each of our six hubs is within 9.4 km of one of them (H1 and H2 on the same farms; H3–H6 2.2–9.4 km away). So on this data, choosing hubs from existing farm sites already captures almost all of the saving: the Hanan grid adds $0.06M / yr and Weiszfeld $0.11M / yr. The larger drop from the earlier $931.3M farm-sites run came from its 80 km haul limit, which forced a seventh refinery, not from the candidate grid. The baseline was solved with SciPy/HiGHS rather than Gurobi; [`standalone/saf_baseline.py`](standalone/saf_baseline.py) is the Gurobi version of the same model, and its farm-sites, 80 km mode reproduces the $931.31M optimum exactly.

## The problem

Choose where to build biomass depots and SAF refineries in Kalimantan, how big (Small/Large), and how to route material farm → depot → refinery → airport, to minimise total yearly cost:

- **Cost** = CapEx / 20 years (no interest) + fixed OpEx (5% of CapEx / yr) + variable OpEx (per tonne in) + transport (per tonne-km).
- **Demand:** 300 kt SAF / yr at each of Pontianak (PNK), Pangkalan Bun (PKN), Balikpapan (BPN), Tarakan (TRK).
- **Supply:** 80 biomass sites, 6,800 kt / yr. Yield 0.20 → 6,000 kt needed; choosing which 800 kt to leave unused is part of the problem.
- **Distance:** great-circle × 1.3. Tarakan's final leg is a barge at the same rate.

| Facility | CapEx | Capacity (kt in / yr) | Yearly fixed cost | Variable OpEx |
|---|---|---|---|---|
| Depot Small / Large | $2.25M / $4.5M | 150 / 300 | $0.225M / $0.45M | $5 / $4 per t |
| Refinery Small / Large | $480M / $765M | 500 / 1,087 | $48M / $76.5M | $60 / $55 per t |

Transport: farm → depot $0.10, depot → refinery $0.12, refinery → airport $0.08 per tonne-km.

## Our approach

**Three findings shrink the problem before solving it:**

1. **Depots belong at the refinery sites.** Depots lose no mass and the depot → refinery leg ($0.12) costs more than farm → depot ($0.10). By the triangle inequality, 0.10·d(farm, refinery) ≤ 0.10·d(farm, depot) + 0.10·d(depot, refinery) < 0.10·d(farm, depot) + 0.12·d(depot, refinery). So every depot sits at its refinery (0 km leg) and the network collapses to one tier of hubs. This is exact for transport. A depot shared between two hubs could in principle pool their spare capacity and save a whole depot, but that is worth at most the depot slack ($0.74M / yr, see below) minus the $0.12/t-km haul to the second refinery, so co-location costs at most that.
2. **Large depots beat Small** (same fixed cost per tonne of capacity, $1/t cheaper to run).
3. **Six Large refineries is the cheapest way to process 6,000 kt** ($789M / yr, vs $811M for the next option, 5 Large + 2 Small).

**Model.** A mixed-integer program (Gurobi) over candidate hub sites: binary refinery-size choice per site (at most one refinery per site), integer depot counts, continuous flows. Constraints: farm supply, refinery and depot capacity, 0.20 yield, exact demand per airport. Two valid cuts tighten the formulation: flow only to open sites (x ≤ supply × open), and at least ⌈6,000 / 1,087⌉ = 6 refineries (the second alone cut solve time by ~35% on a reduced real instance, same optimum). Every solution is re-checked independently: constraints and cost are recomputed from the flows and must match Gurobi's objective.

**Candidate sites.** Facilities may sit anywhere on land, so we generate candidates from the *Hanan grid*: every (latitude, longitude) pair formed by the farm and airport coordinates, plus all 80 farm sites (4,503 cells after filtering). Under Manhattan distance the full Hanan grid provably contains an optimal site for every facility; we keep the part within 150 km of a farm and merge points closer than 1 km. Under the brief's great-circle distance it is a strong but not exhaustive candidate set (densest inside the farm clusters), so we test it with Weiszfeld refinement, which moves each refinery to its exact best point ([below](#weiszfeld-refinement-are-the-grid-sites-in-the-right-place): it gains only 0.012%). Farm → hub arcs longer than 400 road-km are pruned (at $0.10/t-km a 400 km haul already costs $40/t).

## Results

Full instance: 80 farms, 4,503 candidate hub sites, 166,895 farm → hub arcs (≤ 400 road-km); 220,931 variables (18,012 integer) and 203,004 constraints. Gurobi 13, 12 threads, 900 s time limit. Raw outputs in [`outputs/full-hanan-900s/`](outputs/full-hanan-900s/).

| Cost line | $M / yr |
|---|---|
| Refineries: CapEx / 20 + fixed OpEx | 459.0 |
| Refineries: variable OpEx | 330.0 |
| Depots: all costs | 33.7 |
| Transport: farm → hub | 27.9 |
| Transport: hub → airport (incl. Tarakan barge) | 39.7 |
| **Total** | **890.3** |

- **6 Large refineries**, 0 Small; **21 Large + 1 Small depots**, all co-located with refineries.
- **6,000 kt** biomass used (exactly what 1,200 kt SAF needs at 0.20 yield), **800 kt** left unused.
- Utilisation: refineries 92% (6,000 of 6,522 kt), depots 93% (6,000 of 6,450 kt).
- Facilities are 92.4% of cost ($822.74M); transport is 7.6% ($67.55M).
- Solver status: time limit, best plan $890.29M, proven lower bound $863.22M, gap 3.04%.
- Validation: constraints and cost recomputed from the flows match Gurobi's objective.

### Hubs (refinery + co-located depots)

| Hub | District (province) | Lat | Lon | Site | Intake (kt / yr) | Refinery utilisation | Depots | SAF out (kt / yr → airport) |
|---|---|---|---|---|---|---|---|---|
| H1 | Sanggau (West) | 0.2625 | 110.7212 | farm KAL_SUP_46 | 1,087.0 | 100.0% | 4 Large | 47.8 → PNK, 169.6 → TRK (barge) |
| H2 | Kotawaringin Barat (Central) | −2.5395 | 111.7025 | farm KAL_SUP_65 | 893.2 | 82.2% | 3 Large | 178.6 → PKN |
| H3 | Kotawaringin Timur (Central) | −2.4623 | 113.0191 | grid, 7.1 km from KAL_SUP_47 | 1,065.1 | 98.0% | 4 Large | 213.0 → BPN |
| H4 | Ketapang (West) | −1.9542 | 110.0902 | grid, 2.2 km from KAL_SUP_51 | 967.7 | 89.0% | 3 Large + 1 Small | 72.2 → PNK, 121.4 → PKN |
| H5 | Ketapang (West) | −1.6378 | 109.7887 | grid, 4.5 km from KAL_SUP_32 | 900.0 | 82.8% | 3 Large | 180.0 → PNK |
| H6 | Kutai Kartanegara (East) | −0.4098 | 116.8940 | grid, 4.8 km from KAL_SUP_44 | 1,087.0 | 100.0% | 4 Large | 87.0 → BPN, 130.4 → TRK (barge) |
| **Total** | | | | | **6,000.0** | **92.0%** | **21 Large + 1 Small** | **300 to each airport (1,200)** |

All refinery sizes are Large (1,087 kt). District is that of the nearest biomass site. Every hub draws from 12–14 farms; 73 of the 80 farms supply biomass. Full flows: [`flows_farm_depot.csv`](outputs/full-hanan-900s/flows_farm_depot.csv), [`flows_refinery_airport.csv`](outputs/full-hanan-900s/flows_refinery_airport.csv).

**Which 800 kt is left unused, and why.** The unused biomass is all in the east and south: Paser (454.9 kt over 5 sites, south of Balikpapan), Bulungan (189.0 kt over 2 sites, the nearest biomass to Tarakan) and Tanah Laut (156.2 kt over 2 sites, south coast); 7 sites are unused entirely and 2 partly ([`unused_farms.csv`](outputs/full-hanan-900s/unused_farms.csv)). Leaving out the biomass next to Tarakan is the cost structure at work, not a bug: moving the biomass for one tonne of SAF costs 5 t × $0.10 = $0.50 per km, while moving the SAF itself costs $0.08 per km, 6.25× less. So refineries sit in the dense western and central clusters, and the SAF travels east.

## Weiszfeld refinement: are the grid sites in the right place?

The grid restricts hubs to fixed candidate points. To measure what that costs, [`standalone/weiszfeld_refine.py`](standalone/weiszfeld_refine.py) takes the plan above and lets every hub move freely, alternating two steps until the cost stops falling:

1. **Move.** With each hub's farms and airports fixed, move the hub to the point minimising its transport cost Σ wₖ · d(hub, pₖ) (the weighted Fermat–Weber problem), by Weiszfeld iteration with the Vardi–Zhang rule for a hub sitting on a farm. Weights: $0.10 × 1.3 × tonnes for each farm, $0.08 × 1.3 × tonnes of SAF for each airport. A move is kept only if the exact great-circle cost drops.
2. **Re-solve.** With the hubs fixed, re-optimise flows, refinery sizes and depot counts (the same MILP on just these 6 sites).

| Step | $M / yr |
|---|---|
| Grid plan (above) | 890.291 |
| Re-solve flows on the same 6 sites | 890.291 (gain 0.000) |
| **Weiszfeld-refined sites (converged in 2 rounds)** | **890.183** |
| **Improvement** | **0.108 (0.012%)** |

| Hub | Moved | Nearest farm after |
|---|---|---|
| H1 Sanggau, H2 Kotawaringin Barat | 0 km (optimal on their farm site) | 0.0 km |
| H3 Kotawaringin Timur | 4.46 km | 4.9 km |
| H4 Ketapang | 2.18 km (onto farm KAL_SUP_51) | 0.0 km |
| H5 Ketapang | 1.97 km | 2.5 km |
| H6 Kutai Kartanegara | 5.32 km | 9.2 km |

All of the change is transport ($67.548M → $67.440M); facilities are unchanged (6 Large refineries, 21 Large + 1 Small depots). Every refined hub is a verified local minimum (moving it 0.5 km in any of 16 directions raises its cost), and each re-solve passes the same independent cost and constraint check. Outputs: [`outputs/weiszfeld-refined/`](outputs/weiszfeld-refined/) (`refine_summary.json`, `refine_log.csv`, plus the usual plan files).

**Independent reproduction.** A separate implementation (fixed flows, modified Weiszfeld with Vardi–Zhang, moves accepted only if the great-circle × 1.3 cost drops, 400 km haul limit checked) reached $890.182738M with hub moves of 4.454, 2.177, 1.968 and 5.323 km for H3–H6. That matches ours ($890.182730M; 4.46, 2.18, 1.97, 5.32 km) to within $8 of CSV rounding. Its per-hub savings: H3 $29.5k, H4 $26.8k, H5 $10.4k, H6 $41.1k.

**What it shows:**
- **The Hanan grid already places hubs almost exactly right.** Freeing all six hubs from the grid gains $0.11M / yr, 0.012%. The grid restriction is not a meaningful source of cost.
- **The time-limited flows are already optimal for their sites** (the same-site re-solve gains nothing).
- **Any larger saving lies in which clusters get hubs and how farms are split between them**, not in fine positioning. Weiszfeld cannot change that; only more MILP search can.

## Near-optimal, and how to improve it

The 3.04% gap means no plan *on this candidate network* costs less than $863.2M; ours is at most $27.1M / yr above that. Where that slack can be:

- **Refineries ($789.0M): none.** Six Large is the cheapest way to process 6,000 kt, and we use exactly that.
- **Depots ($33.74M): at most $0.74M.** The floor is 20 Large depots ($33.0M); our plan uses one extra Large and one Small because each hub must have whole depots.
- **Transport ($67.55M): the rest.** Any improvement is in routing and site choice, not facility mix.

The best solutions Gurobi found were nearly identical (890.29, 890.34, 890.36), which suggests the plan is close to optimal and the lower bound is what's lagging. More solver time can only lower the cost or prove it optimal.

To tighten it:

1. **More runtime with the refinery count fixed** (removes search Gurobi doesn't need):
   `python standalone/saf_solve.py --n-large 6 --n-small 0 --threads 12 --time-limit 3600 --mipfocus 2`
2. **Feed refined sites back into the full MILP** (planned): add the Weiszfeld points as extra candidates and re-solve, so the search can also re-pick clusters. Fine positioning alone is worth only $0.11M / yr (see above).
3. **Land mask** (planned): snap every site onto land in Kalimantan.

## Running it

Repo package (development):
```bash
python -m venv .venv && source .venv/Scripts/activate
pip install -e ".[dev]"
python -m app.main --config config/base.toml --run-id my-run   # -> outputs/my-run/
python -m pytest -q
```

Standalone (one file, data embedded, needs only `gurobipy`):
```bash
pip install gurobipy
python standalone/saf_solve.py --threads 12 --time-limit 1800   # -> saf_out/
python standalone/weiszfeld_refine.py --base saf_out --out saf_out_refined   # refine a result
python standalone/saf_baseline.py --threads 12 --time-limit 900 --out saf_baseline_out   # baseline
```
`weiszfeld_refine.py` needs `saf_solve.py` beside it; its re-solves are small (~560 variables), so it runs on the pip licence.
The full model has ~221k variables, so it needs an academic or WLS Gurobi licence (the pip licence is capped at 2,000).

Outputs: `facilities.csv`, `flows_farm_depot.csv`, `flows_depot_refinery.csv`, `flows_refinery_airport.csv` (tonnes, km, cost, trips per truck size), `unused_farms.csv`, `costs.json`, `gurobi.log`.

## Repo layout

| Path | Contents |
|---|---|
| `src/app/` | data, geo, candidates, distances, model, validate, report, pipeline, CLI |
| `standalone/saf_solve.py` | self-contained solver for other machines |
| `standalone/weiszfeld_refine.py` | Weiszfeld refinement of a solved plan (experiment) |
| `standalone/saf_baseline.py` | baseline solver: same model, candidates = 80 farms + 4 airports |
| `standalone/verification/run_highs.py` | optional SciPy/HiGHS runner for the baseline (needs scipy) |
| `config/base.toml` | all parameters and run settings (`--set section.key=value` overrides) |
| `data/` | biomass sites, OpenFlights airports, official parameter workbook |
| `outputs/` | solver runs |
| `docs/` | problem statement, plan, design decisions |
| `tests/` | pytest suite (tiny hand-checked instances) |

## Limitations

- **Refinery locations are not yet verified to be on land in Kalimantan.** Candidate sites are not checked against a coastline or the Indonesia–Malaysia border. In this solution the risk is low: H1 and H2 sit exactly on biomass sites, and H3–H6 are grid points 2.2–7.1 km from one, inside their farm clusters and well inland of the Malaysian border (the northernmost hub, H1, is at 0.26° N). None is more than 30 km from a farm (`nearest_farm_km` in `facilities.csv`). The fix (planned) is a GADM land mask for the five Kalimantan provinces, with any off-land site snapped to the nearest land point and the flows re-solved; its cost effect is unknown until that is run.
- **Optimality is relative to the candidate network** (4,503 sites, ≤ 400 km farm → hub hauls). Off-grid sites are cheaper, but by little: Weiszfeld refinement of all six hubs gains $0.11M / yr (0.012%). The refined H3, H5 and H6 positions are 2.5–9.2 km from a farm and are not land-checked either.
- **Not solved to proven optimality:** 900 s time limit, gap 3.04%.

## Assumptions

- Tarakan's barge leg uses great-circle × 1.3, like the road legs (the brief gives the rate but not the distance rule). The whole refinery → TRK leg is costed as one barge leg, including from inland hubs: H1 (Sanggau) → TRK is 1,084 km. Because truck and barge share the $0.08 rate, the mode does not change cost, but a real route via a port could be longer.
- Demand is met exactly; extra SAF has no value.
- At most one refinery per candidate site.
- Depot → refinery distance is 0 km (co-located), so that leg costs $0.

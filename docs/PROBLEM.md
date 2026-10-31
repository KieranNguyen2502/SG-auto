# Problem Statement

Acacia Hackathon Society — Autonomous SG 2026, AI & Aerospace track, Challenge #3 (NUS, 31 Oct 2026).

## Raw statement

Challenge #3 “ How might we optimise the SAF supply chain in Kalimantan? ” Description There is a need to aggressively scale Sustainable Aviation Fuel (SAF) adoption to meet decarbonisation goals. Kalimantan (Indonesian Borneo) has abundant agricultural and forestry residues, making it a potential hub for regional SAF production. Transporting raw biomass, building infrastructure and delivering SAF to airports requires strategic decisions with complex logistical and capital trade-offs. Want to see • A SAF supply chain optimisation model that minimises total yearly cost (annualised CapEx + OpEx + logistics) while meeting SAF demand at Kalimantan’s 4 airports. • Optimal coordinates of depots and refineries, and facility sizing (Small vs Large). • Material flow network: feedstock to depots, depots to refineries, refineries to airports. Feedstock available: 6,800 kt of biomass per year. Capacity is biomass intake.ACACIA HACKATHON SOCIETY National University of Singapore AUTONOMOUS SG 2026 AI & AEROSPACE TRACK Acacia Hackathon Society | 31 October 2026 | NUS 4 / 7 Facility Type Size CapEx (USD) Capacity (kt biomass in / yr) Fixed OpEx (USD / yr) Variable OpEx (USD / t in) Depot Small 2.25M 150 112,500 5 Depot Large 4.5M 300 225,000 4 Refinery Small 480M 500 24.0M 60 Refinery Large 765M 1,087 38.25M 55 Truck Size Farm to Depot Depot to Refinery Refinery to Airport Small 3 t 18 t 16 t Large 9 t 30 t 32 t Cost (USD / tonne-km) 0.10 0.12 0.08 Airport IATA Latitude Longitude SAF demand (kt / yr) Supadio Intl, Pontianak PNK −0.15071 109.40400 300 Iskandar, Pangkalan Bun PKN −2.70520 111.67300 300 Sultan Aji Muhammad Sulaiman Sepinggan Intl, Balikpapan BPN −1.26827 116.89400 300 Juwata Intl, Tarakan TRK 3.32667 117.56944 300 Data provided • Airport locations: Challenge 3 folder, Airport Location/airports.dat (OpenFlights). Only the four airports above count. • Biomass locations: 80 sites, 20–100 kt each, 6,800 kt total, in Biomass location/kalimantan_80_locations_6800kt_full_range.csv. • New: challenge3_parameters.xlsx (all parameters and assumptions) and challenge3_airports_4.csv.ACACIA HACKATHON SOCIETY AUTONOMOUS SG 2026 National University of Singapore Clarifications: Challenge #3 AI & AEROSPACE TRACK • Capacity means biomass intake (kt of biomass per year) for both depots and refineries. • Yield. 1 t biomass → 0.20 t SAF. Depots lose no mass (tonnes in = tonnes out). • Demand. 300 kt SAF per airport per year, 1,200 kt in total, so 6,000 kt of biomass is needed. You do not have to use all 6,800 kt; choosing which sites to leave out is part of the problem. • Time basis: one year. Annualise CapEx straight-line over 20 years, no interest. Fixed OpEx = 5% of CapEx per year. • “Iskandar” means Iskandar Airport, Pangkalan Bun (PKN). • Distance = great-circle distance × 1.3 road factor. Truck cost is per tonne-km and the same for both sizes; truck size only changes the number of trips you report. • Tarakan (TRK) is on an island. Model the final leg as a barge at the same 0.08 USD per tonne-km, with no extra fixed cost. • Facilities may sit anywhere on land in Kalimantan. Report their coordinates.

## Requirements
- Minimise total yearly cost = CapEx/20 (no interest) + fixed OpEx (5% of CapEx/yr) + variable OpEx (USD/t biomass in) + logistics (USD/t-km).
- Meet SAF demand: 300 kt SAF/yr at each of PNK, PKN, BPN, TRK (1,200 kt total).
- Yield 0.20 → 6,000 kt biomass needed of 6,800 kt available; choosing unused sites is part of the answer.
- Network farm → depot → refinery → airport; depots lose no mass.
- Decide coordinates (anywhere on land in Kalimantan) and size (Small/Large) of every depot and refinery.
- Report flows on every link and trip counts per truck size (truck size does not change cost).

### Parameters
| Facility | CapEx (USD) | Capacity (kt in/yr) | Fixed OpEx (USD/yr) | Var OpEx (USD/t in) |
|---|---|---|---|---|
| Depot Small | 2.25M | 150 | 112,500 | 5 |
| Depot Large | 4.5M | 300 | 225,000 | 4 |
| Refinery Small | 480M | 500 | 24.0M | 60 |
| Refinery Large | 765M | 1,087 | 38.25M | 55 |

| Leg | USD/t-km | Small truck | Large truck |
|---|---|---|---|
| Farm → depot | 0.10 | 3 t | 9 t |
| Depot → refinery | 0.12 | 18 t | 30 t |
| Refinery → airport | 0.08 | 16 t | 32 t |

| Airport | IATA | Lat | Lon | SAF demand (kt/yr) |
|---|---|---|---|---|
| Supadio Intl, Pontianak | PNK | −0.15071 | 109.40400 | 300 |
| Iskandar, Pangkalan Bun | PKN | −2.70520 | 111.67300 | 300 |
| Sultan Aji Muhammad Sulaiman Sepinggan Intl, Balikpapan | BPN | −1.26827 | 116.89400 | 300 |
| Juwata Intl, Tarakan | TRK | 3.32667 | 117.56944 | 300 |

Distance = great-circle × 1.3. TRK final leg is a barge at 0.08 USD/t-km, no fixed cost.

## Judging criteria
Not stated in the brief. Ask the organisers. Assume: correctness/optimality of the model, quality of the spatial answer (coordinates, sizing, flows), clarity of presentation.

## Constraints (tech, data, APIs, licensing)
- Data is outside the repo in `E:\sg auto\`: `kalimantan_80_locations_6800kt_full_range.csv` (location_id, province, district, production_kilotons, production_tonnes, latitude, longitude), `airports.dat` (OpenFlights — match by IATA, not name: "Iskandar" also matches Banda Aceh; "Sepinggan" isn't in the file's name), `challenge3_parameters.xlsx`, `challenge3_airports_4.csv`.
- Solver: Gurobi (`gurobipy`). The pip licence is capped at 2,000 vars / 2,000 constraints → academic licence needed.
- Land mask needs an external boundary file (GADM IDN level 1) — external download.

## Deliverables (demo, video, slides, repo, deadline)
- Model + solution: facility coordinates and sizes, flows per link, unused biomass sites, yearly cost breakdown, trip counts.
- Map of the network.
- Deadline: 31 Oct 2026 (exact time and submission format not in the brief — ask).

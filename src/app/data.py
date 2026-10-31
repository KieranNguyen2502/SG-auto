"""Load and validate farms, airports and model parameters."""

import csv
import tomllib
from dataclasses import dataclass
from pathlib import Path


class DataError(ValueError):
    """Input data or config is missing or inconsistent."""


@dataclass(frozen=True)
class Farm:
    id: str
    province: str
    district: str
    supply_kt: float
    lat: float
    lon: float


@dataclass(frozen=True)
class Airport:
    iata: str
    name: str
    lat: float
    lon: float
    demand_kt: float  # SAF
    barge: bool = False


@dataclass(frozen=True)
class FacilitySize:
    capex_usd: float
    capacity_kt: float  # biomass intake
    var_opex_usd_per_t: float
    max_per_cell: int = 1


@dataclass(frozen=True)
class Leg:
    cost_usd_per_tkm: float
    small_truck_t: float
    large_truck_t: float


@dataclass(frozen=True)
class Params:
    yield_: float
    road_factor: float
    capex_years: float
    fixed_opex_frac: float
    depots: dict[str, FacilitySize]
    refineries: dict[str, FacilitySize]
    legs: dict[str, Leg]  # farm_depot, depot_refinery, refinery_airport

    def annual_fixed_usd(self, f: FacilitySize) -> float:
        """Annualised CapEx + fixed OpEx, USD/yr."""
        return f.capex_usd / self.capex_years + self.fixed_opex_frac * f.capex_usd


FARM_COLUMNS = (
    "location_id",
    "province",
    "district",
    "production_kilotons",
    "latitude",
    "longitude",
)
LEG_NAMES = ("farm_depot", "depot_refinery", "refinery_airport")


def load_config(path: str | Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_farms(path: str | Path) -> list[Farm]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(FARM_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise DataError(f"{path}: missing columns {sorted(missing)}")
        farms = []
        for n, row in enumerate(reader, start=2):
            try:
                farm = Farm(
                    id=row["location_id"].strip(),
                    province=row["province"].strip(),
                    district=row["district"].strip(),
                    supply_kt=float(row["production_kilotons"]),
                    lat=float(row["latitude"]),
                    lon=float(row["longitude"]),
                )
            except ValueError as e:
                raise DataError(f"{path}:{n}: {e}") from e
            if farm.supply_kt <= 0:
                raise DataError(f"{path}:{n}: non-positive supply for {farm.id}")
            if not (-90 <= farm.lat <= 90 and -180 <= farm.lon <= 180):
                raise DataError(f"{path}:{n}: bad coordinates for {farm.id}")
            farms.append(farm)
    ids = [f.id for f in farms]
    if len(set(ids)) != len(ids):
        raise DataError(f"{path}: duplicate location_id")
    if not farms:
        raise DataError(f"{path}: no farms")
    return farms


def load_airports(path: str | Path, demand_kt: dict[str, float], barge=()) -> list[Airport]:
    """Read OpenFlights airports.dat (no header) and keep the given IATA codes, in that order.

    Matching is by IATA only: names are unreliable (e.g. "Iskandar" also matches Banda Aceh).
    """
    found: dict[str, Airport] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 8 or row[4] not in demand_kt:
                continue
            iata = row[4]
            found[iata] = Airport(
                iata=iata,
                name=row[1],
                lat=float(row[6]),
                lon=float(row[7]),
                demand_kt=float(demand_kt[iata]),
                barge=iata in barge,
            )
    missing = [c for c in demand_kt if c not in found]
    if missing:
        raise DataError(f"{path}: IATA codes not found: {missing}")
    return [found[c] for c in demand_kt]


def _sizes(section: dict, kind: str) -> dict[str, FacilitySize]:
    if not section:
        raise DataError(f"config: no [{kind}.*] sizes")
    out = {}
    for name, v in section.items():
        size = FacilitySize(
            capex_usd=float(v["capex_usd"]),
            capacity_kt=float(v["capacity_kt"]),
            var_opex_usd_per_t=float(v["var_opex_usd_per_t"]),
            max_per_cell=int(v.get("max_per_cell", 1)),
        )
        if size.capacity_kt <= 0 or size.capex_usd < 0 or size.max_per_cell < 1:
            raise DataError(f"config: bad values for {kind}.{name}")
        out[name] = size
    return out


def load_params(cfg: dict) -> Params:
    try:
        proc = cfg["process"]
        legs = {k: Leg(**cfg["transport"][k]) for k in LEG_NAMES}
        params = Params(
            yield_=float(proc["yield"]),
            road_factor=float(proc["road_factor"]),
            capex_years=float(proc["capex_years"]),
            fixed_opex_frac=float(proc["fixed_opex_frac"]),
            depots=_sizes(cfg.get("depot", {}), "depot"),
            refineries=_sizes(cfg.get("refinery", {}), "refinery"),
            legs=legs,
        )
    except (KeyError, TypeError) as e:
        raise DataError(f"config: missing or bad key {e}") from e
    if not 0 < params.yield_ <= 1:
        raise DataError("config: yield must be in (0, 1]")
    if params.road_factor < 1 or params.capex_years <= 0:
        raise DataError("config: road_factor must be >= 1 and capex_years > 0")
    return params

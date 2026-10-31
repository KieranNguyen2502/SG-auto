from pathlib import Path

import pytest

from app.data import load_config, load_params

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def base_cfg():
    cfg = load_config(ROOT / "config" / "base.toml")
    for k in ("farms_csv", "airports_dat"):
        cfg["data"][k] = str(ROOT / cfg["data"][k])
    return cfg


@pytest.fixture(scope="session")
def params(base_cfg):
    return load_params(base_cfg)

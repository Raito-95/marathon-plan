from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from plan import build, load
from plan.config import PlanConfig

CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "plan.json"


@pytest.fixture
def config() -> PlanConfig:
    return load(CONFIG_PATH)


@pytest.fixture
def plan(config):
    return build(config)


@pytest.fixture
def race_day(config) -> date:
    return config.race.date

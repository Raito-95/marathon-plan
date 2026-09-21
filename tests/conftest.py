from __future__ import annotations

from datetime import date
import pytest

from plan import build
from plan.config import PlanConfig, from_dict

# 測試用的固定設定：18 週全馬、中間一場半馬。
#
# 刻意不讀 data/plan.json —— 那是使用者的真實課表，換一場比賽就會讓整個測試套件
# 垮掉，而測試要驗的是產生器的行為，不是當下在備哪一場賽。data/plan.json 本身由
# test_the_shipped_config_builds 單獨把關。
FIXTURE_RAW = {
    "race": {
        "name": "測試全馬",
        "date": "2027-03-07",
        "distance_km": 42.195,
    },
    "block": {
        "weeks": 18,
        "phases": {"base": 4, "build": 6, "specific": 5, "taper": 3},
    },
    "volume": {
        "start_weekly_km": 40,
        "peak_weekly_km": 65,
        "down_week_factor": 0.78,
        "max_long_run_km": 32,
    },
    "week_template": [
        "rest", "easy", "strength", "quality", "rest", "recovery", "long",
    ],
    "tune_up_races": [
        {"name": "半程馬拉松", "date": "2027-01-24", "distance_km": 21.0975},
    ],
    "athlete": {
        "max_hr": None,
        "resting_hr": None,
        "goal_times": {"marathon": None, "half_marathon": None},
    },
}


@pytest.fixture
def config() -> PlanConfig:
    return from_dict(FIXTURE_RAW)


@pytest.fixture
def plan(config):
    return build(config)


@pytest.fixture
def race_day(config) -> date:
    return config.race.date

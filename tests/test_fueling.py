from __future__ import annotations

import pytest

from plan import fueling


def test_short_long_runs_need_no_fuel():
    advice = fueling.long_run_advice(50)

    assert "不需要途中補給" in advice
    assert "g 醣" not in advice


@pytest.mark.parametrize(
    "minutes,carbs",
    [(75, "30g"), (120, "45g"), (200, "60g")],
)
def test_carb_target_rises_with_duration(minutes, carbs):
    assert carbs in fueling.long_run_advice(minutes)


def test_interval_shortens_as_the_target_rises():
    def interval(minutes: int) -> int:
        text = fueling.long_run_advice(minutes)
        return int(text.split("約每 ")[1].split(" 分鐘")[0])

    assert interval(75) > interval(200)


def test_sodium_only_appears_past_two_and_a_half_hours():
    assert "補鈉" not in fueling.long_run_advice(120)
    assert "補鈉" in fueling.long_run_advice(160)


def test_hydration_advice_scales():
    assert "每 15-20 分鐘喝兩三口" in fueling.long_run_advice(75)
    assert "每小時 400-600ml" in fueling.long_run_advice(120)


def test_race_day_covers_before_and_during():
    advice = fueling.race_day_advice(42.195, 300)

    assert "賽前 2-3 小時" in advice
    assert "起跑後第 40 分鐘" in advice
    assert "補鈉" in advice
    assert "不要第一次嘗試新東西" in advice


def test_short_race_skips_mid_race_fuel():
    advice = fueling.race_day_advice(10.0, 55)

    assert "途中喝水即可" in advice
    assert "每小時" not in advice.split("途中喝水即可")[0].split("賽前")[-1]


def test_every_week_carries_fuel_advice(plan):
    for week in plan.weeks:
        assert week.fuel.strip(), f"第 {week.week} 週沒有補給說明"

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from outputs import intervals
from plan import build, schedule, volume
from plan.config import (
    HALF_MARATHON_KM,
    Athlete,
    ConfigError,
    Race,
    TimeTrial,
    from_dict,
)
from plan.intensity import equivalent_time, format_time
from plan.workouts import Repeat, total_km

TRIAL = TimeTrial(date(2027, 4, 15), 10.0)  # 星期四，主課日


@pytest.fixture
def half(config):
    return replace(
        config,
        race=Race("測試半馬", date(2027, 5, 16), HALF_MARATHON_KM),
        phases=replace(config.phases, base=2, build=4, specific=2, taper=2),
        volume=replace(
            config.volume, start_weekly_km=30, peak_weekly_km=42, max_long_run_km=18
        ),
        tune_up_races=(),
    )


def _steps(day):
    for item in day.steps:
        yield from item.steps if isinstance(item, Repeat) else (item,)


def _trial_day(plan, trial=TRIAL):
    week = plan.week(schedule.week_containing(plan.config, trial.date))
    return week, week.days[trial.date.weekday()]


def test_half_marathon_plan_practices_half_marathon_pace(half):
    plan = build(half)
    days = [day for week in plan.weeks for day in week.days]
    titles = " ".join(day.title for day in days)
    targets = {step.target for day in days for step in _steps(day)}

    assert "半馬節奏" in titles
    assert "馬拉松節奏" not in titles
    assert "half_marathon" in targets
    assert "marathon" not in targets


def test_marathon_plan_keeps_marathon_pace(plan):
    titles = " ".join(day.title for week in plan.weeks for day in week.days)

    assert "馬拉松節奏" in titles
    assert "半馬節奏" not in titles


def test_half_marathon_goal_alone_is_enough_for_paces(config):
    plan = build(replace(config, athlete=Athlete(half_marathon_goal_seconds=6600)))
    band = plan.targets.pace["half_marathon"]

    assert band.low <= 6600 / HALF_MARATHON_KM <= band.high
    assert {"easy", "long_run", "quality", "marathon"} <= set(plan.targets.pace)


def test_time_trial_replaces_one_day_and_counts_toward_the_week(half):
    before_week, _ = _trial_day(build(half))
    week, day = _trial_day(build(replace(half, time_trials=(TRIAL,))))
    index = TRIAL.date.weekday()

    assert day.role == "test"
    assert day.title.startswith("10K 測驗")
    assert [d for i, d in enumerate(week.days) if i != index] == [
        d for i, d in enumerate(before_week.days) if i != index
    ]
    assert int(week.weekly_km_text.rstrip("K")) > int(before_week.weekly_km_text.rstrip("K"))
    assert "10K 測驗" in week.focus


def test_time_trial_shows_what_the_goal_needs(half):
    athlete = Athlete(half_marathon_goal_seconds=6600)
    _, day = _trial_day(build(replace(half, time_trials=(TRIAL,), athlete=athlete)))

    needed = format_time(equivalent_time(6600, HALF_MARATHON_KM, 10.0))
    assert f"跑進 {needed}" in day.note
    assert "半馬 1:50:00" in day.note


def test_time_trial_without_a_goal_gives_no_benchmark(half):
    _, day = _trial_day(build(replace(half, time_trials=(TRIAL,))))

    assert "跑進" not in day.note


@pytest.mark.parametrize(
    "when",
    [
        date(2027, 5, 13),  # 比賽週
        date(2027, 4, 18),  # 長跑日
        date(2026, 1, 1),    # 週期開始之前
    ],
)
def test_time_trials_are_validated(half, when):
    with pytest.raises(ConfigError):
        build(replace(half, time_trials=(TimeTrial(when, 10.0),)))


def test_time_trial_cannot_share_a_week_with_a_tune_up_race(config):
    race = config.tune_up_races[0]
    clash = TimeTrial(race.date.replace(day=race.date.day - 3), 10.0)

    with pytest.raises(ConfigError, match="期中比賽"):
        build(replace(config, time_trials=(clash,)))


def test_time_trials_parse_from_config():
    parsed = from_dict(
        {
            "race": {"name": "測試半馬", "date": "2027-05-16", "distance_km": 21.0975},
            "volume": {"start_weekly_km": 30, "peak_weekly_km": 42},
            "time_trials": [{"date": "2027-04-15", "distance_km": 10}],
        }
    )

    assert parsed.time_trials == (TRIAL,)


def test_time_trial_uploads_with_its_own_name(half):
    plan = build(replace(half, time_trials=(TRIAL,)))
    week, _ = _trial_day(plan)

    names = [event["name"] for event in intervals.week_events(plan, week)]
    assert "10K 測驗" in names


def test_time_trial_week_headline_matches_the_actual_total(half):
    """測驗把當天換成更長的課，標題的跑量要跟著改，不能還停在計畫值。"""
    with_trial = replace(half, time_trials=(TRIAL,))
    week, _ = _trial_day(build(with_trial))
    planned = volume.week_volume(with_trial, week.week).weekly_km

    assert "{weekly}" not in week.focus
    assert week.weekly_km_text in week.focus
    assert int(week.weekly_km_text.rstrip("K")) > planned
    assert f"{planned}K" not in week.focus


def _quality_titles(plan, phase):
    return [
        day.title
        for week in plan.weeks
        if week.phase == phase
        for day in week.days
        if day.role == "quality"
    ]


def test_half_marathon_build_phase_lengthens_the_reps(half):
    titles = _quality_titles(build(half), "build")
    trained = [title for title in titles if " x " in title]

    assert "1K x" in trained[0]
    assert "2K x 2" in trained[-2]
    assert "3K x 2" in trained[-1]


def test_marathon_build_phase_keeps_1k_reps(plan):
    titles = _quality_titles(plan, "build")

    assert all("1K x" in title for title in titles if " x " in title)


def test_half_marathon_specific_phase_starts_with_race_pace_reps(half):
    first = _quality_titles(build(half), "specific")[0]

    assert "半馬節奏 3K x 2" in first


def test_half_marathon_long_runs_finish_at_race_pace(half):
    plan = build(half)
    longs = [
        day
        for week in plan.weeks
        if week.phase == "specific"
        for day in week.days
        if day.role == "long"
    ]

    assert ["最後 3K 半馬節奏" in longs[0].title, "最後 4K 半馬節奏" in longs[-1].title] == [
        True,
        True,
    ]
    for day in longs:
        planned = int(day.title.split()[1].split("K")[0])
        assert total_km(day.steps) == planned
        assert day.steps[-1].target == "half_marathon"


def test_marathon_long_runs_stay_steady(plan):
    for week in plan.weeks:
        for day in week.days:
            if day.role == "long":
                assert "最後" not in day.title

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json

import pytest

import cli
from outputs import intervals
from plan import build, schedule
from plan.config import Athlete
from plan.workouts import Repeat, Step, total_km

RUN_ROLES = {"easy", "recovery", "quality", "long", "race", "test"}


@pytest.fixture
def monday(config):
    start, _ = schedule.week_dates(config, 8)
    return start


@pytest.fixture
def settings():
    return intervals.IntervalsSettings(api_key="secret")


def _all_days(plan):
    return [day for week in plan.weeks for day in week.days]


def test_every_run_day_has_steps_and_nothing_else_does(plan):
    for day in _all_days(plan):
        if day.role in {"rest", "strength"}:
            assert day.steps == (), day
        else:
            assert day.role in RUN_ROLES
            assert day.steps, day


def test_steps_are_positive_and_cooldown_never_disappears(plan):
    for day in _all_days(plan):
        for item in day.steps:
            steps = item.steps if isinstance(item, Repeat) else (item,)
            for step in steps:
                assert (step.km or 0) > 0 or (step.seconds or 0) > 0, day
                if step.label == "收操":
                    assert step.km >= 1


def test_steady_runs_match_the_planned_distance(plan):
    for week in plan.weeks:
        for day in week.days:
            if day.role in {"easy", "recovery", "long"} and day.title.startswith(
                ("輕鬆跑", "恢復跑", "長跑")
            ):
                planned = int(day.title.split()[1].rstrip("K").split("K")[0])
                assert total_km(day.steps) == planned, day


def test_heart_rate_is_preferred_and_sent_as_percent_of_max(config):
    athlete = Athlete(max_hr=180, resting_hr=40, marathon_goal_seconds=4 * 3600)
    plan = build(replace(config, athlete=athlete))
    band = plan.targets.heart_rate["easy"]

    text = intervals.target_text(plan, "easy")

    assert text == f" {round(band.low / 180 * 100)}-{round(band.high / 180 * 100)}% HR"
    assert "bpm" not in text


def test_pace_is_used_without_heart_rate(config):
    plan = build(replace(config, athlete=Athlete(marathon_goal_seconds=4 * 3600)))

    assert intervals.target_text(plan, "marathon").endswith("/km Pace")


def test_no_athlete_data_means_distance_only(plan):
    assert intervals.target_text(plan, "easy") == ""


def test_repeats_are_fenced_by_blank_lines(plan):
    day = next(
        day
        for day in _all_days(plan)
        if any(isinstance(item, Repeat) and item.steps[0].km for item in day.steps)
    )
    lines = intervals.workout_text(plan, day).splitlines()
    header = next(i for i, line in enumerate(lines) if line.endswith("x") and line[:-1].isdigit())

    assert lines[header - 1] == ""
    assert lines[header + 1].startswith("- 快跑 1km")
    assert lines[header + 3] == ""


def test_week_events_skip_rest_and_use_real_dates(plan):
    week = plan.week(8)
    events = intervals.week_events(plan, week)

    runs = [index for index, day in enumerate(week.days) if day.steps]
    assert len(events) == len(runs)
    for index, event in zip(runs, events):
        on = week.start + timedelta(days=index)
        assert event["start_date_local"] == f"{on.isoformat()}T00:00:00"
        assert event["external_id"] == f"marathon-plan-{on.isoformat()}"
        assert event["type"] == "Run"
        assert event["category"] == "WORKOUT"
        assert event["distance"] > 0 and event["moving_time"] > 0


def test_race_day_is_uploaded_with_the_race_name(config, plan):
    events = intervals.week_events(plan, plan.weeks[-1])

    assert events[-1]["name"].startswith(config.race.name)
    assert events[-1]["distance"] == round(config.race.distance_km * 1000)


def test_settings_need_an_api_key():
    with pytest.raises(intervals.IntervalsError):
        intervals.IntervalsSettings.from_env({})

    settings = intervals.IntervalsSettings.from_env({"INTERVALS_API_KEY": " key "})
    assert settings.api_key == "key"
    assert settings.athlete_id == "0"


class FakeApi:
    def __init__(self, existing):
        self.existing = existing
        self.calls = []

    def __call__(self, method, url, settings, body):
        self.calls.append((method, url, body))
        return self.existing if method == "GET" else None


def test_sync_creates_updates_and_deletes_only_its_own_events(plan, monday, settings):
    wanted = [
        event
        for week in intervals.upcoming_weeks(plan, monday)
        for event in intervals.week_events(plan, week)
    ]
    existing = [
        {"id": 1, "external_id": wanted[0]["external_id"]},  # 還在課表裡 → 更新
        {"id": 2, "external_id": "marathon-plan-1999-01-01"},  # 課表裡沒了 → 刪除
        {"id": 3, "external_id": None},  # 使用者自己排的 → 不動
        {"id": 4, "external_id": "someone-else"},  # 其他工具的 → 不動
    ]
    api = FakeApi(existing)

    result = intervals.sync(plan, monday, settings, request=api)

    assert (result.created, result.updated, result.deleted) == (len(wanted) - 1, 1, 1)
    methods = [(method, url.rsplit("/", 1)[-1], body) for method, url, body in api.calls]
    assert ("PUT", "bulk-delete", [{"id": 2}]) in methods
    assert ("PUT", "1", wanted[0]) in methods
    posted = next(body for method, tail, body in methods if method == "POST")
    assert [event["external_id"] for event in posted] == [
        event["external_id"] for event in wanted[1:]
    ]
    assert result.oldest == monday


def test_sync_is_idempotent(plan, monday, settings):
    wanted = [
        event
        for week in intervals.upcoming_weeks(plan, monday)
        for event in intervals.week_events(plan, week)
    ]
    existing = [
        {"id": index, "external_id": event["external_id"]}
        for index, event in enumerate(wanted)
    ]
    api = FakeApi(existing)

    result = intervals.sync(plan, monday, settings, request=api)

    assert (result.created, result.deleted) == (0, 0)
    assert not any(method == "POST" for method, _, _ in api.calls)


def test_upcoming_weeks_stop_at_the_race(plan, race_day):
    weeks = intervals.upcoming_weeks(plan, race_day - timedelta(days=2))

    assert [week.week for week in weeks] == [len(plan.weeks)]


def test_intervals_format_previews_without_a_key(plan, monday):
    payload = json.loads(intervals.render(plan, monday))

    assert payload and all(event["external_id"].startswith("marathon-plan-") for event in payload)


def test_cli_sync_needs_a_key(tmp_path, capsys, monkeypatch):
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps(
            {
                "race": {"name": "測試馬拉松", "date": "2027-03-07"},
                "volume": {"start_weekly_km": 40, "peak_weekly_km": 65},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("INTERVALS_API_KEY", raising=False)

    assert cli.main(["--config", str(path), "--date", "2026-12-09", "--sync"]) == 1
    assert "INTERVALS_API_KEY" in capsys.readouterr().err

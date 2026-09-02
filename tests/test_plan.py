from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from plan import build, schedule


def test_every_week_has_one_entry_per_template_day(config, plan):
    for week in plan.weeks:
        assert len(week.days) == 7
        assert [day.day for day in week.days] == [
            "星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"
        ]


def test_final_week_is_the_goal_race(config, plan):
    final = plan.weeks[-1]

    assert final.week_type == "比賽週"
    assert f"{config.race.name} 42.195K" in " ".join(day.title for day in final.days)
    assert "不含比賽" in final.weekly_km_text
    assert final.long_run_text.startswith("比賽日")

    race_days = [day for day in final.days if day.duration == "比賽日"]
    assert [day.day for day in race_days] == ["星期日"]


def test_tune_up_race_week_is_rewritten(config, plan):
    race = config.tune_up_races[0]
    week = plan.weeks[schedule.week_containing(config, race.date) - 1]

    assert week.week_type == "比賽週"
    assert race.name in week.long_run_text
    race_days = [day for day in week.days if day.duration == "比賽日"]
    assert len(race_days) == 1
    assert race_days[0].day == "星期日"


def test_weeks_around_a_tune_up_race_are_adjusted(config, plan):
    race = config.tune_up_races[0]
    number = schedule.week_containing(config, race.date)

    assert plan.weeks[number - 3].week_type == "距離演練週"
    assert plan.weeks[number - 2].week_type == "賽前調整週"
    assert plan.weeks[number].week_type == "恢復週"


def test_rehearsal_week_runs_close_to_the_race_distance(config, plan):
    race = config.tune_up_races[0]
    rehearsal = plan.weeks[schedule.week_containing(config, race.date) - 3]

    assert rehearsal.long_run_text == f"{round(race.distance_km)}K"
    long_day = [day for day in rehearsal.days if day.role == "long"][0]
    assert "距離演練" in long_day.note


def test_short_tune_up_races_get_no_rehearsal_week(config):
    short = replace(
        config,
        tune_up_races=(replace(config.tune_up_races[0], distance_km=10.0),),
    )
    plan = build(short)
    number = schedule.week_containing(short, short.tune_up_races[0].date)

    assert plan.weeks[number - 3].week_type != "距離演練週"
    assert plan.weeks[number - 2].week_type == "賽前調整週"


def test_down_weeks_replace_the_quality_session(config, plan):
    quality_index = config.week_template.index("quality")

    race_weeks = set(schedule.tune_ups_by_week(config))

    for week in plan.weeks:
        if week.week in race_weeks:
            continue  # 比賽週整週改寫，不套降量規則
        if schedule.is_down_week(config, week.week):
            assert week.week_type == "降量週"
            assert "降量週不做主課" in week.days[quality_index].note


def test_quality_session_progresses_through_the_block(config, plan):
    quality_index = config.week_template.index("quality")
    titles = {
        week.phase: week.days[quality_index].title
        for week in plan.weeks
        if week.week_type == "訓練週"
    }

    assert "跑姿喚醒" in titles["base"]
    assert "1K x" in titles["build"]
    assert "馬拉松節奏" in titles["specific"]


def test_plan_without_a_race_still_builds(config):
    plan = build(replace(config, tune_up_races=()))

    assert len(plan.weeks) == config.total_weeks
    assert all(week.week_type != "恢復週" for week in plan.weeks[:-1])


def test_week_lookup_clamps_outside_the_block(config, plan):
    before = config.race.date - timedelta(weeks=config.total_weeks + 10)
    after = config.race.date + timedelta(weeks=10)

    assert plan.week_for(before).week == 1
    assert plan.week_for(after).week == config.total_weeks


def test_different_week_template_moves_the_long_run(config):
    moved = replace(
        config,
        week_template=("long", "rest", "easy", "strength", "quality", "rest", "recovery"),
    )
    plan = build(moved)
    week = plan.weeks[0]

    assert week.days[0].role == "long"
    assert week.days[1].role == "rest"

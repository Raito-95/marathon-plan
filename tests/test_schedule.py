from __future__ import annotations

from datetime import date, timedelta

import pytest

from plan import schedule


def test_last_week_ends_on_race_day(config):
    monday = schedule.first_monday(config)
    assert monday.weekday() == 0

    start, end = schedule.week_dates(config, config.total_weeks)
    assert end == config.race.date
    assert (end - monday).days == config.total_weeks * 7 - 1


def test_publishing_treats_sunday_as_the_upcoming_week(config):
    """提醒在台灣星期一早上送出，換算 UTC 仍是星期日，不能推剛結束的那一週。"""
    monday, _ = schedule.week_dates(config, 5)
    sunday_before = monday - timedelta(days=1)

    assert schedule.week_to_publish(config, sunday_before) == 5
    assert schedule.week_to_publish(config, monday) == 5
    assert schedule.week_to_publish(config, monday + timedelta(days=3)) == 5
    assert schedule.week_to_publish(config, monday - timedelta(days=2)) == 4


def test_week_containing_uses_plain_monday_to_sunday(config):
    monday, sunday = schedule.week_dates(config, 7)

    assert schedule.week_containing(config, monday) == 7
    assert schedule.week_containing(config, sunday) == 7
    assert schedule.week_containing(config, sunday + timedelta(days=1)) == 8


def test_plan_is_finished_only_after_race_day(config):
    assert not schedule.is_finished(config, config.race.date - timedelta(days=7))
    assert not schedule.is_finished(config, config.race.date - timedelta(days=1))
    assert schedule.is_finished(config, config.race.date)
    assert schedule.is_finished(config, config.race.date + timedelta(days=30))


@pytest.mark.parametrize("week", [4, 8, 12])
def test_every_fourth_loading_week_is_a_down_week(config, week):
    assert schedule.is_down_week(config, week)


def test_taper_weeks_are_not_down_weeks(config):
    for week in range(config.phases.loading + 1, config.total_weeks + 1):
        assert not schedule.is_down_week(config, week)


def test_tune_up_races_are_indexed_by_week(config):
    races = schedule.tune_ups_by_week(config)
    for week, race in races.items():
        start, end = schedule.week_dates(config, week)
        assert start <= race.date <= end


def test_next_tune_up_ignores_past_races(config):
    race = config.tune_up_races[0]

    assert schedule.next_tune_up(config, race.date) is race
    assert schedule.next_tune_up(config, race.date + timedelta(days=1)) is None

from __future__ import annotations

import pytest

from plan import intensity
from plan.config import (
    HALF_MARATHON_KM,
    MARATHON_KM,
    Athlete,
    ConfigError,
    parse_goal_time,
)


def test_no_athlete_data_means_no_targets():
    targets = intensity.build(Athlete())

    assert targets.is_empty
    assert targets.summary_lines(Athlete()) == []
    assert targets.text_for("easy") is None


def test_heart_rate_uses_reserve_method():
    athlete = Athlete(max_hr=195, resting_hr=55)
    targets = intensity.build(athlete)

    assert targets.heart_rate["easy"].text == "138-156 bpm"     # 59-72% of 140
    assert targets.heart_rate["quality"].text == "167-178 bpm"  # 80-88%
    assert not targets.pace


def test_paces_come_from_the_goal_time():
    athlete = Athlete(marathon_goal_seconds=parse_goal_time("4:00:00", "goal"))
    targets = intensity.build(athlete)

    assert targets.pace["marathon"].text == "5:35-5:45/km"
    assert targets.heart_rate == {}


def test_targets_combine_pace_and_heart_rate():
    athlete = Athlete(
        max_hr=195,
        resting_hr=55,
        marathon_goal_seconds=parse_goal_time("4:00:00", "goal"),
    )
    text = intensity.build(athlete).text_for("easy")

    assert "/km" in text and "bpm" in text and "／" in text


def test_half_marathon_pace_is_optional():
    goal = parse_goal_time("4:00:00", "goal")
    without = intensity.build(Athlete(marathon_goal_seconds=goal))
    with_half = intensity.build(
        Athlete(
            marathon_goal_seconds=goal,
            half_marathon_goal_seconds=parse_goal_time("1:55:00", "goal"),
        )
    )

    assert "half_marathon" not in without.pace
    assert with_half.pace["half_marathon"].text.startswith("5:2")


def test_zones_are_ordered_from_easy_to_hard():
    targets = intensity.build(Athlete(max_hr=195, resting_hr=55))
    bands = targets.heart_rate

    assert bands["recovery"].high <= bands["easy"].high
    assert bands["easy"].high <= bands["long_run"].high
    assert bands["long_run"].high < bands["marathon"].high
    assert bands["marathon"].high <= bands["quality"].high


def test_rejects_max_below_resting():
    with pytest.raises(ValueError):
        intensity.build(Athlete(max_hr=120, resting_hr=150))


def test_riegel_equivalents():
    marathon = parse_goal_time("4:00:00", "goal")
    half = intensity.equivalent_time(marathon, MARATHON_KM, HALF_MARATHON_KM)

    assert intensity.format_time(half).startswith("1:55")


def test_duration_uses_goal_pace_when_available():
    plain = intensity.build(Athlete())
    fast = intensity.build(
        Athlete(marathon_goal_seconds=parse_goal_time("3:00:00", "goal"))
    )

    assert intensity.duration_text(10, fast, "easy") != intensity.duration_text(
        10, plain, "easy"
    )


@pytest.mark.parametrize("value", ["4:00", "abc", "4:60:00", "0:00:00"])
def test_goal_time_parsing_rejects_bad_input(value):
    with pytest.raises(ConfigError):
        parse_goal_time(value, "goal")

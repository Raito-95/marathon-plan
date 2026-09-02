from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json

import pytest

from outputs import FORMATS, json_out, line, markdown, text
from plan import build, schedule
from plan.config import Athlete


@pytest.fixture
def midweek(config):
    start, _ = schedule.week_dates(config, 6)
    return start + timedelta(days=2)


def test_text_output_covers_the_week(plan, midweek):
    rendered = text.render(plan, midweek)

    assert plan.config.race.name in rendered
    assert "本週類型：" in rendered
    assert "每日計畫：" in rendered
    assert "執行原則：" in rendered
    assert rendered.count("｜") >= 7


def test_text_output_hides_targets_without_athlete_data(plan, midweek):
    assert "強度目標：" not in text.render(plan, midweek)


def test_text_output_shows_targets_when_configured(config, midweek):
    plan = build(replace(config, athlete=Athlete(max_hr=195, resting_hr=55)))
    rendered = text.render(plan, midweek)

    assert "強度目標：" in rendered
    assert "bpm" in rendered


def test_text_output_counts_down_to_the_next_tune_up(config, plan):
    race = config.tune_up_races[0]
    before = text.render(plan, race.date - timedelta(days=14))
    after = text.render(plan, race.date + timedelta(days=1))

    assert f"下一場比賽：{race.name}" in before
    assert "下一場比賽" not in after


def test_markdown_lists_every_week(plan, midweek):
    rendered = markdown.render(plan, midweek)

    for week in plan.weeks:
        assert f"### 第 {week.week} 週" in rendered
    assert "**←本週**" in rendered


def test_json_round_trips(plan, midweek):
    payload = json.loads(json_out.render(plan, midweek))

    assert payload["block"]["weeks"] == plan.config.total_weeks
    assert len(payload["weeks"]) == plan.config.total_weeks
    assert payload["weeks"][0]["days"][0]["day"] == "星期一"
    assert payload["currentWeek"] == plan.week_for(midweek).week


def test_every_registered_format_renders(plan, midweek):
    for name, render in FORMATS.items():
        assert render(plan, midweek).strip(), f"{name} 產出空白"


def test_line_settings_need_both_values():
    with pytest.raises(line.LineError):
        line.LineSettings.from_env({"LINE_CHANNEL_ACCESS_TOKEN": "token"})
    with pytest.raises(line.LineError):
        line.LineSettings.from_env({"LINE_TO_ID": "target"})

    settings = line.LineSettings.from_env(
        {"LINE_CHANNEL_ACCESS_TOKEN": " token ", "LINE_TO_ID": " target "}
    )
    assert settings.token == "token"
    assert settings.to == "target"


def test_line_refuses_empty_messages():
    settings = line.LineSettings(token="token", to="target")

    with pytest.raises(line.LineError):
        line.push("   ", settings)

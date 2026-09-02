from __future__ import annotations

import json

import pytest

import cli
from plan import config as config_module
from plan.config import ConfigError


def _raw(**overrides):
    data = {
        "race": {"name": "測試馬拉松", "date": "2027-03-07"},
        "block": {"weeks": 18, "phases": {"base": 4, "build": 6, "specific": 5, "taper": 3}},
        "volume": {"start_weekly_km": 40, "peak_weekly_km": 65},
    }
    data.update(overrides)
    return data


def test_defaults_fill_in_the_optional_parts():
    parsed = config_module.from_dict(_raw())

    assert parsed.week_template == config_module.DEFAULT_TEMPLATE
    assert parsed.tune_up_races == ()
    assert parsed.athlete.max_hr is None
    assert parsed.total_weeks == 18


def test_week_count_must_match_the_phases():
    with pytest.raises(ConfigError, match="不符"):
        config_module.from_dict(
            _raw(block={"weeks": 20, "phases": {"base": 4, "build": 6, "specific": 5, "taper": 3}})
        )


@pytest.mark.parametrize(
    "template",
    [
        ["rest"] * 7,                                   # 沒有長跑
        ["long"] * 7,                                   # 太多長跑
        ["rest", "easy", "strength", "quality", "rest", "recovery"],  # 只有 6 天
        ["rest", "easy", "strength", "sprint", "rest", "recovery", "long"],  # 未知角色
    ],
)
def test_week_template_is_validated(template):
    with pytest.raises(ConfigError):
        config_module.from_dict(_raw(week_template=template))


def test_athlete_data_can_come_from_the_environment():
    base = config_module.from_dict(_raw())
    assert not base.athlete.has_heart_rate

    updated = config_module.apply_env(
        base, {"MAX_HR": "195", "RESTING_HR": "55", "MARATHON_GOAL": "3:30:00"}
    )

    assert updated.athlete.max_hr == 195
    assert updated.athlete.has_goal
    assert updated.athlete.marathon_goal_seconds == 12600


def test_partial_heart_rate_environment_is_ignored():
    updated = config_module.apply_env(config_module.from_dict(_raw()), {"MAX_HR": "195"})

    assert not updated.athlete.has_heart_rate


def test_missing_config_file_is_reported(tmp_path):
    with pytest.raises(ConfigError, match="不存在"):
        config_module.load(tmp_path / "nope.json")


def test_invalid_json_is_reported(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(ConfigError, match="JSON"):
        config_module.load(path)


def _write_config(tmp_path, **overrides):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(_raw(**overrides), ensure_ascii=False), encoding="utf-8")
    return path


def test_cli_prints_the_week(tmp_path, capsys):
    path = _write_config(tmp_path)

    assert cli.main(["--config", str(path), "--date", "2026-12-09"]) == 0
    assert "測試馬拉松" in capsys.readouterr().out


def test_cli_writes_to_a_file(tmp_path):
    path = _write_config(tmp_path)
    out = tmp_path / "plan.md"

    assert cli.main(
        ["--config", str(path), "--format", "markdown", "--out", str(out)]
    ) == 0
    assert "## 週次總覽" in out.read_text(encoding="utf-8")


def test_cli_stops_after_race_day(tmp_path, capsys):
    path = _write_config(tmp_path)

    assert cli.main(["--config", str(path), "--date", "2027-03-08"]) == 0
    assert "訓練週期已結束" in capsys.readouterr().out


def test_cli_reports_bad_config(tmp_path, capsys):
    path = tmp_path / "plan.json"
    path.write_text("{}", encoding="utf-8")

    assert cli.main(["--config", str(path)]) == 1
    assert "錯誤" in capsys.readouterr().err


def test_cli_refuses_to_send_non_text_formats(tmp_path, capsys):
    path = _write_config(tmp_path)

    assert cli.main(
        ["--config", str(path), "--date", "2026-12-09", "--format", "json", "--send"]
    ) == 1
    assert "只支援 text" in capsys.readouterr().err

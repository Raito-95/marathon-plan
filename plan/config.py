from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from json import JSONDecodeError
from pathlib import Path
from typing import Any
import json
import os

MARATHON_KM = 42.195
HALF_MARATHON_KM = 21.0975

WEEKDAY_NAMES = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
ROLES = ("rest", "easy", "strength", "quality", "recovery", "long")
DEFAULT_TEMPLATE = ("rest", "easy", "strength", "quality", "rest", "recovery", "long")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Race:
    name: str
    date: date
    distance_km: float = MARATHON_KM


@dataclass(frozen=True)
class TuneUpRace:
    name: str
    date: date
    distance_km: float

    @property
    def is_long(self) -> bool:
        """夠長才值得在賽前兩週安排距離演練。"""
        return self.distance_km >= 15.0


@dataclass(frozen=True)
class TimeTrial:
    """測驗課：只換掉當天的課，不像期中比賽會改寫前後幾週。"""

    date: date
    distance_km: float


@dataclass(frozen=True)
class Phases:
    base: int
    build: int
    specific: int
    taper: int

    @property
    def total(self) -> int:
        return self.base + self.build + self.specific + self.taper

    @property
    def loading(self) -> int:
        """減量期之前的累積週數，跑量曲線在這段爬升。"""
        return self.base + self.build + self.specific

    def phase_of(self, week: int) -> tuple[str, int]:
        if not 1 <= week <= self.total:
            raise ValueError(f"週次 {week} 超出 1-{self.total}")
        for key in ("base", "build", "specific", "taper"):
            span = getattr(self, key)
            if week <= span:
                return key, week
            week -= span
        raise AssertionError


@dataclass(frozen=True)
class Volume:
    start_weekly_km: float
    peak_weekly_km: float
    down_week_factor: float = 0.78
    max_long_run_km: float = 32.0

    def validate(self) -> None:
        if self.start_weekly_km <= 0:
            raise ConfigError("volume.start_weekly_km 必須大於 0")
        if self.peak_weekly_km < self.start_weekly_km:
            raise ConfigError("volume.peak_weekly_km 不可小於 start_weekly_km")
        if not 0.4 <= self.down_week_factor <= 1.0:
            raise ConfigError("volume.down_week_factor 必須介於 0.4 與 1.0")
        if self.max_long_run_km <= 0:
            raise ConfigError("volume.max_long_run_km 必須大於 0")


@dataclass(frozen=True)
class Athlete:
    """全部可選。沒給就用感受式強度描述，不輸出 bpm 或配速。"""

    max_hr: int | None = None
    resting_hr: int | None = None
    marathon_goal_seconds: int | None = None
    half_marathon_goal_seconds: int | None = None

    @property
    def has_heart_rate(self) -> bool:
        return self.max_hr is not None and self.resting_hr is not None

    @property
    def has_goal(self) -> bool:
        return (
            self.marathon_goal_seconds is not None
            or self.half_marathon_goal_seconds is not None
        )


@dataclass(frozen=True)
class PlanConfig:
    race: Race
    phases: Phases
    volume: Volume
    week_template: tuple[str, ...]
    tune_up_races: tuple[TuneUpRace, ...] = ()
    athlete: Athlete = Athlete()
    time_trials: tuple[TimeTrial, ...] = ()

    @property
    def total_weeks(self) -> int:
        return self.phases.total


def parse_goal_time(value: str, field: str) -> int:
    parts = str(value).strip().split(":")
    if len(parts) != 3:
        raise ConfigError(f"{field} 必須是 H:MM:SS")
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError as exc:
        raise ConfigError(f"{field} 必須是 H:MM:SS") from exc
    if min(hours, minutes, seconds) < 0 or minutes > 59 or seconds > 59:
        raise ConfigError(f"{field} 的時分秒超出範圍")
    total = hours * 3600 + minutes * 60 + seconds
    if total <= 0:
        raise ConfigError(f"{field} 必須大於 0")
    return total


def _as_date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ConfigError(f"{field} 必須是 YYYY-MM-DD") from exc


def _template_from(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return DEFAULT_TEMPLATE
    if not isinstance(raw, list) or len(raw) != 7:
        raise ConfigError("week_template 必須是 7 個角色，index 0 為星期一")
    roles = tuple(str(item) for item in raw)
    unknown = [role for role in roles if role not in ROLES]
    if unknown:
        raise ConfigError(f"week_template 有不支援的角色：{', '.join(unknown)}")
    if roles.count("long") != 1:
        raise ConfigError("week_template 必須剛好有一個 long")
    return roles


def _athlete_from(raw: Any) -> Athlete:
    if raw is None:
        return Athlete()
    if not isinstance(raw, dict):
        raise ConfigError("athlete 必須是物件")
    goals = raw.get("goal_times") or {}
    if not isinstance(goals, dict):
        raise ConfigError("athlete.goal_times 必須是物件")
    marathon = goals.get("marathon")
    half = goals.get("half_marathon")
    return Athlete(
        max_hr=_as_int(raw.get("max_hr"), "athlete.max_hr"),
        resting_hr=_as_int(raw.get("resting_hr"), "athlete.resting_hr"),
        marathon_goal_seconds=(
            parse_goal_time(marathon, "athlete.goal_times.marathon") if marathon else None
        ),
        half_marathon_goal_seconds=(
            parse_goal_time(half, "athlete.goal_times.half_marathon") if half else None
        ),
    )


def _as_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{field} 必須是整數") from exc


def from_dict(data: dict[str, Any]) -> PlanConfig:
    try:
        race_raw = data["race"]
        block = data.get("block") or {}
        phases_raw = block.get("phases") or {}
        volume_raw = data["volume"]
    except KeyError as exc:
        raise ConfigError(f"設定缺少必要欄位：{exc.args[0]}") from exc

    phases = Phases(
        base=_as_int(phases_raw.get("base"), "phases.base") or 4,
        build=_as_int(phases_raw.get("build"), "phases.build") or 6,
        specific=_as_int(phases_raw.get("specific"), "phases.specific") or 5,
        taper=_as_int(phases_raw.get("taper"), "phases.taper") or 3,
    )
    if min(phases.base, phases.build, phases.specific, phases.taper) < 1:
        raise ConfigError("每個階段至少要有 1 週")

    weeks = _as_int(block.get("weeks"), "block.weeks")
    if weeks is not None and weeks != phases.total:
        raise ConfigError(f"block.weeks（{weeks}）與各階段加總（{phases.total}）不符")

    volume = Volume(
        start_weekly_km=float(volume_raw["start_weekly_km"]),
        peak_weekly_km=float(volume_raw["peak_weekly_km"]),
        down_week_factor=float(volume_raw.get("down_week_factor", 0.78)),
        max_long_run_km=float(volume_raw.get("max_long_run_km", 32.0)),
    )
    volume.validate()

    races_raw = data.get("tune_up_races") or []
    if not isinstance(races_raw, list):
        raise ConfigError("tune_up_races 必須是陣列")
    tune_ups = tuple(
        sorted(
            (
                TuneUpRace(
                    name=str(item["name"]),
                    date=_as_date(item["date"], "tune_up_races.date"),
                    distance_km=float(item["distance_km"]),
                )
                for item in races_raw
            ),
            key=lambda race: race.date,
        )
    )

    trials_raw = data.get("time_trials") or []
    if not isinstance(trials_raw, list):
        raise ConfigError("time_trials 必須是陣列")
    time_trials = tuple(
        sorted(
            (
                TimeTrial(
                    date=_as_date(item["date"], "time_trials.date"),
                    distance_km=float(item["distance_km"]),
                )
                for item in trials_raw
            ),
            key=lambda trial: trial.date,
        )
    )

    return PlanConfig(
        race=Race(
            name=str(race_raw["name"]),
            date=_as_date(race_raw["date"], "race.date"),
            distance_km=float(race_raw.get("distance_km", MARATHON_KM)),
        ),
        phases=phases,
        volume=volume,
        week_template=_template_from(data.get("week_template")),
        tune_up_races=tune_ups,
        athlete=_athlete_from(data.get("athlete")),
        time_trials=time_trials,
    )


def resolve(path: Path, env: dict[str, str] | None = None) -> PlanConfig:
    """設定來源：PLAN_CONFIG 環境變數優先，沒有才讀檔。

    部署到 CI 時，設定可以放 repository secret 或 variable，不必進版控。
    """
    env = os.environ if env is None else env
    raw = env.get("PLAN_CONFIG")
    if raw and raw.strip():
        return apply_env(from_dict(_parse(raw, "PLAN_CONFIG")), env)
    return load(path, env)


def _parse(raw: str, label: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except JSONDecodeError as exc:
        raise ConfigError(f"{label} JSON 格式錯誤：第 {exc.lineno} 行") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{label} 必須是 JSON 物件")
    return data


def load(path: Path, env: dict[str, str] | None = None) -> PlanConfig:
    if not path.exists():
        raise ConfigError(f"設定檔不存在：{path}")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ConfigError(f"{path.name} 無法讀取：{exc}") from exc
    return apply_env(from_dict(_parse(text, path.name)), env)


def apply_env(config: PlanConfig, env: dict[str, str] | None = None) -> PlanConfig:
    """生理數據與目標成績可以放環境變數，設定檔就能公開。"""
    env = os.environ if env is None else env
    athlete = config.athlete

    max_hr = _as_int(env.get("MAX_HR") or None, "MAX_HR")
    resting_hr = _as_int(env.get("RESTING_HR") or None, "RESTING_HR")
    if max_hr is not None and resting_hr is not None:
        athlete = replace(athlete, max_hr=max_hr, resting_hr=resting_hr)

    marathon = env.get("MARATHON_GOAL")
    if marathon:
        athlete = replace(
            athlete,
            marathon_goal_seconds=parse_goal_time(marathon, "MARATHON_GOAL"),
        )
    half = env.get("HALF_MARATHON_GOAL")
    if half:
        athlete = replace(
            athlete,
            half_marathon_goal_seconds=parse_goal_time(half, "HALF_MARATHON_GOAL"),
        )

    return replace(config, athlete=athlete)

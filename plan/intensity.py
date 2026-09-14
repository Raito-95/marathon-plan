from __future__ import annotations

from dataclasses import dataclass

from .config import HALF_MARATHON_KM, MARATHON_KM, Athlete

HR_BANDS = {
    "recovery": (0.50, 0.59),
    "easy": (0.59, 0.72),
    "long_run": (0.62, 0.75),
    "quality": (0.80, 0.88),
    "marathon": (0.78, 0.85),
    "half_marathon": (0.85, 0.88),
}

# 相對於馬拉松目標配速的秒數偏移（每公里）。
PACE_OFFSETS = {
    "easy": (55, 85),
    "recovery": (85, 115),
    "long_run": (65, 100),
    "quality": (-40, -25),
    "marathon": (-6, 4),
}

KEYS = ("recovery", "easy", "long_run", "quality", "marathon", "half_marathon")
LABELS = {
    "recovery": "恢復跑",
    "easy": "輕鬆跑",
    "long_run": "長跑",
    "quality": "主課",
    "marathon": "馬拉松節奏",
    "half_marathon": "半馬節奏",
}


@dataclass(frozen=True)
class Band:
    low: int
    high: int
    unit: str

    @property
    def text(self) -> str:
        if self.unit == "bpm":
            return f"{self.low}-{self.high} bpm"
        return f"{_pace(self.low)}-{_pace(self.high)}/km"


def _pace(seconds: int) -> str:
    minutes, rest = divmod(int(round(seconds)), 60)
    return f"{minutes}:{rest:02d}"


def format_time(total_seconds: int) -> str:
    hours, rest = divmod(int(total_seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def equivalent_time(from_seconds: int, from_km: float, to_km: float) -> int:
    """Riegel 等價成績換算，指數 1.06。"""
    return int(round(from_seconds * (to_km / from_km) ** 1.06))


@dataclass(frozen=True)
class Targets:
    heart_rate: dict[str, Band]
    pace: dict[str, Band]

    def text_for(self, key: str) -> str | None:
        parts = [
            band.text
            for band in (self.pace.get(key), self.heart_rate.get(key))
            if band is not None
        ]
        return "／".join(parts) if parts else None

    @property
    def is_empty(self) -> bool:
        return not self.heart_rate and not self.pace

    def summary_lines(self, athlete: Athlete) -> list[str]:
        if self.is_empty:
            return []
        lines = [
            f"{LABELS[key]} {self.text_for(key)}"
            for key in KEYS
            if self.text_for(key)
        ]
        if athlete.has_heart_rate:
            lines.append(
                f"（最大心率 {athlete.max_hr}、靜息心率 {athlete.resting_hr}，用心率儲備法換算）"
            )
        return lines


def _hr_bands(max_hr: int, resting_hr: int) -> dict[str, Band]:
    reserve = max_hr - resting_hr
    bands = {}
    for key, (low, high) in HR_BANDS.items():
        bands[key] = Band(
            low=int(round(resting_hr + reserve * low)),
            high=int(round(resting_hr + reserve * high)),
            unit="bpm",
        )
    return bands


def _pace_bands(
    marathon_seconds: int, half_seconds: int | None
) -> dict[str, Band]:
    marathon_pace = marathon_seconds / MARATHON_KM
    bands = {}
    for key, (low, high) in PACE_OFFSETS.items():
        bands[key] = Band(
            low=int(round(marathon_pace + min(low, high))),
            high=int(round(marathon_pace + max(low, high))),
            unit="pace",
        )
    if half_seconds is not None:
        half_pace = half_seconds / HALF_MARATHON_KM
        low, high = PACE_OFFSETS["marathon"]
        bands["half_marathon"] = Band(
            low=int(round(half_pace + min(low, high))),
            high=int(round(half_pace + max(low, high))),
            unit="pace",
        )
    return bands


def build(athlete: Athlete) -> Targets:
    if athlete.has_heart_rate and (athlete.max_hr or 0) <= (athlete.resting_hr or 0):
        raise ValueError("最大心率必須大於靜息心率")

    heart_rate = (
        _hr_bands(athlete.max_hr, athlete.resting_hr) if athlete.has_heart_rate else {}
    )
    pace = (
        _pace_bands(_marathon_seconds(athlete), athlete.half_marathon_goal_seconds)
        if athlete.has_goal
        else {}
    )
    return Targets(heart_rate=heart_rate, pace=pace)


def _marathon_seconds(athlete: Athlete) -> int:
    """只給半馬目標時，其他配速都從它換算的全馬等價成績推出來。"""
    if athlete.marathon_goal_seconds is not None:
        return athlete.marathon_goal_seconds
    return equivalent_time(
        athlete.half_marathon_goal_seconds, HALF_MARATHON_KM, MARATHON_KM
    )


DEFAULT_MINUTES_PER_KM = {"easy": (6.5, 8.0), "long_run": (7.0, 8.5)}


def duration_range(km: float, targets: Targets, key: str) -> tuple[float, float]:
    band = targets.pace.get(key)
    if band is not None:
        return km * band.low / 60, km * band.high / 60
    low, high = DEFAULT_MINUTES_PER_KM.get(key, DEFAULT_MINUTES_PER_KM["easy"])
    return km * low, km * high


def duration_minutes(km: float, targets: Targets, key: str) -> int:
    """取區間中點，給補給量分級用。"""
    low, high = duration_range(km, targets, key)
    return int(round((low + high) / 2))


def duration_text(km: float, targets: Targets, key: str) -> str:
    low, high = duration_range(km, targets, key)
    first = max(5, int(round(low / 5)) * 5)
    second = max(5, int(round(high / 5)) * 5)
    if first == second:
        return f"約 {first} 分鐘"
    return f"約 {first}-{second} 分鐘"

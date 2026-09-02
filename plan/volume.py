from __future__ import annotations

from dataclasses import dataclass

from .config import PlanConfig
from .schedule import is_down_week

# 以每週跑 5 天為基準；跑得天數少，長跑自然佔更大比例。
LONG_RUN_SHARE = {"base": 0.32, "build": 0.38, "specific": 0.45}
BASELINE_RUN_DAYS = 5
SHARE_SCALE_RANGE = (0.8, 1.35)
MAX_LONG_RUN_SHARE = 0.50
TAPER_WEEKLY_RANGE = (0.75, 0.35)
TAPER_LONG_SHARE_RANGE = (0.38, 0.20)
DAILY_WEIGHTS = {"easy": 0.35, "quality": 0.40, "recovery": 0.25}


@dataclass(frozen=True)
class WeekVolume:
    week: int
    phase: str
    phase_week: int
    weekly_km: int
    long_run_km: int
    daily_km: tuple[int, ...]

    @property
    def is_race_week_placeholder(self) -> bool:
        return self.long_run_km == 0


def _interpolate(span: tuple[float, float], index: int, count: int) -> float:
    if count <= 1:
        return sum(span) / 2
    low, high = span
    return low + (high - low) * (index / (count - 1))


def _loading_weekly_km(config: PlanConfig, week: int) -> float:
    loading = config.phases.loading
    volume = config.volume
    if loading <= 1:
        return volume.peak_weekly_km
    progress = (week - 1) / (loading - 1)
    km = volume.start_weekly_km + (volume.peak_weekly_km - volume.start_weekly_km) * progress
    if is_down_week(config, week):
        km *= volume.down_week_factor
    return km


def _taper_weekly_km(config: PlanConfig, phase_week: int) -> float:
    factor = _interpolate(TAPER_WEEKLY_RANGE, phase_week - 1, config.phases.taper)
    return config.volume.peak_weekly_km * factor


def _share_scale(config: PlanConfig) -> float:
    run_days = len(_running_slots(config)) + 1
    low, high = SHARE_SCALE_RANGE
    return max(low, min(high, BASELINE_RUN_DAYS / run_days))


def _long_run_km(config: PlanConfig, phase: str, phase_week: int, weekly: int) -> int:
    if phase == "taper":
        share = _interpolate(TAPER_LONG_SHARE_RANGE, phase_week - 1, config.phases.taper)
    else:
        share = LONG_RUN_SHARE[phase]
    share = min(share * _share_scale(config), MAX_LONG_RUN_SHARE)
    km = min(weekly * share, config.volume.max_long_run_km)
    ceiling = int(weekly * MAX_LONG_RUN_SHARE)
    return max(1, min(int(round(km)), ceiling, weekly - 1))


def _running_slots(config: PlanConfig) -> list[tuple[int, str]]:
    return [
        (index, role)
        for index, role in enumerate(config.week_template)
        if role in DAILY_WEIGHTS
    ]


def _distribute(remainder: int, slots: list[tuple[int, str]]) -> dict[int, int]:
    """把長跑以外的公里數分給其他跑步日，總和一定等於 remainder。"""
    if not slots:
        return {}
    counts: dict[str, int] = {}
    for _, role in slots:
        counts[role] = counts.get(role, 0) + 1

    shares = [DAILY_WEIGHTS[role] / counts[role] for _, role in slots]
    total_share = sum(shares)
    raw = [remainder * share / total_share for share in shares]

    assigned = [max(1, int(value)) for value in raw]
    drift = remainder - sum(assigned)
    order = sorted(range(len(slots)), key=lambda i: raw[i] - int(raw[i]), reverse=True)
    step = 1 if drift > 0 else -1
    position = 0
    while drift != 0 and order:
        index = order[position % len(order)]
        if step < 0 and assigned[index] <= 1:
            position += 1
            if position > len(order) * 3:
                break
            continue
        assigned[index] += step
        drift -= step
        position += 1

    return {slots[i][0]: assigned[i] for i in range(len(slots))}


def week_volume(config: PlanConfig, week: int) -> WeekVolume:
    phase, phase_week = config.phases.phase_of(week)

    if phase == "taper":
        weekly_raw = _taper_weekly_km(config, phase_week)
    else:
        weekly_raw = _loading_weekly_km(config, week)
    weekly = max(len(_running_slots(config)) + 1, int(round(weekly_raw)))

    long_run = _long_run_km(config, phase, phase_week, weekly)
    daily = [0] * 7
    long_index = config.week_template.index("long")
    daily[long_index] = long_run
    for index, km in _distribute(weekly - long_run, _running_slots(config)).items():
        daily[index] = km

    return WeekVolume(
        week=week,
        phase=phase,
        phase_week=phase_week,
        weekly_km=weekly,
        long_run_km=long_run,
        daily_km=tuple(daily),
    )


def curve(config: PlanConfig) -> list[WeekVolume]:
    return [week_volume(config, week) for week in range(1, config.total_weeks + 1)]

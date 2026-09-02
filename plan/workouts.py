from __future__ import annotations

from dataclasses import dataclass

from .config import WEEKDAY_NAMES
from .intensity import Targets, duration_text

WARMUP_KM = 2
COOLDOWN_KM = 1.5
REP_WITH_RECOVERY_KM = 1.4


@dataclass(frozen=True)
class DailyWorkout:
    day: str
    role: str
    title: str
    duration: str
    note: str


def _suffix(targets: Targets, key: str) -> str:
    text = targets.text_for(key)
    return f"（{text}）" if text else ""


def _at(targets: Targets, key: str) -> str:
    text = targets.text_for(key)
    return f" @ {text}" if text else ""


def _progress(phase_week: int, phase_length: int) -> float:
    if phase_length <= 1:
        return 1.0
    return (phase_week - 1) / (phase_length - 1)


def _reps(km: int, floor: int = 3, ceiling: int = 8) -> int:
    """趟數由課量推算，熱身收操與組間慢跑都算進去。"""
    usable = km - WARMUP_KM - COOLDOWN_KM
    return max(floor, min(ceiling, int(round(usable / REP_WITH_RECOVERY_KM))))


def _rest(index: int) -> DailyWorkout:
    if index == 0:
        return DailyWorkout(
            day=WEEKDAY_NAMES[index],
            role="rest",
            title="完全休息",
            duration="全天",
            note="讓身體完整恢復，這天不用補課。",
        )
    return DailyWorkout(
        day=WEEKDAY_NAMES[index],
        role="rest",
        title="休息 + 伸展",
        duration="15-20 分鐘",
        note="雙腿緊繃的話，散步和伸展就夠了。",
    )


def _strength(index: int, phase: str) -> DailyWorkout:
    table = {
        "base": ("基礎肌力 + 核心", "15-20 分鐘", "以徒手動作建立習慣與穩定度。"),
        "build": ("肌力 + 核心", "25-30 分鐘", "跑量拉高後更需要臀腿穩定度，不要做到力竭。"),
        "specific": ("維持肌力 + 核心", "15-20 分鐘", "維持即可，不要影響隔天的主課。"),
        "taper": ("輕量肌力 + 活動度", "10-15 分鐘", "以放鬆與維持啟動感為主。"),
    }
    title, duration, note = table[phase]
    return DailyWorkout(WEEKDAY_NAMES[index], "strength", title, duration, note)


def _easy(index: int, km: int, phase: str, targets: Targets) -> DailyWorkout:
    title = f"輕鬆跑 {km}K{_suffix(targets, 'easy')}"
    note = "維持舒服節奏，讓跑姿保持穩定。"
    if phase == "specific":
        title = f"輕鬆跑 {km}K{_suffix(targets, 'easy')} + 跑姿喚醒 4 組"
        note = "跑姿喚醒只是維持腳感，不是衝刺。"
    elif phase == "taper":
        note = "刻意放輕，讓身體準備恢復。"
    return DailyWorkout(
        WEEKDAY_NAMES[index], "easy", title, duration_text(km, targets, "easy"), note
    )


def _recovery(index: int, km: int, phase: str, targets: Targets) -> DailyWorkout:
    title = f"恢復跑 {km}K{_suffix(targets, 'recovery')}"
    note = "跑完應該覺得更輕鬆，而不是更累。"
    if phase in {"build", "specific"}:
        note = "隔天要長跑，今天寧可跑太慢也不要跑太快。"
    return DailyWorkout(
        WEEKDAY_NAMES[index],
        "recovery",
        title,
        duration_text(km, targets, "recovery"),
        note,
    )


def _quality(
    index: int,
    km: int,
    phase: str,
    phase_week: int,
    phase_length: int,
    targets: Targets,
    is_down_week: bool,
) -> DailyWorkout:
    duration = duration_text(km, targets, "easy")
    day = WEEKDAY_NAMES[index]

    if is_down_week:
        return DailyWorkout(
            day,
            "quality",
            f"輕鬆跑 {km}K{_suffix(targets, 'easy')}",
            duration,
            "降量週不做主課，讓身體吸收前幾週訓練。",
        )

    progress = _progress(phase_week, phase_length)

    if phase == "base":
        title = f"輕鬆跑 {km}K{_suffix(targets, 'easy')} + 跑姿喚醒 4 組 20 秒"
        note = "基礎期不追強度，喚醒只是讓腳感醒著。"
    elif phase == "build":
        reps = _reps(km, ceiling=4 + int(round(progress * 4)))
        title = (
            f"{km}K：熱身 {WARMUP_KM}K + 1K x {reps}"
            f"{_at(targets, 'quality')}（組間慢跑 400m）+ 收操"
        )
        note = "每趟跑得一樣穩比越跑越快重要；掉速明顯就提前收。"
    elif phase == "specific":
        if progress < 0.34:
            reps = _reps(km)
            title = (
                f"{km}K：熱身 {WARMUP_KM}K + 1K x {reps}"
                f"{_at(targets, 'quality')}（組間慢跑 400m）+ 收操"
            )
            note = "專項期前段仍保留間歇維持速度。"
        elif progress < 0.67:
            title = (
                f"{km}K：熱身 {WARMUP_KM}K + 1K x 3{_at(targets, 'quality')}"
                f" + 馬拉松節奏 3K{_at(targets, 'marathon')} + 收操"
            )
            note = "從間歇過渡到比賽節奏；節奏段落明顯比間歇慢。"
        else:
            segment = max(5, int(round(km * 0.7)))
            title = (
                f"{km}K：熱身 {WARMUP_KM}K + 馬拉松節奏 {segment}K"
                f"{_at(targets, 'marathon')} + 收操"
            )
            note = "連續節奏要能一路撐完，跑硬了就是練錯。"
    else:
        remaining = 1.0 - progress
        if remaining < 0.34:
            title = f"輕鬆跑 {km}K{_suffix(targets, 'easy')} + 4 組 20 秒喚醒"
            note = "保持輕鬆，讓身體維持醒著的狀態。"
        else:
            segment = max(2, int(round(km * 0.45)))
            title = (
                f"{km}K：熱身 {WARMUP_KM}K + 馬拉松節奏 {segment}K"
                f"{_at(targets, 'marathon')} + 收操"
            )
            note = "維持節奏感即可，不再增加負荷。"

    return DailyWorkout(day, "quality", title, duration, note)


def _long(
    index: int,
    km: int,
    phase: str,
    targets: Targets,
    note_override: str | None,
) -> DailyWorkout:
    notes = {
        "base": "以能聊天的節奏完成，先把距離穩定跑完。",
        "build": "維持舒服節奏，優先練耐力與穩定性，不要在最後幾公里加速。",
        "specific": "超過 60 分鐘就照補給計畫吃，速度全程保持可控制。",
        "taper": "比前幾週再輕一點，只保留長跑腳感。",
    }
    return DailyWorkout(
        WEEKDAY_NAMES[index],
        "long",
        f"長跑 {km}K{_suffix(targets, 'long_run')}",
        duration_text(km, targets, "long_run"),
        note_override or notes[phase],
    )


def build_day(
    *,
    index: int,
    role: str,
    km: int,
    phase: str,
    phase_week: int,
    phase_length: int,
    targets: Targets,
    is_down_week: bool = False,
    long_run_note: str | None = None,
) -> DailyWorkout:
    if role == "rest":
        return _rest(index)
    if role == "strength":
        return _strength(index, phase)
    if role == "easy":
        return _easy(index, km, phase, targets)
    if role == "recovery":
        return _recovery(index, km, phase, targets)
    if role == "quality":
        return _quality(
            index, km, phase, phase_week, phase_length, targets, is_down_week
        )
    if role == "long":
        return _long(index, km, phase, targets, long_run_note)
    raise ValueError(f"未知的角色：{role}")


def race_day(index: int, name: str, distance_text: str) -> DailyWorkout:
    return DailyWorkout(
        WEEKDAY_NAMES[index],
        "race",
        f"{name} {distance_text}",
        "比賽日",
        "前段刻意保守，補給照練過的節奏執行。",
    )

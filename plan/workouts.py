from __future__ import annotations

from dataclasses import dataclass

from .config import WEEKDAY_NAMES
from .intensity import LABELS, Targets, duration_text, format_time

WARMUP_KM = 2
COOLDOWN_KM = 1.5
REP_KM = 1
REP_RECOVERY_KM = 0.4
REP_WITH_RECOVERY_KM = REP_KM + REP_RECOVERY_KM
MIN_COOLDOWN_KM = 1.0


@dataclass(frozen=True)
class Step:
    """手錶上的一段。距離或時間擇一；target 是 Targets 的 key，None 表示不設強度。"""

    label: str
    km: float | None = None
    seconds: int | None = None
    target: str | None = None


@dataclass(frozen=True)
class Repeat:
    times: int
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class DailyWorkout:
    day: str
    role: str
    title: str
    duration: str
    note: str
    # 結構化分段，給手錶用。休息日與肌力日沒有。
    steps: tuple[Step | Repeat, ...] = ()


STRIDES = Repeat(4, (Step("跑姿喚醒", seconds=20), Step("走路恢復", seconds=60)))

# 目標賽短於這個距離，節奏跑改練半馬配速。
MARATHON_PACE_MIN_KM = 30.0


def race_pace_key(distance_km: float) -> str:
    """節奏跑要練的是目標賽的配速：半馬課表練馬拉松配速會慢十幾秒，等於沒練到比賽強度。"""
    return "marathon" if distance_km >= MARATHON_PACE_MIN_KM else "half_marathon"


def total_km(steps: tuple[Step | Repeat, ...]) -> float:
    total = 0.0
    for item in steps:
        if isinstance(item, Repeat):
            total += item.times * sum(step.km or 0 for step in item.steps)
        else:
            total += item.km or 0
    return round(total, 3)


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


def _warmup() -> Step:
    return Step("熱身", km=WARMUP_KM, target="easy")


def _cooldown(km: int, used: float) -> Step:
    """收操吃掉剩下的距離；課量太小算不出來時至少留 1K。"""
    return Step("收操", km=round(max(MIN_COOLDOWN_KM, km - used), 1), target="recovery")


def _intervals(reps: int) -> Repeat:
    return Repeat(
        reps,
        (
            Step("快跑", km=REP_KM, target="quality"),
            Step("慢跑恢復", km=REP_RECOVERY_KM, target="recovery"),
        ),
    )


def _easy_with_strides(km: int) -> tuple[Step | Repeat, ...]:
    return (Step("輕鬆跑", km=km, target="easy"), STRIDES)


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


def _strength(index: int, phase: str, is_down_week: bool = False) -> DailyWorkout:
    table = {
        "base": ("基礎肌力 + 核心", "15-20 分鐘", "以徒手動作建立習慣與穩定度。"),
        "build": ("肌力 + 核心", "25-30 分鐘", "跑量拉高後更需要臀腿穩定度，不要做到力竭。"),
        "specific": ("維持肌力 + 核心", "15-20 分鐘", "維持即可，不要影響隔天的主課。"),
        "taper": ("輕量肌力 + 活動度", "10-15 分鐘", "以放鬆與維持啟動感為主。"),
    }
    title, duration, note = table[phase]
    if is_down_week:
        # 降量週跑量是往下收的，沿用累積期那句「跑量拉高後」會自相矛盾。
        note = "降量週一樣照做，維持穩定度就好，不要做到力竭。"
    return DailyWorkout(WEEKDAY_NAMES[index], "strength", title, duration, note)


def _easy(index: int, km: int, phase: str, targets: Targets) -> DailyWorkout:
    title = f"輕鬆跑 {km}K{_suffix(targets, 'easy')}"
    note = "維持舒服節奏，讓跑姿保持穩定。"
    steps: tuple[Step | Repeat, ...] = (Step("輕鬆跑", km=km, target="easy"),)
    if phase == "specific":
        title = f"輕鬆跑 {km}K{_suffix(targets, 'easy')} + 跑姿喚醒 4 組"
        note = "跑姿喚醒只是維持腳感，不是衝刺。"
        steps = _easy_with_strides(km)
    elif phase == "taper":
        note = "刻意放輕，讓身體準備恢復。"
    return DailyWorkout(
        WEEKDAY_NAMES[index],
        "easy",
        title,
        duration_text(km, targets, "easy"),
        note,
        steps,
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
        (Step("恢復跑", km=km, target="recovery"),),
    )


def _quality(
    index: int,
    km: int,
    phase: str,
    phase_week: int,
    phase_length: int,
    targets: Targets,
    is_down_week: bool,
    race_pace: str = "marathon",
) -> DailyWorkout:
    duration = duration_text(km, targets, "easy")
    day = WEEKDAY_NAMES[index]
    pace_label = LABELS[race_pace]

    if is_down_week:
        return DailyWorkout(
            day,
            "quality",
            f"輕鬆跑 {km}K{_suffix(targets, 'easy')}",
            duration,
            "降量週不做主課，讓身體吸收前幾週訓練。",
            (Step("輕鬆跑", km=km, target="easy"),),
        )

    progress = _progress(phase_week, phase_length)

    if phase == "base":
        title = f"輕鬆跑 {km}K{_suffix(targets, 'easy')} + 跑姿喚醒 4 組 20 秒"
        note = "基礎期不追強度，喚醒只是讓腳感醒著。"
        steps = _easy_with_strides(km)
    elif phase == "build":
        reps = _reps(km, ceiling=4 + int(round(progress * 4)))
        title = (
            f"{km}K：熱身 {WARMUP_KM}K + 1K x {reps}"
            f"{_at(targets, 'quality')}（組間慢跑 400m）+ 收操"
        )
        note = "每趟跑得一樣穩比越跑越快重要；掉速明顯就提前收。"
        steps = (
            _warmup(),
            _intervals(reps),
            _cooldown(km, WARMUP_KM + reps * REP_WITH_RECOVERY_KM),
        )
    elif phase == "specific":
        if progress < 0.34:
            reps = _reps(km)
            title = (
                f"{km}K：熱身 {WARMUP_KM}K + 1K x {reps}"
                f"{_at(targets, 'quality')}（組間慢跑 400m）+ 收操"
            )
            note = "專項期前段仍保留間歇維持速度。"
            steps = (
                _warmup(),
                _intervals(reps),
                _cooldown(km, WARMUP_KM + reps * REP_WITH_RECOVERY_KM),
            )
        elif progress < 0.67:
            title = (
                f"{km}K：熱身 {WARMUP_KM}K + 1K x 3{_at(targets, 'quality')}"
                f" + {pace_label} 3K{_at(targets, race_pace)} + 收操"
            )
            note = "從間歇過渡到比賽節奏；節奏段落明顯比間歇慢。"
            steps = (
                _warmup(),
                _intervals(3),
                Step(pace_label, km=3, target=race_pace),
                _cooldown(km, WARMUP_KM + 3 * REP_WITH_RECOVERY_KM + 3),
            )
        else:
            segment = max(5, int(round(km * 0.7)))
            title = (
                f"{km}K：熱身 {WARMUP_KM}K + {pace_label} {segment}K"
                f"{_at(targets, race_pace)} + 收操"
            )
            note = "連續節奏要能一路撐完，跑硬了就是練錯。"
            steps = (
                _warmup(),
                Step(pace_label, km=segment, target=race_pace),
                _cooldown(km, WARMUP_KM + segment),
            )
    else:
        remaining = 1.0 - progress
        if remaining < 0.34:
            title = f"輕鬆跑 {km}K{_suffix(targets, 'easy')} + 4 組 20 秒喚醒"
            note = "保持輕鬆，讓身體維持醒著的狀態。"
            steps = _easy_with_strides(km)
        else:
            segment = max(2, int(round(km * 0.45)))
            title = (
                f"{km}K：熱身 {WARMUP_KM}K + {pace_label} {segment}K"
                f"{_at(targets, race_pace)} + 收操"
            )
            note = "維持節奏感即可，不再增加負荷。"
            steps = (
                _warmup(),
                Step(pace_label, km=segment, target=race_pace),
                _cooldown(km, WARMUP_KM + segment),
            )

    return DailyWorkout(day, "quality", title, duration, note, steps)


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
        (Step("長跑", km=km, target="long_run"),),
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
    race_pace: str = "marathon",
) -> DailyWorkout:
    if role == "rest":
        return _rest(index)
    if role == "strength":
        return _strength(index, phase, is_down_week)
    if role == "easy":
        return _easy(index, km, phase, targets)
    if role == "recovery":
        return _recovery(index, km, phase, targets)
    if role == "quality":
        return _quality(
            index, km, phase, phase_week, phase_length, targets, is_down_week, race_pace
        )
    if role == "long":
        return _long(index, km, phase, targets, long_run_note)
    raise ValueError(f"未知的角色：{role}")


def time_trial(
    index: int,
    distance_km: float,
    targets: Targets,
    benchmark: tuple[str, int] | None = None,
) -> DailyWorkout:
    """benchmark 是（比賽目標文字, 測驗距離的等價秒數），有目標成績才給。"""
    km_text = f"{distance_km:g}K"
    note = "用能平均撐完的配速跑，前 2K 不要衝；前一天休息或輕鬆跑。"
    if benchmark is not None:
        goal, seconds = benchmark
        note += (
            f"跑進 {format_time(seconds)} 代表{goal} 的目標有機會；"
            "明顯慢的話，比賽目標往後調，不要硬撐。"
        )
    return DailyWorkout(
        WEEKDAY_NAMES[index],
        "test",
        f"{km_text} 測驗：熱身 {WARMUP_KM}K + {km_text} 全力 + 收操 {COOLDOWN_KM:g}K",
        duration_text(distance_km + WARMUP_KM + COOLDOWN_KM, targets, "easy"),
        note,
        (
            _warmup(),
            Step("測驗", km=distance_km),
            Step("收操", km=COOLDOWN_KM, target="recovery"),
        ),
    )


def race_day(
    index: int, name: str, distance_text: str, distance_km: float | None = None
) -> DailyWorkout:
    return DailyWorkout(
        WEEKDAY_NAMES[index],
        "race",
        f"{name} {distance_text}",
        "比賽日",
        "前段刻意保守，補給照練過的節奏執行。",
        (Step(name, km=distance_km),) if distance_km else (),
    )

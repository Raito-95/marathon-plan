from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import fueling, intensity, schedule, volume, workouts
from .config import PlanConfig, TuneUpRace
from .intensity import Targets
from .workouts import DailyWorkout

PHASE_NAMES = {
    "base": "基礎期",
    "build": "建構期",
    "specific": "專項期",
    "taper": "減量期",
}

REMINDERS = {
    "base": [
        "基礎期的目標是把跑步變成習慣，不是把自己練累。",
        "跑後伸展與補水，不要讓疲勞累積。",
        "覺得喘就放慢，能聊天的強度就是對的強度。",
    ],
    "build": [
        "跑量往上推的時候，睡眠與恢復比多跑幾公里重要。",
        "前一天很累就把主課改成輕鬆跑，不用硬補。",
        "長跑前一天保留體力，恢復跑就真的跑很慢。",
        "補給要從現在練，不要等到比賽當天第一次嘗試。",
    ],
    "specific": [
        "長跑超過 90 分鐘就照比賽的補給節奏吃與喝。",
        "節奏段落只求穩定，不要在訓練裡把比賽跑掉。",
        "腿沉、心率偏高或睡不好，就降強度或把長跑砍短。",
        "長跑至少演練一次比賽日的鞋子、衣服與補給。",
    ],
    "taper": [
        "減量期間不要臨時加練，也不要補之前漏掉的課。",
        "這幾週練不出新的體能，維持腳感就好。",
        "睡眠、補水與飲食比多跑幾公里更重要。",
    ],
}

INTENSITY_NOTES = {
    "base": "輕鬆跑與長跑維持能完整說話的節奏；覺得喘就放慢或改跑走。",
    "build": (
        "輕鬆跑 / 恢復跑 / 長跑：能完整說話的舒服節奏。\n"
        "主課：用最後一趟還跑得出來的強度，不是每趟都拚。"
    ),
    "specific": (
        "輕鬆跑 / 恢復跑：刻意跑慢，這兩天的任務是恢復。\n"
        "長跑：用能從頭穩定跑到尾的節奏。\n"
        "馬拉松節奏：比賽當天有把握撐完全程的節奏，明顯比間歇慢。"
    ),
    "taper": "所有跑步都刻意放輕；短段比賽節奏只用來喚醒身體，不跑到累。",
}

DOWNGRADE_NOTE = "降階原則：主課跑不動就改輕鬆跑，長跑撐不住就縮短距離或分段走。"



@dataclass(frozen=True)
class WeekPlan:
    week: int
    start: date
    end: date
    phase: str
    phase_week: int
    week_type: str
    focus: str
    weekly_km_text: str
    long_run_text: str
    days: tuple[DailyWorkout, ...]
    reminder: str
    fuel: str

    @property
    def phase_name(self) -> str:
        return PHASE_NAMES[self.phase]


@dataclass(frozen=True)
class TrainingPlan:
    config: PlanConfig
    targets: Targets
    weeks: tuple[WeekPlan, ...]

    def week(self, number: int) -> WeekPlan:
        return self.weeks[schedule.clamp(self.config, number) - 1]

    def week_for(self, today: date) -> WeekPlan:
        return self.week(schedule.week_to_publish(self.config, today))


STANDARD_DISTANCES = ((42.195, "42.195K"), (21.0975, "21.1K"))


def _distance_text(km: float) -> str:
    for value, text in STANDARD_DISTANCES:
        if abs(km - value) < 0.01:
            return text
    return f"{round(km, 1):g}K"


def _pre_post_cap(race: TuneUpRace) -> int:
    return max(5, int(round(race.distance_km * 0.66)))


def _race_week(
    config: PlanConfig, race: TuneUpRace, targets: Targets
) -> tuple[str, str, str, tuple[DailyWorkout, ...], str, str]:
    shakeout = max(3, int(round(config.volume.peak_weekly_km * 0.06)))
    race_index = race.date.weekday()

    days: list[DailyWorkout] = []
    for index, role in enumerate(config.week_template):
        if index == race_index:
            days.append(workouts.race_day(index, race.name, _distance_text(race.distance_km)))
        elif role == "rest":
            days.append(
                DailyWorkout(
                    workouts.WEEKDAY_NAMES[index],
                    "rest",
                    "完全休息",
                    "全天",
                    "比賽週最重要的一課就是休息。",
                )
            )
        elif role == "strength":
            days.append(
                DailyWorkout(
                    workouts.WEEKDAY_NAMES[index],
                    "strength",
                    "輕量啟動 + 活動度",
                    "10-15 分鐘",
                    "只做喚醒，不做任何會讓腿痠的訓練。",
                )
            )
        elif role == "long":
            days.append(
                DailyWorkout(
                    workouts.WEEKDAY_NAMES[index],
                    "rest",
                    "休息或散步",
                    "20-30 分鐘",
                    "比賽排在其他天，這天不再安排長跑。",
                )
            )
        else:
            days.append(
                DailyWorkout(
                    workouts.WEEKDAY_NAMES[index],
                    role,
                    f"輕鬆跑 {shakeout}K",
                    f"約 {shakeout * 7} 分鐘",
                    "維持腳感即可，不要在比賽週練體能。",
                )
            )

    running = sum(1 for role in config.week_template if role in {"easy", "quality", "recovery"})
    total = running * shakeout + race.distance_km
    return (
        "比賽週",
        f"{race.date.isoformat()} 比{race.name}，平日只維持腳感，把狀態留到比賽當天。",
        f"約 {round(total)}K（含比賽 {_distance_text(race.distance_km)}）",
        tuple(days),
        "比賽週不練新東西：鞋子、衣服、補給都用練過的。",
        fueling.race_day_advice(
            race.distance_km,
            intensity.duration_minutes(race.distance_km, targets, "marathon"),
        ),
    )


def _week_type_and_focus(
    config: PlanConfig,
    week: int,
    phase: str,
    phase_week: int,
    week_volume: volume.WeekVolume,
    nearby: dict[str, TuneUpRace | None],
) -> tuple[str, str, int, str | None]:
    long_run = week_volume.long_run_km
    long_note = None

    if nearby["rehearsal"] is not None and nearby["rehearsal"].is_long:
        race = nearby["rehearsal"]
        long_run = min(int(round(race.distance_km)), int(config.volume.max_long_run_km))
        long_note = (
            f"當成{race.name}的距離演練：鞋子、衣服與補給照比賽日用一次，配速維持輕鬆。"
        )
        return (
            "距離演練週",
            f"兩週後比{race.name}，這趟長跑是最後一次完整演練。",
            long_run,
            long_note,
        )

    if nearby["next"] is not None:
        race = nearby["next"]
        long_run = min(long_run, _pre_post_cap(race))
        return (
            "賽前調整週",
            f"下週比{race.name}，本週開始降量，長跑收在 {long_run}K。",
            long_run,
            long_note,
        )

    if nearby["previous"] is not None:
        race = nearby["previous"]
        long_run = min(long_run, _pre_post_cap(race))
        return (
            "恢復週",
            f"剛比完{race.name}，這週不追跑量，痠痛沒退就再減。",
            long_run,
            long_note,
        )

    if phase == "taper":
        return (
            "減量週",
            f"刻意降低負荷，長跑收在 {long_run}K，把狀態留到比賽日。",
            long_run,
            long_note,
        )

    if schedule.is_down_week(config, week):
        return (
            "降量週",
            f"降量週，週跑量收在 {week_volume.weekly_km}K，讓身體吸收前幾週訓練。",
            long_run,
            long_note,
        )

    headline = {
        "base": "建立規律，把跑步量穩定累積起來",
        "build": "跑量與長跑一起往上推",
        "specific": "把比賽節奏與長距離放進同一週",
        "taper": "維持跑感",
    }[phase]
    return (
        "訓練週",
        f"{headline}：週跑量 {week_volume.weekly_km}K，長跑 {long_run}K。",
        long_run,
        long_note,
    )


def build(config: PlanConfig) -> TrainingPlan:
    targets = intensity.build(config.athlete)
    races = schedule.tune_ups_by_week(config)
    phase_lengths = {
        "base": config.phases.base,
        "build": config.phases.build,
        "specific": config.phases.specific,
        "taper": config.phases.taper,
    }

    weeks: list[WeekPlan] = []
    for number in range(1, config.total_weeks + 1):
        week_volume = volume.week_volume(config, number)
        phase, phase_week = week_volume.phase, week_volume.phase_week
        start, end = schedule.week_dates(config, number)

        if number in races:
            week_type, focus, weekly_text, days, reminder, fuel = _race_week(
                config, races[number], targets
            )
            weeks.append(
                WeekPlan(
                    week=number,
                    start=start,
                    end=end,
                    phase=phase,
                    phase_week=phase_week,
                    week_type=week_type,
                    focus=focus,
                    weekly_km_text=weekly_text,
                    long_run_text=(
                        f"{_distance_text(races[number].distance_km)}（{races[number].name}）"
                    ),
                    days=days,
                    reminder=reminder,
                    fuel=fuel,
                )
            )
            continue

        nearby = {
            "next": races.get(number + 1),
            "previous": races.get(number - 1),
            "rehearsal": races.get(number + 2),
        }
        week_type, focus, long_run, long_note = _week_type_and_focus(
            config, number, phase, phase_week, week_volume, nearby
        )

        daily = list(week_volume.daily_km)
        long_index = config.week_template.index("long")
        if long_run != week_volume.long_run_km:
            daily[long_index] = long_run
        weekly_km = sum(daily)

        is_down = schedule.is_down_week(config, number)
        days = tuple(
            workouts.build_day(
                index=index,
                role=role,
                km=daily[index],
                phase=phase,
                phase_week=phase_week,
                phase_length=phase_lengths[phase],
                targets=targets,
                is_down_week=is_down,
                long_run_note=long_note if role == "long" else None,
            )
            for index, role in enumerate(config.week_template)
        )

        long_minutes = intensity.duration_minutes(long_run, targets, "long_run")
        is_final = number == config.total_weeks
        if is_final:
            days = tuple(
                workouts.race_day(
                    index, config.race.name, _distance_text(config.race.distance_km)
                )
                if role == "long"
                else day
                for index, (role, day) in enumerate(zip(config.week_template, days))
            )
            weekly_km -= long_run

        weeks.append(
            WeekPlan(
                week=number,
                start=start,
                end=end,
                phase=phase,
                phase_week=phase_week,
                week_type="比賽週" if is_final else week_type,
                focus=(
                    f"{config.race.name}就在本週日，前段保守，照補給計畫執行。"
                    if is_final
                    else focus
                ),
                weekly_km_text=(
                    f"{weekly_km}K（不含比賽）" if is_final else f"{weekly_km}K"
                ),
                long_run_text=(
                    f"比賽日 {_distance_text(config.race.distance_km)}"
                    if is_final
                    else f"{long_run}K"
                ),
                days=days,
                reminder=REMINDERS[phase][(number - 1) % len(REMINDERS[phase])],
                fuel=(
                    fueling.race_day_advice(
                        config.race.distance_km,
                        intensity.duration_minutes(
                            config.race.distance_km, targets, "marathon"
                        ),
                    )
                    if is_final
                    else fueling.long_run_advice(long_minutes)
                ),
            )
        )

    return TrainingPlan(config=config, targets=targets, weeks=tuple(weeks))

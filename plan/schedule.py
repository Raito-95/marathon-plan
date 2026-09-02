from __future__ import annotations

from datetime import date, timedelta

from .config import PlanConfig, TuneUpRace


def first_monday(config: PlanConfig) -> date:
    """第 1 週的星期一。最後一週的星期日就是比賽日，所以整份課表從比賽日往回推。"""
    race_week_monday = config.race.date - timedelta(days=config.race.date.weekday())
    return race_week_monday - timedelta(weeks=config.total_weeks - 1)


def week_dates(config: PlanConfig, week: int) -> tuple[date, date]:
    monday = first_monday(config) + timedelta(weeks=week - 1)
    return monday, monday + timedelta(days=6)


def week_containing(config: PlanConfig, value: date) -> int:
    """value 落在第幾個星期一到星期日的訓練週。"""
    return ((value - first_monday(config)).days // 7) + 1


def week_to_publish(config: PlanConfig, value: date) -> int:
    """value 這天該發佈的訓練週。

    每週提醒固定在台灣時間星期一早上送出，換算成 UTC 仍是星期日，所以判定起點要比
    星期一早一天；否則星期日會被算成剛結束的那一週。
    """
    start = first_monday(config) - timedelta(days=1)
    return ((value - start).days // 7) + 1


def is_finished(config: PlanConfig, value: date) -> bool:
    return week_to_publish(config, value) > config.total_weeks


def clamp(config: PlanConfig, week: int) -> int:
    return max(1, min(config.total_weeks, week))


def is_down_week(config: PlanConfig, week: int) -> bool:
    """三升一降：累積期每第 4 週降量。

    累積期最後一週是整份課表的峰值，即使剛好落在第 4 的倍數也不降量，
    否則跑量永遠到不了設定的 peak_weekly_km。
    """
    loading = config.phases.loading
    return week < loading and week % 4 == 0


def tune_ups_by_week(config: PlanConfig) -> dict[int, TuneUpRace]:
    return {
        week_containing(config, race.date): race for race in config.tune_up_races
    }


def next_tune_up(config: PlanConfig, today: date) -> TuneUpRace | None:
    for race in config.tune_up_races:
        if race.date >= today:
            return race
    return None

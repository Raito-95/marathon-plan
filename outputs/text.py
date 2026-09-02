from __future__ import annotations

from datetime import date
import math

from plan import schedule
from plan.plan import DOWNGRADE_NOTE, INTENSITY_NOTES, TrainingPlan, WeekPlan

WEEKDAYS = "一二三四五六日"


def _date_text(value: date) -> str:
    return f"{value.isoformat()}（{WEEKDAYS[value.weekday()]}）"


def _weeks_until(target: date, today: date) -> int:
    return max(0, math.ceil((target - today).days / 7))


def render_week(plan: TrainingPlan, week: WeekPlan, today: date) -> str:
    config = plan.config
    lines = [
        f"訓練計畫：{config.race.name}",
        f"賽事日期：{_date_text(config.race.date)}",
        f"距離比賽：約 {_weeks_until(config.race.date, today)} 週",
    ]

    upcoming = schedule.next_tune_up(config, today)
    if upcoming is not None:
        weeks = _weeks_until(upcoming.date, today)
        countdown = "本週" if weeks == 0 else f"約 {weeks} 週"
        lines.append(
            f"下一場比賽：{upcoming.name}｜{_date_text(upcoming.date)}｜{countdown}"
        )

    lines += [
        "",
        f"訓練階段：{week.phase_name}",
        f"本週類型：{week.week_type}",
        f"本週重點：{week.focus}",
        f"本週跑量：{week.weekly_km_text}",
        f"長跑：{week.long_run_text}",
        "身體不適時可少跑；能恢復比跑滿更重要。",
        "",
        "每日計畫：",
    ]

    for day in week.days:
        lines.append(f"{day.day}｜{day.title}｜{day.duration}")
        lines.append(f"  {day.note}")

    targets = plan.targets.summary_lines(config.athlete)
    if targets:
        lines += ["", "強度目標：", *targets]

    lines += [
        "",
        "強度說明：",
        INTENSITY_NOTES[week.phase],
        "",
        "補給：",
        week.fuel,
        "",
        "執行原則：",
        DOWNGRADE_NOTE,
        "",
        f"提醒：{week.reminder}",
    ]
    return "\n".join(lines)


def render(plan: TrainingPlan, today: date) -> str:
    return render_week(plan, plan.week_for(today), today)

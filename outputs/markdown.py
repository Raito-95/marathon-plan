from __future__ import annotations

from datetime import date

from plan import workouts
from plan.plan import TrainingPlan


def render(plan: TrainingPlan, today: date) -> str:
    config = plan.config
    phases = config.phases
    current = plan.week_for(today).week if not _outside(plan, today) else None

    lines = [
        f"# {config.race.name} {config.total_weeks} 週課表",
        "",
        f"- 比賽日：{config.race.date.isoformat()}",
        f"- 週期：{config.total_weeks} 週"
        f"（基礎 {phases.base} / 建構 {phases.build} /"
        f" 專項 {phases.specific} / 減量 {phases.taper}）",
        f"- 跑量：{config.volume.start_weekly_km:g}K 起，峰值"
        f" {config.volume.peak_weekly_km:g}K，長跑上限"
        f" {config.volume.max_long_run_km:g}K",
    ]
    for race in config.tune_up_races:
        lines.append(f"- 期中比賽：{race.name}（{race.date.isoformat()}）")

    targets = plan.targets.summary_lines(config.athlete, workouts.race_pace_key(config.race.distance_km))
    if targets:
        lines += ["", "## 強度目標", ""]
        lines += [f"- {line}" for line in targets]

    lines += [
        "",
        "## 週次總覽",
        "",
        "| 週 | 日期 | 階段 | 類型 | 跑量 | 長跑 |",
        "| ---: | --- | --- | --- | ---: | ---: |",
    ]
    for week in plan.weeks:
        marker = " **←本週**" if week.week == current else ""
        lines.append(
            f"| {week.week} | {week.start.isoformat()}~{week.end.isoformat()} |"
            f" {week.phase_name} | {week.week_type} |"
            f" {week.weekly_km_text} | {week.long_run_text}{marker} |"
        )

    lines += ["", "## 每週明細", ""]
    for week in plan.weeks:
        lines += [
            f"### 第 {week.week} 週 ・ {week.start.isoformat()}~{week.end.isoformat()}"
            f" ・ {week.phase_name} ・ {week.week_type}",
            "",
            week.focus,
            "",
            f"跑量 {week.weekly_km_text} ｜ 長跑 {week.long_run_text}",
            "",
            "| 日 | 內容 | 時間 | 備註 |",
            "| --- | --- | --- | --- |",
        ]
        for day in week.days:
            lines.append(
                f"| {day.day} | {day.title} | {day.duration} | {day.note} |"
            )
        lines += ["", f"補給：{week.fuel}", "", f"提醒：{week.reminder}", ""]

    return "\n".join(lines)


def _outside(plan: TrainingPlan, today: date) -> bool:
    first = plan.weeks[0]
    last = plan.weeks[-1]
    return today < first.start or today > last.end

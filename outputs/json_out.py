from __future__ import annotations

from dataclasses import asdict
from datetime import date
import json

from plan import workouts
from plan.plan import TrainingPlan


def to_dict(plan: TrainingPlan, today: date) -> dict:
    config = plan.config
    return {
        "race": {
            "name": config.race.name,
            "date": config.race.date.isoformat(),
            "distanceKm": config.race.distance_km,
        },
        "block": {
            "weeks": config.total_weeks,
            "phases": {
                "base": config.phases.base,
                "build": config.phases.build,
                "specific": config.phases.specific,
                "taper": config.phases.taper,
            },
        },
        "volume": asdict(config.volume),
        "tuneUpRaces": [
            {
                "name": race.name,
                "date": race.date.isoformat(),
                "distanceKm": race.distance_km,
            }
            for race in config.tune_up_races
        ],
        "targets": plan.targets.summary_lines(config.athlete, workouts.race_pace_key(config.race.distance_km)),
        "currentWeek": plan.week_for(today).week,
        "weeks": [
            {
                "week": week.week,
                "start": week.start.isoformat(),
                "end": week.end.isoformat(),
                "phase": week.phase,
                "phaseName": week.phase_name,
                "weekType": week.week_type,
                "focus": week.focus,
                "weeklyKm": week.weekly_km_text,
                "longRun": week.long_run_text,
                "reminder": week.reminder,
                "fuel": week.fuel,
                "days": [
                    {
                        "day": day.day,
                        "role": day.role,
                        "title": day.title,
                        "duration": day.duration,
                        "note": day.note,
                    }
                    for day in week.days
                ],
            }
            for week in plan.weeks
        ],
    }


def render(plan: TrainingPlan, today: date) -> str:
    return json.dumps(to_dict(plan, today), ensure_ascii=False, indent=2)

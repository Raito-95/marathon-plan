"""把課表上傳到 intervals.icu，再由它同步到 COROS 手錶。

COROS 的 Training API 只開放給合作夥伴，個人程式推不上去；intervals.icu 是合作夥伴之一，
而且個人帳號用 API key 就能寫入行事曆。每天的課轉成 intervals.icu 的課表文字，
在 intervals.icu 連結 COROS 並勾選 Upload planned workouts 之後，手錶上就是分段的結構化課表。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from plan.intensity import duration_minutes
from plan.plan import TrainingPlan, WeekPlan
from plan.workouts import DailyWorkout, Repeat, Step, total_km

BASE_URL = "https://intervals.icu/api/v1"
TIMEOUT_SECONDS = 20
# 只動自己上傳的課：external_id 用這個前綴，使用者手動排的課不會被刪。
EXTERNAL_PREFIX = "marathon-plan-"
# 本週加下週。intervals.icu 只把接下來 7 天推到 COROS，多傳一週讓星期日的排程也涵蓋得到。
DEFAULT_WEEKS = 2
SHORT_NAMES = {"easy": "輕鬆跑", "recovery": "恢復跑", "quality": "主課", "long": "長跑"}
# 這兩種課的標題本身就是名字：比賽名稱、「10K 測驗」。
TITLED_ROLES = {"race", "test"}


class IntervalsError(Exception):
    pass


@dataclass(frozen=True)
class IntervalsSettings:
    api_key: str
    athlete_id: str = "0"  # 0 代表 API key 本人

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "IntervalsSettings":
        env = os.environ if env is None else env
        api_key = (env.get("INTERVALS_API_KEY") or "").strip()
        if not api_key:
            raise IntervalsError("需要 INTERVALS_API_KEY（intervals.icu 設定頁的 Developer Settings）")
        athlete_id = (env.get("INTERVALS_ATHLETE_ID") or "").strip() or "0"
        return cls(api_key=api_key, athlete_id=athlete_id)


def _km_text(km: float) -> str:
    return f"{round(km, 3):g}km"


def _time_text(seconds: int) -> str:
    minutes, rest = divmod(seconds, 60)
    return f"{minutes}m" if minutes and not rest else f"{seconds}s"


def _pace_text(seconds: int) -> str:
    minutes, rest = divmod(int(round(seconds)), 60)
    return f"{minutes}:{rest:02d}"


def target_text(plan: TrainingPlan, key: str | None) -> str:
    """手錶一段只能有一個目標。心率優先，理由同 README：心率不會叫人跑超過能力。

    intervals.icu 不收絕對 bpm，只收最大心率的百分比，並用 intervals.icu 裡設定的最大心率
    換算回 bpm —— 所以那邊的最大心率要跟 MAX_HR 一致。
    """
    if key is None:
        return ""
    max_hr = plan.config.athlete.max_hr
    heart_rate = plan.targets.heart_rate.get(key)
    if heart_rate is not None and max_hr:
        low = int(round(heart_rate.low / max_hr * 100))
        high = int(round(heart_rate.high / max_hr * 100))
        return f" {low}-{high}% HR"
    pace = plan.targets.pace.get(key)
    if pace is not None:
        return f" {_pace_text(pace.low)}-{_pace_text(pace.high)}/km Pace"
    return ""


def _step_line(plan: TrainingPlan, step: Step) -> str:
    amount = _km_text(step.km) if step.km else _time_text(step.seconds or 0)
    return f"- {step.label} {amount}{target_text(plan, step.target)}"


def workout_text(plan: TrainingPlan, day: DailyWorkout) -> str:
    lines = [day.note, ""]
    for item in day.steps:
        if isinstance(item, Repeat):
            # 重複段前後都要空行，intervals.icu 才認得出範圍。
            if lines[-1]:
                lines.append("")
            lines.append(f"{item.times}x")
            lines += [_step_line(plan, step) for step in item.steps]
            lines.append("")
        else:
            lines.append(_step_line(plan, item))
    return "\n".join(lines).strip() + "\n"


def event_name(day: DailyWorkout) -> str:
    if day.role in TITLED_ROLES:
        return day.title.split("：")[0]
    km = total_km(day.steps)
    distance_steps = [
        step
        for item in day.steps
        for step in (item.steps if isinstance(item, Repeat) else (item,))
        if step.km
    ]
    if len(distance_steps) == 1:
        label = distance_steps[0].label
    else:
        label = SHORT_NAMES.get(day.role, "跑步")
    return f"{label} {km:g}K"


def week_events(plan: TrainingPlan, week: WeekPlan) -> list[dict[str, Any]]:
    events = []
    for index, day in enumerate(week.days):
        if not day.steps:
            continue
        on = week.start + timedelta(days=index)
        km = total_km(day.steps)
        key = "long_run" if day.role == "long" else "easy"
        events.append(
            {
                "category": "WORKOUT",
                "type": "Run",
                "start_date_local": f"{on.isoformat()}T00:00:00",
                "external_id": f"{EXTERNAL_PREFIX}{on.isoformat()}",
                "name": event_name(day),
                "description": workout_text(plan, day),
                "distance": int(round(km * 1000)),
                "moving_time": duration_minutes(km, plan.targets, key) * 60,
            }
        )
    return events


def upcoming_weeks(
    plan: TrainingPlan, today: date, weeks: int = DEFAULT_WEEKS
) -> list[WeekPlan]:
    first = plan.week_for(today).week
    last = min(first + weeks - 1, len(plan.weeks))
    return [plan.week(number) for number in range(first, last + 1)]


def render(plan: TrainingPlan, today: date) -> str:
    """預覽會上傳的內容，不需要 API key。"""
    events = [
        event for week in upcoming_weeks(plan, today) for event in week_events(plan, week)
    ]
    return json.dumps(events, ensure_ascii=False, indent=2)


Request = Callable[[str, str, IntervalsSettings, Any], Any]


def _request(method: str, url: str, settings: IntervalsSettings, body: Any = None) -> Any:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    token = base64.b64encode(f"API_KEY:{settings.api_key}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise IntervalsError(f"intervals.icu 回應 {exc.code}（{method} {url}）") from exc
    except urllib.error.URLError as exc:
        raise IntervalsError(f"連線 intervals.icu 失敗：{exc.reason}") from exc
    return json.loads(raw) if raw.strip() else None


@dataclass(frozen=True)
class SyncResult:
    created: int
    updated: int
    deleted: int
    oldest: date
    newest: date


def sync(
    plan: TrainingPlan,
    today: date,
    settings: IntervalsSettings,
    weeks: int = DEFAULT_WEEKS,
    request: Request = _request,
) -> SyncResult:
    """讓 intervals.icu 在這幾週的課跟課表一致：新的建立、有的更新、課表裡沒了的刪掉。

    不靠 bulk upsert 的 external_id 比對 —— 文件寫那只對同一個 OAuth app 有效，
    API key 不保證算數。先列出區間內的課，用 id 更新或刪除，重跑幾次都不會重複。
    """
    chosen = upcoming_weeks(plan, today, weeks)
    wanted = {
        event["external_id"]: event
        for week in chosen
        for event in week_events(plan, week)
    }
    oldest, newest = chosen[0].start, chosen[-1].end

    base = f"{BASE_URL}/athlete/{urllib.parse.quote(settings.athlete_id)}/events"
    query = urllib.parse.urlencode(
        {"oldest": oldest.isoformat(), "newest": newest.isoformat(), "category": "WORKOUT"}
    )
    existing = request("GET", f"{base}?{query}", settings, None) or []
    ours = {
        str(event["external_id"]): event["id"]
        for event in existing
        if str(event.get("external_id") or "").startswith(EXTERNAL_PREFIX)
    }

    doomed = [{"id": event_id} for key, event_id in ours.items() if key not in wanted]
    if doomed:
        request("PUT", f"{base}/bulk-delete", settings, doomed)

    updated = 0
    for key, event in wanted.items():
        if key in ours:
            request("PUT", f"{base}/{ours[key]}", settings, event)
            updated += 1

    fresh = [event for key, event in wanted.items() if key not in ours]
    if fresh:
        request("POST", f"{base}/bulk", settings, fresh)

    return SyncResult(
        created=len(fresh),
        updated=updated,
        deleted=len(doomed),
        oldest=oldest,
        newest=newest,
    )

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import urllib.error
import urllib.request

ENDPOINT = "https://api.line.me/v2/bot/message/push"
TIMEOUT_SECONDS = 10


class LineError(Exception):
    pass


@dataclass(frozen=True)
class LineSettings:
    token: str
    to: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "LineSettings":
        env = os.environ if env is None else env
        token = (env.get("LINE_CHANNEL_ACCESS_TOKEN") or "").strip()
        to = (env.get("LINE_TO_ID") or "").strip()
        if not token or not to:
            raise LineError("需要 LINE_CHANNEL_ACCESS_TOKEN 與 LINE_TO_ID")
        return cls(token=token, to=to)


def push(message: str, settings: LineSettings) -> None:
    if not message.strip():
        raise LineError("訊息不可為空")

    payload = json.dumps(
        {"to": settings.to, "messages": [{"type": "text", "text": message}]}
    ).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise LineError(f"LINE 回應 {response.status}")
    except urllib.error.HTTPError as exc:
        raise LineError(f"LINE 回應 {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise LineError(f"連線 LINE 失敗：{exc.reason}") from exc

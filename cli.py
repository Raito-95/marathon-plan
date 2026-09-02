from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

from outputs import FORMATS, line as line_output
from plan import build, resolve
from plan.config import ConfigError
from plan.schedule import is_finished

DEFAULT_CONFIG = Path(__file__).resolve().parent / "data" / "plan.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="產生馬拉松訓練課表。")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="設定檔路徑；設了 PLAN_CONFIG 環境變數就以它為準。",
    )
    parser.add_argument(
        "--format",
        choices=sorted(FORMATS),
        default="text",
        help="text 只輸出當週，markdown 與 json 輸出整份課表。",
    )
    parser.add_argument("--date", type=date.fromisoformat, help="指定日期（YYYY-MM-DD）。")
    parser.add_argument(
        "--send", action="store_true", help="把 text 輸出推播到 LINE；預設只印出來。"
    )
    parser.add_argument("--out", type=Path, help="寫入檔案而非印到終端機。")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    today = args.date or date.today()

    try:
        config = resolve(args.config)
    except ConfigError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1

    if is_finished(config, today):
        print(
            f"訓練週期已結束（{config.race.name} {config.race.date.isoformat()}）。\n"
            "要接下一場比賽，請更新設定檔的 race.date。"
        )
        return 0

    plan = build(config)
    rendered = FORMATS[args.format](plan, today)

    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
        print(f"已寫入 {args.out}")
    elif not args.send:
        print(rendered)

    if args.send:
        if args.format != "text":
            print("錯誤：--send 只支援 text 格式", file=sys.stderr)
            return 1
        try:
            line_output.push(rendered, line_output.LineSettings.from_env())
        except line_output.LineError as exc:
            print(f"錯誤：{exc}", file=sys.stderr)
            return 1
        print("已推播到 LINE。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

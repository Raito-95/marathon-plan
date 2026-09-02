# marathon-plan

把馬拉松訓練課表寫成可運算的設定，而不是一份固定的 PDF。

給比賽日、起始週跑量與峰值週跑量，產生一份 18 週備賽課表 —— 分期、三升一降的跑量曲線、
每日課表、目標心率與配速都是算出來的。無資料庫、無外部服務，執行期只用標準函式庫。

```bash
python cli.py --format markdown --out plan.md
```

## 為什麼是設定驅動

課表的麻煩不在寫出來，在維護。這三件事在多數課表工具裡都要重排：

**換賽事** —— 改設定檔的 `race.date`，整份課表自動平移，最後一週的星期日永遠是比賽日。
抽籤沒中改跑別場也一樣。

**插入期中比賽** —— 在 `tune_up_races` 加一場，程式算出它落在第幾週，然後改寫比賽當週、
前兩週（距離演練）、前一週（減量）與後一週（恢復）。日期改了這四週跟著移動；距離太短
（未滿 15K）就不安排距離演練。

**換強度依據** —— 有實測心率就給目標 bpm，有目標成績就給配速區間，兩個都沒有就退回感受式
描述。同一份課表支援三種狀態。

## 兩個設計上的坑

**排程時間會飄，週次判定不能天真。** 提醒排在台灣時間星期一早上，換算成 UTC 是星期日 23:00，
但 GitHub Actions 的排程會延遲數十分鐘。以星期一切週的話，跨過午夜的那幾次會被算成下一週 ——
實際造成過漏送一整週、重送兩週。`schedule.week_to_publish` 把判定起點往前挪一天，星期日與
星期一就落在同一個週次。

**個人化的配速可能是危險的。** 配速由目標完賽時間換算；目標訂得比實力高的時候，算出來的
「輕鬆跑」會比跑者實際跑得動的強度還快，照著跑每天都是硬課。所以沒有實測成績時不設目標時間，
並且優先用心率當強度依據 —— 心率不會叫人跑超過能力。

## 設定

`data/plan.json`：

```json
{
  "race": { "name": "2027 東京馬拉松", "date": "2027-03-07", "distance_km": 42.195 },
  "block": { "weeks": 18, "phases": { "base": 4, "build": 6, "specific": 5, "taper": 3 } },
  "volume": { "start_weekly_km": 40, "peak_weekly_km": 65, "max_long_run_km": 32 },
  "week_template": ["rest", "easy", "strength", "quality", "rest", "recovery", "long"],
  "tune_up_races": [
    { "name": "半程馬拉松", "date": "2027-01-24", "distance_km": 21.0975 }
  ]
}
```

`week_template` 的 index 0 是星期一，角色可選 `rest` / `easy` / `strength` / `quality` /
`recovery` / `long`，其中 `long` 必須剛好一個。想跑五天就把某個 `rest` 換成 `easy`，
跑量會自動重新分配。

跑量曲線：累積期從 `start_weekly_km` 線性爬到 `peak_weekly_km`，每第 4 週乘上
`down_week_factor` 降量，峰值落在累積期最後一週，減量期再遞減到比賽。長跑取週跑量的
固定比例（基礎 32% / 建構 38% / 專項 45%），並受 `max_long_run_km` 限制。
剩下的公里數按角色權重分給其他跑步日，**每週的每日距離加總一定等於週跑量**，有測試擋著。

## 個人資料

生理數據與目標成績建議放環境變數，設定檔就能公開：

| 變數 | 說明 |
| --- | --- |
| `MAX_HR` / `RESTING_HR` | 實測最大 / 靜息心率，兩個都給才生效 |
| `MARATHON_GOAL` | 目標完賽時間，`H:MM:SS` |
| `HALF_MARATHON_GOAL` | 半馬目標，選填 |
| `PLAN_CONFIG` | 整份設定的 JSON。設了就以它為準，不讀設定檔 |

`PLAN_CONFIG` 是給 CI 用的：課表本身也算個人資訊，放 repository secret 就不必進版控，換週期時改那一個 secret 即可。

## 輸出

輸出與課表產生分開，加新格式只要在 `outputs/__init__.py` 的 `FORMATS` 註冊。

| 格式 | 內容 |
| --- | --- |
| `text` | 當週課表，給 LINE 或終端機 |
| `markdown` | 整份課表，含週次總覽與每週明細 |
| `json` | 整份課表，給前端或其他工具 |

```bash
python cli.py                              # 當週，印到終端機
python cli.py --date 2027-01-20            # 指定日期
python cli.py --format json --out plan.json
python cli.py --send                       # 推播到 LINE
```

`--send` 需要 `LINE_CHANNEL_ACCESS_TOKEN` 與 `LINE_TO_ID`，且只支援 `text`。
比賽日過後不再推播，只印出週期已結束的提示。

## 排程

`.github/workflows/weekly.yml` 每週推播一次。

全部走 repository secrets：`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_TO_ID`、`PLAN_CONFIG`、
`MAX_HR`、`RESTING_HR`、`MARATHON_GOAL`、`HALF_MARATHON_GOAL`。

心率與成績不是憑證，但公開 repo 的 Actions log 任何人都讀得到，而 secrets 會在 log 裡
被遮成 `***`、variables 不會 —— 所以個人數據放 secrets 而不是 variables。

沒有設 `PLAN_CONFIG` 就用 repo 裡的 `data/plan.json`。

## 測試

```bash
pip install -r requirements-dev.txt
pytest
```

covers 週次與日期對齊、跑量曲線的不變量、比賽週前後的調整、強度換算、三種輸出格式與 CLI。

## 結構

```text
plan/
  config.py      設定、驗證、環境變數覆寫
  schedule.py    分期、週次與日期對齊
  volume.py      跑量曲線與每日分配
  workouts.py    每日課表文字
  intensity.py   心率與配速換算
  plan.py        組裝成 TrainingPlan
outputs/
  text.py markdown.py json_out.py line.py
cli.py
```

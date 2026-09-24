# marathon-plan

把備賽課表寫成可運算的設定，而不是一份固定的 PDF。全馬與半馬都適用 ——
節奏跑練的是目標賽的配速，由 `race.distance_km` 決定。

給比賽日、起始週跑量與峰值週跑量就能產生一份，週數由 `block.phases` 決定 —— 分期、
三升一降的跑量曲線、每日課表、目標心率與配速都是算出來的。
無資料庫、無外部服務，執行期只用標準函式庫。

```bash
uv run cli.py --format markdown --out plan.md
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

補給量也是算的，不是一句固定的提醒：依當週長跑的預估時間分級，給每小時醣類克數、
吃第一份的時間點、間隔分鐘、水分，超過 2.5 小時再加鈉。比賽週改成賽前加賽中的版本。

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
  "race": { "name": "11/15 半程馬拉松", "date": "2026-11-15", "distance_km": 21.0975 },
  "block": { "weeks": 8, "phases": { "base": 1, "build": 3, "specific": 3, "taper": 1 } },
  "volume": { "start_weekly_km": 32, "peak_weekly_km": 44, "max_long_run_km": 18 },
  "week_template": ["rest", "easy", "strength", "quality", "rest", "recovery", "long"],
  "tune_up_races": [],
  "time_trials": [{ "date": "2026-10-22", "distance_km": 10 }]
}
```

`week_template` 的 index 0 是星期一，角色可選 `rest` / `easy` / `strength` / `quality` /
`recovery` / `long`，其中 `long` 必須剛好一個。想跑五天就把某個 `rest` 換成 `easy`，
跑量會自動重新分配。

跑量曲線：累積期從 `start_weekly_km` 線性爬到 `peak_weekly_km`，每第 4 週乘上
`down_week_factor` 降量，峰值落在累積期最後一週，減量期再遞減到比賽。長跑取週跑量的
固定比例（基礎 32% / 建構 38% / 專項 45%），並受 `max_long_run_km` 限制。
剩下的公里數按角色權重分給其他跑步日，**每週的每日距離加總一定等於週跑量**，有測試擋著。

節奏跑練的是目標賽的配速：目標賽短於 30K（例如半馬）時，專項期與減量期的節奏段改成半馬節奏。
半馬課表練馬拉松配速會慢十幾秒，等於從頭到尾沒練到比賽強度。

半馬課表另外加重比賽配速的量，因為半馬比的是把接近閾值的配速撐一個多小時：

- 建構期後段的主課從 1K 間歇拉長成 2K x 2、3K x 2。
- 專項期第一堂主課直接跑半馬節奏 3K x 2，再接連續 7K。
- 專項期長跑的最後 3K、4K 換成半馬節奏，練累了還守得住配速。

全馬課表不受影響。

測驗課放在 `time_trials`：

```json
"time_trials": [{ "date": "2026-10-22", "distance_km": 10 }]
```

只換掉當天的課（熱身 + 全力測驗 + 收操），前後幾週不動，當週跑量把多出來的距離算進去。
有目標成績時，備註會寫出測驗距離的等價成績（Riegel 換算），跑不到就該把比賽目標往後調。
不能排在長跑日、比賽週或期中比賽那週。

## 個人資料

生理數據與目標成績建議放環境變數，設定檔就能公開：

| 變數 | 說明 |
| --- | --- |
| `MAX_HR` / `RESTING_HR` | 實測最大 / 靜息心率，兩個都給才生效 |
| `MARATHON_GOAL` | 目標完賽時間，`H:MM:SS`。**優先於 `HALF_MARATHON_GOAL`** —— 備半馬時要清掉，否則輕鬆跑與主課配速仍從全馬目標換算 |
| `HALF_MARATHON_GOAL` | 半馬目標，選填。只給這個也可以，其他配速從它換算 |
| `PLAN_CONFIG` | 整份設定的 JSON。設了就以它為準，不讀設定檔 |

`PLAN_CONFIG` 是給 CI 用的：課表本身也算個人資訊，放 repository secret 就不必進版控，換週期時改那一個 secret 即可。

## 輸出

輸出與課表產生分開，加新格式只要在 `outputs/__init__.py` 的 `FORMATS` 註冊。

| 格式 | 內容 |
| --- | --- |
| `text` | 當週課表，給 LINE 或終端機 |
| `markdown` | 整份課表，含週次總覽與每週明細 |
| `json` | 整份課表，給前端或其他工具 |
| `intervals` | 本週與下週的結構化課表，預覽 `--sync` 會上傳的內容 |

每週的輸出都含補給建議與提醒。

```bash
uv run cli.py                              # 當週，印到終端機
uv run cli.py --date 2026-10-22            # 指定日期
uv run cli.py --format json --out plan.json
uv run cli.py --send                       # 推播到 LINE
uv run cli.py --sync                       # 上傳到 intervals.icu → COROS
```

沒有 uv 的話 `python cli.py` 也可以 —— 執行期沒有任何第三方套件。

`--send` 需要 `LINE_CHANNEL_ACCESS_TOKEN` 與 `LINE_TO_ID`，且只支援 `text`。
比賽日過後不再推播，只印出週期已結束的提示。

## 同步到 COROS 手錶

COROS 的 Training API 只開放給合作夥伴，官方 MCP 目前也只能讀資料，個人程式沒辦法直接把課推到手錶。
所以走 intervals.icu 中轉：它是 COROS 的合作夥伴，個人帳號用 API key 就能寫入行事曆。

1. intervals.icu → Settings → Connections 連結 COROS，勾選 **Upload planned workouts**。
2. COROS App 的行事曆加入「Intervals.icu Training Plan」。
3. intervals.icu → Settings → Developer Settings 產生 API key，設成 `INTERVALS_API_KEY`。
4. 有給 `MAX_HR` 的話，intervals.icu 設定裡的跑步最大心率要填同一個數字（原因見下）。

`--sync` 把本週與下週的跑步課上傳成結構化課表：熱身、每趟距離、組間恢復、重複次數、收操各自一段。
休息日與肌力日不上傳。intervals.icu 再把接下來 7 天推到 COROS。

- **強度目標一段只能一個**，心率優先、沒有才用配速、兩個都沒有就只有距離。
  intervals.icu 不收絕對 bpm，只收最大心率的百分比，並用它自己設定的最大心率換算回 bpm。
- **只動自己上傳的課。** `external_id` 帶 `marathon-plan-` 前綴；手動排的課不會被改或刪。
  課表改了（換賽事、加期中賽），區間內不再需要的課會刪掉，重跑幾次結果都一樣。

## 排程

`.github/workflows/weekly.yml` 每週推播一次；有設 `INTERVALS_API_KEY` 就接著同步到 intervals.icu，
LINE 推播失敗也照樣同步。

全部走 repository secrets：`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_TO_ID`、`PLAN_CONFIG`、
`MAX_HR`、`RESTING_HR`、`MARATHON_GOAL`、`HALF_MARATHON_GOAL`、`INTERVALS_API_KEY`，
以及選填的 `INTERVALS_ATHLETE_ID`（預設 `0`，代表 API key 本人）。

心率與成績不是憑證，但公開 repo 的 Actions log 任何人都讀得到，而 secrets 會在 log 裡
被遮成 `***`、variables 不會 —— 所以個人數據放 secrets 而不是 variables。

沒有設 `PLAN_CONFIG` 就用 repo 裡的 `data/plan.json`。

## 測試

```bash
uv run pytest
```

涵蓋週次與日期對齊、跑量曲線的不變量、比賽週前後的調整、強度換算、各輸出格式與 CLI。

## 結構

```text
plan/
  config.py      設定、驗證、環境變數覆寫
  schedule.py    分期、週次與日期對齊
  volume.py      跑量曲線與每日分配
  workouts.py    每日課表文字與手錶用的分段
  fueling.py     依長跑時間換算補給量
  intensity.py   心率與配速換算
  plan.py        組裝成 TrainingPlan
outputs/
  text.py        當週課表，LINE 與終端機用
  markdown.py    整份課表
  json_out.py    整份課表的 JSON
  line.py        LINE push API
  intervals.py   上傳到 intervals.icu（→ COROS）
data/
  plan.json      課表設定
tests/
cli.py
```

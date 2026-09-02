"""依當週長跑時間給具體的補給量。

醣類需求隨運動時間拉長而增加，所以這裡的門檻用分鐘而不是公里 ——
同樣 20K，跑 100 分鐘和跑 160 分鐘要吃的量差很多。

數字取自一般耐力運動的補給區間，個人腸胃耐受度差異很大，
實際份量要在長跑裡試出來，比賽日不要用沒練過的東西。
"""

from __future__ import annotations

GEL_CARBS_G = 25  # 市售能量膠一條大多 20-30g 醣

# (時間上限, 每小時醣類克數, 第一份要在第幾分鐘吃)
TIERS = (
    (60, 0, 0),
    (90, 30, 40),
    (150, 45, 40),
    (10_000, 60, 40),
)


def _tier(minutes: int) -> tuple[int, int]:
    for limit, carbs, first in TIERS:
        if minutes <= limit:
            return carbs, first
    return TIERS[-1][1], TIERS[-1][2]


def _interval(carbs_per_hour: int) -> int:
    """吃一份的間隔分鐘，抓成 5 的倍數比較好記。"""
    if carbs_per_hour <= 0:
        return 0
    minutes = 60 * GEL_CARBS_G / carbs_per_hour
    return max(15, int(round(minutes / 5)) * 5)


def long_run_advice(minutes: int) -> str:
    carbs, first = _tier(minutes)
    if carbs == 0:
        return (
            "本週長跑不到 60 分鐘，不需要途中補給；跑前正常吃，口渴就喝水。"
        )

    interval = _interval(carbs)
    lines = [
        f"本週長跑約 {minutes} 分鐘，途中補給目標每小時 {carbs}g 醣"
        f"（約每 {interval} 分鐘一份，一條能量膠大多 20-30g）。",
        f"第 {first} 分鐘吃第一份，不要等到覺得餓或沒力才吃。",
    ]
    if minutes >= 90:
        lines.append("水分每小時 400-600ml，分次小口喝，天熱再往上加。")
    else:
        lines.append("水分每 15-20 分鐘喝兩三口就夠。")
    if minutes >= 150:
        lines.append("超過 2.5 小時要補鈉，每小時 300-600mg，可用鹽錠或運動飲料。")
    return "\n".join(lines)


def race_day_advice(distance_km: float, minutes: int) -> str:
    carbs, first = _tier(minutes)
    lines = [
        "賽前 2-3 小時吃完早餐，以好消化的醣類為主"
        "（吐司、飯糰、香蕉），抓每公斤體重 1-2g 醣。",
    ]
    if carbs == 0:
        lines.append("比賽時間短，途中喝水即可。")
    else:
        interval = _interval(carbs)
        lines.append(
            f"起跑後第 {first} 分鐘吃第一份，之後每 {interval} 分鐘一份，"
            f"目標每小時 {carbs}g 醣。"
        )
        lines.append("每個水站都喝，天熱時交替喝水與運動飲料。")
    if minutes >= 150:
        lines.append("補鈉每小時 300-600mg。")
    lines.append("所有品項都要是長跑練過的，比賽日不要第一次嘗試新東西。")
    return "\n".join(lines)

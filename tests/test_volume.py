from __future__ import annotations

from dataclasses import replace

import pytest

from plan import schedule, volume
from plan.config import PlanConfig, Volume


def curve(config: PlanConfig) -> list[volume.WeekVolume]:
    """整個區塊每一週的跑量；只有測試需要攤平成一份清單。"""
    return [volume.week_volume(config, week) for week in range(1, config.total_weeks + 1)]


def test_daily_distances_always_sum_to_the_weekly_total(config):
    for week in curve(config):
        assert sum(week.daily_km) == week.weekly_km, f"第 {week.week} 週對不起來"


def test_rest_and_strength_days_carry_no_distance(config):
    long_index = config.week_template.index("long")
    for week in curve(config):
        for index, role in enumerate(config.week_template):
            if role in {"rest", "strength"}:
                assert week.daily_km[index] == 0
            else:
                assert week.daily_km[index] > 0
        assert week.daily_km[long_index] == week.long_run_km


def test_volume_starts_and_peaks_where_configured(config):
    weeks = curve(config)

    assert weeks[0].weekly_km == pytest.approx(config.volume.start_weekly_km, abs=1)
    peak = max(week.weekly_km for week in weeks)
    assert peak == pytest.approx(config.volume.peak_weekly_km, abs=1)


def test_peak_lands_on_the_last_loading_week(config):
    weeks = curve(config)
    loading = [week for week in weeks if week.week <= config.phases.loading]

    assert max(loading, key=lambda week: week.weekly_km).week == config.phases.loading


def test_down_weeks_are_lighter_than_the_week_before(config):
    weeks = {week.week: week for week in curve(config)}

    for number in weeks:
        if schedule.is_down_week(config, number) and number > 1:
            assert weeks[number].weekly_km < weeks[number - 1].weekly_km


def test_taper_descends_every_week(config):
    taper = [
        week for week in curve(config) if week.week > config.phases.loading
    ]
    volumes = [week.weekly_km for week in taper]

    assert volumes == sorted(volumes, reverse=True)


def test_long_run_never_exceeds_the_cap(config):
    capped = replace(
        config, volume=replace(config.volume, max_long_run_km=25)
    )

    for week in curve(capped):
        assert week.long_run_km <= 25


def test_long_run_stays_below_the_weekly_total(config):
    for week in curve(config):
        assert 0 < week.long_run_km < week.weekly_km


def test_higher_peak_produces_a_bigger_plan(config):
    small = replace(config, volume=replace(config.volume, peak_weekly_km=50))
    large = replace(config, volume=replace(config.volume, peak_weekly_km=90))

    assert sum(w.weekly_km for w in curve(small)) < sum(
        w.weekly_km for w in curve(large)
    )


def test_volume_config_rejects_impossible_values():
    with pytest.raises(Exception):
        Volume(start_weekly_km=0, peak_weekly_km=50).validate()
    with pytest.raises(Exception):
        Volume(start_weekly_km=60, peak_weekly_km=50).validate()
    with pytest.raises(Exception):
        Volume(start_weekly_km=40, peak_weekly_km=50, down_week_factor=1.5).validate()


def test_peak_survives_when_the_loading_block_is_a_multiple_of_four(config):
    """累積期剛好 4 的倍數時，峰值週不能被降量規則吃掉。"""
    from dataclasses import replace

    from plan.config import Phases

    tuned = replace(
        config,
        phases=Phases(base=2, build=4, specific=2, taper=2),
    )
    weeks = curve(tuned)

    assert not schedule.is_down_week(tuned, tuned.phases.loading)
    assert weeks[tuned.phases.loading - 1].weekly_km == pytest.approx(
        tuned.volume.peak_weekly_km, abs=1
    )


def test_fewer_running_days_means_a_bigger_long_run_share(config):
    """跑 4 天與跑 6 天的人，同樣週跑量下長跑佔比不該一樣。"""
    from dataclasses import replace

    four_days = replace(
        config,
        week_template=("rest", "easy", "strength", "quality", "rest", "recovery", "long"),
    )
    six_days = replace(
        config,
        week_template=("easy", "easy", "quality", "easy", "recovery", "easy", "long"),
    )

    four = volume.week_volume(four_days, 6)
    six = volume.week_volume(six_days, 6)

    assert four.long_run_km / four.weekly_km > six.long_run_km / six.weekly_km


def test_long_run_never_takes_more_than_half_the_week(config):
    from dataclasses import replace

    three_days = replace(
        config,
        week_template=("rest", "easy", "rest", "quality", "rest", "rest", "long"),
    )

    for week in curve(three_days):
        assert week.long_run_km / week.weekly_km <= 0.51

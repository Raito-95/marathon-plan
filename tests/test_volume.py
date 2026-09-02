from __future__ import annotations

from dataclasses import replace

import pytest

from plan import schedule, volume
from plan.config import Volume


def test_daily_distances_always_sum_to_the_weekly_total(config):
    for week in volume.curve(config):
        assert sum(week.daily_km) == week.weekly_km, f"第 {week.week} 週對不起來"


def test_rest_and_strength_days_carry_no_distance(config):
    long_index = config.week_template.index("long")
    for week in volume.curve(config):
        for index, role in enumerate(config.week_template):
            if role in {"rest", "strength"}:
                assert week.daily_km[index] == 0
            else:
                assert week.daily_km[index] > 0
        assert week.daily_km[long_index] == week.long_run_km


def test_volume_starts_and_peaks_where_configured(config):
    weeks = volume.curve(config)

    assert weeks[0].weekly_km == pytest.approx(config.volume.start_weekly_km, abs=1)
    peak = max(week.weekly_km for week in weeks)
    assert peak == pytest.approx(config.volume.peak_weekly_km, abs=1)


def test_peak_lands_on_the_last_loading_week(config):
    weeks = volume.curve(config)
    loading = [week for week in weeks if week.week <= config.phases.loading]

    assert max(loading, key=lambda week: week.weekly_km).week == config.phases.loading


def test_down_weeks_are_lighter_than_the_week_before(config):
    weeks = {week.week: week for week in volume.curve(config)}

    for number in weeks:
        if schedule.is_down_week(config, number) and number > 1:
            assert weeks[number].weekly_km < weeks[number - 1].weekly_km


def test_taper_descends_every_week(config):
    taper = [
        week for week in volume.curve(config) if week.week > config.phases.loading
    ]
    volumes = [week.weekly_km for week in taper]

    assert volumes == sorted(volumes, reverse=True)


def test_long_run_never_exceeds_the_cap(config):
    capped = replace(
        config, volume=replace(config.volume, max_long_run_km=25)
    )

    for week in volume.curve(capped):
        assert week.long_run_km <= 25


def test_long_run_stays_below_the_weekly_total(config):
    for week in volume.curve(config):
        assert 0 < week.long_run_km < week.weekly_km


def test_higher_peak_produces_a_bigger_plan(config):
    small = replace(config, volume=replace(config.volume, peak_weekly_km=50))
    large = replace(config, volume=replace(config.volume, peak_weekly_km=90))

    assert sum(w.weekly_km for w in volume.curve(small)) < sum(
        w.weekly_km for w in volume.curve(large)
    )


def test_volume_config_rejects_impossible_values():
    with pytest.raises(Exception):
        Volume(start_weekly_km=0, peak_weekly_km=50).validate()
    with pytest.raises(Exception):
        Volume(start_weekly_km=60, peak_weekly_km=50).validate()
    with pytest.raises(Exception):
        Volume(start_weekly_km=40, peak_weekly_km=50, down_week_factor=1.5).validate()

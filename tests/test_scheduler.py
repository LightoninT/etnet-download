"""Unit tests for the scheduling engine (incl. HKT timezone handling)."""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.scheduler import (  # noqa: E402
    ScheduleConfig, from_hkt_naive, hkt_display, next_run, to_hkt_naive,
)

# New York in August = EDT, UTC-4 (fixed offset, no DST in our tests)
NY = dt.timezone(dt.timedelta(hours=-4))


def mkcfg(**kw) -> ScheduleConfig:
    cfg = ScheduleConfig()
    cfg.times = ["09:00", "17:30"]
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def test_daily_next_run_same_day():
    cfg = mkcfg(mode="daily")
    now = dt.datetime(2026, 8, 16, 8, 0)   # Sunday, before 09:00
    assert next_run(now, cfg) == dt.datetime(2026, 8, 16, 9, 0)


def test_daily_next_run_after_all_times():
    cfg = mkcfg(mode="daily")
    now = dt.datetime(2026, 8, 16, 18, 0)  # after 17:30
    assert next_run(now, cfg) == dt.datetime(2026, 8, 17, 9, 0)


def test_daily_mid_gap():
    cfg = mkcfg(mode="daily")
    now = dt.datetime(2026, 8, 16, 9, 30)  # between 09:00 and 17:30
    assert next_run(now, cfg) == dt.datetime(2026, 8, 16, 17, 30)


def test_weekly_respects_weekdays():
    cfg = mkcfg(mode="weekly", weekdays=[0, 2])  # Mon, Wed
    # Saturday 2026-08-15 -> next is Monday 17:30? No: times 09:00/17:30; Monday 09:00
    now = dt.datetime(2026, 8, 15, 12, 0)  # Saturday
    assert next_run(now, cfg) == dt.datetime(2026, 8, 17, 9, 0)


def test_weekly_same_day_later_time():
    cfg = mkcfg(mode="weekly", weekdays=[0])
    now = dt.datetime(2026, 8, 17, 10, 0)  # Monday after 09:00
    assert next_run(now, cfg) == dt.datetime(2026, 8, 17, 17, 30)


def test_weekly_no_more_today():
    cfg = mkcfg(mode="weekly", weekdays=[0])
    now = dt.datetime(2026, 8, 17, 18, 0)  # Monday after all times
    assert next_run(now, cfg) == dt.datetime(2026, 8, 24, 9, 0)


def test_interval_basic():
    cfg = mkcfg(mode="interval", interval_days=2, start_date="2026-08-14")
    now = dt.datetime(2026, 8, 16, 8, 0)  # aligned day (14,16,18,...)
    assert next_run(now, cfg) == dt.datetime(2026, 8, 16, 9, 0)


def test_interval_off_day():
    cfg = mkcfg(mode="interval", interval_days=2, start_date="2026-08-14")
    now = dt.datetime(2026, 8, 17, 8, 0)  # off day -> next aligned is 18th
    assert next_run(now, cfg) == dt.datetime(2026, 8, 18, 9, 0)


def test_interval_start_date_future():
    cfg = mkcfg(mode="interval", interval_days=5, start_date="2026-08-20")
    now = dt.datetime(2026, 8, 16, 8, 0)
    assert next_run(now, cfg) == dt.datetime(2026, 8, 20, 9, 0)


def test_validation_rejects_empty_times():
    cfg = mkcfg(mode="daily", times=[])
    assert cfg.validate() != ""
    assert next_run(dt.datetime.now(), cfg) is None


def test_validation_rejects_bad_time():
    cfg = mkcfg(mode="daily", times=["25:99"])
    assert cfg.validate() != ""


def test_validation_weekly_needs_day():
    cfg = mkcfg(mode="weekly", weekdays=[])
    assert cfg.validate() != ""


def test_counts():
    cfg = mkcfg(mode="weekly", weekdays=[0, 2, 4], times=["09:00", "17:30"])
    assert cfg.times_per_day() == 2
    assert cfg.days_per_week() == 3
    assert cfg.times_per_week() == 6
    cfg2 = mkcfg(mode="daily", times=["09:00", "12:00", "17:30"])
    assert cfg2.times_per_week() == 21


# ---------------------------------------------------------------------------
# HKT (Hong Kong Time, UTC+8) handling
# ---------------------------------------------------------------------------


def test_hkt_conversions():
    local = dt.datetime(2026, 8, 16, 4, 30)
    hkt = to_hkt_naive(local, NY)                      # NY 04:30 = HKT 16:30
    assert hkt == dt.datetime(2026, 8, 16, 16, 30)
    back = from_hkt_naive(hkt, NY)
    assert back == local
    assert hkt_display(local, NY) == "2026-08-16 16:30"


def test_hkt_next_run_from_other_timezone():
    cfg = mkcfg(mode="daily", times=["16:30"])         # 16:30 HKT
    now = dt.datetime(2026, 8, 16, 4, 0)               # NY morning = HKT 16:00
    nxt = next_run(now, cfg, local_tz=NY)
    assert nxt == dt.datetime(2026, 8, 16, 4, 30)      # NY 04:30 = HKT 16:30


def test_hkt_next_run_rolls_over_next_day():
    cfg = mkcfg(mode="daily", times=["16:30"])         # 16:30 HKT
    now = dt.datetime(2026, 8, 16, 9, 0)               # NY 09:00 = HKT 21:00 (after 16:30)
    nxt = next_run(now, cfg, local_tz=NY)
    assert nxt == dt.datetime(2026, 8, 17, 4, 30)      # next HKT 16:30 -> NY 04:30


def test_hkt_weekly_weekday_in_hkt_domain():
    cfg = mkcfg(mode="weekly", weekdays=[1], times=["10:00"])  # Tuesday 10:00 HKT
    # Monday 2026-08-17 23:00 NY = Tuesday 2026-08-18 11:00 HKT -> past the 10:00 HKT slot
    now = dt.datetime(2026, 8, 17, 23, 0)              # NY Monday late night
    nxt = next_run(now, cfg, local_tz=NY)
    # next Tuesday 10:00 HKT (2026-08-25) = 2026-08-24 22:00 NY (Monday evening)
    assert nxt == dt.datetime(2026, 8, 24, 22, 0)


def test_use_hkt_false_interprets_times_as_local():
    cfg = mkcfg(mode="daily", times=["16:30"])
    cfg.use_hkt = False
    now = dt.datetime(2026, 8, 16, 16, 0)              # NY 16:00 local
    nxt = next_run(now, cfg, local_tz=NY)
    assert nxt == dt.datetime(2026, 8, 16, 16, 30)     # local 16:30, no conversion


def test_hkt_identity_when_machine_is_in_hkt():
    HKT = dt.timezone(dt.timedelta(hours=8))
    cfg = mkcfg(mode="daily", times=["09:00"])
    now = dt.datetime(2026, 8, 16, 8, 0)
    assert next_run(now, cfg, local_tz=HKT) == dt.datetime(2026, 8, 16, 9, 0)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

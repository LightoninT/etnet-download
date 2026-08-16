"""Pure-python scheduling engine (no Qt dependency).

Supported schedule modes
------------------------
* ``weekly``   - run on selected weekdays (Mon..Sun) at one or more times
* ``daily``    - run every day at one or more times
* ``interval`` - run every N days at one or more times

Times are wall-clock in **Hong Kong Time (HKT, UTC+8, no DST since 1979)** by
default (``use_hkt=True``); the engine converts to/from the local timezone so
the schedule fires at the correct HKT moment on any machine.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import List, Optional

WEEKDAY_NAMES = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
WEEKDAY_SHORT = ["一", "二", "三", "四", "五", "六", "日"]

# Hong Kong Time: fixed UTC+8 offset, no DST since 1979 -> no tzdata needed.
HKT = dt.timezone(dt.timedelta(hours=8))


def _local_tzinfo() -> dt.tzinfo:
    return dt.datetime.now().astimezone().tzinfo


def to_hkt_naive(local_naive: dt.datetime, local_tz: dt.tzinfo = None) -> dt.datetime:
    """Convert a naive local datetime to naive HKT wall-clock time."""
    if local_tz is None:
        local_tz = _local_tzinfo()
    return local_naive.replace(tzinfo=local_tz).astimezone(HKT).replace(tzinfo=None)


def from_hkt_naive(hkt_naive: dt.datetime, local_tz: dt.tzinfo = None) -> dt.datetime:
    """Convert a naive HKT datetime to naive local wall-clock time."""
    if local_tz is None:
        local_tz = _local_tzinfo()
    return hkt_naive.replace(tzinfo=HKT).astimezone(local_tz).replace(tzinfo=None)


def hkt_display(local_naive: dt.datetime, local_tz: dt.tzinfo = None) -> str:
    """Format a naive local datetime as HKT for display."""
    return to_hkt_naive(local_naive, local_tz).strftime("%Y-%m-%d %H:%M")


@dataclass
class ScheduleConfig:
    enabled: bool = False
    mode: str = "weekly"                       # weekly | daily | interval
    weekdays: List[int] = field(default_factory=lambda: list(range(5)))  # 0=Mon..6=Sun
    times: List[str] = field(default_factory=lambda: ["16:30"])          # "HH:MM" (HKT)
    interval_days: int = 1                     # every N days (interval mode)
    start_date: str = ""                       # ISO yyyy-mm-dd anchor for interval mode
    products: List[str] = field(default_factory=lambda: ["HSI", "HHI"])  # ticked products
    output_dir: str = ""                       # "" = Desktop
    use_hkt: bool = True                       # times are in Hong Kong Time

    # ------------------------------------------------------------------
    def validate(self) -> str:
        """Return an error message, or '' when valid."""
        if self.mode not in ("weekly", "daily", "interval"):
            return f"未知排程模式: {self.mode}"
        if not self.times:
            return "請至少設定一個執行時間"
        for t in self.times:
            try:
                dt.datetime.strptime(t, "%H:%M")
            except ValueError:
                return f"無效時間: {t}"
        if self.mode == "weekly" and not self.weekdays:
            return "每週模式需要至少選擇一天"
        if self.mode == "interval" and self.interval_days < 1:
            return "每隔日數必須 >= 1"
        if not self.products:
            return "請至少勾選一個期貨產品"
        return ""

    # ------------------------------------------------------------------
    def times_per_day(self) -> int:
        return len(self.times)

    def days_per_week(self) -> int:
        if self.mode == "weekly":
            return len(self.weekdays)
        if self.mode == "daily":
            return 7
        # interval: roughly 7/N days per week
        return max(1, round(7.0 / max(1, self.interval_days)))

    def times_per_week(self) -> int:
        return self.times_per_day() * self.days_per_week()

    def summary(self) -> str:
        tz_note = "（香港時間 HKT）" if self.use_hkt else "（本機時間）"
        if self.mode == "weekly":
            days = "、".join(WEEKDAY_NAMES[d] for d in sorted(self.weekdays))
            return (
                f"每週在 {days} 執行 {self.times_per_day()} 次/日 "
                f"（共 {self.times_per_week()} 次/週）於 "
                f"{', '.join(self.times)} {tz_note}"
            )
        if self.mode == "daily":
            return (
                f"每日執行 {self.times_per_day()} 次（每週 {self.times_per_week()} 次）"
                f"於 {', '.join(self.times)} {tz_note}"
            )
        return (
            f"每隔 {self.interval_days} 日執行 {self.times_per_day()} 次/日"
            f"（約每週 {self.times_per_week()} 次）於 {', '.join(self.times)} {tz_note}"
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def parse_time(t: str) -> dt.time:
    return dt.datetime.strptime(t, "%H:%M").time()


def _next_time_on_date(date: dt.date, times: List[str], after: Optional[dt.datetime]) -> Optional[dt.datetime]:
    """Earliest configured time on ``date`` strictly after ``after``."""
    best = None
    for t in times:
        cand = dt.datetime.combine(date, parse_time(t))
        if after is None or cand > after:
            if best is None or cand < best:
                best = cand
    return best


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------


def _next_run_naive(now: dt.datetime, cfg: ScheduleConfig) -> Optional[dt.datetime]:
    """Earliest scheduled run strictly after ``now`` (both in the same
    wall-clock timezone, naive)."""
    err = cfg.validate()
    if err:
        return None
    times = sorted(set(cfg.times))

    if cfg.mode == "daily":
        cand = _next_time_on_date(now.date(), times, now)
        if cand:
            return cand
        return _next_time_on_date(now.date() + dt.timedelta(days=1), times, None)

    if cfg.mode == "weekly":
        best = None
        for offset in range(0, 8):
            d = (now + dt.timedelta(days=offset)).date()
            if d.weekday() not in cfg.weekdays:
                continue
            cand = _next_time_on_date(d, times, now if offset == 0 else None)
            if cand and (best is None or cand < best):
                best = cand
        return best

    if cfg.mode == "interval":
        base = None
        try:
            base = dt.date.fromisoformat(cfg.start_date) if cfg.start_date else None
        except ValueError:
            base = None
        if base is None:
            base = now.date()
        n = max(1, int(cfg.interval_days))
        # next run date: first date >= today aligned to base + k*n
        d = now.date()
        run_date = None
        for offset in range(0, n + 1):
            cand_date = d + dt.timedelta(days=offset)
            if (cand_date - base).days % n == 0:
                run_date = cand_date
                break
        if run_date is None:
            return None
        cand = _next_time_on_date(run_date, times, now if run_date == d else None)
        if cand:
            return cand
        run_date = run_date + dt.timedelta(days=n)
        return _next_time_on_date(run_date, times, None)

    return None


def next_run(now: dt.datetime, cfg: ScheduleConfig,
             local_tz: dt.tzinfo = None) -> Optional[dt.datetime]:
    """Earliest scheduled run strictly after ``now`` (naive local time).

    When ``cfg.use_hkt`` is set, the configured ``times`` are interpreted as
    HKT wall-clock and the result is converted back to local time.
    """
    if not cfg.use_hkt:
        return _next_run_naive(now, cfg)
    if local_tz is None:
        local_tz = _local_tzinfo()
    now_hkt = to_hkt_naive(now, local_tz)
    cand = _next_run_naive(now_hkt, cfg)
    if cand is None:
        return None
    return from_hkt_naive(cand, local_tz)

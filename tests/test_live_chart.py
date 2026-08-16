"""Unit tests for the native live-chart data mapping."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.downloader import FuturesPage, IntervalRow, SessionQuote  # noqa: E402
from app.live_chart import page_to_chart, running_range_mid  # noqa: E402


def mk_page(month="202608"):
    page = FuturesPage(subtype="HSI", month=month, contract_name="恒生指數期貨")
    page.sessions = [
        SessionQuote(session="日市", last=25186, prev_close=25373, high=25237, low=25160),
        SessionQuote(session="夜市", last=25199, prev_close=25373),
    ]
    rows = [
        ("09:30", 25191, 25237, 25160, 25186),
        ("09:45", 25186, 25215, 25118, 25199),
        ("10:00", 25200, 25283, 25191, 25220),
    ]
    for t, o, h, l, c in rows:
        page.interval.append(IntervalRow(time=t, open=o, high=h, low=l, last=c))
    return page


def test_running_range_mid():
    candles = [
        {"high": 100, "low": 80},
        {"high": 95, "low": 85},   # inside -> keep
        {"high": 110, "low": 88},  # new high -> (110+80)/2
        {"high": 105, "low": 70},  # new low  -> (110+70)/2
        {"high": 120, "low": 60},  # both     -> (120+60)/2
    ]
    assert running_range_mid(candles) == [90, 90, 95, 90, 90]


def test_page_to_chart():
    d = page_to_chart(mk_page())
    assert d["code"] == "HSI" and d["month"] == "202608"
    assert d["prevClose"] == 25373
    assert len(d["candles"]) == 3
    c0 = d["candles"][0]
    assert c0["open"] == 25191 and c0["high"] == 25237
    assert c0["low"] == 25160 and c0["close"] == 25186
    assert isinstance(c0["time"], int) and c0["time"] > 1e9
    # mid line (running range): (25237+25160)/2; then low->25118: (25237+25118)/2;
    # then high->25283: (25283+25118)/2
    assert d["mids"][0] == (25237 + 25160) / 2
    assert d["mids"][1] == (25237 + 25118) / 2
    assert d["mids"][2] == (25283 + 25118) / 2


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

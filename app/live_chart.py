"""Native live-chart widgets (Qt painting) - no QtWebEngine needed.

Data is fetched via the Cloudflare Worker proxy (same offload design as the
web page): the exe asks the worker, the worker fetches etnet.
"""

from __future__ import annotations

import calendar
import datetime as dt
import urllib.parse

import requests
from PySide6.QtCore import QPointF, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from . import downloader
from .scheduler import HKT

WORKER_URL = "https://etnet-proxy.etnetdata.workers.dev/"

PROXIES = [
    lambda u: f"{WORKER_URL}?url={urllib.parse.quote(u, safe='')}",
    lambda u: f"https://api.cors.lol/?url={urllib.parse.quote(u, safe='')}",
    lambda u: f"https://api.allorigins.win/raw?url={urllib.parse.quote(u, safe='')}",
    lambda u: f"https://api.codetabs.com/v1/proxy?quest={urllib.parse.quote(u, safe='')}",
]

UP = QColor("#e53e3e")      # HK convention: red = up
DOWN = QColor("#2f9e44")    # green = down
MID_COLOR = QColor("#e67e22")


def _candle_time(month: str, hhmm: str) -> int:
    h, m = (int(x) for x in hhmm.split(":"))
    now_hkt = dt.datetime.now(HKT)
    return calendar.timegm((now_hkt.year, now_hkt.month, now_hkt.day, h, m, 0, 0, 0, 0))


def running_range_mid(candles: list) -> list:
    """Mid line = running range midpoint (4 rules): the (high, low) range only
    expands; mid = (range high + range low) / 2 per candle."""
    out = []
    r_high = r_low = None
    for c in candles:
        if r_high is None:
            r_high, r_low = c["high"], c["low"]
        else:
            if c["high"] > r_high:
                r_high = c["high"]
            if c["low"] < r_low:
                r_low = c["low"]
        out.append((r_high + r_low) / 2)
    return out


def page_to_chart(page: downloader.FuturesPage) -> dict:
    candles = [
        {"time": _candle_time(page.month, r.time),
         "open": r.open, "high": r.high, "low": r.low, "close": r.last}
        for r in page.interval if r.time not in ("上日", "今日")
    ]
    prev_close = next((s.prev_close for s in page.sessions if s.prev_close), None)
    return {
        "code": page.subtype,
        "month": page.month,
        "prevClose": prev_close,
        "updated": page.update_time,
        "candles": candles,
        "mids": running_range_mid(candles),
    }


def fetch_proxied(url: str, timeout: int = 25) -> str:
    """Fetch HTML through the Cloudflare Worker proxy, then public fallbacks,
    then etnet directly (last resort)."""
    headers = {"User-Agent": downloader.USER_AGENT}
    last_err = None
    for proxy in PROXIES:
        try:
            resp = requests.get(proxy(url), headers=headers, timeout=timeout)
            if resp.ok:
                return resp.text
            last_err = f"HTTP {resp.status_code}"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
    # last resort: direct etnet fetch (same as the download tab)
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.ok:
            return resp.text
        last_err = f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        last_err = str(exc)
    raise RuntimeError(f"所有代理失敗: {last_err}")


class ChartFetcher(QThread):
    """Fetch HSI + HHI chart data via the proxy chain."""

    got = Signal(dict)   # {code: chart-data}

    def run(self):
        out = {}
        for code in ("HSI", "HHI"):
            try:
                html = fetch_proxied(
                    f"https://www.etnet.com.hk/www/tc/futures/?subtype={code}"
                )
                out[code] = page_to_chart(downloader.parse_page(html))
            except Exception as exc:  # noqa: BLE001
                out[code] = {"code": code, "error": str(exc)}
        self.got.emit(out)


class CandleChartWidget(QWidget):
    """Paints 15-min candles (thick wicks) + mid line + axes."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.data = None

    def set_data(self, data: dict):
        self.data = data
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.fillRect(self.rect(), QColor("#ffffff"))

        d = self.data
        if not d or d.get("error"):
            p.setPen(QColor("#c00000"))
            p.drawText(self.rect(), Qt.AlignCenter,
                       d.get("error", "等待數據...") if d else "等待數據...")
            return

        candles = d.get("candles") or []
        if not candles:
            p.setPen(QColor("#6b7280"))
            p.drawText(self.rect(), Qt.AlignCenter, "沒有數據")
            return

        w, h = self.width(), self.height()
        left, right, top, bottom = 8, 52, 8, 22   # margins
        pw, ph = w - left - right, h - top - bottom

        # price range across candles + mid line
        lo = min(c["low"] for c in candles)
        hi = max(c["high"] for c in candles)
        mids = d.get("mids") or []
        if mids:
            lo = min(lo, min(mids))
            hi = max(hi, max(mids))
        if d.get("prevClose"):
            lo = min(lo, d["prevClose"])
            hi = max(hi, d["prevClose"])
        pad = (hi - lo) * 0.05 or 1
        lo, hi = lo - pad, hi + pad

        def x(i):  # index-based x
            n = max(len(candles), 1)
            return left + (i + 0.5) * pw / n

        def y(v):
            return top + (hi - v) / (hi - lo) * ph

        # grid + price labels
        p.setPen(QPen(QColor("#eef1f6"), 1))
        for k in range(6):
            gy = top + ph * k / 5
            p.drawLine(left, int(gy), left + pw, int(gy))
        p.setPen(QColor("#6b7280"))
        p.setFont(QFont("Helvetica", 9))
        for k in range(6):
            v = hi - (hi - lo) * k / 5
            p.drawText(right - 48, int(top + ph * k / 5) + 3, 46, 14,
                       Qt.AlignRight | Qt.AlignVCenter, f"{v:,.1f}")

        # candles: thick wicks + bodies
        spacing = pw / max(len(candles), 1)
        body_w = max(2, min(spacing * 0.7, 9))
        for i, c in enumerate(candles):
            cx = x(i)
            up = c["close"] >= c["open"]
            color = UP if up else DOWN
            # thick wick
            p.setPen(QPen(color, 3))
            p.drawLine(int(cx), int(y(c["high"])), int(cx), int(y(c["low"])))
            # body
            yt, yb = y(max(c["open"], c["close"])), y(min(c["open"], c["close"]))
            p.fillRect(int(cx - body_w / 2), int(yt),
                       max(1, int(body_w)), max(1, int(yb - yt)), color)

        # mid line (dashed orange polyline)
        if mids:
            pen = QPen(MID_COLOR, 1)
            pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            pts = [QPointF(x(i), y(v)) for i, v in enumerate(mids)]
            for i in range(len(pts) - 1):
                p.drawLine(pts[i], pts[i + 1])

        # time labels (first / middle / last)
        p.setPen(QColor("#6b7280"))
        n = len(candles)
        for i in (0, n // 2, n - 1):
            hhmm = dt.datetime.fromtimestamp(candles[i]["time"], tz=HKT).strftime("%H:%M")
            p.drawText(int(x(i)) - 22, h - 20, 44, 16,
                       Qt.AlignHCenter | Qt.AlignTop, hhmm)

        p.end()


class LiveChartsPanel(QWidget):
    """Two stacked candle charts (HSI on top, HHI below) + 2s refresh."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self.widgets = {}
        self.labels = {}
        for code, title in (("HSI", "恒生指數期貨 (HSI)"),
                            ("HHI", "恒生中國企業指數期貨 (HHI)")):
            meta = QLabel("月份: -")
            chart = CandleChartWidget(title)
            self.widgets[code] = chart
            self.labels[code] = meta
            box = QVBoxLayout()
            head = QVBoxLayout()
            tl = QLabel(f"<b>{title}</b>")
            head.addWidget(tl)
            head.addWidget(meta)
            lay.addLayout(head)
            lay.addWidget(chart, 1)

        self._fetcher = None
        self._last_data = {}
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh)

    # ------------------------------------------------------------------
    def refresh(self):
        if self._fetcher is not None and self._fetcher.isRunning():
            return  # still fetching -> skip this tick
        self._fetcher = ChartFetcher(self)
        self._fetcher.got.connect(self._on_data)
        self._fetcher.start()

    def _on_data(self, data: dict):
        self._last_data = data
        for code, d in data.items():
            if code not in self.widgets:
                continue
            self.widgets[code].set_data(d)
            if d.get("error"):
                self.labels[code].setText(f"❌ {d['error']}")
            else:
                month = d["month"]
                m = f"{month[:4]}/{month[4:]}" if len(month) == 6 else month
                self.labels[code].setText(
                    f"月份: {m}　網頁更新: {d.get('updated', '-')}　本地: "
                    f"{dt.datetime.now().strftime('%H:%M:%S')}"
                )

    def start(self):
        self.timer.start()
        self.refresh()

    def stop(self):
        self.timer.stop()
        if self._fetcher is not None and self._fetcher.isRunning():
            self._fetcher.wait(3000)

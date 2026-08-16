"""Local HTTP server + 60s data refresh backing the live-charts tab.

The QWebEngineView tab loads this local server (same-origin, no CORS), and the
page's JS polls ``/api/hsi`` and ``/api/hhi`` every 60 s. A QTimer refreshes
the JSON cache from etnet (front/current month) every 60 s via the Python
downloader, so no third-party CORS proxy is needed inside the exe.
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QObject, QTimer

from . import downloader
from .scheduler import HKT  # fixed UTC+8, no DST

PORT_START = 8787


def page_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "webpage"
    return Path(__file__).resolve().parent.parent / "webpage"


def candle_time(month: str, hhmm: str) -> int:
    """Unix seconds of (HKT today, HH:MM) - matches the JS parser."""
    h, m = (int(x) for x in hhmm.split(":"))
    now_hkt = dt.datetime.now(HKT)
    return calendar.timegm((now_hkt.year, now_hkt.month, now_hkt.day, h, m, 0, 0, 0, 0))


class DataCache(QObject):
    """Fetches HSI/HHI front-month 15-min candles every 60 s."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict = {}
        self._lock = threading.Lock()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(60_000)
        self.refresh()

    def refresh(self):
        for code in ("HSI", "HHI"):
            try:
                page = downloader.get_futures_page(code)  # no month -> front month
                candles = [
                    {
                        "time": candle_time(page.month, r.time),
                        "open": r.open, "high": r.high,
                        "low": r.low, "close": r.last,
                    }
                    for r in page.interval if r.time not in ("上日", "今日")
                ]
                prev_close = next(
                    (s.prev_close for s in page.sessions if s.prev_close), None
                )
                self._data[code] = {
                    "code": code,
                    "month": page.month,
                    "name": page.contract_name,
                    "prevClose": prev_close,
                    "updated": page.update_time,
                    "candles": candles,
                }
            except Exception as exc:  # noqa: BLE001 - keep last good data on failure
                self._data[code] = {"code": code, "error": str(exc)}

    def get(self, code: str) -> dict:
        with self._lock:
            return dict(self._data.get(code, {"code": code, "error": "no data"}))


def start_server(cache: DataCache, page_dir_path: Path) -> int:
    """Start the HTTP server on 127.0.0.1 (first free port >= PORT_START).
    Returns the port, or 0 on failure."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence
            pass

        def _send(self, body: bytes, ctype: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                path = "/index.html"
            if path.startswith("/api/"):
                code = path.split("/")[2].upper()
                if code in ("HSI", "HHI"):
                    body = json.dumps(cache.get(code), ensure_ascii=False).encode("utf-8")
                    self._send(body, "application/json; charset=utf-8")
                elif path == "/api/status":
                    self._send(
                        json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8"),
                        "application/json",
                    )
                else:
                    self._send(b"{}", "application/json", 404)
                return
            # static files
            safe = Path(path.lstrip("/"))
            f = (page_dir_path / safe).resolve()
            if not str(f).startswith(str(page_dir_path.resolve())) or not f.is_file():
                self._send(b"not found", "text/plain", 404)
                return
            ctype = {
                ".html": "text/html; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
            }.get(f.suffix, "application/octet-stream")
            self._send(f.read_bytes(), ctype)

    for port in range(PORT_START, PORT_START + 10):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        except OSError:
            continue
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return port
    return 0

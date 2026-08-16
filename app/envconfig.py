"""Tiny stdlib-only .env loader + app settings.

Reads ``.env`` from (in order): the folder next to the exe (when frozen),
the project root (when running from source), and the app config dir.
Real environment variables always win over .env values.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "FuturesExporter"

DEFAULTS = {
    "ETNET_FUTURES_URL": "https://www.etnet.com.hk/www/tc/futures/",
    "REQUEST_TIMEOUT": "30",
    "USER_AGENT": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "OUTPUT_DIR": "",  # empty = Desktop
    "DOWNLOAD_PREFIX": "etnet_futures",
}


def env_files() -> list:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent  # next to the exe
    else:
        base = Path(__file__).resolve().parent.parent  # project root
    return [base / ".env", Path.home() / f".{APP_NAME}" / ".env"]


def parse_env(text: str) -> dict:
    """Parse KEY=VALUE lines; ignore blanks and # comments."""
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            out[key] = value
    return out


def load_settings(files=None) -> dict:
    settings = dict(DEFAULTS)
    for f in (files if files is not None else env_files()):
        p = Path(f)
        if p.is_file():
            settings.update(parse_env(p.read_text(encoding="utf-8")))
    for key in DEFAULTS:  # real env vars win
        if os.environ.get(key):
            settings[key] = os.environ[key]
    return settings


SETTINGS = load_settings()

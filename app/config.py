"""Persist application settings (schedule config) as JSON."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .scheduler import ScheduleConfig

APP_NAME = "FuturesExporter"


def config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME}"


def config_file() -> Path:
    return config_dir() / "config.json"


def load_config() -> ScheduleConfig:
    cfg = ScheduleConfig()
    try:
        data = json.loads(config_file().read_text(encoding="utf-8"))
        cfg.enabled = bool(data.get("enabled", False))
        cfg.mode = data.get("mode", "weekly")
        cfg.weekdays = [int(d) for d in data.get("weekdays", list(range(5)))]
        cfg.times = [str(t) for t in data.get("times", ["16:30"])]
        cfg.interval_days = int(data.get("interval_days", 1))
        cfg.start_date = str(data.get("start_date", ""))
        cfg.contract = str(data.get("contract", ""))
        cfg.all_contracts = bool(data.get("all_contracts", False))
        cfg.output_dir = str(data.get("output_dir", ""))
    except Exception:
        pass
    return cfg


def save_config(cfg: ScheduleConfig) -> None:
    config_file().parent.mkdir(parents=True, exist_ok=True)
    data = {
        "enabled": cfg.enabled,
        "mode": cfg.mode,
        "weekdays": cfg.weekdays,
        "times": cfg.times,
        "interval_days": cfg.interval_days,
        "start_date": cfg.start_date,
        "contract": cfg.contract,
        "all_contracts": cfg.all_contracts,
        "output_dir": cfg.output_dir,
    }
    config_file().write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

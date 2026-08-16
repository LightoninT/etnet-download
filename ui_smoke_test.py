"""Offscreen UI smoke test - verifies the main window builds and that
collecting config from the UI produces a valid ScheduleConfig."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config as app_config  # noqa: E402

# deterministic: start from a clean config
cfg_file = app_config.config_file()
if cfg_file.exists():
    cfg_file.unlink()

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.scheduler import ScheduleConfig  # noqa: E402
from app.ui_main import MainWindow  # noqa: E402


def main():
    app = QApplication([])
    win = MainWindow()
    win.show()

    cfg = win._collect_config()
    assert isinstance(cfg, ScheduleConfig), "config collection broken"
    assert cfg.validate() == "", f"default config invalid: {cfg.validate()}"
    print("default config summary:", cfg.summary())

    # weekly mode
    win.radio_weekly.setChecked(True)
    cfg = win._collect_config()
    assert cfg.mode == "weekly" and cfg.weekdays, cfg

    # daily mode
    win.radio_daily.setChecked(True)
    cfg = win._collect_config()
    assert cfg.mode == "daily" and cfg.times_per_week() == 7 * len(cfg.times), cfg

    # interval mode
    win.radio_interval.setChecked(True)
    win.interval_spin.setValue(3)
    cfg = win._collect_config()
    assert cfg.mode == "interval" and cfg.interval_days == 3, cfg

    # add/remove time
    win.radio_daily.setChecked(True)
    win.time_edit.setTime(__import__("PySide6.QtCore", fromlist=["QTime"]).QTime(8, 0))
    win._on_add_time()
    times = [win.times_list.item(k).text() for k in range(win.times_list.count())]
    print("times after add:", times)
    assert "08:00" in times

    # HKT dropdown: pick a time from the combo and add it
    win.hkt_combo.setCurrentText("09:15")
    win._on_add_combo_time()
    times = [win.times_list.item(k).text() for k in range(win.times_list.count())]
    print("times after combo add:", times)
    assert "09:15" in times

    # HKT checkbox wiring
    assert win.hkt_check.isChecked()
    cfg = win._collect_config()
    assert cfg.use_hkt is True
    assert "HKT" in cfg.summary()
    win.hkt_check.setChecked(False)
    cfg = win._collect_config()
    assert cfg.use_hkt is False
    win.hkt_check.setChecked(True)

    # toggle schedule on/off
    win._toggle_schedule()
    assert win._schedule_active and win.start_btn.text() == "停止排程"
    win._toggle_schedule()
    assert not win._schedule_active and win.start_btn.text() == "開始排程"

    # next run label computed
    win._schedule_active = True
    win._update_next_run_label()
    print("next run label:", win.next_run_label.text())
    assert win.next_run_label.text().startswith("下次執行:")

    win.close()
    print("UI SMOKE TEST OK")


if __name__ == "__main__":
    main()

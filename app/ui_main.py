"""Main window: two tabs - manual download + scheduled download."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, QTime, QTimer, QUrl, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QRadioButton, QSpinBox, QTabWidget, QTimeEdit, QVBoxLayout,
    QWidget,
)

from . import config as app_config
from .downloader import fetch_html, product_month_map
from .scheduler import WEEKDAY_NAMES, ScheduleConfig, hkt_display, next_run
from .worker import DEFAULT_PRODUCTS, DownloadWorker, desktop_dir

# products checked by default (恆生指數期貨 + 恆生中國企業指數期貨)
DEFAULT_TICKED = ["HSI", "HHI"]


class _ContractLoader(QThread):
    """Fetch the product list (code -> name/months) from etnet in background."""

    loaded = Signal(dict)      # {code: (name, [months...])}
    failed = Signal(str)

    def run(self):
        try:
            pmap = product_month_map(fetch_html())
            if not pmap:
                raise RuntimeError("產品清單為空")
            self.loaded.emit(pmap)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ETNet 期貨數據匯出工具")
        self.resize(880, 680)

        self._workers: list = []          # keep references to running threads
        self._busy = False
        self._schedule_active = False
        self._last_fired = None
        self._pending_scheduled = None    # queued scheduled run while busy
        self._start_date = ""             # interval-mode anchor date
        self._contract_loader = None
        self.live_refresh_timer = None    # 2s live-chart refresher (created in _build_live_tab)

        self._build_ui()
        self._load_settings_into_ui()

        # scheduler tick
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start(10000)
        self._on_tick()

        # background contract list
        self._start_contract_loader()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        tabs = QTabWidget()
        # live charts tab FIRST (before 下載數據)
        self._build_live_tab(tabs)
        tabs.addTab(self._build_download_tab(), "下載數據")
        tabs.addTab(self._build_schedule_tab(), "排程下載")
        self.setCentralWidget(tabs)
        self.statusBar().showMessage("就緒")

    def _build_live_tab(self, tabs: QTabWidget):
        """即時圖表: renders the GitHub Pages webpage (HSI/HHI range-block +
        mid-line charts). Data is fetched by the webpage itself via the
        Cloudflare Worker proxy - the exe does not fetch etnet directly."""
        self.live_view = QWebEngineView()
        self.live_view.load(QUrl("https://lightonint.github.io/etnet-download/"))
        tabs.insertTab(0, self.live_view, "即時圖表")

        # refresh the live chart every 2 seconds while this tab is active
        self.live_refresh_timer = QTimer(self)
        self.live_refresh_timer.setInterval(2000)
        self.live_refresh_timer.timeout.connect(self._refresh_live_view)
        tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int):
        if self.live_refresh_timer is not None:
            if index == 0:  # live tab active
                self.live_refresh_timer.start()
                self._refresh_live_view()
            else:
                self.live_refresh_timer.stop()

    def _refresh_live_view(self):
        if self.live_view.page() is not None:
            self.live_view.page().runJavaScript(
                "typeof refresh === 'function' && refresh();"
            )

    # -- tab 1: manual download -----------------------------------------
    def _build_download_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        info = QLabel(
            "資料來源: https://www.etnet.com.hk/www/tc/futures/\n"
            "勾選要下載的期貨產品（每個產品一個 Excel 分頁，包含報價、未平倉、"
            "15分鐘時段記錄）。月份自動下載「即月 + 下一個月」。"
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        prod_grp = QGroupBox("選擇期貨產品（tick box，可多選）")
        pg = QVBoxLayout(prod_grp)
        self.product_checks: dict = {}
        first = True
        for code in DEFAULT_PRODUCTS:
            cb = QCheckBox(code)
            cb.setChecked(True)
            cb.toggled.connect(self._on_config_changed)
            self.product_checks[code] = cb
            pg.addWidget(cb)
            first = False
        self.product_extra_label = QLabel("正在讀取其他產品 ...")
        pg.addWidget(self.product_extra_label)
        lay.addWidget(prod_grp)

        btn_row = QHBoxLayout()
        self.get_btn = QPushButton("Get Data")
        self.get_btn.setMinimumHeight(34)
        self.get_btn.clicked.connect(self._on_get_data)
        btn_row.addWidget(self.get_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.out_dir_label = QLabel()
        lay.addWidget(self.out_dir_label)

        self.dl_status = QLabel("尚未下載")
        self.dl_status.setWordWrap(True)
        lay.addWidget(self.dl_status)

        btn_row = QHBoxLayout()
        self.open_folder_btn = QPushButton("開啟桌面資料夾")
        self.open_folder_btn.clicked.connect(self._open_output_dir)
        btn_row.addWidget(self.open_folder_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)
        lay.addStretch(1)
        return w

    # -- tab 2: scheduler ------------------------------------------------
    def _build_schedule_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        # --- settings group ---
        grp = QGroupBox("排程設定")
        g = QVBoxLayout(grp)

        mode_row = QHBoxLayout()
        self.radio_weekly = QRadioButton("每週（指定日子）")
        self.radio_daily = QRadioButton("每日")
        self.radio_interval = QRadioButton("每隔 N 日")
        self.radio_weekly.setChecked(True)
        for rb in (self.radio_weekly, self.radio_daily, self.radio_interval):
            rb.toggled.connect(self._on_mode_changed)
            mode_row.addWidget(rb)
        mode_row.addStretch(1)
        g.addLayout(mode_row)

        # weekday checkboxes
        wd_row = QHBoxLayout()
        wd_row.addWidget(QLabel("執行日子:"))
        self.weekday_checks = []
        for i, name in enumerate(WEEKDAY_NAMES):
            cb = QCheckBox(name)
            cb.setChecked(i < 5)
            cb.toggled.connect(self._on_config_changed)
            self.weekday_checks.append(cb)
            wd_row.addWidget(cb)
        wd_row.addStretch(1)
        self.wd_row_layout = wd_row
        g.addLayout(wd_row)

        # interval days
        iv_row = QHBoxLayout()
        iv_row.addWidget(QLabel("每隔"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 30)
        self.interval_spin.setValue(1)
        self.interval_spin.valueChanged.connect(self._on_config_changed)
        iv_row.addWidget(self.interval_spin)
        iv_row.addWidget(QLabel("日"))
        iv_row.addStretch(1)
        self.iv_row_layout = iv_row
        g.addLayout(iv_row)

        # times editor
        t_row = QHBoxLayout()
        t_row.addWidget(QLabel("執行時間 (每日可多個):"))
        self.hkt_check = QCheckBox("以香港時間 (HKT) 計算")
        self.hkt_check.setChecked(True)
        self.hkt_check.toggled.connect(self._on_config_changed)
        t_row.addStretch(1)
        t_row.addWidget(self.hkt_check)
        g.addLayout(t_row)

        times_row = QHBoxLayout()
        self.times_list = QListWidget()
        self.times_list.setMaximumHeight(110)
        times_row.addWidget(self.times_list, 1)

        t_edit_col = QVBoxLayout()
        # dropdown of common HK times (5-min steps, covers HK futures sessions)
        self.hkt_combo = QComboBox()
        for h in range(24):
            for m in range(0, 60, 5):
                self.hkt_combo.addItem(f"{h:02d}:{m:02d}")
        self.hkt_combo.setCurrentText("16:30")
        t_edit_col.addWidget(self.hkt_combo)
        self.add_combo_time_btn = QPushButton("加入(下拉)")
        self.add_combo_time_btn.clicked.connect(self._on_add_combo_time)
        t_edit_col.addWidget(self.add_combo_time_btn)
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime(16, 30))
        t_edit_col.addWidget(self.time_edit)
        self.add_time_btn = QPushButton("加入時間")
        self.add_time_btn.clicked.connect(self._on_add_time)
        t_edit_col.addWidget(self.add_time_btn)
        self.del_time_btn = QPushButton("移除時間")
        self.del_time_btn.clicked.connect(self._on_remove_time)
        t_edit_col.addWidget(self.del_time_btn)
        times_row.addLayout(t_edit_col)
        g.addLayout(times_row)

        # products note (selection lives on the download tab)
        c_row = QHBoxLayout()
        self.sched_products_label = QLabel(
            "下載產品: 以「下載數據」頁的 tick box 勾選為準（自動下載即月 + 下一個月）"
        )
        self.sched_products_label.setWordWrap(True)
        c_row.addWidget(self.sched_products_label, 1)
        g.addLayout(c_row)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        g.addWidget(self.summary_label)

        lay.addWidget(grp)

        # --- control group ---
        ctrl = QGroupBox("執行控制")
        cv = QVBoxLayout(ctrl)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("開始排程")
        self.start_btn.setMinimumHeight(34)
        self.start_btn.clicked.connect(self._toggle_schedule)
        btn_row.addWidget(self.start_btn)
        self.run_now_btn = QPushButton("立即執行一次")
        self.run_now_btn.clicked.connect(lambda: self._run_download(manual=True))
        btn_row.addWidget(self.run_now_btn)
        btn_row.addStretch(1)
        cv.addLayout(btn_row)

        self.next_run_label = QLabel("下次執行: -")
        cv.addWidget(self.next_run_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        cv.addWidget(self.log_view, 1)

        lay.addWidget(ctrl, 1)
        return w

    # ------------------------------------------------------------------
    # settings <-> UI
    # ------------------------------------------------------------------
    def _load_settings_into_ui(self):
        cfg = app_config.load_config()
        if cfg.mode == "daily":
            self.radio_daily.setChecked(True)
        elif cfg.mode == "interval":
            self.radio_interval.setChecked(True)
        else:
            self.radio_weekly.setChecked(True)
        for i, cb in enumerate(self.weekday_checks):
            cb.setChecked(i in cfg.weekdays)
        self.interval_spin.setValue(max(1, cfg.interval_days))
        self.hkt_check.setChecked(cfg.use_hkt)
        self._start_date = cfg.start_date
        self.times_list.clear()
        for t in sorted(set(cfg.times)):
            self.times_list.addItem(t)
        for code, cb in self.product_checks.items():
            cb.setChecked(code in cfg.products)
        self._schedule_active = cfg.enabled
        self._sync_start_stop_button()
        self._on_mode_changed()
        self._on_config_changed()
        self._update_next_run_label()

    def _collect_config(self) -> ScheduleConfig:
        cfg = ScheduleConfig()
        if self.radio_daily.isChecked():
            cfg.mode = "daily"
        elif self.radio_interval.isChecked():
            cfg.mode = "interval"
        else:
            cfg.mode = "weekly"
        cfg.weekdays = [
            i for i, cb in enumerate(self.weekday_checks) if cb.isChecked()
        ]
        cfg.interval_days = self.interval_spin.value()
        cfg.times = [
            self.times_list.item(k).text()
            for k in range(self.times_list.count())
        ]
        cfg.products = [
            code for code, cb in self.product_checks.items() if cb.isChecked()
        ]
        cfg.output_dir = ""
        cfg.use_hkt = self.hkt_check.isChecked()
        cfg.start_date = self._start_date
        cfg.enabled = self._schedule_active
        return cfg

    def _persist(self):
        try:
            app_config.save_config(self._collect_config())
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # event handlers
    # ------------------------------------------------------------------
    def _on_config_changed(self):
        cfg = self._collect_config()
        err = cfg.validate()
        if err:
            self.summary_label.setText(f"<span style='color:#c00000'>{err}</span>")
            self.start_btn.setEnabled(False)
        else:
            self.summary_label.setText(cfg.summary())
            self.start_btn.setEnabled(True)
        self._update_next_run_label()
        self._persist()

    def _on_mode_changed(self):
        weekly = self.radio_weekly.isChecked()
        interval = self.radio_interval.isChecked()
        for cb in self.weekday_checks:
            cb.setEnabled(weekly)
        self.interval_spin.setEnabled(interval)
        self._on_config_changed()

    def _on_add_time(self):
        t = self.time_edit.time().toString("HH:mm")
        if t not in [self.times_list.item(k).text() for k in range(self.times_list.count())]:
            self.times_list.addItem(t)
            self._on_config_changed()

    def _on_add_combo_time(self):
        t = self.hkt_combo.currentText()
        if t not in [self.times_list.item(k).text() for k in range(self.times_list.count())]:
            self.times_list.addItem(t)
            self._on_config_changed()

    def _on_remove_time(self):
        row = self.times_list.currentRow()
        if row >= 0:
            self.times_list.takeItem(row)
            self._on_config_changed()

    def _on_get_data(self):
        self._run_download(manual=True)

    def _toggle_schedule(self):
        if self._schedule_active:
            self._schedule_active = False
            self._last_fired = None
            self._log("排程已停止")
        else:
            cfg = self._collect_config()
            err = cfg.validate()
            if err:
                QMessageBox.warning(self, "排程設定錯誤", err)
                return
            self._start_date = dt.date.today().isoformat()
            self._schedule_active = True
            self._log(f"排程已啟動: {cfg.summary()}")
        self._sync_start_stop_button()
        self._persist()
        self._update_next_run_label()

    def _sync_start_stop_button(self):
        if self._schedule_active:
            self.start_btn.setText("停止排程")
        else:
            self.start_btn.setText("開始排程")

    # ------------------------------------------------------------------
    # scheduler loop
    # ------------------------------------------------------------------
    def _on_tick(self):
        if self._schedule_active:
            cfg = self._collect_config()
            now = dt.datetime.now()
            # candidate scheduled within the last 61 seconds -> fire now
            nxt = next_run(now - dt.timedelta(seconds=61), cfg)
            if nxt is not None and nxt <= now and nxt != self._last_fired:
                self._last_fired = nxt
                self._log(f"排程觸發: {nxt.strftime('%Y-%m-%d %H:%M')}")
                self._run_download(manual=False, scheduled=nxt)
        self._update_next_run_label()

    def _update_next_run_label(self):
        cfg = self._collect_config()
        if self._schedule_active:
            nxt = next_run(dt.datetime.now(), cfg)
            if nxt:
                local_s = nxt.strftime("%Y-%m-%d %H:%M:%S")
                if cfg.use_hkt:
                    self.next_run_label.setText(
                        f"下次執行: {local_s}（香港時間 {hkt_display(nxt)}）"
                    )
                else:
                    self.next_run_label.setText(f"下次執行: {local_s}")
                return
        self.next_run_label.setText("下次執行: -")

    # ------------------------------------------------------------------
    # download execution
    # ------------------------------------------------------------------
    def _run_download(self, manual: bool, scheduled: dt.datetime | None = None):
        if self._busy:
            if not manual and scheduled is not None:
                # queue the scheduled run; dispatch when the current download ends
                self._pending_scheduled = scheduled
                self._log(
                    "警告: 上一次下載仍在進行中，本次排程已排隊，完成後會立即執行"
                )
            else:
                self._log("警告: 上一次下載仍在進行中，本次已略過")
            return
        self._pending_scheduled = None
        products = self._collect_config().products
        if not products:
            self._log("錯誤: 請先勾選至少一個期貨產品")
            if manual:
                QMessageBox.warning(self, "未選擇產品", "請先勾選至少一個期貨產品")
            return

        worker = DownloadWorker(products=products)
        worker.progress.connect(lambda m: self._log(m))
        worker.succeeded.connect(self._on_download_success)
        worker.failed.connect(self._on_download_failed)
        self._workers.append(worker)
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))
        self._busy = True
        self.dl_status.setText("正在下載 ...")
        self.statusBar().showMessage("正在下載數據 ...")
        worker.start()

    def _on_download_success(self, path: str):
        self.dl_status.setText(f"✅ 已儲存: {path}")
        self.statusBar().showMessage("下載完成")
        self._log(f"完成: {path}")
        self.out_dir_label.setText(f"輸出位置: {Path(path).parent}")

    def _on_download_failed(self, msg: str):
        self.dl_status.setText(f"❌ 下載失敗: {msg}")
        self.statusBar().showMessage("下載失敗")
        self._log(f"失敗: {msg}")

    def _cleanup_worker(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)
        self._busy = False
        # dispatch a scheduled run that was queued while a download was running
        if self._pending_scheduled is not None:
            nxt = self._pending_scheduled
            self._pending_scheduled = None
            self._log(f"執行排隊的排程: {nxt.strftime('%Y-%m-%d %H:%M')}")
            self._run_download(manual=False, scheduled=nxt)

    def _open_output_dir(self):
        d = desktop_dir()
        try:
            d.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(d))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(d)])
            else:
                subprocess.Popen(["xdg-open", str(d)])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "無法開啟資料夾", str(exc))

    def _log(self, msg: str):
        stamp = dt.datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{stamp}] {msg}")

    # ------------------------------------------------------------------
    # contract list
    # ------------------------------------------------------------------
    def _start_contract_loader(self):
        def fill(pmap: dict):
            for code, (name, months) in sorted(pmap.items()):
                if code in self.product_checks:
                    cb = self.product_checks[code]
                    cb.setText(f"{code} - {name}")
                    continue
                cb = QCheckBox(f"{code} - {name}")
                cb.setChecked(False)
                cb.toggled.connect(self._on_config_changed)
                self.product_checks[code] = cb
                # insert before the extra label
                lay = self.product_extra_label.parentWidget().layout()
                lay.insertWidget(lay.count() - 1, cb)
            self.product_extra_label.setText("月份: 自動下載「即月 + 下一個月」")
            self._apply_saved_contract()

        def on_fail(msg):
            self.product_extra_label.setText(f"無法取得產品清單: {msg}")

        self._contract_loader = _ContractLoader()
        self._contract_loader.loaded.connect(fill)
        self._contract_loader.failed.connect(on_fail)
        self._contract_loader.start()

    def _apply_saved_contract(self):
        cfg = app_config.load_config()
        for code, cb in self.product_checks.items():
            cb.setChecked(code in cfg.products)

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self._tick.stop()
        self._persist()
        if self._contract_loader is not None and self._contract_loader.isRunning():
            self._contract_loader.wait(3000)
        for w in list(self._workers):
            if w.isRunning():
                w.wait(3000)
        event.accept()

"""Background download worker (QThread) used by both the manual button and
the scheduler."""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import downloader, excel_writer
from .envconfig import SETTINGS


def desktop_dir() -> Path:
    """Resolve the user's Desktop directory."""
    if sys.platform == "win32":
        profile = os.environ.get("USERPROFILE") or str(Path.home())
        cand = Path(profile) / "Desktop"
        if cand.exists():
            return cand
        # OneDrive-redirected desktop
        od = Path(profile) / "OneDrive" / "Desktop"
        if od.exists():
            return od
        return cand
    return Path.home() / "Desktop"


class DownloadWorker(QThread):
    """Fetch one contract (or all front-month contracts) and save .xlsx.

    Signals:
        progress(str)  - human readable progress message
        succeeded(str) - path of the saved file
        failed(str)    - error message
    """

    progress = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, contract: str = "", all_contracts: bool = False,
                 output_dir: str = "", parent=None):
        super().__init__(parent)
        self.contract = contract          # "CODE|YYYYMM" or ""
        self.all_contracts = all_contracts
        self.output_dir = output_dir

    # ------------------------------------------------------------------
    def run(self):
        try:
            out_dir = Path(self.output_dir) if self.output_dir else (
                Path(SETTINGS["OUTPUT_DIR"]) if SETTINGS["OUTPUT_DIR"] else desktop_dir()
            )
            out_dir.mkdir(parents=True, exist_ok=True)
            prefix = SETTINGS["DOWNLOAD_PREFIX"] or "etnet_futures"

            if self.all_contracts:
                self.progress.emit("正在讀取合約清單 ...")
                html = downloader.fetch_html()
                opts = downloader.front_month_options(html)
                if not opts:
                    raise RuntimeError("無法從網頁取得合約清單")
                pages = []
                for code, month, label in opts:
                    self.progress.emit(f"下載中: {label} ({code})")
                    try:
                        p = downloader.get_futures_page(code, month)
                    except Exception as exc:  # keep going on per-contract errors
                        self.progress.emit(f"警告: {label} 下載失敗 - {exc}")
                        continue
                    pages.append(p)
                if not pages:
                    raise RuntimeError("所有合約均下載失敗")
                wb = excel_writer.build_multi_workbook(pages)
                filename = (
                    f"{prefix}_ALL_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                )
            else:
                subtype = month = ""
                if self.contract and "|" in self.contract:
                    subtype, month = self.contract.split("|", 1)
                label = subtype or "即月"
                self.progress.emit(f"下載中: {label} ...")
                page = downloader.get_futures_page(subtype, month)
                wb = excel_writer.build_workbook(page)
                filename = excel_writer.default_filename(page, prefix=prefix)

            path = out_dir / filename
            self.progress.emit(f"寫入檔案: {path.name} ...")
            wb.save(str(path))
            self.succeeded.emit(str(path))
        except Exception as exc:  # noqa: BLE001 - surface all failures to UI
            self.failed.emit(str(exc))

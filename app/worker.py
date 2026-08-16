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

DEFAULT_PRODUCTS = ["HSI", "HHI"]


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
    """Fetch the ticked products (current + next contract month) and save .xlsx.

    Signals:
        progress(str)  - human readable progress message
        succeeded(str) - path of the saved file
        failed(str)    - error message
    """

    progress = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, products: list = None, output_dir: str = "", parent=None):
        super().__init__(parent)
        self.products = list(products) if products else list(DEFAULT_PRODUCTS)
        self.output_dir = output_dir

    # ------------------------------------------------------------------
    def run(self):
        try:
            out_dir = Path(self.output_dir) if self.output_dir else (
                Path(SETTINGS["OUTPUT_DIR"]) if SETTINGS["OUTPUT_DIR"] else desktop_dir()
            )
            out_dir.mkdir(parents=True, exist_ok=True)
            prefix = SETTINGS["DOWNLOAD_PREFIX"] or "etnet_futures"

            self.progress.emit("正在讀取產品/月份清單 ...")
            html = downloader.fetch_html()
            pmap = downloader.product_month_map(html)
            if not pmap:
                raise RuntimeError("無法從網頁取得產品清單")

            pages_by_code: dict = {}
            for code in self.products:
                if code not in pmap:
                    self.progress.emit(f"警告: 找不到產品 {code}")
                    continue
                name, months = pmap[code]
                for month in months[:2]:  # current + next month only
                    self.progress.emit(f"下載中: {name} ({month})")
                    try:
                        p = downloader.get_futures_page(code, month)
                    except Exception as exc:  # keep going on per-contract errors
                        self.progress.emit(f"警告: {name} ({month}) 下載失敗 - {exc}")
                        continue
                    pages_by_code.setdefault(code, []).append(p)

            if not pages_by_code:
                raise RuntimeError("所有勾選的產品均下載失敗")

            wb = excel_writer.build_tabs_workbook(
                pages_by_code, {k: v[0] for k, v in pmap.items()}
            )
            codes = "_".join(sorted(pages_by_code))
            filename = (
                f"{prefix}_{codes}_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            )

            path = out_dir / filename
            self.progress.emit(f"寫入檔案: {path.name} ...")
            wb.save(str(path))
            self.succeeded.emit(str(path))
        except Exception as exc:  # noqa: BLE001 - surface all failures to UI
            self.failed.emit(str(exc))

"""ETNet Futures Exporter - entry point.

Downloads HK index futures data from https://www.etnet.com.hk/www/tc/futures/
into an .xlsx file on the Desktop, with an optional scheduler and a live
candlestick-chart tab.
"""

import os
import sys

# QtWebEngine sandbox flags must be set before QApplication is created
# (required for packaged PyInstaller builds on Windows).
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui_main import MainWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ETNet Futures Exporter")
    app.setOrganizationName("FuturesExporter")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

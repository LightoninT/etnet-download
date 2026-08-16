"""ETNet Futures Exporter - entry point.

Downloads HK index futures data from https://www.etnet.com.hk/www/tc/futures/
into an .xlsx file on the Desktop, with an optional scheduler and a live
candlestick-chart tab.
"""

import os
import sys
from pathlib import Path

# QtWebEngine sandbox flags must be set before QApplication is created
# (required for packaged PyInstaller builds on Windows).
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

# Frozen macOS bundles ship QtWebEngineProcess.app under Contents/Resources
# (PyInstaller's hook does not copy the helper into the bundle), and the
# webengine .pak resources land at a non-standard framework path.
if getattr(sys, "frozen", False) and sys.platform == "darwin":
    meipass = Path(getattr(sys, "_MEIPASS", ""))
    helper = (
        meipass / ".." / "Resources"
        / "QtWebEngineProcess.app" / "Contents" / "MacOS" / "QtWebEngineProcess"
    )
    if helper.exists():
        os.environ.setdefault("QTWEBENGINEPROCESS_PATH", str(helper))
    res = (
        meipass / "PySide6" / "Qt" / "lib" / "QtWebEngineCore.framework"
        / "Versions" / "Resources" / "Resources"
    )
    if (res / "qtwebengine_resources.pak").exists():
        os.environ.setdefault("QTWEBENGINE_RESOURCES_PATH", str(res))

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

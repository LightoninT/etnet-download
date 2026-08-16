"""ETNet Futures Exporter - entry point.

Downloads HK index futures data from https://www.etnet.com.hk/www/tc/futures/
into an .xlsx file on the Desktop, with an optional scheduler and a native
live candlestick-chart tab.
"""

import sys

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

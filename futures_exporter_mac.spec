# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for macOS: builds ETNetFuturesExporter.app (windowed).
# Usage:  pyinstaller --clean --noconfirm futures_exporter_mac.spec

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'bs4',
        'lxml',
        'openpyxl',
        'openpyxl.cell._writer',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtMultimedia',
        'PySide6.Qt3DCore',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ETNetFuturesExporter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='ETNetFuturesExporter',
)

app = BUNDLE(
    coll,
    name='ETNetFuturesExporter.app',
    icon='app.icns',
    bundle_identifier='com.lightonin.etnetfuturesexporter',
)

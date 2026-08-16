#!/bin/bash
# Publish a GitHub release with the Windows exe + macOS dmg.
# Requires: gh authenticated with write access to LightoninT/etnet-download.
set -e
cd "$(dirname "$0")"

GH="git -c credential.helper='!gh auth git-credential'"

echo "[1/3] Pushing code ..."
git -c credential.helper='!gh auth git-credential' push -u origin main

echo "[2/3] Tagging v1.1.1 ..."
git tag -f v1.1.1
git -c credential.helper='!gh auth git-credential' push -f origin v1.1.1

echo "[3/3] Creating GitHub release ..."
gh release create v1.1.1 \
  dist/ETNetFuturesExporter.exe \
  ETNetFuturesExporter-mac-arm64.dmg \
  --title "ETNet Futures Exporter v1.1.1" \
  --notes "## ETNet Futures Exporter v1.1.1

- Tab「下載數據」: 一鍵下載 etnet 期貨數據並儲存 .xlsx 到桌面
- Tab「排程下載」: 每週/每日/每隔N日 + 多個執行時間（香港時間 HKT 下拉選單）
- Windows: ETNetFuturesExporter.exe（PySide6 6.8.x, 64-bit）
- macOS: ETNetFuturesExporter-mac-arm64.dmg（Apple Silicon）"

echo "Release published: https://github.com/LightoninT/etnet-download/releases/tag/v1.1.1"

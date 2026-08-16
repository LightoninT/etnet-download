#!/bin/bash
# Publish a GitHub release with the Windows exe + onedir zip + macOS dmg.
# Requires: gh authenticated with write access to LightoninT/etnet-download.
set -e
cd "$(dirname "$0")"

VERSION="v1.1.5"

echo "[1/3] Pushing code ..."
git -c credential.helper='!gh auth git-credential' push -u origin main

echo "[2/3] Tagging $VERSION ..."
git tag -f "$VERSION"
git -c credential.helper='!gh auth git-credential' push -f origin "$VERSION"

echo "[3/3] Creating GitHub release ..."
gh release create "$VERSION" \
  dist/ETNetFuturesExporter.exe \
  dist/ETNetFuturesExporter-windows-onedir.zip \
  ETNetFuturesExporter-mac-arm64.dmg \
  --title "ETNet Futures Exporter $VERSION" \
  --notes "## ETNet Futures Exporter $VERSION

- Tab「即時圖表」: 原生繪製 HSI/HHI 15分鐘陰陽燭（粗影線）+ 中線（區間均值），每 2 秒經 Cloudflare Worker 更新
- Tab「下載數據」: tick box 選擇產品，即月+下月，一產品一頁（報價/未平倉/15分鐘時段記錄）
- Tab「排程下載」: 每週/每日/每隔N日 + 多個香港時間（HKT），排程不會因忙碌而漏跑
- Windows exe 已內嵌版本資訊；SmartScreen 提示請見 README（簽章指南: docs/SIGNING.md）
- 檔案:
  - ETNetFuturesExporter.exe (單檔, ~51MB)
  - ETNetFuturesExporter-windows-onedir.zip (資料夾版, 防毒誤報較少)
  - ETNetFuturesExporter-mac-arm64.dmg (macOS Apple Silicon)"

echo "Release published: https://github.com/LightoninT/etnet-download/releases/tag/$VERSION"

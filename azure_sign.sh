#!/bin/bash
# Sign the Windows exe with Azure Trusted Signing (free tier).
#
# One-time setup (docs/SIGNING.md):
#   1. Create a free Azure account + Trusted Signing resource + certificate profile
#   2. On this machine: brew install --cask dotnet-sdk
#
# Usage - fill in the 4 values from your Trusted Signing resource:
#   AZURE_ENDPOINT="https://xxxx.codesigning.azure.net" \
#   AZURE_ACCOUNT="xxxx" \
#   AZURE_PROFILE="xxxx" \
#   AZURE_CERT="xxxx" \
#   ./azure_sign.sh
set -e
cd "$(dirname "$0")"

EXE="dist/ETNetFuturesExporter.exe"
OUT="dist/ETNetFuturesExporter-signed.exe"

if [ ! -f "$EXE" ]; then echo "exe not found: $EXE"; exit 1; fi

: "${AZURE_ENDPOINT:?set AZURE_ENDPOINT (Trusted Signing endpoint)}"
: "${AZURE_ACCOUNT:?set AZURE_ACCOUNT}"
: "${AZURE_PROFILE:?set AZURE_PROFILE (certificate profile)}"
: "${AZURE_CERT:?set AZURE_CERT (certificate name)}"

if ! command -v azuresigntool >/dev/null 2>&1; then
  echo "installing AzureSignTool ..."
  dotnet tool install --global AzureSignTool
  export PATH="$PATH:$HOME/.dotnet/tools"
fi

azuresigntool sign \
  -kvu "$AZURE_ENDPOINT" \
  -kvi "$AZURE_ACCOUNT" \
  -kvs "$AZURE_PROFILE" \
  -kvc "$AZURE_CERT" \
  -tr http://timestamp.digicert.com -v \
  -in "$EXE" -out "$OUT"

echo "✅ 已簽章: $OUT"
azuresigntool verify "$OUT" | head -8
echo "發布前請執行: gh release upload v1.1.6 $OUT --repo LightoninT/etnet-download --clobber"

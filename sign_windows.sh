#!/bin/bash
# Sign the Windows exe with a code-signing certificate (osslsigncode).
#
# Why: Windows SmartScreen / antivirus flag any *unsigned* exe downloaded
# from the internet ("Unknown publisher"). Signing with a CA-trusted
# certificate removes that warning.
#
# Requirements (choose one):
#   A) Azure Trusted Signing (free tier, recommended) -> exports .pfx or
#      use azuresigntool instead; or
#   B) a commercial OV code-signing certificate (cert.pem + key.pem), or
#   C) an existing .pfx file.
#
# Usage:
#   ./sign_windows.sh                    # looks for cert.pem+key.pem
#   PFX=my.pfx PFX_PASS=secret ./sign_windows.sh
set -e
cd "$(dirname "$0")"
EXE="dist/ETNetFuturesExporter.exe"
OUT="dist/ETNetFuturesExporter-signed.exe"

if [ ! -f "$EXE" ]; then echo "exe not found: $EXE"; exit 1; fi

TS="http://timestamp.digicert.com"   # free RFC3161 timestamp server

if [ -n "$PFX" ]; then
  osslsigncode sign -pkcs12 "$PFX" -pass "$PFX_PASS" -h sha256 \
    -t "$TS" -in "$EXE" -out "$OUT"
elif [ -f cert.pem ] && [ -f key.pem ]; then
  osslsigncode sign -certs cert.pem -key key.pem -h sha256 \
    -t "$TS" -in "$EXE" -out "$OUT"
else
  echo "[錯誤] 找不到簽章憑證。"
  echo "       方法A(Azure Trusted Signing, 免費): 見 docs/SIGNING.md"
  echo "       方法B: 把 cert.pem + key.pem 放在本目錄"
  echo "       方法C: 用 PFX=/path/file.pfx PFX_PASS=xxx ./sign_windows.sh"
  exit 1
fi

echo "✅ 已簽章: $OUT"
osslsigncode verify "$OUT" | head -8

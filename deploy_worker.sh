#!/bin/bash
# Deploy the Cloudflare Worker proxy.
# Needs CLOUDFLARE_API_TOKEN (export it, or put it in the git-ignored .env).
set -e
cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
  echo "[錯誤] 未設定 CLOUDFLARE_API_TOKEN"
  echo "       請在 .env 加入: CLOUDFLARE_API_TOKEN=你的token"
  exit 1
fi

npx --yes wrangler deploy
echo
echo "✅ Worker 已部署。請把 workers.dev 網址告訴 agent，"
echo "   它會寫入 webpage/app.js 的 CLOUDFLARE_WORKER_URL。"

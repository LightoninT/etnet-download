/* ETNet 期貨 15分鐘陰陽燭圖
 * - Two charts: HSI (恒生指數期貨) and HHI (恒生中國企業指數期貨), current month
 * - 15-min candlestick + horizontal mid line (前收市)
 * - Polls every 60 seconds.
 * Data path:
 *   1. same-origin /api/<code> (the exe's built-in local server) - preferred
 *   2. public CORS proxies fetching the etnet page directly (GitHub Pages)
 */
"use strict";

const REFRESH_MS = 60 * 1000; // 1-minute timer

const PRODUCTS = [
  { code: "HSI", title: "恒生指數期貨 (HSI)" },
  { code: "HHI", title: "恒生中國企業指數期貨 (HHI)" },
];

// Cloudflare Worker proxy (free). Deploy webpage/worker_proxy.js to a worker,
// then put its URL here. It is tried first; the public proxies below are fallbacks.
const CLOUDFLARE_WORKER_URL = "https://etnet-proxy.etnetdata.workers.dev";

// public CORS proxies, tried in order when same-origin API is unavailable
const PROXIES = [
  (u) => CLOUDFLARE_WORKER_URL
    ? `${CLOUDFLARE_WORKER_URL}?url=${encodeURIComponent(u)}`
    : null, // not configured -> skipped
  (u) => `https://api.cors.lol/?url=${encodeURIComponent(u)}`,
  (u) => `https://api.allorigins.win/raw?url=${encodeURIComponent(u)}`,
  (u) => `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(u)}`,
];

const statusEl = document.getElementById("status");
const charts = {};   // code -> chart instance
const series = {};   // code -> candlestick series
const midLines = {}; // code -> price line

// ---------------------------------------------------------------------------
// HKT display helper
// ---------------------------------------------------------------------------
function hktNowStr() {
  return new Intl.DateTimeFormat("zh-HK", {
    timeZone: "Asia/Hong_Kong", hour: "2-digit", minute: "2-digit", second: "2-digit",
    hour12: false,
  }).format(new Date());
}

// ---------------------------------------------------------------------------
// Parsing: handled by parser.js (ETNetParser) - shared with the exe's page
// ---------------------------------------------------------------------------
const { parsePage } = ETNetParser;

// ---------------------------------------------------------------------------
// Fetching
// ---------------------------------------------------------------------------
async function fetchJsonOrHtml(code) {
  // proxy chain (Cloudflare Worker first, then public CORS proxies) -> parse HTML
  const url = `https://www.etnet.com.hk/www/tc/futures/?subtype=${code}`;
  let lastErr = null;
  for (const proxy of PROXIES) {
    if (!proxy(url)) continue; // skip unconfigured proxy (empty CLOUDFLARE_WORKER_URL)
    try {
      const resp = await fetch(proxy(url));
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const text = await resp.text();
      return { page: parsePage(text, code) };
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error("無法取得數據");
}

// ---------------------------------------------------------------------------
// Chart rendering
// ---------------------------------------------------------------------------
function makeChart(el) {
  const chart = LightweightCharts.createChart(el, {
    height: 380,
    layout: { background: { color: "#ffffff" }, textColor: "#1c2330" },
    grid: {
      vertLines: { color: "#eef1f6" },
      horzLines: { color: "#eef1f6" },
    },
    rightPriceScale: { borderColor: "#dde1e9" },
    timeScale: { borderColor: "#dde1e9", timeVisible: true, secondsVisible: false },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  });
  const s = chart.addCandlestickSeries({
    upColor: "#e53e3e", downColor: "#2f9e44",
    borderUpColor: "#e53e3e", borderDownColor: "#2f9e44",
    wickUpColor: "#e53e3e", wickDownColor: "#2f9e44",
  });
  return { chart, s };
}

function setMidLine(s, price) {
  if (midLines[s] !== undefined) s.removePriceLine(midLines[s]);
  if (price != null && Number.isFinite(price)) {
    midLines[s] = s.createPriceLine({
      price,
      color: "#1f6feb",
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: true,
      title: "中線(日中點)",
    });
  }
}

function render(code, data) {
  const chart = charts[code];
  chart.s.setData(data.candles);
  chart.chart.timeScale().fitContent();
  // mid line = session mid-point, fallback to previous close
  setMidLine(chart.s, data.midPoint != null ? data.midPoint : data.prevClose);

  const meta = document.getElementById(`meta-${code}`);
  const last = data.candles.length ? data.candles[data.candles.length - 1].close : null;
  const change = last != null && data.prevClose != null ? last - data.prevClose : null;
  const pct = change != null && data.prevClose ? ((change / data.prevClose) * 100) : null;
  const cls = change > 0 ? "up" : change < 0 ? "down" : "";
  const arrow = change > 0 ? "▲" : change < 0 ? "▼" : "";
  const month = data.month ? `${data.month.slice(0, 4)}/${data.month.slice(4)}` : "";
  meta.innerHTML =
    `<span>月份: ${month}</span><br>` +
    `<span class="last">${last != null ? last.toLocaleString() : "—"}</span> ` +
    `<span class="${cls}">${arrow}${change != null ? change.toLocaleString() : ""} ` +
    `(${pct != null ? pct.toFixed(2) : "—"}%)</span><br>` +
    `<span>網頁更新: ${data.updated || "—"}　本地: ${hktNowStr()}</span>`;
}

// ---------------------------------------------------------------------------
// Main loop (1-minute timer)
// ---------------------------------------------------------------------------
async function refresh() {
  let ok = 0;
  for (const p of PRODUCTS) {
    try {
      const res = await fetchJsonOrHtml(p.code);
      render(p.code, res.page);
      ok++;
    } catch (e) {
      document.getElementById(`meta-${p.code}`).textContent = `❌ ${e.message}`;
    }
  }
  statusEl.textContent =
    ok === PRODUCTS.length
      ? `✅ 已更新 ${hktNowStr()}（每 60 秒自動更新）`
      : `⚠️ 部分更新失敗 ${hktNowStr()}，下一分鐘重試`;
  statusEl.classList.toggle("err", ok !== PRODUCTS.length);
}

function init() {
  for (const p of PRODUCTS) {
    const el = document.getElementById(`chart-${p.code}`);
    charts[p.code] = makeChart(el);
  }
  refresh();
  setInterval(refresh, REFRESH_MS);
}

document.addEventListener("DOMContentLoaded", init);

/* Integration test: loads index.html + parser.js + app.js in jsdom,
 * stubs the chart library and the /api endpoints, verifies both charts render.
 * Run: node webpage/test_page.mjs
 */
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";

const html = readFileSync(new URL("./index.html", import.meta.url), "utf8");
const parserSrc = readFileSync(new URL("./parser.js", import.meta.url), "utf8");
const appSrc = readFileSync(new URL("./app.js", import.meta.url), "utf8");

const dom = new JSDOM(html, { runScripts: "outside-only", url: "http://127.0.0.1:8787/" });

const setDataCalls = [];
const priceLineCalls = [];
dom.window.LightweightCharts = {
  createChart: () => ({
    timeScale: () => ({ fitContent: () => {} }),
    addCandlestickSeries: () => ({
      setData: (d) => setDataCalls.push(d),
      createPriceLine: (o) => { priceLineCalls.push(o.price); return {}; },
      removePriceLine: () => {},
    }),
  }),
  LineStyle: { Dashed: 0 },
  CrosshairMode: { Normal: 0 },
};

dom.window.fetch = async (url) => {
  const code = url.startsWith("/api/") ? url.split("/api/")[1].toUpperCase() : null;
  if (!code) return { ok: false, status: 404 };
  return {
    ok: true,
    json: async () => ({
      code,
      month: "202608",
      prevClose: 25373,
      midPoint: 25168,
      updated: "14/08/2026 17:59",
      candles: [
        { time: 1786872600, open: 25191, high: 25237, low: 25160, close: 25186 },
        { time: 1786873500, open: 25186, high: 25215, low: 25118, close: 25199 },
      ],
    }),
  };
};

dom.window.eval(parserSrc);
// capture the DOMContentLoaded handler deterministically (jsdom also fires it natively)
dom.window.document.addEventListener = (type, fn) => {
  if (type === "DOMContentLoaded") dom.window.__init = fn;
};
dom.window.eval(appSrc);
dom.window.__init();  // run init once

await new Promise((r) => setTimeout(r, 100));

let ok = true;
try {
  if (setDataCalls.length !== 2) throw new Error(`expected 2 chart series updates, got ${setDataCalls.length}`);
  if (setDataCalls[0][0].time !== 1786872600) throw new Error("bad candle time");
  // mid line must use the session mid-point (not prev close)
  if (priceLineCalls.length !== 2 || priceLineCalls.some((p) => p !== 25168))
    throw new Error(`mid line not at session mid-point: ${priceLineCalls}`);
  const status = dom.window.document.getElementById("status").textContent;
  const metaHSI = dom.window.document.getElementById("meta-HSI").textContent;
  console.log("status:", status);
  console.log("meta-HSI:", metaHSI.replace(/\s+/g, " ").slice(0, 80));
  if (!status.includes("已更新")) throw new Error(`status not updated: ${status}`);
  if (!metaHSI.includes("2026/08")) throw new Error(`meta missing month: ${metaHSI}`);
  console.log("PAGE INTEGRATION TEST OK");
} catch (e) {
  ok = false;
  console.error("PAGE INTEGRATION TEST FAILED:", e.message);
}
dom.window.close();
process.exit(ok ? 0 : 1);

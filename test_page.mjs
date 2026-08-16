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

// Minimal etnet-like HTML fixture exercising the real proxy->parse path
const FIXTURE = `<!doctype html><html><body>
<select id="subtypelist"><option value="HSI|202608" selected>恒生指數期貨(08/2026)</option></select>
<div class="futures-home-session-card">
  <h3 class="futures-home-card-heading">恒生指數期貨(08/2026) <span class="label">日市</span></h3>
  <ul class="futures-home-quote-stats">
    <li class="futures-home-quote-stat"><span class="futures-home-quote-label">最高:</span><span class="futures-home-quote-value">25,283</span></li>
    <li class="futures-home-quote-stat"><span class="futures-home-quote-label">最低:</span><span class="futures-home-quote-value">25,053</span></li>
    <li class="futures-home-quote-stat"><span class="futures-home-quote-label">前收市:</span><span class="futures-home-quote-value">25,373</span></li>
  </ul>
</div>
<div class="et-swiper-table"><table><tbody>
  <tr><td>上日</td><td>25,333</td><td>25,513</td><td>25,266</td><td>25,373</td><td>-35<br/>(-0.138%)</td><td>-23.51</td><td>56,358</td><td>48,325</td><td>1.166</td></tr>
  <tr><td>今日</td><td>25,191</td><td>25,283</td><td>25,053</td><td>25,094</td><td>-279<br/>(-1.100%)</td><td>-23</td><td>65,108</td><td>54,696</td><td>1.190</td></tr>
  <tr><td>09:30</td><td>25,191</td><td>25,237</td><td>25,160</td><td>25,186</td><td>-187<br/>(-0.737%)</td><td>-33.15</td><td>3,945</td><td>3,015</td><td>1.308</td></tr>
</tbody></table></div>
</body></html>`;

const candleDataCalls = [];
const markersCalls = [];
const midLineCalls = [];
let customSeriesPlugin = null;
let areaSeriesCreated = false;
let standardCandlesCreated = false;
dom.window.LightweightCharts = {
  createChart: () => ({
    timeScale: () => ({ fitContent: () => {} }),
    addCustomSeries: (plugin, opts) => {
      customSeriesPlugin = plugin;
      return {
        setData: (d) => candleDataCalls.push(d),
        setMarkers: (m) => markersCalls.push(m),
      };
    },
    addCandlestickSeries: () => { standardCandlesCreated = true; return { setData() {} }; },
    addAreaSeries: () => { areaSeriesCreated = true; return { setData() {} }; },
    addLineSeries: () => ({
      setData: (d) => midLineCalls.push(d),
    }),
  }),
  LineStyle: { Dashed: 0, Solid: 0 },
  CrosshairMode: { Normal: 0 },
};

dom.window.fetch = async (url) => {
  const code = url.includes("subtype=HHI") || url.includes("%3Fsubtype%3DHHI") ? "HHI" : "HSI";
  const fixture = code === "HHI"
    ? FIXTURE.replaceAll("HSI", "HHI").replace("恒生指數期貨", "恒生中國企業指數期貨")
    : FIXTURE;
  return { ok: true, text: async () => fixture };
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
  if (standardCandlesCreated || areaSeriesCreated)
    throw new Error("standard candle/area series should NOT be created (custom thick-wick used)");
  if (!customSeriesPlugin || typeof customSeriesPlugin.renderer.draw !== "function")
    throw new Error("custom thick-wick candle series not registered");
  if (candleDataCalls.length !== 2) throw new Error(`expected 2 candle updates, got ${candleDataCalls.length}`);
  const c0 = candleDataCalls[0][0];
  if (!Number.isInteger(c0.time) || c0.time < 1e9) throw new Error(`bad time: ${c0.time}`);
  if (c0.open !== 25191 || c0.high !== 25237 || c0.low !== 25160 || c0.close !== 25186)
    throw new Error(`bad first candle: ${JSON.stringify(c0)}`);
  // big dots removed: no markers set
  if (markersCalls.length !== 0) throw new Error(`markers should be removed, got ${markersCalls.length}`);
  // mid line = running range midpoint (25237+25160)/2
  if (midLineCalls.length !== 2) throw new Error(`expected 2 mid-line updates, got ${midLineCalls.length}`);
  if (midLineCalls[0][0].value !== (25237 + 25160) / 2)
    throw new Error(`bad mid line: ${JSON.stringify(midLineCalls[0][0])}`);
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

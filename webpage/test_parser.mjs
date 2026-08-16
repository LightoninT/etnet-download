/* Node test: ETNetParser against a real etnet HTML fixture.
 * Run: node webpage/test_parser.mjs (jsdom required: npm i jsdom)
 */
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { JSDOM } from "jsdom";

const require = createRequire(import.meta.url);
global.DOMParser = new JSDOM().window.DOMParser;

// load parser.js like a browser script would
const parserSrc = readFileSync(new URL("./parser.js", import.meta.url), "utf8");
eval(parserSrc);

const html = readFileSync(process.argv[2] || "/tmp/cors_hsi.html", "utf8");

const page = global.ETNetParser.parsePage(html, "HSI");
console.log("code:", page.code, "| month:", page.month);
console.log("prevClose:", page.prevClose, "| updated:", page.updated);
console.log("candles:", page.candles.length);
console.log("first:", JSON.stringify(page.candles[0]));
console.log("last:", JSON.stringify(page.candles[page.candles.length - 1]));

// assertions mirroring the Python downloader results
if (page.month !== "202608") throw new Error("month mismatch");
if (page.prevClose !== 25373) throw new Error(`prevClose mismatch: ${page.prevClose}`);
if (page.candles.length < 20) throw new Error("too few candles");
const c0 = page.candles[0];
if (c0.open !== 25191 || c0.high !== 25237 || c0.low !== 25160 || c0.close !== 25186)
  throw new Error(`first candle mismatch: ${JSON.stringify(c0)}`);
if (!Number.isInteger(c0.time) || c0.time < 1e9) throw new Error(`bad time: ${c0.time}`);
console.log("PARSER TEST OK");

// ---- range band algorithm (expansion rules) ----
const { rangeBand } = global.ETNetParser;
// seed: high 100 low 80
const C = [
  { time: 1, high: 100, low: 80 },
  { time: 2, high: 95, low: 85 },  // inside range -> keep (100, 80)
  { time: 3, high: 110, low: 88 }, // new high     -> (110, 80)
  { time: 4, high: 105, low: 70 }, // new low      -> (110, 70)
  { time: 5, high: 120, low: 60 }, // breaks both  -> (120, 60)
  { time: 6, high: 118, low: 65 }, // inside range -> keep (120, 60)
];
const band = rangeBand(C);
const expected = [
  { time: 1, high: 100, low: 80 },
  { time: 2, high: 100, low: 80 },
  { time: 3, high: 110, low: 80 },
  { time: 4, high: 110, low: 70 },
  { time: 5, high: 120, low: 60 },
  { time: 6, high: 120, low: 60 },
];
band.forEach((b, i) => {
  if (b.high !== expected[i].high || b.low !== expected[i].low)
    throw new Error(`band rule ${i + 1} failed: got (${b.high},${b.low}), want (${expected[i].high},${expected[i].low})`);
});
console.log("RANGE BAND TEST OK:", JSON.stringify(band.map((b) => [b.high, b.low])));

// mid line = running range midpoint of the same band
const { candleMidLine, rangeMarkers } = global.ETNetParser;
const mids = candleMidLine(C);
const midExpected = [90, 90, 95, 90, 90, 90]; // (100+80)/2, keep, (110+80)/2, (110+70)/2, (120+60)/2, keep
mids.forEach((m, i) => {
  if (m.value !== midExpected[i])
    throw new Error(`mid ${i + 1} failed: got ${m.value}, want ${midExpected[i]}`);
});
console.log("MID LINE TEST OK:", JSON.stringify(mids.map((m) => m.value)));

// markers: big dots at new range highs (above) and new range lows (below)
const markers = rangeMarkers(C);
const markerSummary = markers.map((m) => `${m.time}:${m.position}`);
const wantSummary = ["1:aboveBar", "1:belowBar", "3:aboveBar", "4:belowBar", "5:aboveBar", "5:belowBar"];
if (JSON.stringify(markerSummary) !== JSON.stringify(wantSummary))
  throw new Error(`markers mismatch: ${markerSummary} want ${wantSummary}`);
if (markers.some((m) => m.shape !== "circle" || m.size < 4))
  throw new Error("markers must be big circles");
console.log("MARKERS TEST OK:", JSON.stringify(markerSummary));

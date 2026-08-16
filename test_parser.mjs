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

// ---- mid-line algorithm (4 rules) ----
const { candleMidLine } = global.ETNetParser;
// seed: high 100 low 80 -> mid 90
const C = [
  { time: 1, high: 100, low: 80 },
  { time: 2, high: 95, low: 85 },  // rule 1: inside range -> keep 90
  { time: 3, high: 110, low: 88 }, // rule 2: new high -> (110 + 80)/2 = 95
  { time: 4, high: 105, low: 70 }, // rule 3: new low  -> (110 + 70)/2 = 90
  { time: 5, high: 120, low: 60 }, // rule 4: both     -> (120 + 60)/2 = 90
  { time: 6, high: 118, low: 65 }, // rule 1 again     -> keep 90
];
const mids = candleMidLine(C);
const expected = [90, 90, 95, 90, 90, 90];
mids.forEach((m, i) => {
  if (m.value !== expected[i])
    throw new Error(`mid rule ${i + 1} failed: got ${m.value}, want ${expected[i]}`);
});
if (mids[2].time !== 3 || mids[2].value !== 95)
  throw new Error("rule 2 (new high) failed");
console.log("MID-LINE RULES TEST OK:", JSON.stringify(mids.map((m) => m.value)));

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
console.log("prevClose:", page.prevClose, "| midPoint:", page.midPoint, "| updated:", page.updated);
console.log("candles:", page.candles.length);
console.log("first:", JSON.stringify(page.candles[0]));
console.log("last:", JSON.stringify(page.candles[page.candles.length - 1]));

// assertions mirroring the Python downloader results
if (page.month !== "202608") throw new Error("month mismatch");
if (page.prevClose !== 25373) throw new Error(`prevClose mismatch: ${page.prevClose}`);
// session mid-point = (day session high 25283 + low 25053) / 2
if (page.midPoint !== 25168) throw new Error(`midPoint mismatch: ${page.midPoint}`);
if (page.candles.length < 20) throw new Error("too few candles");
const c0 = page.candles[0];
if (c0.open !== 25191 || c0.high !== 25237 || c0.low !== 25160 || c0.close !== 25186)
  throw new Error(`first candle mismatch: ${JSON.stringify(c0)}`);
if (!Number.isInteger(c0.time) || c0.time < 1e9) throw new Error(`bad time: ${c0.time}`);
console.log("PARSER TEST OK");

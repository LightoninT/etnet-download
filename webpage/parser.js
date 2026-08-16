/* ETNet futures page parser - standalone, testable in Node and browser.
 * Exposes window.ETNetParser / globalThis.ETNetParser.
 */
(function (global) {
  "use strict";

  function hktToday() {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Hong_Kong", year: "numeric", month: "2-digit", day: "2-digit",
    }).formatToParts(new Date());
    const get = (t) => parts.find((p) => p.type === t).value;
    return `${get("year")}-${get("month")}-${get("day")}`;
  }

  function toUnixSeconds(hktDate, hhmm) {
    const [h, m] = hhmm.split(":").map(Number);
    const [y, mo, d] = hktDate.split("-").map(Number);
    return Math.floor(Date.UTC(y, mo - 1, d, h, m) / 1000);
  }

  function cleanText(s) {
    return (s || "").replace(/\s+/g, " ").trim();
  }

  function toNum(s) {
    s = cleanText(s).replace(/,/g, "");
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : null;
  }

  function parsePage(html, code) {
    const doc = new global.DOMParser().parseFromString(html, "text/html");

    let month = "";
    const sel = doc.querySelector("select#subtypelist");
    if (sel) {
      const opt = sel.querySelector("option[selected]");
      if (opt) {
        const v = opt.value || "";
        const p = v.split("|");
        if (p[0] === code && p[1]) month = p[1];
      }
    }
    if (!month) throw new Error(`無法讀取 ${code} 合約月份`);

    let prevClose = null;
    let dayHigh = null;
    let dayLow = null;
    // session cards: 日市 / 夜市 quote stats
    for (const card of doc.querySelectorAll(".futures-home-session-card")) {
      const label = cleanText(card.querySelector(".label")?.textContent);
      const stats = {};
      for (const li of card.querySelectorAll("li.futures-home-quote-stat")) {
        const lab = cleanText(li.querySelector(".futures-home-quote-label")?.textContent);
        const val = toNum(li.querySelector(".futures-home-quote-value")?.textContent);
        if (lab) stats[lab] = val;
      }
      if (stats["前收市:"] != null && prevClose == null) prevClose = stats["前收市:"];
      if (label.includes("日市")) {
        dayHigh = stats["最高:"] ?? null;
        dayLow = stats["最低:"] ?? null;
      }
    }
    // session mid-point = (day session high + low) / 2
    const midPoint =
      dayHigh != null && dayLow != null ? (dayHigh + dayLow) / 2 : null;

    const candles = [];
    const tbody = doc.querySelector(".et-swiper-table table tbody");
    if (tbody) {
      for (const tr of tbody.querySelectorAll("tr")) {
        const tds = tr.querySelectorAll("td");
        if (tds.length < 10) continue;
        const time = cleanText(tds[0].textContent);
        if (time === "上日" || time === "今日") continue;
        const open = toNum(tds[1].textContent);
        const high = toNum(tds[2].textContent);
        const low = toNum(tds[3].textContent);
        const close = toNum(tds[4].textContent);
        if (open == null || high == null || low == null || close == null) continue;
        candles.push({
          time: toUnixSeconds(hktToday(), time),
          open, high, low, close,
        });
      }
    }

    const m = html.match(/即時更新[：:]\s*([\d/]+\s+[\d:]+)/);
    const updated = m ? m[1] : null;

    if (!candles.length) throw new Error(`${code}: 沒有 15 分鐘數據`);
    return { code, month, prevClose, midPoint, candles, updated };
  }

  global.ETNetParser = { parsePage, toUnixSeconds, hktToday, cleanText, toNum };
})(typeof window !== "undefined" ? window : globalThis);

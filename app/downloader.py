"""Fetch and parse HK index futures data from etnet.com.hk.

The official page https://www.etnet.com.hk/www/tc/futures/ is server-rendered.
A specific contract can be requested via query params
``?subtype=HSI&month=202608``.  This module downloads the HTML, parses it
with BeautifulSoup and returns structured, Excel-friendly data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .envconfig import SETTINGS

BASE_URL = SETTINGS["ETNET_FUTURES_URL"]
USER_AGENT = SETTINGS["USER_AGENT"]
TIMEOUT = int(float(SETTINGS["REQUEST_TIMEOUT"]))

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


def _num(text: str):
    """Convert a display string like '25,094' / '-279' / '(-1.10%)' to a
    number, or return the stripped string when it cannot be converted."""
    t = (text or "").strip()
    if not t:
        return ""
    sign = 1.0
    s = t
    if s.startswith(("+", "-")):
        if s.startswith("-"):
            sign = -1.0
        s = s[1:]
    # percentage: (-1.10%) -> -0.011
    m = re.fullmatch(r"\(([+\-]?[\d,\.]+)%\)", s)
    if m:
        try:
            return round(sign * float(m.group(1).replace(",", "")) / 100.0, 6)
        except ValueError:
            return t
    try:
        f = sign * float(s.replace(",", ""))
        if f == int(f):
            return int(f)
        return f
    except ValueError:
        return t


@dataclass
class SessionQuote:
    """One trading session quote card (日市 / 夜市)."""

    session: str = ""
    contract: str = ""
    last: object = ""
    change: object = ""
    change_pct: object = ""
    premium: str = ""
    high: object = ""
    low: object = ""
    prev_close: object = ""
    open: object = ""
    volume: object = ""
    trades: object = ""
    avg_trade: object = ""


@dataclass
class OpenInterest:
    contract: str = ""
    expiry: str = ""
    goi: object = ""
    noi: object = ""


@dataclass
class SpotQuote:
    name: str = ""
    last: object = ""
    change: object = ""
    change_pct: object = ""
    high: object = ""
    low: object = ""
    prev_close: object = ""
    open: object = ""


@dataclass
class IntervalRow:
    time: str = ""
    open: object = ""
    high: object = ""
    low: object = ""
    last: object = ""
    change: object = ""
    change_pct: object = ""
    premium: object = ""
    volume: object = ""
    trades: object = ""
    avg_trade: object = ""


@dataclass
class FuturesPage:
    subtype: str = ""
    month: str = ""
    contract_name: str = ""
    update_time: str = ""
    sessions: List[SessionQuote] = field(default_factory=list)
    open_interest: Optional[OpenInterest] = None
    spot: Optional[SpotQuote] = None
    interval: List[IntervalRow] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def fetch_html(subtype: str = "", month: str = "", timeout: int = TIMEOUT) -> str:
    """Download the futures page HTML (optionally for a specific contract)."""
    url = BASE_URL
    params = {}
    if subtype:
        params["subtype"] = subtype
    if month:
        params["month"] = month
    resp = requests.get(
        url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout
    )
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _text(node) -> str:
    return (node.get_text(" ", strip=True) if node is not None else "")


def parse_contract_options(soup: BeautifulSoup) -> List[tuple]:
    """Return [(code, month, label), ...] from the contract dropdown."""
    sel = soup.find("select", id="subtypelist")
    out = []
    if not sel:
        return out
    for opt in sel.find_all("option"):
        value = opt.get("value", "")
        if "|" not in value:
            continue
        code, month = value.split("|", 1)
        out.append((code, month, _text(opt)))
    return out


def _parse_stats(ul) -> dict:
    """Parse a <ul class="futures-home-quote-stats"> into {label: value}."""
    stats = {}
    if not ul:
        return stats
    for li in ul.find_all("li", recursive=False):
        label = _text(li.find(class_="futures-home-quote-label"))
        value = _text(li.find(class_="futures-home-quote-value"))
        if label:
            stats[label] = value
    return stats


def parse_session_card(card) -> Optional[SessionQuote]:
    """Parse one quote card (futures-home-session-card)."""
    heading = card.find(class_="futures-home-card-heading")
    heading_text = _text(heading) if heading else ""
    label_node = card.find(class_="label")
    session = _text(label_node) if label_node else ""
    # strip the trailing session label from the contract heading
    contract = heading_text
    if session and contract.endswith(session):
        contract = contract[: -len(session)].strip()

    nominal = _text(card.find(class_="futures-home-nominal"))
    change_items = [
        _text(x) for x in card.find_all(class_="futures-home-change-item")
    ]
    premium = ""
    if change_items:
        last_item = change_items[-1]
        if any(k in last_item for k in ("低水", "高水", "平水")):
            premium = last_item
            change_items = change_items[:-1]
    change = change_items[0] if len(change_items) > 0 else ""
    change_pct = change_items[1] if len(change_items) > 1 else ""

    stats = _parse_stats(card.find("ul", class_="futures-home-quote-stats"))
    return SessionQuote(
        session=session,
        contract=contract,
        last=_num(nominal),
        change=_num(change),
        change_pct=_num(change_pct),
        premium=premium,
        high=_num(stats.get("最高:", "")),
        low=_num(stats.get("最低:", "")),
        prev_close=_num(stats.get("前收市:", "")),
        open=_num(stats.get("開市:", "")),
        volume=_num(stats.get("成交張數:", "")),
        trades=_num(stats.get("交易宗數:", "")),
        avg_trade=_num(stats.get("每宗成交:", "")),
    )


def parse_open_interest(soup: BeautifulSoup) -> Optional[OpenInterest]:
    card = soup.find(class_="futures-home-open-interest-card")
    if not card:
        return None
    heading = _text(card.find(class_="futures-home-card-heading"))
    if heading == "未平倉":  # generic heading; actual contract comes from page
        heading = ""
    # expiry inside <span> (到期日︰28/08/2026)
    expiry = ""
    for sp in card.find_all("span"):
        t = _text(sp)
        if "到期日" in t:
            expiry = t
            break
    m = re.search(r"(\d{2}/\d{2}/\d{4})", expiry)
    if m:
        expiry = m.group(1)
    labels = {}
    for row in card.find_all(class_="futures-home-open-interest-data-row"):
        for item in row.find_all(class_="futures-home-data-item"):
            lab = _text(item.find(class_="futures-home-quote-label"))
            val = _text(item.find(class_="futures-home-quote-value"))
            if "總數" in lab:
                labels["goi"] = val
            elif "淨數" in lab:
                labels["noi"] = val
    return OpenInterest(
        contract=heading,
        expiry=expiry,
        goi=_num(labels.get("goi", "")),
        noi=_num(labels.get("noi", "")),
    )

def parse_spot(soup: BeautifulSoup) -> Optional[SpotQuote]:
    card = soup.find(class_="futures-home-spot-card")
    if not card:
        return None
    heading = _text(card.find(class_="futures-home-card-heading"))
    nominal = _text(card.find(class_="futures-home-nominal"))
    change_items = [_text(x) for x in card.find_all(class_="futures-home-change-item")]
    change = change_items[0] if change_items else ""
    change_pct = change_items[1] if len(change_items) > 1 else ""
    stats = _parse_stats(card.find("ul", class_="futures-home-quote-stats"))
    return SpotQuote(
        name=heading,
        last=_num(nominal),
        change=_num(change),
        change_pct=_num(change_pct),
        high=_num(stats.get("最高:", "")),
        low=_num(stats.get("最低:", "")),
        prev_close=_num(stats.get("前收市:", "")),
        open=_num(stats.get("開市:", "")),
    )


def parse_interval_table(soup: BeautifulSoup) -> List[IntervalRow]:
    """Parse the 15-minute interval table (et-swiper-table)."""
    rows: List[IntervalRow] = []
    table = soup.select_one(".et-swiper-table table")
    if not table:
        return rows
    tbody = table.find("tbody")
    if not tbody:
        return rows
    for tr in tbody.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(cells) < 10:
            continue
        time_v = cells[0]
        change_raw = cells[5]
        m = re.match(r"([^(\n]*)(?:\(([^)]*)\))?", change_raw)
        change = m.group(1).strip() if m else ""
        pct_raw = (m.group(2).strip() if m and m.group(2) else "").rstrip("%")
        rows.append(
            IntervalRow(
                time=time_v,
                open=_num(cells[1]),
                high=_num(cells[2]),
                low=_num(cells[3]),
                last=_num(cells[4]),
                change=_num(change),
                change_pct=_num(f"({pct_raw}%)") if pct_raw else "",
                premium=_num(cells[6]),
                volume=_num(cells[7]),
                trades=_num(cells[8]),
                avg_trade=_num(cells[9]),
            )
        )
    return rows


def parse_page(html: str) -> FuturesPage:
    """Parse the full futures page into a FuturesPage."""
    soup = BeautifulSoup(html, "html.parser")
    page = FuturesPage()

    # selected contract (from the select's selected option)
    sel = soup.find("select", id="subtypelist")
    if sel:
        selected = sel.find("option", selected=True)
        if selected:
            value = selected.get("value", "")
            if "|" in value:
                page.subtype, page.month = value.split("|", 1)
            page.contract_name = _text(selected)

    # update time: 「期貨之報價為即時更新： 15/08/2026 03:00」
    m = re.search(r"即時更新[：:]\s*([\d/]+\s+[\d:]+)", html)
    if m:
        page.update_time = m.group(1).strip()

    for card in soup.find_all(class_="futures-home-session-card"):
        q = parse_session_card(card)
        if q is not None and q.contract:
            page.sessions.append(q)

    page.open_interest = parse_open_interest(soup)
    page.spot = parse_spot(soup)
    page.interval = parse_interval_table(soup)
    return page


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def get_futures_page(subtype: str = "", month: str = "", timeout: int = TIMEOUT) -> FuturesPage:
    """Download and parse one futures page."""
    html = fetch_html(subtype, month, timeout=timeout)
    return parse_page(html)


def front_month_options(html: str) -> List[tuple]:
    """Return the front (nearest) contract option per product code.

    Returns [(code, month, label), ...] sorted by code.
    """
    soup = BeautifulSoup(html, "html.parser")
    options = parse_contract_options(soup)
    front: dict = {}
    for code, month, label in options:
        if code not in front or month < front[code][0]:
            front[code] = (month, label)
    return [(code, m, lab) for code, (m, lab) in sorted(front.items())]


def product_month_map(html: str) -> dict:
    """Map product code -> (display name, [months...]).

    Months are sorted; the first two are the current & next contract months.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: dict = {}
    for code, month, label in parse_contract_options(soup):
        if code not in out:
            name = re.sub(r"\(\d{2}/\d{4}\)", "", label).strip()
            out[code] = [name or code, []]
        if month not in out[code][1]:
            out[code][1].append(month)
    for code, (name, months) in out.items():
        out[code] = (name, sorted(months))
    return out

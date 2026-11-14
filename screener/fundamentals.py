"""Fundamentals aus den offiziellen SEC-Meldungen (EDGAR, kostenlos) + Earnings-Termine (Alpha Vantage, optional).

SEC verlangt einen User-Agent mit Name und E-Mail (SEC_USER_AGENT in .env).
Ergebnisse werden in data/fund/ zwischengespeichert.
"""
from __future__ import annotations

import io
import json
import os
import time
from datetime import datetime

import pandas as pd
import requests

REV_TAGS = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet"]
EPS_TAGS = ["EarningsPerShareDiluted", "EarningsPerShareBasic"]


class SEC:
    def __init__(self, folder: str, user_agent: str, cache_days: int = 3):
        self.dir = os.path.join(folder, "data", "fund")
        os.makedirs(self.dir, exist_ok=True)
        self.h = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self.cache_days = cache_days
        self._map = None

    def _get(self, url):
        for attempt in range(3):
            r = requests.get(url, headers=self.h, timeout=30)
            if r.status_code == 200:
                time.sleep(0.12)            # SEC-Limit: max. 10 Anfragen/Sekunde
                return r.json()
            if r.status_code == 404:
                return None
            time.sleep(1 + attempt)
        r.raise_for_status()

    def ticker_map(self) -> dict:
        if self._map is None:
            path = os.path.join(self.dir, "_tickers.json")
            if os.path.exists(path) and time.time() - os.path.getmtime(path) < 7 * 86400:
                with open(path) as fh:
                    self._map = json.load(fh)
            else:
                raw = self._get("https://www.sec.gov/files/company_tickers.json") or {}
                self._map = {v["ticker"].upper(): int(v["cik_str"]) for v in raw.values()}
                with open(path, "w") as fh:
                    json.dump(self._map, fh)
        return self._map

    def shares_map(self, progress=None) -> dict:
        """Aktienanzahl je Ticker für (fast) alle US-Firmen in wenigen Abrufen.

        Quelle: SEC 'frames' für dei:EntityCommonStockSharesOutstanding (Angabe auf dem Deckblatt
        jedes 10-Q/10-K/20-F). Pro Firma wird die jüngste Angabe der letzten 6 Quartale genommen.
        Cache 7 Tage."""
        path = os.path.join(self.dir, "_shares.json")
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < 7 * 86400:
            with open(path) as fh:
                return json.load(fh)
        today = pd.Timestamp.today()
        by_cik = {}
        for back in range(6):
            q = (today - pd.DateOffset(months=3 * back)).to_period("Q")
            frame = f"CY{q.year}Q{q.quarter}I"
            if progress:
                progress(f"Lade Aktienanzahl (SEC {frame})")
            data = self._get(f"https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/{frame}.json")
            for r in (data or {}).get("data", []):
                cik, end, val = int(r["cik"]), r.get("end", ""), float(r.get("val") or 0)
                if val > 0 and (cik not in by_cik or end > by_cik[cik][0]):
                    by_cik[cik] = (end, val)
        out = {}
        for ticker, cik in self.ticker_map().items():
            if cik in by_cik:
                out[ticker] = by_cik[cik][1]
            else:
                out.setdefault(ticker, None)
        out = {k: v for k, v in out.items() if v}
        # Tickermap enthält auch Firmen ohne Aktienangabe: als Aktie markieren, Kapitalisierung unbekannt
        known = {t: out.get(t) for t in self.ticker_map()}
        with open(path, "w") as fh:
            json.dump(known, fh)
        return known

    def summary(self, symbol: str) -> dict:
        path = os.path.join(self.dir, f"{symbol}.json")
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < self.cache_days * 86400:
            with open(path) as fh:
                return json.load(fh)
        cik = self.ticker_map().get(symbol.upper())
        if cik is None:
            out = {"symbol": symbol, "error": "nicht bei der SEC (z. B. ausländische Firma oder ETF)"}
        else:
            facts = self._get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json") or {}
            subs = self._get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json") or {}
            out = summarize(facts, symbol)
            out["industry"] = subs.get("sicDescription")
            out["name"] = subs.get("name") or facts.get("entityName")
        with open(path, "w") as fh:
            json.dump(out, fh)
        return out


def quarterly(gaap: dict, tags: list[str], unit: str) -> pd.Series | None:
    """Quartalswerte je Quartalsende. Q4 wird aus Geschäftsjahr minus Q1–Q3 abgeleitet, wenn nötig."""
    best = None
    for tag in tags:
        node = gaap.get(tag)
        if not node or unit not in node.get("units", {}):
            continue
        q, fy = {}, []
        for r in node["units"][unit]:
            if "start" not in r or "end" not in r:
                continue
            s, e = pd.Timestamp(r["start"]), pd.Timestamp(r["end"])
            days, filed = (e - s).days, r.get("filed", "")
            if 75 <= days <= 105:
                if e not in q or filed > q[e][1]:
                    q[e] = (float(r["val"]), filed)
            elif 340 <= days <= 380:
                fy.append((s, e, float(r["val"]), filed))
        for s, e, val, filed in fy:
            if e in q:
                continue
            inside = [v for k, v in q.items() if s < k < e]
            if len(inside) == 3:
                q[e] = (val - sum(x[0] for x in inside), filed)
        if not q:
            continue
        ser = pd.Series({k: v[0] for k, v in q.items()}).sort_index()
        if best is None or ser.index[-1] > best.index[-1]:
            best = ser
    return best


def _yoy_at(ser: pd.Series | None, end):
    if ser is None or end not in ser.index:
        return None
    val = ser[end]
    prior = ser[(ser.index >= end - pd.Timedelta(days=390)) & (ser.index <= end - pd.Timedelta(days=340))]
    if prior.empty:
        return None
    pv = prior.iloc[-1]
    if pv <= 0:
        return "turnaround" if val > 0 else None
    return round((val / pv - 1) * 100, 1)


def _yoy(ser: pd.Series | None, back: int = 0):
    if ser is None or len(ser) <= back:
        return None
    return _yoy_at(ser, ser.index[-1 - back])


def summarize(facts: dict, symbol: str) -> dict:
    gaap = facts.get("facts", {}).get("us-gaap", {})
    rev = quarterly(gaap, REV_TAGS, "USD")
    eps = quarterly(gaap, EPS_TAGS, "USD/shares")
    out = {"symbol": symbol, "rev_yoy": _yoy(rev), "rev_yoy_prev": _yoy(rev, 1),
           "eps_yoy": _yoy(eps), "eps_yoy_prev": _yoy(eps, 1),
           "last_quarter": str(rev.index[-1].date()) if rev is not None else None, "quarters": []}
    def num(x):
        return x if isinstance(x, (int, float)) else None
    a, b = num(out["rev_yoy"]), num(out["rev_yoy_prev"])
    out["rev_accel"] = bool(a > b) if a is not None and b is not None else None
    a, b = num(out["eps_yoy"]), num(out["eps_yoy_prev"])
    out["eps_accel"] = bool(a > b) if a is not None and b is not None else None
    if rev is not None:
        for k in range(min(6, len(rev))):
            end = rev.index[-1 - k]
            e = eps.get(end) if eps is not None else None
            out["quarters"].append({"end": str(end.date()), "revenue_m": round(rev.iloc[-1 - k] / 1e6, 1),
                                    "rev_yoy": _yoy(rev, k), "eps": round(float(e), 3) if e is not None else None,
                                    "eps_yoy": _yoy_at(eps, end)})
    return out


def earnings_calendar(folder: str, api_key: str) -> dict:
    """Nächster Earnings-Termin je Symbol (Alpha Vantage, 3 Monate voraus). Cache 12 h."""
    path = os.path.join(folder, "data", "fund", "_earnings.csv")
    if not (os.path.exists(path) and time.time() - os.path.getmtime(path) < 12 * 3600):
        r = requests.get("https://www.alphavantage.co/query",
                         params={"function": "EARNINGS_CALENDAR", "horizon": "3month", "apikey": api_key}, timeout=60)
        r.raise_for_status()
        if not r.text.startswith("symbol"):
            raise RuntimeError("Alpha Vantage: " + r.text[:200])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(r.text)
    cal = pd.read_csv(path)
    cal["reportDate"] = pd.to_datetime(cal["reportDate"], errors="coerce")
    today = pd.Timestamp(datetime.now().date())
    cal = cal[cal["reportDate"] >= today].sort_values("reportDate")
    return {s: str(d.date()) for s, d in cal.groupby("symbol")["reportDate"].first().items()}

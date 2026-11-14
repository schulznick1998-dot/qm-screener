"""Sektoren und Branchen für alle US-Aktien.

Quelle 1: Nasdaq-Screener (ein Abruf für alle Aktien an NYSE/NASDAQ/AMEX, kostenlos, ohne Schlüssel).
Quelle 2 (Rückfall): SEC-Branchencode (SIC) je Firma, langsamer, nur für liquide Aktien.
Cache: data/groups.json, 7 Tage.
"""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pandas as pd
import requests

SECTOR_DE = {
    "Technology": "Technologie", "Health Care": "Gesundheit", "Finance": "Finanzen",
    "Consumer Discretionary": "Zyklischer Konsum", "Consumer Staples": "Basiskonsum", "Industrials": "Industrie",
    "Energy": "Energie", "Utilities": "Versorger", "Real Estate": "Immobilien", "Basic Materials": "Grundstoffe",
    "Telecommunications": "Telekommunikation", "Miscellaneous": "Sonstige",
}


def sic_sector(sic: int) -> str:
    s = int(sic or 0)
    ranges = [
        (100, 999, "Grundstoffe"), (1000, 1299, "Grundstoffe"), (1300, 1399, "Energie"), (1400, 1499, "Grundstoffe"),
        (1500, 1799, "Industrie"), (2000, 2199, "Basiskonsum"), (2200, 2399, "Zyklischer Konsum"),
        (2400, 2699, "Grundstoffe"), (2700, 2799, "Zyklischer Konsum"), (2800, 2829, "Grundstoffe"),
        (2830, 2839, "Gesundheit"), (2840, 2899, "Grundstoffe"), (2900, 2999, "Energie"), (3000, 3399, "Grundstoffe"),
        (3400, 3569, "Industrie"), (3570, 3579, "Technologie"), (3580, 3599, "Industrie"), (3600, 3699, "Technologie"),
        (3710, 3716, "Zyklischer Konsum"), (3700, 3799, "Industrie"), (3800, 3839, "Technologie"),
        (3840, 3851, "Gesundheit"), (3852, 3899, "Technologie"), (3900, 3999, "Zyklischer Konsum"),
        (4000, 4799, "Industrie"), (4800, 4899, "Telekommunikation"), (4900, 4999, "Versorger"),
        (5000, 5199, "Industrie"), (5400, 5499, "Basiskonsum"), (5200, 5999, "Zyklischer Konsum"),
        (6000, 6499, "Finanzen"), (6500, 6799, "Immobilien"), (7370, 7379, "Technologie"),
        (7000, 7999, "Zyklischer Konsum"), (8000, 8099, "Gesundheit"), (8700, 8799, "Industrie"),
    ]
    for a, b, name in ranges:
        if a <= s <= b:
            return name
    return "Sonstige"


def _num(x):
    try:
        return float(str(x).replace("$", "").replace(",", "").strip() or "nan")
    except ValueError:
        return float("nan")


def from_nasdaq() -> dict:
    url = "https://api.nasdaq.com/api/screener/stocks"
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0 Safari/537.36", "Accept": "application/json, text/plain, */*",
         "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
    r = requests.get(url, params={"tableonly": "true", "limit": "25000", "download": "true"}, headers=h, timeout=60)
    r.raise_for_status()
    rows = (r.json().get("data") or {}).get("rows") or []
    out = {}
    for x in rows:
        sym = str(x.get("symbol", "")).strip().upper().replace("/", ".")
        sec = SECTOR_DE.get(str(x.get("sector") or "").strip())
        ind = str(x.get("industry") or "").strip()
        if not sym or not sec or not ind:
            continue
        out[sym] = {"sector": sec, "industry": ind, "mcap": _num(x.get("marketCap")), "last": _num(x.get("lastsale"))}
    if len(out) < 1000:
        raise RuntimeError(f"Nasdaq lieferte nur {len(out)} Einträge")
    return out


def from_sec(sec_client, symbols: list[str], progress=None) -> dict:
    out = {}
    tmap = sec_client.ticker_map()
    for k, s in enumerate(symbols):
        cik = tmap.get(s)
        if cik is None:
            continue
        if progress and k % 50 == 0:
            progress(f"Lade Branchen (SEC) {k}/{len(symbols)}")
        try:
            sub = sec_client._get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json") or {}
        except Exception:
            continue
        desc, sic = sub.get("sicDescription"), sub.get("sic")
        if desc and sic:
            out[s] = {"sector": sic_sector(int(sic)), "industry": str(desc).title(), "mcap": float("nan"), "last": float("nan")}
    return out


def load_groups(folder: str, sec_client=None, liquid_symbols: list[str] | None = None, progress=None) -> tuple[dict, str]:
    """Liefert ({symbol: {sector, industry, mcap, last}}, Quelle)."""
    path = os.path.join(folder, "data", "groups.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 7 * 86400:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d["groups"], d.get("source", "Cache")
    groups, source = {}, ""
    try:
        if progress:
            progress("Lade Sektoren und Branchen (Nasdaq)")
        groups, source = from_nasdaq(), "Nasdaq"
    except Exception as e:
        print("Nasdaq-Sektoren nicht erreichbar:", e)
        if sec_client is not None and liquid_symbols:
            groups, source = from_sec(sec_client, liquid_symbols, progress), "SEC (SIC-Code)"
    if groups:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"source": source, "groups": groups}, fh)
    return groups, source


def demo_groups(symbols) -> dict:
    rng = np.random.default_rng(7)
    tree = {"Technologie": ["Semiconductors", "Computer Software", "Computer Peripheral Equipment", "EDP Services"],
            "Gesundheit": ["Biotechnology", "Medical Specialities", "Major Pharmaceuticals"],
            "Finanzen": ["Major Banks", "Investment Managers", "Property-Casualty Insurers"],
            "Zyklischer Konsum": ["Restaurants", "Clothing/Shoe/Accessory Stores", "Auto Manufacturing"],
            "Industrie": ["Aerospace", "Industrial Machinery", "Trucking"],
            "Energie": ["Oil & Gas Production", "Integrated oil Companies"]}
    flat = [(s, i) for s, inds in tree.items() for i in inds]
    out = {}
    for k, sym in enumerate(sorted(symbols)):
        if sym in ("QQQ", "SPY", "DIA", "IWM"):
            continue
        s, i = flat[0] if k < 40 and k % 3 == 0 else flat[int(rng.integers(len(flat)))]
        out[sym] = {"sector": s, "industry": i, "mcap": float("nan"), "last": float("nan")}
    return out


# ---------------------------------------------------------------- Kennzahlen je Aktie und Gruppe
PERF = (("p1w", 5), ("p1m", 21), ("p3m", 63), ("p6m", 126))


def stock_table(df: pd.DataFrame, groups: dict, lm: pd.DataFrame | None = None,
                min_price: float = 3.0, min_dollar_vol: float = 1e6) -> pd.DataFrame:
    """Close-zu-Close-Performance wie TradingView + Breite (über SMA 50, nahe Hoch) für alle Aktien mit Sektor."""
    C = df.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    V = df.pivot_table(index="date", columns="symbol", values="volume", aggfunc="last").sort_index()
    H = df.pivot_table(index="date", columns="symbol", values="high", aggfunc="last").sort_index()
    syms = [s for s in C.columns if s in groups and pd.notna(C[s].iloc[-1])]
    C, V, H = C[syms], V[syms], H[syms]
    last = C.iloc[-1]
    t = pd.DataFrame(index=syms)
    t["close"] = last
    t["chg"] = (last / C.iloc[-2] - 1) * 100
    for k, n in PERF:
        t[k] = (last / C.iloc[-1 - n] - 1) * 100 if len(C) > n else np.nan
    t["dvol"] = (C * V).iloc[-20:].mean()
    t["above50"] = last > C.iloc[-50:].mean()
    t["from_high"] = (last / H.iloc[-252:].max() - 1) * 100
    t["sector"] = [groups[s]["sector"] for s in syms]
    t["industry"] = [groups[s]["industry"] for s in syms]
    if lm is not None:
        for col in ("rs_rating", "market_cap", "adr_pct", "rs_new_high"):
            if col in lm.columns:
                t[col] = lm[col].reindex(syms)
    t = t[(t["close"] >= min_price) & (t["dvol"] >= min_dollar_vol)]
    return t


def group_table(t: pd.DataFrame, key: str) -> pd.DataFrame:
    g = t.groupby(key)
    out = pd.DataFrame({
        "n": g.size(),
        **{k: g[k].median() for k, _ in PERF},
        "breadth50": g["above50"].mean() * 100,
        "near_high": g["from_high"].apply(lambda x: (x >= -10).mean() * 100),
    })
    if key == "industry":
        out["sector"] = g["sector"].agg(lambda x: x.mode().iat[0])
    out["rank_1m"] = out["p1m"].rank(ascending=False, method="min")
    big = out["n"] >= 5
    score = (out.loc[big, "p1w"].rank(pct=True) + out.loc[big, "p1m"].rank(pct=True)) / 2
    out["rank"] = score.rank(ascending=False, method="min")
    return out


def market_cards(df: pd.DataFrame, symbols=("QQQ", "SPY", "DIA", "IWM")) -> list[dict]:
    names = {"QQQ": "NASDAQ 100", "SPY": "S&P 500", "DIA": "Dow Jones", "IWM": "Russell 2000"}
    out = []
    for s in symbols:
        g = df[df["symbol"] == s].sort_values("date")
        if len(g) < 60:
            continue
        c = g["close"].reset_index(drop=True)
        last = c.iloc[-1]
        e21 = c.ewm(span=21, adjust=False).mean().iloc[-1]
        s50 = c.iloc[-50:].mean()
        s200 = c.iloc[-200:].mean() if len(c) >= 200 else np.nan
        out.append({"symbol": s, "name": names.get(s, s), "close": round(float(last), 2),
                    "p1w": round(float((last / c.iloc[-6] - 1) * 100), 2),
                    "p1m": round(float((last / c.iloc[-22] - 1) * 100), 2),
                    "ema21": bool(last > e21), "sma50": bool(last > s50),
                    "sma200": bool(last > s200) if pd.notna(s200) else None})
    return out

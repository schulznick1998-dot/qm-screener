"""Kursdaten: lokaler Cache + Download von Alpaca (oder Demo-Daten).

Der Cache liegt in data/daily.parquet. "Daten laden" holt die Historie komplett neu
(split-bereinigt wie TradingView), damit Splits nie zu falschen Kursen führen.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

NY = "America/New_York"
COLS = ["symbol", "date", "open", "high", "low", "close", "volume"]


def cache_path(folder: str) -> str:
    return os.path.join(folder, "data", "daily.parquet")


def load_cache(folder: str) -> pd.DataFrame | None:
    path = cache_path(folder)
    if not os.path.exists(path):
        return None
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _typed(df: pd.DataFrame) -> pd.DataFrame:
    """Zahlenspalten als Zahlen, Datum als Datum (Schutz gegen 'object'-Spalten nach concat)."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    for c in ("open", "high", "low", "close", "volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df


def save_cache(folder: str, df: pd.DataFrame):
    os.makedirs(os.path.join(folder, "data"), exist_ok=True)
    df[COLS].to_parquet(cache_path(folder), index=False)


# ---------------------------------------------------------------- Alpaca
def alpaca_universe(key: str, secret: str, exchanges, folder: str | None = None) -> list[str]:
    """Aktive US-Aktien direkt über die REST-Schnittstelle (robust gegen neue Börsenkürzel wie TXSE,
    die die alpaca-py-Bibliothek noch nicht kennt)."""
    import requests
    r = requests.get("https://paper-api.alpaca.markets/v2/assets",
                     params={"status": "active", "asset_class": "us_equity"},
                     headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, timeout=60)
    if r.status_code in (401, 403):
        raise RuntimeError("Alpaca lehnt die Schlüssel ab (401/403). Bitte ALPACA_KEY / ALPACA_SECRET prüfen.")
    r.raise_for_status()
    out = set()
    exmap = {}
    for a in r.json():
        ex = str(a.get("exchange", "")).upper()
        sym = str(a.get("symbol", ""))
        if not a.get("tradable") or not any(e in ex for e in exchanges):
            continue
        if not sym.isalpha():               # keine Vorzugsaktien/Units/Warrants wie BRK.B, XYZ/WS
            continue
        out.add(sym)
        exmap[sym] = ex
    if folder:
        try:
            import json
            os.makedirs(os.path.join(folder, "data"), exist_ok=True)
            with open(os.path.join(folder, "data", "exchanges.json"), "w", encoding="utf-8") as fh:
                json.dump(exmap, fh)
        except OSError:
            pass
    return sorted(out)


TV_PREFIX = {"NASDAQ": "NASDAQ", "NYSE": "NYSE", "ARCA": "AMEX", "AMEX": "AMEX", "BATS": "CBOE"}


def tv_symbol(folder: str, sym: str, _cache={}) -> str:
    """Symbol im TradingView-Format (BÖRSE:SYMBOL). Ohne bekannte Börse nur das Symbol."""
    path = os.path.join(folder, "data", "exchanges.json")
    try:
        mt = os.path.getmtime(path)
        if _cache.get("mt") != mt:
            import json
            with open(path, encoding="utf-8") as fh:
                _cache.update(mt=mt, map=json.load(fh))
    except OSError:
        _cache.setdefault("map", {})
    ex = TV_PREFIX.get(_cache.get("map", {}).get(sym, ""))
    return f"{ex}:{sym}" if ex else sym


LOGFILE = None   # wird von app.py gesetzt: data/ladezeiten.log


def log(msg: str):
    """Ladezeiten mitschreiben, damit langsame Schritte nachvollziehbar sind."""
    if not LOGFILE:
        return
    try:
        with open(LOGFILE, "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except OSError:
        pass


def alpaca_download(key: str, secret: str, symbols: list[str], history_days: int,
                    include_today_partial: bool, progress=None, start_date=None, label: str = "Lade Kurse",
                    chunk: int = 200) -> pd.DataFrame:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import Adjustment, DataFeed

    client = StockHistoricalDataClient(key, secret)
    now = datetime.now(timezone.utc)
    end = now - timedelta(minutes=16)       # kostenloses Konto: SIP-Daten erst nach 15 Min.
    start = now - timedelta(days=history_days) if start_date is None else pd.Timestamp(start_date).tz_localize(timezone.utc).to_pydatetime()
    frames = []
    t0 = time.time()
    slow = []
    for k in range(0, len(symbols), chunk):
        part = symbols[k:k + chunk]
        if progress:
            el = time.time() - t0
            rate = f" · {k / el:.0f} Aktien/s" if el > 5 and k else ""
            progress(f"{label} {k}/{len(symbols)}{rate}")
        req = StockBarsRequest(symbol_or_symbols=part, timeframe=TimeFrame.Day, start=start, end=end,
                               adjustment=Adjustment.SPLIT, feed=DataFeed.SIP)
        try:
            t1 = time.time()
            bars = client.get_stock_bars(req).df
            dt = time.time() - t1
            if dt > 10:
                slow.append(f"{k}:{dt:.0f}s")
        except Exception as e:
            msg = str(e)
            if "subscription" in msg.lower() or "403" in msg:
                raise RuntimeError("Alpaca verweigert SIP-Daten. Prüfe Key und Konto (Market Data, kostenloser Plan reicht).") from e
            raise
        if bars.empty:
            continue
        bars = bars.reset_index()
        bars["date"] = pd.to_datetime(bars["timestamp"]).dt.tz_convert(NY).dt.tz_localize(None).dt.normalize()
        frames.append(bars[COLS])
    log(f"{label}: {len(symbols)} Symbole in {time.time() - t0:.0f} s, {-(-len(symbols) // chunk)} Abfragen à {chunk}"
        + (f", langsame Abfragen: {', '.join(slow[:10])}" if slow else ""))
    if not frames:
        if start_date is not None:
            return pd.DataFrame(columns=COLS)
        raise RuntimeError("Keine Kursdaten erhalten.")
    df = pd.concat(frames, ignore_index=True)
    if not include_today_partial:
        ny_now = pd.Timestamp.now(tz=NY)
        today = ny_now.tz_localize(None).normalize()
        market_open_today = ny_now.hour * 60 + ny_now.minute < 16 * 60 + 15
        if market_open_today:
            df = df[df["date"] < today]
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


# ---------------------------------------------------------------- Vorbörse
def alpaca_premarket(key: str, secret: str, symbols: list[str], progress=None) -> dict:
    """Vorbörse heute (4:00–9:30 New York): letzter Kurs, Hoch und Volumen je Aktie.
    15-Minuten-Kerzen über SIP; kostenloses Konto = 15 Minuten verzögert."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.data.enums import Adjustment, DataFeed

    ny_now = pd.Timestamp.now(tz=NY)
    start = ny_now.normalize() + pd.Timedelta(hours=4)
    end = min(pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=16), ny_now.normalize() + pd.Timedelta(hours=9, minutes=30))
    if end <= start:
        return {}
    client = StockHistoricalDataClient(key, secret)
    out: dict = {}
    chunk = 200
    for k in range(0, len(symbols), chunk):
        part = symbols[k:k + chunk]
        if progress:
            progress(f"Lade Vorbörse {k}/{len(symbols)}")
        req = StockBarsRequest(symbol_or_symbols=part, timeframe=TimeFrame(15, TimeFrameUnit.Minute),
                               start=start.to_pydatetime(), end=end.to_pydatetime(),
                               adjustment=Adjustment.SPLIT, feed=DataFeed.SIP)
        bars = client.get_stock_bars(req).df
        # gestriger Schluss direkt von Alpaca (unabhängig davon, wie aktuell die gespeicherten Tageskurse sind)
        try:
            dreq = StockBarsRequest(symbol_or_symbols=part, timeframe=TimeFrame.Day,
                                    start=(ny_now.normalize() - pd.Timedelta(days=10)).to_pydatetime(),
                                    end=ny_now.normalize().to_pydatetime(), adjustment=Adjustment.SPLIT, feed=DataFeed.SIP)
            db = client.get_stock_bars(dreq).df.reset_index()
            db["d"] = pd.to_datetime(db["timestamp"]).dt.tz_convert(NY).dt.normalize()
            db = db[db["d"] < ny_now.normalize()].sort_values("d")
            prevc = db.groupby("symbol")["close"].last().to_dict()
        except Exception:
            prevc = {}
        if bars.empty:
            continue
        bars = bars.reset_index()
        bars["t"] = pd.to_datetime(bars["timestamp"]).dt.tz_convert(NY)
        bars = bars[bars["t"] < ny_now.normalize() + pd.Timedelta(hours=9, minutes=30)].sort_values("t")
        for sym, g in bars.groupby("symbol"):
            out[sym] = {"pm_price": float(g["close"].iloc[-1]), "pm_high": float(g["high"].max()),
                        "prev_close": float(prevc[sym]) if sym in prevc else None,
                        "pm_vol": float(g["volume"].sum()), "pm_time": g["t"].iloc[-1].strftime("%H:%M")}
    return out


# ---------------------------------------------------------------- Demo
def demo_shares(df: pd.DataFrame) -> dict:
    """Erfundene Aktienanzahl für den Demo-Modus (ETF-Benchmarks ausgenommen)."""
    rng = np.random.default_rng(1)
    return {s: float(rng.uniform(2e7, 8e8)) for s in df["symbol"].unique() if s not in ("QQQ", "SPY", "DIA", "IWM")}


def demo_data(n_symbols: int = 400, days: int = 330, seed: int = 3) -> pd.DataFrame:
    """Synthetische Kurse mit eingebauten Setups am letzten Tag. Nur zum Ausprobieren der Oberfläche."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=days)
    rows = []
    names = [f"DM{k:03d}" for k in range(n_symbols)]
    for k, sym in enumerate(names):
        r = rng.normal(0.0005, 0.022, days)
        vs = np.ones(days)
        vol = np.ones(days)
        if k < 40:                                  # Momentum-Aktien
            run, base = int(rng.integers(10, 18)), int(rng.integers(12, 34))
            s = days - run - base
            r[s:s + run] = rng.uniform(0.02, 0.035) + rng.normal(0, 0.008, run)
            vol[s:s + run] = 1.8
            u = np.arange(1, base + 1) / base
            depth = rng.uniform(0.08, 0.18)
            path = np.concatenate([[1.0], 1 - depth * np.exp(-1.3 * u) * np.abs(np.sin(rng.integers(2, 4) * np.pi * u))])
            r[s + run:] = path[1:] / path[:-1] - 1 + rng.normal(0, 0.003, base)
            loose = k % 4 == 3                      # einige absichtlich nicht eng
            vs[s + run:] = 1.0 if loose else 1 - 0.75 * u
            vol[s + run:] = 1.1 if loose else 1.1 - 0.7 * u
        if 40 <= k < 46:                            # Episodic Pivots am letzten Tag
            r[-1] = rng.uniform(0.12, 0.25)
            vol[-1] = rng.uniform(4, 8)
        c = 30 * np.exp(np.cumsum(r)) * rng.uniform(0.5, 4)
        o = np.concatenate([[c[0]], c[:-1]]) * (1 + rng.normal(0, 0.004, days))
        if 40 <= k < 46:
            o[-1] = c[-2] * (1 + r[-1] * 0.8)
        spread = np.abs(rng.normal(0.025, 0.01, days)) * vs + 0.004
        h = np.maximum(o, c) * (1 + spread * rng.uniform(0.2, 0.8, days))
        l = np.minimum(o, c) * (1 - spread * rng.uniform(0.2, 0.8, days))
        v = rng.uniform(5e5, 4e6) * vol * rng.uniform(0.7, 1.3, days)
        rows.append(pd.DataFrame({"symbol": sym, "date": dates, "open": o, "high": h, "low": l, "close": c, "volume": v}))
    q = 400 * np.exp(np.cumsum(rng.normal(0.0012, 0.008, days)))
    rows.append(pd.DataFrame({"symbol": "QQQ", "date": dates, "open": q, "high": q * 1.006, "low": q * 0.994, "close": q, "volume": 4e7}))
    spy = 550 * np.exp(np.cumsum(rng.normal(0.0008, 0.007, days)))
    rows.append(pd.DataFrame({"symbol": "SPY", "date": dates, "open": spy, "high": spy * 1.005, "low": spy * 0.995, "close": spy, "volume": 7e7}))
    for sym, base, mu, sd in (("DIA", 420, 0.0006, 0.007), ("IWM", 210, -0.0002, 0.011)):
        x = base * np.exp(np.cumsum(rng.normal(mu, sd, days)))
        rows.append(pd.DataFrame({"symbol": sym, "date": dates, "open": x, "high": x * 1.006, "low": x * 0.994, "close": x, "volume": 3e7}))
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------- Nachladen statt Komplett-Download
FULL_MARK = "last_full.txt"


def needs_full(folder: str, cache: pd.DataFrame | None, max_age_days: int = 7) -> str | None:
    """Grund für einen Komplett-Download oder None."""
    if cache is None or cache.empty:
        return "kein Cache"
    mark = os.path.join(folder, "data", FULL_MARK)
    if not os.path.exists(mark):
        return "erster Lauf mit Nachladen"
    age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(mark))).days
    if age >= max_age_days:
        return f"wöchentlicher Komplett-Abgleich ({age} Tage)"
    if (pd.Timestamp.now().normalize() - cache["date"].max()).days > 30:
        return "Daten älter als 30 Tage"
    return None


def mark_full(folder: str):
    os.makedirs(os.path.join(folder, "data"), exist_ok=True)
    with open(os.path.join(folder, "data", FULL_MARK), "w") as fh:
        fh.write(datetime.now().isoformat())


def alpaca_update(key: str, secret: str, symbols: list[str], cache: pd.DataFrame, history_days: int,
                  include_today_partial: bool, progress=None, overlap_days: int = 7, tol: float = 0.005):
    """Lädt nur die letzten Tage nach. Aktien mit Split (Kurse der Überlappung weichen ab) und neue Aktien
    werden komplett neu geladen. Gibt (DataFrame, Info-Text) zurück."""
    last = cache["date"].max()
    start = (last - pd.Timedelta(days=overlap_days)).normalize()
    fresh = alpaca_download(key, secret, symbols, history_days, include_today_partial, progress,
                            start_date=start, label="Lade neue Tage", chunk=1000)
    known = set(cache["symbol"].unique())
    # Split-Erkennung über die überlappenden Tage. Der letzte gespeicherte Tag zählt nicht mit:
    # er kann eine laufende Tageskerze (Kurs mitten am Tag) sein und weicht dann natürlich ab.
    # Ein echter Split verschiebt ALLE alten Kurse, darum müssen mind. 2 Tage abweichen.
    ov = fresh[fresh["date"] < last].merge(cache[(cache["date"] >= start) & (cache["date"] < last)][["symbol", "date", "close"]],
                                           on=["symbol", "date"], suffixes=("", "_old"))
    ov["bad"] = (ov["close"] / ov["close_old"] - 1).abs() > tol
    agg = ov.groupby("symbol")["bad"].agg(["sum", "count"])
    changed = set(agg[(agg["sum"] >= 2) & (agg["sum"] >= 0.6 * agg["count"])].index)
    new_syms = sorted(set(fresh["symbol"]) - known)
    reload = sorted(changed | set(new_syms))
    full = pd.DataFrame(columns=COLS)
    if reload:
        full = alpaca_download(key, secret, reload, history_days, include_today_partial, progress,
                               label="Lade komplette Historie (Split/neu)")
    keep = cache[~cache["symbol"].isin(reload) & (cache["date"] < start)]
    upd = fresh[~fresh["symbol"].isin(reload)]
    parts = [x[COLS] for x in (keep, upd, full) if len(x)]   # leere Tabellen nicht anhängen (würden Zahlen zu Objekten machen)
    df = _typed(pd.concat(parts, ignore_index=True))
    df = df[df["symbol"].isin(set(symbols))]
    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=history_days)
    df = df[df["date"] >= cutoff].drop_duplicates(["symbol", "date"], keep="last")
    info = f"nachgeladen ab {start.date()}, {len(changed)} Split(s), {len(new_syms)} neue Aktie(n)"
    log("Nachladen: " + info + (f" · Splits z. B. {', '.join(sorted(changed)[:15])}" if changed else "")
        + (f" · neu z. B. {', '.join(new_syms[:15])}" if new_syms else ""))
    return df.sort_values(["symbol", "date"]).reset_index(drop=True), info

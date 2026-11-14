"""Trading-Journal: holt ausgeführte Trades über den IBKR Flex Web Service und fasst sie zu Trades zusammen.

Einrichtung bei IBKR (Client Portal → Performance & Berichte → Flex Queries):
  1. Kontoumsatz-Flex-Query mit Abschnitt „Trades“ (alle Felder), Format XML, Zeitraum z. B. 365 Tage
  2. optional Handelsbestätigungs-Flex-Query (Abschnitt „Handelsbestätigung“), Format XML
     – liefert die Trades schon am selben Tag, die Kontoumsatz-Query erst am nächsten Morgen
  3. Flex Web Service aktivieren und Token erzeugen
Token und Query-IDs werden in der .env im Programmordner gespeichert (nie in Git).

Dateien (gehören dem Nutzer, kommen nie in Git):
  data/journal_exec.json   alle einzelnen Ausführungen (Kauf/Verkauf), Schlüssel = IBKR-Trade-ID
  journal.json             deine Einträge je Trade: Stop, Setup, Notiz, Fehler; Startdatum
  Journal/<Datum_Symbol>/  Chartbild und Notiz je Trade (Knopf „Chartbild speichern“)
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FLEX_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/SendRequest"
UA = "QM-Screener-Journal/1.0"
DEFAULT_START = "2026-11-11"


# ───────────────────────── Abruf ─────────────────────────
def _ctx():
    """SSL mit den Zertifikaten von certifi (auf dem Mac fehlen Python sonst oft die Root-Zertifikate)."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        tok = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("t", [""])[0]
        raise RuntimeError(f"Verbindung zu IBKR fehlgeschlagen: {str(e).replace(tok, '***') if tok else e}") from None


def fetch_flex(token: str, query_id: str, tries: int = 12, wait: float = 5.0) -> str:
    """Flex-Bericht holen: erst anfordern (Referenzcode), dann abholen. IBKR braucht oft ein paar Sekunden."""
    q = urllib.parse.urlencode({"t": token, "q": query_id, "v": "3"})
    for attempt in range(4):
        root = ET.fromstring(_get(f"{FLEX_URL}?{q}"))
        if (root.findtext("ErrorCode") or "").strip() != "1018":
            break
        time.sleep(10 + attempt * 5)          # 1018 = zu viele Anfragen kurz hintereinander
    if (root.findtext("Status") or "").strip() != "Success":
        code = root.findtext("ErrorCode") or "?"
        msg = root.findtext("ErrorMessage") or "unbekannter Fehler"
        raise RuntimeError(f"IBKR lehnt die Anfrage ab (Query {query_id}, Fehler {code}): {msg}")
    ref = root.findtext("ReferenceCode")
    base = root.findtext("Url")
    last = ""
    for _ in range(tries):
        txt = _get(f"{base}?{urllib.parse.urlencode({'t': token, 'q': ref, 'v': '3'})}", timeout=60)
        if "<FlexQueryResponse" in txt:
            return txt
        last = txt
        # 1019 = Bericht wird noch erstellt, 1018 = zu viele Anfragen
        time.sleep(wait)
    try:
        r2 = ET.fromstring(last)
        raise RuntimeError(f"IBKR: {r2.findtext('ErrorMessage') or 'Bericht nicht fertig geworden'} (Query {query_id})")
    except ET.ParseError:
        raise RuntimeError(f"IBKR hat keinen Bericht geliefert (Query {query_id}). Später nochmal versuchen.")


# ───────────────────────── Auswerten ─────────────────────────
def _num(v, default=0.0):
    try:
        return float(str(v).replace(",", "")) if v not in (None, "") else default
    except ValueError:
        return default


def _dt(a: dict) -> str:
    """IBKR liefert Zeiten je nach Einstellung als 20261111;101523, 2026-11-11;10:15:23 usw. → 2026-11-11 10:15:23"""
    raw = a.get("dateTime") or a.get("tradeDate") or ""
    d = re.sub(r"\D", "", raw)
    if len(d) < 8:
        return ""
    s = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
    if len(d) >= 12:
        s += f" {d[8:10]}:{d[10:12]}:{d[12:14] or '00'}"
    return s


def parse_flex(xml_text: str) -> list[dict]:
    """Einzelne Ausführungen aus Kontoumsatz (<Trade>) und Handelsbestätigung (<TradeConfirm>)."""
    root = ET.fromstring(xml_text)
    out = []
    for el in list(root.iter("Trade")) + list(root.iter("TradeConfirm")):
        a = el.attrib
        lvl = (a.get("levelOfDetail") or "EXECUTION").upper()
        if lvl not in ("EXECUTION", ""):
            continue                      # Sammelzeilen (ORDER, CLOSED_LOT …) überspringen
        sym = (a.get("symbol") or "").strip()
        if not sym:
            continue
        if (a.get("assetCategory") or "") == "CASH":
            continue                      # Devisentausch (z. B. EUR → USD) ist kein Trade
        side = (a.get("buySell") or "").upper()
        qty = abs(_num(a.get("quantity")))
        if qty == 0:
            continue
        if side.startswith("SELL"):
            sq = -qty
        elif side.startswith("BUY"):
            sq = qty
        else:
            sq = _num(a.get("quantity"))
        tid = a.get("tradeID") or a.get("execID") or a.get("transactionID") or \
            f"{sym}-{_dt(a)}-{sq}-{a.get('tradePrice') or a.get('price')}"
        fee = _num(a.get("ibCommission"), None)
        if fee is None:
            fee = _num(a.get("commission"))
        out.append({
            "id": str(tid), "symbol": sym, "under": (a.get("underlyingSymbol") or "").strip(), "asset": a.get("assetCategory") or "STK",
            "time": _dt(a), "qty": sq, "price": _num(a.get("tradePrice") or a.get("price")),
            "fee": fee, "currency": a.get("currency") or "USD",
            "fx": _num(a.get("fxRateToBase"), 0.0) or None, "account": a.get("accountId") or "",
            "order_type": a.get("orderType") or "",
        })
    return out


# ───────────────────────── Speichern ─────────────────────────
def _load(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _save(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def exec_path(folder):
    return os.path.join(folder, "data", "journal_exec.json")


def meta_path(folder):
    return os.path.join(folder, "journal.json")


def load_meta(folder) -> dict:
    m = _load(meta_path(folder), None)
    if m is None:                      # erster Start: Journal beginnt heute
        m = {"start": time.strftime("%Y-%m-%d"), "trades": {}}
        try:
            save_meta(folder, m)
        except OSError:
            pass
    m.setdefault("start", DEFAULT_START)
    m.setdefault("trades", {})
    return m


def save_meta(folder, m):
    _save(meta_path(folder), m)


def merge_execs(folder, new: list[dict]) -> int:
    cur = {e["id"]: e for e in _load(exec_path(folder), [])}
    before = len(cur)
    for e in new:
        cur[e["id"]] = {**cur.get(e["id"], {}), **e}
    _save(exec_path(folder), sorted(cur.values(), key=lambda e: e["time"]))
    return len(cur) - before


def fetch_all(folder, env: dict) -> dict:
    _log(folder, "Abruf gestartet")
    tok = env.get("IBKR_FLEX_TOKEN")
    qs = [q for q in (env.get("IBKR_FLEX_QUERY"), env.get("IBKR_FLEX_QUERY_TODAY")) if q]
    if not tok or not qs:
        raise RuntimeError("IBKR ist noch nicht verbunden: Token und mindestens eine Query-ID unter „IBKR verbinden“ eintragen.")
    got, errs = [], []
    for q in qs:
        try:
            got += parse_flex(fetch_flex(tok, q))
        except Exception as e:                       # eine Query darf scheitern, die andere zählt trotzdem
            errs.append(str(e)[:200])
    _log(folder, f"Abruf: {len(got)} Ausführungen, Fehler: {errs or 'keine'}")
    if not got and errs:
        raise RuntimeError(" · ".join(errs))
    added = merge_execs(folder, got)
    m = load_meta(folder)
    m["last_fetch"] = time.strftime("%Y-%m-%d %H:%M")
    save_meta(folder, m)
    return {"received": len(got), "new": added, "warnings": errs}


def _log(folder, msg):
    try:
        with open(os.path.join(folder, "data", "journal.log"), "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def intraday_stop(folder, env, symbol: str, entry_time: str, side: str):
    """Tagestief (Long) bzw. Tageshoch (Short) von Handelsbeginn bis zur Einstiegsminute, aus 1-Minuten-Kerzen
    von Alpaca. Das ist der Stop „am Tagestief“, so wie er beim Kauf im Markt lag. Ergebnis wird zwischengespeichert."""
    if not entry_time or len(entry_time) < 16:
        return None
    cpath = os.path.join(folder, "data", "journal_lod.json")
    cache = _load(cpath, {})
    key = f"{symbol}|{entry_time}|{side}"
    if key in cache:
        return cache[key]
    if not (env and env.get("ALPACA_KEY") and env.get("ALPACA_SECRET")):
        return None
    try:
        import pandas as pd
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import Adjustment, DataFeed
        t = pd.Timestamp(entry_time).tz_localize("America/New_York")
        day = t.normalize()
        start = day + pd.Timedelta(hours=9, minutes=30)
        if t < start:
            start = day + pd.Timedelta(hours=4)          # Einstieg vorbörslich
        end = t + pd.Timedelta(minutes=1)
        now_lim = pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=16)
        if end.tz_convert("UTC") > now_lim:
            end = now_lim.tz_convert("America/New_York")
        if end <= start:
            return None
        cl = StockHistoricalDataClient(env["ALPACA_KEY"], env["ALPACA_SECRET"])
        req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Minute, start=start.to_pydatetime(),
                               end=end.to_pydatetime(), adjustment=Adjustment.SPLIT, feed=DataFeed.SIP)
        b = cl.get_stock_bars(req).df
        if b.empty:
            return None
        v = float(b["low"].min()) if side == "long" else float(b["high"].max())
    except Exception as e:
        _log(folder, f"Intraday-Stop {symbol} {entry_time}: {str(e)[:150]}")
        return None
    cache[key] = round(v, 4)
    _save(cpath, cache)
    return cache[key]


def base_symbol(e: dict) -> str:
    """Kurs-Symbol für den Chart: bei CFDs das Basis-Symbol (IBKR schreibt z. B. FROGn statt FROG)."""
    s = e.get("under") or e["symbol"]
    if e.get("asset") == "CFD" and not e.get("under") and len(s) > 1 and s.endswith("n"):
        s = s[:-1]
    return s.replace(" ", ".")


# ───────────────────────── Trades bilden ─────────────────────────
def build(folder, df=None, env=None) -> dict:
    meta = load_meta(folder)
    start = meta["start"]
    ex = [e for e in _load(exec_path(folder), []) if e["time"][:10] >= start and e.get("asset") != "CASH"]
    for e in ex:
        e["symbol"] = base_symbol(e)
    ex.sort(key=lambda e: (e["time"], e["id"]))
    last_close, day_low = {}, {}
    if df is not None:
        syms = {e["symbol"] for e in ex}
        sub = df[df["symbol"].isin(syms)]
        for s, g in sub.groupby("symbol"):
            g = g.sort_values("date")
            last_close[s] = float(g["close"].iloc[-1])
            day_low[s] = {str(d.date()): (float(lo), float(hi)) for d, lo, hi in zip(g["date"], g["low"], g["high"])}

    trades, pos = [], {}
    for e in ex:
        key = (e["symbol"], e["asset"])
        t = pos.get(key)
        if t is None:
            t = {"symbol": e["symbol"], "asset": e["asset"], "currency": e["currency"], "side": "long" if e["qty"] > 0 else "short",
                 "execs": [], "open": 0.0}
            pos[key] = t
        t["execs"].append(e)
        t["open"] += e["qty"]
        if abs(t["open"]) < 1e-9:
            trades.append(t)
            del pos[key]
    trades += list(pos.values())          # noch offene Positionen

    out = []
    for t in trades:
        xs = t["execs"]
        sign = 1 if t["side"] == "long" else -1
        opens = [x for x in xs if x["qty"] * sign > 0]
        closes = [x for x in xs if x["qty"] * sign < 0]
        oq = sum(abs(x["qty"]) for x in opens)
        cq = sum(abs(x["qty"]) for x in closes)
        entry = sum(abs(x["qty"]) * x["price"] for x in opens) / oq if oq else None
        exitp = sum(abs(x["qty"]) * x["price"] for x in closes) / cq if cq else None
        fees = sum(x["fee"] for x in xs)                       # IBKR: Gebühren negativ
        cash = sum(-x["qty"] * x["price"] for x in xs)         # Verkäufe +, Käufe −
        is_open = abs(t["open"]) > 1e-9
        tid = f"{xs[0]['time'][:10]}_{t['symbol']}_{xs[0]['id']}"
        m = meta["trades"].get(tid, {})
        last = last_close.get(t["symbol"])
        if is_open:
            pnl = cash + t["open"] * last + fees if last else None
        else:
            pnl = cash + fees
        fx = next((x["fx"] for x in reversed(xs) if x.get("fx")), None)
        d0 = xs[0]["time"][:10]
        lo_hi = day_low.get(t["symbol"], {}).get(d0)
        stop_hint = (lo_hi[0] if sign > 0 else lo_hi[1]) if lo_hi else None
        hint_src = "Tages" + ("tief" if sign > 0 else "hoch") if stop_hint is not None else None
        first_open = opens[0]["time"] if opens else xs[0]["time"]
        iv = intraday_stop(folder, env, t["symbol"], first_open, t["side"])
        if iv is not None:
            stop_hint, hint_src = iv, ("Tief" if sign > 0 else "Hoch") + " bis Einstieg " + first_open[11:16]
        mode = m.get("stop_mode") or ("manual" if m.get("stop") else "lod")
        stop = stop_hint if mode == "lod" else m.get("stop")
        risk = abs(entry - stop) * oq if (stop and entry) else None
        r_mult = pnl / risk if (risk and pnl is not None) else None
        d1 = (xs[-1]["time"][:10] if not is_open else time.strftime("%Y-%m-%d"))
        try:
            days = (time.mktime(time.strptime(d1, "%Y-%m-%d")) - time.mktime(time.strptime(d0, "%Y-%m-%d"))) / 86400
        except ValueError:
            days = None
        out.append({
            "id": tid, "symbol": t["symbol"], "asset": t["asset"], "currency": t["currency"], "side": t["side"],
            "open": is_open, "qty": oq, "qty_open": abs(t["open"]), "entry": entry, "exit": exitp,
            "first": xs[0]["time"], "last": xs[-1]["time"], "days": round(days) if days is not None else None,
            "fees": fees, "pnl": pnl, "pnl_base": pnl * fx if (pnl is not None and fx) else None,
            "last_close": last, "stop": stop, "stop_hint": stop_hint, "hint_src": hint_src, "stop_mode": mode, "stop_manual": m.get("stop"), "r": r_mult,
            "risk": risk, "setup": m.get("setup", ""), "note": m.get("note", ""), "mistake": m.get("mistake", ""),
            "execs": [{"time": x["time"], "qty": x["qty"], "price": x["price"]} for x in xs],
        })
    out.sort(key=lambda x: x["first"], reverse=True)
    return {"trades": out, "stats": stats(out), "start": start, "last_fetch": meta.get("last_fetch")}


def _block(ts):
    closed = [t for t in ts if not t["open"] and t["pnl"] is not None]
    win = [t for t in closed if t["pnl"] > 0]
    loss = [t for t in closed if t["pnl"] <= 0]
    rs = [t["r"] for t in closed if t["r"] is not None]
    rw = [t["r"] for t in win if t["r"] is not None]
    rl = [t["r"] for t in loss if t["r"] is not None]
    avg = lambda a: sum(a) / len(a) if a else None
    return {
        "closed": len(closed), "open": sum(1 for t in ts if t["open"]),
        "winrate": len(win) / len(closed) * 100 if closed else None,
        "pnl": sum(t["pnl"] for t in closed),
        "pnl_base": sum(t["pnl_base"] for t in closed) if closed and all(t["pnl_base"] is not None for t in closed) else None,
        "r_sum": sum(rs) if rs else None, "r_avg": avg(rs), "r_win": avg(rw), "r_loss": avg(rl),
        "r_missing": sum(1 for t in closed if t["r"] is None),
        "best": max(rs) if rs else None, "worst": min(rs) if rs else None,
        "days_win": avg([t["days"] for t in win if t["days"] is not None]),
        "days_loss": avg([t["days"] for t in loss if t["days"] is not None]),
    }


def stats(ts) -> dict:
    by = {}
    for t in ts:
        by.setdefault(t["setup"] or "ohne Setup", []).append(t)
    return {"all": _block(ts), "by_setup": {k: _block(v) for k, v in sorted(by.items())}}


def set_trade(folder, tid: str, fields: dict):
    m = load_meta(folder)
    cur = m["trades"].get(tid, {})
    if fields.get("stop_mode") in ("lod", "manual"):
        cur["stop_mode"] = fields["stop_mode"]
    for k in ("stop", "setup", "note", "mistake"):
        if k in fields:
            v = fields[k]
            if k == "stop":
                try:
                    v = round(float(v), 4) if v not in (None, "") else None
                except (TypeError, ValueError):
                    continue
            else:
                v = str(v or "")[:1000]
            cur[k] = v
    m["trades"][tid] = cur
    save_meta(folder, m)


def trade_folder(folder, tid: str) -> str:
    date, sym = tid.split("_")[0], tid.split("_")[1]
    p = os.path.join(folder, "Journal", f"{date}_{re.sub(r'[^A-Za-z0-9.-]', '', sym)}")
    os.makedirs(p, exist_ok=True)
    return p

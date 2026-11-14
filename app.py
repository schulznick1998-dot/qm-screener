"""QM Screener – lokaler Qullamaggie-Breakout-Scanner.

Start:   python app.py            (öffnet den Browser auf http://127.0.0.1:8765)
Demo:    python app.py --demo     (synthetische Daten, ohne Schlüssel)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import threading
import time
import traceback
import webbrowser

import pandas as pd
import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from screener import data as D
from screener.env import load_env, missing_message
from screener.fundamentals import SEC, earnings_calendar
from screener.params import PRESETS, Params, SETTINGS_META, load_params, save_settings
from screener.scan import chart_payload, check_rows, run_scan
from screener import scan as S
from screener import groups as G
from screener import themes as TH
from screener import journal as J
from screener.env import save_values
from screener import update as UPD

HERE = os.path.dirname(os.path.abspath(__file__))
app = FastAPI()
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")

STATE = {"scan_no": 0, "running": False, "message": "bereit", "error": None, "result": None, "scanned_at": None, "demo": False}
DF: dict = {"df": None, "shares": None}
LOCK = threading.Lock()


D.LOGFILE = os.path.join(HERE, "data", "ladezeiten.log")
_T = {"t": 0.0, "last": ""}


def _msg(m: str):
    # Schrittwechsel mit Dauer protokollieren (data/ladezeiten.log), Fortschritt je Paket nicht
    words = []
    for w in m.split(" "):
        if any(ch.isdigit() for ch in w):
            break
        words.append(w)
    step = words[:4]
    if " ".join(step) != _T["last"]:
        now = time.time()
        if _T["last"]:
            D.log(f"  {_T['last']} … {now - _T['t']:.0f} s")
        _T.update(t=now, last=" ".join(step))
    STATE["message"] = m


def _job(download: bool, scan: bool = True):
    D.log(f"=== Start: {('Daten laden + scannen' if scan else 'nur Daten laden') if download else 'nur scannen'}")
    _T.update(t=time.time(), last="")
    try:
        p = load_params(HERE)
        env = load_env(HERE)
        if STATE["demo"]:
            _msg("Erzeuge Demo-Daten")
            DF["df"] = D.demo_data()
        elif download:
            if not env.get("ALPACA_KEY") or not env.get("ALPACA_SECRET"):
                raise RuntimeError(missing_message(HERE))
            _msg("Lade Aktienliste von Alpaca")
            syms = D.alpaca_universe(env["ALPACA_KEY"], env["ALPACA_SECRET"], p.exchanges, HERE)
            for b in (p.benchmark, p.rs_benchmark, "QQQ", "SPY", "DIA", "IWM", *TH.theme_etfs()):
                if b not in syms:
                    syms.append(b)
            cache = DF["df"] if DF["df"] is not None else D.load_cache(HERE)
            why = D.needs_full(HERE, cache)
            if why is None:
                try:
                    df, info = D.alpaca_update(env["ALPACA_KEY"], env["ALPACA_SECRET"], syms, cache, p.history_days,
                                               p.include_today_partial, progress=_msg)
                    print("Kurse", info)
                except Exception:
                    traceback.print_exc()
                    why = "Nachladen fehlgeschlagen"
            if why is not None:
                print("Komplett-Download:", why)
                df = D.alpaca_download(env["ALPACA_KEY"], env["ALPACA_SECRET"], syms, p.history_days,
                                       p.include_today_partial, progress=_msg)
                D.mark_full(HERE)
            _msg("Speichere Cache")
            D.save_cache(HERE, df)
            DF["df"] = df
            if not scan:
                last = DF["df"]["date"].max()
                _msg(f"Kurse geladen bis {last:%d.%m.%Y}. Scannen mit „Nur neu scannen“ oder Scan wählen")
                D.log(f"=== fertig (nur Daten, bis {last:%Y-%m-%d})")
                return
        elif DF["df"] is None:
            DF["df"] = D.load_cache(HERE)
            if DF["df"] is None:
                raise RuntimeError("Noch keine Daten. Bitte zuerst 'Daten laden + scannen'.")
        if STATE["demo"]:
            DF["shares"] = D.demo_shares(DF["df"])
        elif env.get("SEC_USER_AGENT"):
            try:
                DF["shares"] = SEC(HERE, env["SEC_USER_AGENT"]).shares_map(progress=_msg)
            except Exception as e:
                traceback.print_exc()
                DF["shares"] = None
        # Sektoren/Branchen (+ Marktkapitalisierung als Ersatz, wo die SEC keine Aktienanzahl hat)
        groups, gsource = {}, ""
        try:
            if STATE["demo"]:
                groups, gsource = G.demo_groups(DF["df"]["symbol"].unique()), "Demo"
            else:
                last = DF["df"].sort_values("date").groupby("symbol").tail(20)
                dv = (last["close"] * last["volume"]).groupby(last["symbol"]).mean()
                liquid = sorted(dv[dv >= 5e6].index)
                sec_c = SEC(HERE, env["SEC_USER_AGENT"]) if env.get("SEC_USER_AGENT") else None
                groups, gsource = G.load_groups(HERE, sec_c, liquid, progress=_msg)
        except Exception:
            traceback.print_exc()
        if groups and DF["shares"] is not None and not STATE["demo"]:
            added = 0
            for sym, g in groups.items():
                if not DF["shares"].get(sym) and g.get("mcap") and g.get("last") and g["mcap"] > 0 and g["last"] > 0:
                    DF["shares"][sym] = g["mcap"] / g["last"]
                    added += 1
        pm, pm_note = None, None
        if (p.min_pm_gap_pct > 0 or p.min_pm_volume > 0) and not STATE["demo"]:
            if not env.get("ALPACA_KEY"):
                raise RuntimeError(missing_message(HERE))
            # Erst alle übrigen Filter (Kurs, Volumen, Marktkap., SMA 50 …) anwenden, dann nur für diese
            # Kandidaten die Vorbörse laden. Das spart bei strengen Vorlagen 90 % der Abfragen.
            _msg("Prüfe Tagesfilter vor der Vorbörse")
            from dataclasses import replace as _replace
            p0 = _replace(p, min_pm_gap_pct=0.0, min_pm_volume=0.0, min_price=p.min_price * 0.8)
            lm0 = S.last_metrics(DF["df"], p0, DF["shares"], p.rs_benchmark)
            pre = sorted(lm0.index[lm0["eligible"].fillna(False).astype(bool)])
            _msg(f"Lade Vorbörse für {len(pre)} Kandidaten")
            try:
                pm = D.alpaca_premarket(env["ALPACA_KEY"], env["ALPACA_SECRET"], pre, progress=_msg)
            except Exception as e:
                traceback.print_exc()
                pm, pm_note = {}, f"Vorbörse nicht geladen: {str(e)[:140]}"
            if not pm and not pm_note:
                pm_note = "Keine Vorbörsenkurse für heute (vor 10:15 Uhr, Wochenende oder Feiertag?)."
            last_day = DF["df"]["date"].max()
            today_ny = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
            if (today_ny - last_day).days > 4:
                pm_note = (pm_note + " · " if pm_note else "") + "Tageskurse veraltet: „Daten laden + scannen“ nutzen, sonst stimmt der Bezug „gestriger Schluss“ nicht."
        _msg("Scanne")
        keep = {}
        res = run_scan(DF["df"], p, progress=_msg, shares=DF["shares"], keep=keep, groups=groups, pm=pm)
        if pm_note:
            res["notes"].append(pm_note)
        tmap = {}
        try:
            t_all = G.stock_table(DF["df"], groups, keep.get("lm")) if groups else None
            th_rows, tmap = TH.theme_table(DF["df"], groups, t_all)
            STATE["themes"] = {"themes": th_rows, "last_date": res["last_date"]}
        except Exception:
            traceback.print_exc()
            STATE["themes"] = None
        for r in res["rows"]:
            r["themes"] = tmap.get(r["symbol"], [])
        if groups:
            try:
                t = G.stock_table(DF["df"], groups, keep.get("lm"))
                sec_t, ind_t = G.group_table(t, "sector"), G.group_table(t, "industry")
                def recs(frame, idx):
                    fr = frame.reset_index().rename(columns={"index": idx})
                    return json.loads(fr.to_json(orient="records", double_precision=2))
                stocks = t.reset_index().rename(columns={"index": "symbol"})
                stocks["market_cap_m"] = stocks.get("market_cap", pd.Series(dtype=float)) / 1e6
                cols = [c for c in ("symbol", "sector", "industry", "close", "chg", "p1w", "p1m", "p3m", "p6m", "from_high",
                                    "rs_rating", "market_cap_m", "adr_pct", "rs_new_high", "above50") if c in stocks.columns]
                stocks["themes"] = [tmap.get(x, []) for x in stocks["symbol"]]
                cols.append("themes")
                STATE["groups"] = {"source": gsource, "market": G.market_cards(DF["df"]),
                                   "sectors": recs(sec_t, "sector"), "industries": recs(ind_t, "industry"),
                                   "stocks": json.loads(stocks[cols].to_json(orient="records", double_precision=2)),
                                   "last_date": res["last_date"]}
            except Exception:
                traceback.print_exc()
                STATE["groups"] = None
        else:
            STATE["groups"] = None
            if not STATE["demo"]:
                res["notes"].append("Sektoren/Branchen nicht geladen (Nasdaq nicht erreichbar und kein SEC_USER_AGENT).")
        n_caps = sum(1 for v in (DF["shares"] or {}).values() if v)
        if DF["shares"] is not None and not STATE["demo"] and n_caps < 2000:
            res["notes"].append(f"Marktkapitalisierung nur für {n_caps} Firmen gefunden (erwartet: mehrere Tausend).")

        # Fundamentals: zuerst Setups, dann übrige Kandidaten nach Abstand zum Pivot
        if not STATE["demo"] and env.get("SEC_USER_AGENT"):
            sec = SEC(HERE, env["SEC_USER_AGENT"], p.fundamentals_cache_days)
            order = sorted(res["rows"], key=lambda r: (not r["setup"], abs(r.get("to_pivot_pct") or 99)))
            for k, r in enumerate(order[:p.fundamentals_max]):
                _msg(f"Fundamentals {k + 1}/{min(len(order), p.fundamentals_max)}: {r['symbol']}")
                try:
                    r["fund"] = sec.summary(r["symbol"])
                except Exception as e:
                    r["fund"] = {"error": str(e)[:120]}
        elif not STATE["demo"]:
            res["notes"].append("Fundamentals aus: SEC_USER_AGENT in .env eintragen.")
        if p.min_rev_yoy > 0 or p.require_rev_accel:
            def _ok(r):
                f = r.get("fund") or {}
                y = f.get("rev_yoy")
                if p.min_rev_yoy > 0 and not (isinstance(y, (int, float)) and y >= p.min_rev_yoy):
                    return False
                return not p.require_rev_accel or bool(f.get("rev_accel"))
            before = len(res["rows"])
            res["rows"] = [r for r in res["rows"] if _ok(r)]
            res["after_filters"] = len(res["rows"])
            res["setups"] = sum(1 for r in res["rows"] if r.get("setup"))
            if before > p.fundamentals_max:
                res["notes"].append(f"Umsatzfilter: nur die ersten {p.fundamentals_max} von {before} Kandidaten geprüft "
                                    f"(Einstellungen → Fundamentals laden für).")
            if STATE["demo"]:
                res["notes"].append("Demo-Modus hat keine Fundamentals, der Umsatzfilter lässt deshalb nichts durch.")
        if not STATE["demo"] and env.get("ALPHAVANTAGE_KEY"):
            try:
                _msg("Lade Earnings-Termine")
                cal = earnings_calendar(HERE, env["ALPHAVANTAGE_KEY"])
                today = pd.Timestamp.now().normalize()
                for r in res["rows"]:
                    d = cal.get(r["symbol"])
                    r["earnings"] = d
                    r["earnings_days"] = int((pd.Timestamp(d) - today).days) if d else None
            except Exception as e:
                res.setdefault("notes", []).append(f"Earnings-Termine nicht geladen: {str(e)[:120]}")
        res["params"] = p.to_dict()
        STATE["result"] = res
        STATE["scanned_at"] = time.strftime("%d.%m.%Y %H:%M")
        STATE["scan_no"] += 1
        _msg(f"fertig: {res['setups']} Setups, {res['after_filters']} Kandidaten")
        D.log(f"=== fertig ({res['after_filters']} Kandidaten)")
    except Exception as e:
        traceback.print_exc()
        STATE["error"] = str(e)
        _msg("Fehler")
    finally:
        STATE["running"] = False


@app.post("/api/scan")
def start_scan(download: bool = Query(False), scan: bool = Query(True)):
    with LOCK:
        if STATE["running"]:
            return {"ok": False, "message": "läuft bereits"}
        STATE.update(running=True, error=None, message="startet")
    threading.Thread(target=_job, args=(download, scan), daemon=True).start()
    return {"ok": True}


@app.get("/api/status")
def status():
    cache = D.cache_path(HERE)
    return {"running": STATE["running"], "message": STATE["message"], "error": STATE["error"],
            "scanned_at": STATE["scanned_at"], "scan_no": STATE["scan_no"], "demo": STATE["demo"],
            "has_cache": os.path.exists(cache) or STATE["demo"]}


@app.get("/api/result")
def result():
    return JSONResponse(STATE["result"] or {})


@app.get("/api/groups")
def get_groups():
    return JSONResponse(STATE.get("groups") or {"error": "Noch kein Scan mit Sektordaten. Bitte scannen."})


@app.get("/api/themes")
def get_themes():
    return JSONResponse(STATE.get("themes") or {"error": "Noch kein Scan. Bitte scannen."})


@app.post("/api/tvlist")
async def tv_list(request: Request):
    """TradingView-Watchlist als .txt: ###Abschnitt,BÖRSE:SYM,…  (in TradingView: Watchlist → Liste importieren)."""
    body = await request.json()
    parts = []
    for sec in body.get("sections", []):
        syms = [D.tv_symbol(HERE, str(x).upper()) for x in sec.get("symbols", []) if str(x).strip()]
        if not syms:
            continue
        title = str(sec.get("title", "Liste")).replace(",", " ").replace("#", "").strip()[:40] or "Liste"
        parts.append("###" + title)
        parts.extend(dict.fromkeys(syms))
    name = "".join(ch for ch in str(body.get("name", "qm_liste")) if ch.isalnum() or ch in "-_ ").strip() or "qm_liste"
    return StreamingResponse(iter([",".join(parts)]), media_type="text/plain; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}.txt"'})


@app.get("/api/chart/{symbol}")
def chart(symbol: str):
    if DF["df"] is None:
        return JSONResponse({"error": "keine Daten"}, status_code=404)
    return JSONResponse(chart_payload(DF["df"], symbol.upper(), load_params(HERE)))


@app.get("/api/export.csv")
def export_csv(symbols: str = ""):
    """Prüfmodus: ohne Parameter alle Kandidaten, mit ?symbols=AAPL,NVDA genau diese Aktien."""
    p = load_params(HERE)
    if symbols:
        out = check_rows(DF["df"], [s.strip().upper() for s in symbols.split(",") if s.strip()], p, DF["shares"])
    else:
        rows = (STATE["result"] or {}).get("rows", [])
        out = pd.DataFrame([{k: (", ".join(v) if k == "fails" else v) for k, v in r.items() if k not in ("fund",)} for r in rows])
    buf = io.StringIO()
    out.to_csv(buf, index=False, sep=";", decimal=",")
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=qm_scan.csv"})


@app.get("/api/settings")
def get_settings():
    try:
        cur = load_params(HERE).to_dict()
        err = None
    except Exception as e:
        cur, err = Params().to_dict(), str(e)
    meta = [{"key": k, "group": g, "label": l, "unit": u, "factor": f, "step": st, "help": h} for k, g, l, u, f, st, h in SETTINGS_META]
    presets = {}
    for k, pr in PRESETS.items():
        vals = Params().to_dict()
        vals.update(pr["values"])
        presets[k] = {"label": pr["label"], "desc": pr["desc"], "values": vals, "archived": bool(pr.get("archived")),
                      "explain": [{"t": t, "x": x} for t, x in pr.get("explain", [])]}
    names = {f for f in Params().to_dict()}
    for name, sc in _my_scans().items():
        vals = Params().to_dict()
        vals.update({k: v for k, v in sc.get("values", {}).items() if k in names})
        presets["my:" + name] = {"label": name, "desc": sc.get("desc", ""), "values": vals, "own": True,
                                 "explain": [{"t": "Eigener Scan", "x": sc.get("desc", "")}]}
    return {"defaults": Params().to_dict(), "current": cur, "meta": meta, "presets": presets, "error": err}


FOKUS = os.path.join(HERE, "fokusliste.json")


def _fokus() -> dict:
    try:
        with open(FOKUS, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _fokus_save(d: dict):
    with open(FOKUS, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2, ensure_ascii=False)


@app.get("/api/fokus")
def get_fokus():
    d = _fokus()
    out = []
    df = DF["df"]
    last = {}
    if df is not None and d:
        sub = df[df["symbol"].isin(list(d))].sort_values("date")
        for sym, g in sub.groupby("symbol"):
            g = g.tail(21)
            c = float(g["close"].iloc[-1])
            prev = float(g["close"].iloc[-2]) if len(g) > 1 else c
            adr = float(((g["high"] / g["low"]).iloc[-20:].mean() - 1) * 100) if len(g) >= 20 else None
            last[sym] = {"close": round(c, 2), "chg_pct": round((c / prev - 1) * 100, 2),
                         "adr_pct": round(adr, 2) if adr else None, "low": round(float(g["low"].iloc[-1]), 2),
                         "date": str(g["date"].iloc[-1].date())}
    for sym, e in d.items():
        r = {"symbol": sym, **e, **last.get(sym, {})}
        c, pv, st = r.get("close"), e.get("pivot"), e.get("stop")
        if c and pv:
            r["to_pivot_pct"] = round((pv / c - 1) * 100, 2)
        if pv and st and pv > st:
            r["risk_pct"] = round((pv - st) / pv * 100, 2)
            if r.get("adr_pct"):
                r["risk_adr"] = round(r["risk_pct"] / r["adr_pct"], 2)
        out.append(r)
    out.sort(key=lambda x: x.get("added", ""), reverse=True)
    return {"items": out}


@app.post("/api/fokus")
async def set_fokus(request: Request):
    body = await request.json()
    sym = str(body.get("symbol", "")).strip().upper()
    if not sym:
        return JSONResponse({"ok": False, "error": "Symbol fehlt"}, status_code=400)
    d = _fokus()
    e = d.get(sym, {"added": time.strftime("%Y-%m-%d"), "src": str(body.get("src", ""))[:40]})
    for k in ("pivot", "stop"):
        if k in body:
            try:
                e[k] = round(float(body[k]), 4) if body[k] not in (None, "") else None
            except (TypeError, ValueError):
                pass
    if "note" in body:
        e["note"] = str(body["note"] or "")[:300]
    d[sym] = e
    _fokus_save(d)
    return {"ok": True}


@app.delete("/api/fokus")
def clear_fokus():
    """Ganze Fokusliste leeren. Vorher Sicherung in fokus_archiv/fokusliste_DATUM.json."""
    d = _fokus()
    saved = None
    if d:
        arch = os.path.join(HERE, "fokus_archiv")
        os.makedirs(arch, exist_ok=True)
        saved = os.path.join(arch, f"fokusliste_{time.strftime('%Y-%m-%d_%H%M')}.json")
        with open(saved, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=2, ensure_ascii=False)
    _fokus_save({})
    return {"ok": True, "removed": len(d), "saved": os.path.relpath(saved, HERE) if saved else None}


@app.delete("/api/fokus/{sym}")
def del_fokus(sym: str):
    d = _fokus()
    d.pop(sym.upper(), None)
    _fokus_save(d)
    return {"ok": True}


MYSCANS = os.path.join(HERE, "eigene_scans.json")


def _my_scans() -> dict:
    try:
        with open(MYSCANS, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


@app.post("/api/myscans")
async def save_my_scan(request: Request):
    body = await request.json()
    name = str(body.get("name", "")).strip()[:40]
    if not name:
        return JSONResponse({"ok": False, "error": "Bitte einen Namen eingeben."}, status_code=400)
    d = _my_scans()
    d[name] = {"desc": str(body.get("desc", ""))[:400], "values": body.get("values", {})}
    with open(MYSCANS, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2, ensure_ascii=False)
    return {"ok": True}


@app.delete("/api/myscans/{name}")
def delete_my_scan(name: str):
    d = _my_scans()
    d.pop(name, None)
    with open(MYSCANS, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2, ensure_ascii=False)
    return {"ok": True}


@app.post("/api/settings")
async def post_settings(request: Request):
    body = await request.json()
    try:
        save_settings(HERE, body.get("values", {}))
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    return {"ok": True}


# ───────────────────────── Journal (IBKR Flex) ─────────────────────────
@app.get("/api/journal")
def journal_get():
    env = load_env(HERE)
    res = J.build(HERE, DF["df"], env)
    res["configured"] = {"token": bool(env.get("IBKR_FLEX_TOKEN")), "query": env.get("IBKR_FLEX_QUERY") or "",
                         "query_today": env.get("IBKR_FLEX_QUERY_TODAY") or ""}
    return JSONResponse(res)


@app.post("/api/journal/fetch")
def journal_fetch():
    try:
        r = J.fetch_all(HERE, load_env(HERE))
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)[:400]}, status_code=400)
    return {"ok": True, **r}


@app.post("/api/journal/config")
async def journal_config(request: Request):
    b = await request.json()
    upd = {}
    tok = str(b.get("token") or "").strip()
    if tok:
        if not tok.isalnum() or len(tok) < 10:
            return JSONResponse({"ok": False, "error": "Der Token sieht nicht richtig aus (nur Ziffern/Buchstaben, mind. 10 Zeichen)."}, status_code=400)
        upd["IBKR_FLEX_TOKEN"] = tok
    for k, key in (("query", "IBKR_FLEX_QUERY"), ("query_today", "IBKR_FLEX_QUERY_TODAY")):
        v = str(b.get(k) or "").strip()
        if v:
            if not v.isdigit():
                return JSONResponse({"ok": False, "error": "Query-IDs bestehen nur aus Ziffern."}, status_code=400)
            upd[key] = v
    if not upd:
        return JSONResponse({"ok": False, "error": "Nichts eingetragen."}, status_code=400)
    save_values(HERE, upd)
    return {"ok": True}


@app.post("/api/journal/start")
async def journal_start(request: Request):
    b = await request.json()
    d = str(b.get("start") or "")
    if not (len(d) == 10 and d[4] == "-" and d[7] == "-"):
        return JSONResponse({"ok": False, "error": "Datum im Format JJJJ-MM-TT"}, status_code=400)
    m = J.load_meta(HERE)
    m["start"] = d
    J.save_meta(HERE, m)
    return {"ok": True}


@app.post("/api/journal/trade")
async def journal_trade(request: Request):
    b = await request.json()
    tid = str(b.get("id") or "")
    if not tid:
        return JSONResponse({"ok": False, "error": "id fehlt"}, status_code=400)
    J.set_trade(HERE, tid, b)
    return {"ok": True}


@app.post("/api/journal/snapshot")
async def journal_snapshot(request: Request):
    """Chartbild (PNG als data-URL) und Notiz in Journal/<Datum_Symbol>/ ablegen."""
    import base64
    b = await request.json()
    tid = str(b.get("id") or "")
    img = str(b.get("png") or "")
    if not tid or not img.startswith("data:image/png;base64,"):
        return JSONResponse({"ok": False, "error": "Bild fehlt"}, status_code=400)
    p = J.trade_folder(HERE, tid)
    with open(os.path.join(p, "chart.png"), "wb") as fh:
        fh.write(base64.b64decode(img.split(",", 1)[1]))
    with open(os.path.join(p, "trade.md"), "w", encoding="utf-8") as fh:
        fh.write(str(b.get("md") or ""))
    return {"ok": True, "folder": os.path.relpath(p, HERE)}


# ───────────────────────── Einrichtung (Schlüssel) ─────────────────────────
@app.get("/api/setup")
def setup_get():
    env = load_env(HERE)
    ua = env.get("SEC_USER_AGENT", "")
    parts = ua.rsplit(" ", 1) if "@" in ua else [ua, ""]
    return {"alpaca": bool(env.get("ALPACA_KEY") and env.get("ALPACA_SECRET")), "sec": bool(ua),
            "name": parts[0] if len(parts) == 2 else ua, "email": parts[1] if len(parts) == 2 else "",
            "alphavantage": bool(env.get("ALPHAVANTAGE_KEY")), "ibkr": bool(env.get("IBKR_FLEX_TOKEN")),
            "version": UPD.local_version(HERE), "folder": HERE}


def _test_alpaca(key: str, secret: str) -> str | None:
    """Kurzer Test: einen Tageskurs von SPY abrufen. None = ok, sonst Fehlermeldung."""
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed
        end = pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=20)
        req = StockBarsRequest(symbol_or_symbols="SPY", timeframe=TimeFrame.Day, start=(end - pd.Timedelta(days=10)).to_pydatetime(),
                               end=end.to_pydatetime(), feed=DataFeed.SIP)
        StockHistoricalDataClient(key, secret).get_stock_bars(req)
        return None
    except Exception as e:
        m = str(e)
        if "401" in m or "403" in m or "forbidden" in m.lower() or "unauthorized" in m.lower():
            return "Alpaca lehnt die Schlüssel ab. Bitte Key und Secret nochmal kopieren (Paper-Konto, nicht Live)."
        return f"Test nicht möglich ({m[:120]}). Schlüssel wurden trotzdem gespeichert."


@app.post("/api/setup")
async def setup_post(request: Request):
    b = await request.json()
    name, email = str(b.get("name") or "").strip(), str(b.get("email") or "").strip()
    key, sec = str(b.get("alpaca_key") or "").strip(), str(b.get("alpaca_secret") or "").strip()
    av = str(b.get("alphavantage") or "").strip()
    env = load_env(HERE)
    upd = {}
    if name or email:
        if not name or "@" not in email or " " in email:
            return JSONResponse({"ok": False, "error": "Bitte Vor- und Nachname und eine gültige E-Mail eintragen."}, status_code=400)
        upd["SEC_USER_AGENT"] = f"{name} {email}"
    if key or sec:
        if not (key and sec) or not key.isalnum() or len(key) < 10 or len(sec) < 20:
            return JSONResponse({"ok": False, "error": "Alpaca-Key und -Secret bitte beide vollständig einfügen."}, status_code=400)
        upd["ALPACA_KEY"], upd["ALPACA_SECRET"] = key, sec
    if av:
        upd["ALPHAVANTAGE_KEY"] = av
    if not upd:
        return JSONResponse({"ok": False, "error": "Nichts eingetragen."}, status_code=400)
    if not env.get("SEC_USER_AGENT") and "SEC_USER_AGENT" not in upd:
        return JSONResponse({"ok": False, "error": "Bitte noch Name und E-Mail eintragen."}, status_code=400)
    warn = _test_alpaca(key, sec) if key else None
    if warn and warn.startswith("Alpaca lehnt"):
        upd.pop("ALPACA_KEY", None)
        upd.pop("ALPACA_SECRET", None)
        if upd:
            save_values(HERE, upd)
        return JSONResponse({"ok": False, "error": warn}, status_code=400)
    save_values(HERE, upd)
    return {"ok": True, "warning": warn}


# ───────────────────────── Update von GitHub ─────────────────────────
@app.get("/api/update")
def update_check():
    return UPD.check(HERE)


@app.post("/api/update")
def update_apply():
    try:
        r = UPD.apply(HERE)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"Update fehlgeschlagen: {str(e)[:200]}"}, status_code=500)
    return {"ok": True, **r}


@app.get("/")
def index():
    page = os.path.join(HERE, "static", "index.html")
    if not os.path.exists(page):
        from fastapi.responses import HTMLResponse
        return HTMLResponse(f"<h2>index.html fehlt</h2><p>Gesucht in: <b>{page}</b></p>"
                            f"<p>Lege die Datei <b>index.html</b> (genau dieser Name) in den Ordner <b>static</b> "
                            f"neben app.py und lade die Seite neu.</p>", status_code=500)
    return FileResponse(page, headers={"Cache-Control": "no-store"})


def stop_old_screeners(port: int = 8765, verbose: bool = True) -> int:
    """Beendet andere laufende QM-Screener (alte Fenster/Kopien), damit der Port frei ist. Nur Windows."""
    import socket, subprocess
    if os.name != "nt":
        return 0
    me = os.getpid()
    ps = ("$r=@(); Get-CimInstance Win32_Process -Filter \"Name like 'python%' or Name like 'py.exe'\" | "
          "Where-Object { $_.CommandLine -match 'app\\.py' -and $_.ProcessId -ne %d } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $r+=$_.ProcessId }; "
          "try { Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction Stop | ForEach-Object { "
          "$p=Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; "
          "if ($p -and $p.ProcessName -like 'py*' -and $p.Id -ne %d) { Stop-Process -Id $p.Id -Force; $r+=$p.Id } } } catch {}; "
          "$r.Count") % (me, port, me)
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30).stdout.strip()
        n = int(out.splitlines()[-1]) if out else 0
    except Exception:
        n = 0
    if n and verbose:
        print(f"Alten Screener beendet ({n} Prozess(e)).")
    import time as _t
    for _ in range(20):                      # warten, bis der Port frei ist
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return n
            except OSError:
                _t.sleep(0.3)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="synthetische Daten zum Ausprobieren")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    STATE["demo"] = a.demo
    if not a.demo:
        DF["df"] = D.load_cache(HERE)
    url = f"http://127.0.0.1:{a.port}"
    if not a.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"QM Screener läuft auf {url}  (Beenden mit Strg+C)")
    print(f"Programmordner: {HERE}")
    _e = load_env(HERE)
    print("Schlüssel: " + (f"gefunden in {_e['_source']}" if _e.get("_source") else "NICHT gefunden (nur Demo möglich)"))
    stop_old_screeners(a.port)
    # Beim Start sofort mit den vorhandenen Daten scannen (ohne Download), damit die Liste gleich da ist
    if a.demo or DF["df"] is not None:
        STATE.update(running=True, error=None, message="startet")
        threading.Thread(target=_job, args=(False,), daemon=True).start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
    except SystemExit:
        print("\nPort " + str(a.port) + " ist belegt: Es läuft noch ein anderer Screener. Alle schwarzen Fenster "
              "schließen und neu über das Desktop-Symbol starten.")
        raise


if __name__ == "__main__":
    main()

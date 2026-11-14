"""Scan-Logik: Momentum-Rang, Filter, Setup-Diagnose, Marktampel.

Datenformat überall: langes DataFrame mit Spalten
symbol, date, open, high, low, close, volume (date = Handelstag als Timestamp).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .params import Params


# ---------------------------------------------------------------- Indikatoren
def add_features(f: pd.DataFrame) -> pd.DataFrame:
    d = f.copy()
    c = d["close"]
    d["ema10"] = c.ewm(span=10, adjust=False).mean()
    d["ema20"] = c.ewm(span=20, adjust=False).mean()
    d["sma50"] = c.rolling(50).mean()
    d["adr_pct"] = 100 * ((d["high"] / d["low"]).rolling(20).mean() - 1)
    d["dollar_vol"] = (c * d["volume"]).rolling(20).mean()
    d["vol50"] = d["volume"].rolling(50).mean()
    return d


def _not_pinned(f: pd.DataFrame, adr60: float) -> bool:
    """Übernahme-Kandidaten kleben am Angebotspreis: Tagesspanne der letzten 10 Tage fast null.
    Echte enge Bases schwanken weiter (mind. 1 % bzw. 30 % der normalen Spanne)."""
    adr10 = float(((f["high"] / f["low"]).iloc[-10:].mean() - 1) * 100)
    return adr10 >= max(1.0, 0.3 * adr60)


def tight_daily(f: pd.DataFrame, p) -> tuple[bool, dict]:
    """Enge Base im Tageschart: Vorlauf, Base 2–8 Wochen, enger werdend, rechte Seite eng
    (gemessen an der 60-Tage-ADR, nicht an einer festen Zahl), Volumen trocken, Trend intakt."""
    n = len(f)
    if n < 80:
        return False, {}
    h, l, c, v = f["high"], f["low"], f["close"], f["volume"]
    adr60 = float(((h / l).iloc[-60:].mean() - 1) * 100)
    win = min(p.tb_max_days + 1, n)
    i_hi = n - win + int(np.argmax(h.iloc[-win:].values))
    base_days = n - 1 - i_hi
    bh = float(h.iloc[i_hi])
    seg = f.iloc[i_hi:]
    depth = (1 - float(seg["low"].min()) / bh) * 100
    pre = l.iloc[max(0, i_hi - 63):i_hi + 1]
    prior = (bh / float(pre.min()) - 1) * 100
    half = max(2, base_days // 2)
    s1, s2 = seg.iloc[:half], seg.iloc[half:]
    rng = lambda x: (x["high"].max() / x["low"].min() - 1) * 100 if len(x) else None
    r1, r2 = rng(s1), rng(s2)
    last = f.iloc[-p.tb_tight_days:]
    tight_pct = rng(last)
    tight_mult = tight_pct / adr60 if adr60 > 0 else 99
    piv = float(last["high"].max())
    to_piv = (piv / float(c.iloc[-1]) - 1) * 100
    from_bh = (bh / float(c.iloc[-1]) - 1) * 100
    e20, s50 = f["ema20"], f["sma50"]
    checks = {
        "Base 2–8 Wochen": p.tb_min_days <= base_days <= p.tb_max_days,
        f"Vorlauf ≥ {p.tb_prior_min * 100:.0f} %": prior >= p.tb_prior_min * 100,
        f"Base ≤ {p.tb_max_depth * 100:.0f} % tief": depth <= p.tb_max_depth * 100,
        "wird enger": r2 is not None and r1 is not None and r2 <= r1,
        f"rechts eng ≤ {p.tb_tight_mult}× ADR60": tight_mult <= p.tb_tight_mult,
        "Volumen trocken": float(v.iloc[-5:].mean()) < float(f["vol50"].iloc[-1]),
        "über steigendem 20er/50er": float(c.iloc[-1]) > float(e20.iloc[-1]) and float(c.iloc[-1]) > float(s50.iloc[-1])
                                     and e20.iloc[-1] > e20.iloc[-6] and s50.iloc[-1] > s50.iloc[-11],
        f"≤ {p.tb_max_to_pivot:.0f} % unter Base-Hoch": from_bh <= p.tb_max_to_pivot,
        "keine Übernahme (Kurs nicht festgenagelt)": _not_pinned(f, adr60),
    }
    soft = {"wird enger", "Volumen trocken"}      # Bonus, nicht Pflicht: entscheidet über Status „Setup“
    fails = [k for k, ok in checks.items() if not ok]
    info = {"tb_days": int(base_days), "tb_depth": round(depth, 1), "tb_prior": round(prior, 0),
            "tb_tight_mult": round(tight_mult, 2), "adr60_pct": round(adr60, 2), "tb_pivot": round(piv, 4),
            "tb_to_pivot": round(to_piv, 2), "tb_fails": fails,
            "tb_soft_missing": [k for k in fails if k in soft]}
    return not [k for k in fails if k not in soft], info


def tight_weekly(f: pd.DataFrame, p) -> tuple[bool, dict]:
    """Enge Base im Wochenchart: Vorlauf, Base 3–15 Wochen, Kurs oben in der Base, letzte Wochenschlüsse eng, Spanne kleiner als die Base,
    über steigender 10- und 30-Wochen-Linie, Wochenvolumen fällt."""
    w = f[["open", "high", "low", "close", "volume"]].resample("W-FRI").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    n = len(w)
    if n < 25:
        return False, {}
    win = min(p.tw_max_weeks + 1, n)
    i_hi = n - win + int(np.argmax(w["high"].iloc[-win:].values))
    base_w = n - 1 - i_hi
    bh = float(w["high"].iloc[i_hi])
    depth = (1 - float(w["low"].iloc[i_hi:].min()) / bh) * 100
    pre = w["low"].iloc[max(0, i_hi - 52):i_hi + 1]
    prior = (bh / float(pre.min()) - 1) * 100
    k = p.tw_tight_weeks
    lc = w["close"].iloc[-k:]
    tight = (lc.max() / lc.min() - 1) * 100
    m10, m30 = w["close"].rolling(10).mean(), w["close"].rolling(30).mean()
    cl = float(w["close"].iloc[-1])
    ma_ok = cl > m10.iloc[-1] and m10.iloc[-1] > m10.iloc[-4]
    if n >= 34 and pd.notna(m30.iloc[-1]):
        ma_ok = ma_ok and cl > m30.iloc[-1] and m30.iloc[-1] > m30.iloc[-5]
    vol_dry = float(w["volume"].iloc[-k:].mean()) < float(w["volume"].iloc[-k - 10:-k].mean())
    rng = (float(w["high"].iloc[-k:].max()) / float(w["low"].iloc[-k:].min()) - 1) * 100
    cl_d = float(f["close"].iloc[-1])
    below = (1 - cl_d / bh) * 100
    piv = bh
    checks = {
        "Base 3–15 Wochen": p.tw_min_weeks <= base_w <= p.tw_max_weeks,
        f"Vorlauf ≥ {p.tw_prior_min * 100:.0f} %": prior >= p.tw_prior_min * 100,
        f"Base ≤ {p.tw_max_depth * 100:.0f} % tief": depth <= p.tw_max_depth * 100,
        f"{k} Wochenschlüsse ≤ {p.tw_close_pct:g} %": tight <= p.tw_close_pct,
        f"≤ {p.tw_max_below:g} % unter Base-Hoch": below <= p.tw_max_below,
        "Base wird ruhiger": rng <= p.tw_contract * depth,
        "über steigender 10/30-Wochen-Linie": bool(ma_ok),
        "Wochenvolumen fällt": vol_dry,
        "Daily über 20er": float(f["close"].iloc[-1]) > float(f["ema20"].iloc[-1]),
        "keine Übernahme (Kurs nicht festgenagelt)": _not_pinned(f, float(((f["high"] / f["low"]).iloc[-60:].mean() - 1) * 100)),
    }
    info = {"tw_weeks": int(base_w), "tw_depth": round(depth, 1), "tw_prior": round(prior, 0),
            "tw_tight_pct": round(tight, 2), "tw_pivot": round(piv, 4),
            "tw_to_pivot": round((piv / float(f["close"].iloc[-1]) - 1) * 100, 2),
            "tw_fails": [k2 for k2, ok in checks.items() if not ok]}
    return all(checks.values()), info


def market_regime(bench: pd.DataFrame) -> dict:
    """Ampel aus 10er/20er EMA des Benchmarks am letzten Tag."""
    c = bench.sort_values("date")["close"].reset_index(drop=True)
    e10, e20 = c.ewm(span=10, adjust=False).mean(), c.ewm(span=20, adjust=False).mean()
    up10, up20 = e10.iloc[-1] > e10.iloc[-2], e20.iloc[-1] > e20.iloc[-2]
    if e10.iloc[-1] > e20.iloc[-1] and up10 and up20:
        state = "green"
    elif e10.iloc[-1] < e20.iloc[-1] and not up10 and not up20:
        state = "red"
    else:
        state = "yellow"
    return {"state": state, "ema10": round(float(e10.iloc[-1]), 2), "ema20": round(float(e20.iloc[-1]), 2),
            "ema10_rising": bool(up10), "ema20_rising": bool(up20), "close": round(float(c.iloc[-1]), 2)}


# ---------------------------------------------------------------- Stufe 1: ganzer Markt, Matrix-Rechnung
RS_WEIGHTS = ((63, 0.4), (126, 0.2), (189, 0.2), (252, 0.2))   # IBD-Näherung: letztes Quartal doppelt


def rs_score_last(C: pd.DataFrame) -> pd.Series:
    """Gewichtete 12-Monats-Performance am letzten Tag: 0,4·C/C63 + 0,2·C/C126 + 0,2·C/C189 + 0,2·C/C252.
    Junge Aktien (IPOs): Gewichte nur über die vorhandenen Quartale, mindestens 63 Tage nötig."""
    last = C.iloc[-1]
    num = pd.Series(0.0, index=C.columns)
    den = pd.Series(0.0, index=C.columns)
    for k, w in RS_WEIGHTS:
        if len(C) <= k:
            continue
        ratio = last / C.iloc[-1 - k]
        ok = ratio.notna()
        num[ok] += w * ratio[ok]
        den[ok] += w
    return (num / den).where(den > 0)


def last_metrics(df: pd.DataFrame, p: Params, shares: dict | None = None, rs_bench: str = "SPY",
                 pm: dict | None = None) -> pd.DataFrame:
    w = {k: df.pivot_table(index="date", columns="symbol", values=k, aggfunc="last").sort_index()
         for k in ("open", "high", "low", "close", "volume")}
    O, H, L, C, V = w["open"], w["high"], w["low"], w["close"], w["volume"]
    # Short-Modus: Kurse gespiegelt, echter Kurs in 'rc'
    RC = df.pivot_table(index="date", columns="symbol", values="rc", aggfunc="last").sort_index().reindex_like(C) \
        if "rc" in df.columns else C
    last_date = C.index[-1]
    fresh = C.columns[C.iloc[-1].notna()]
    n = len(C)
    out = pd.DataFrame(index=fresh)
    close = C.iloc[-1][fresh]
    out["close"] = close
    out["price"] = RC.iloc[-1][fresh]
    out["adr_pct"] = (100 * ((H / L).iloc[-20:].mean() - 1))[fresh].where(C.iloc[-20:][fresh].count() >= 20)
    out["adr60_pct"] = (100 * ((H / L).iloc[-60:].mean() - 1))[fresh].where(C.iloc[-60:][fresh].count() >= 40)
    out["dollar_vol"] = (RC * V).iloc[-20:].mean()[fresh].where(C.iloc[-20:][fresh].count() >= 20)
    out["avg_vol30"] = V.iloc[-30:].mean()[fresh]
    out["volume"] = V.iloc[-1][fresh]
    out["chg_pct"] = (close / C.iloc[-2][fresh] - 1) * 100 if n > 1 else np.nan
    out["chg_open_pct"] = (close / O.iloc[-1][fresh] - 1) * 100
    s50 = C[fresh].rolling(50).mean()
    out["above_sma50"] = close > s50.iloc[-1]
    out["sma50_rising"] = (s50.iloc[-1] > s50.iloc[-11]) if n > 60 else False
    # Vorbörse: gestriger Schluss = letzter Tag vor heute (New York)
    if pm:
        today = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
        prev = C[C.index < today].iloc[-1][fresh] if (C.index < today).any() else close
        pmp = pd.Series({s: pm[s]["pm_price"] for s in fresh if s in pm}, dtype=float)
        if "rc" in df.columns:          # gespiegelt: Vorbörsenkurs ebenfalls umdrehen
            pmp = 1.0 / pmp
        out["pm_price"] = pmp
        # gestriger Schluss bevorzugt direkt von Alpaca (stimmt auch, wenn die Tageskurse veraltet sind)
        pc = pd.Series({s: pm[s].get("prev_close") for s in fresh if s in pm}, dtype=float)
        prev = pc.where(pc.notna(), prev.reindex(pc.index))
        out["pm_gap_pct"] = (pmp / prev.reindex(pmp.index) - 1) * 100
        out["pm_vol"] = pd.Series({s: pm[s]["pm_vol"] for s in fresh if s in pm}, dtype=float)
        out["pm_time"] = pd.Series({s: pm[s]["pm_time"] for s in fresh if s in pm}, dtype=object)
    else:
        out["pm_price"] = out["pm_gap_pct"] = out["pm_vol"] = np.nan
        out["pm_time"] = None
    rng = (H.iloc[-1][fresh] - L.iloc[-1][fresh])
    out["close_pos"] = ((close - L.iloc[-1][fresh]) / rng).where(rng > 0)

    # Momentum (Anstieg vom tiefsten Tief der letzten N Tage) + Rang
    for win in p.mom_windows:
        lw = L.iloc[-win:][fresh]
        mom = (close / lw.min() - 1) * 100
        out[f"mom{win}"] = mom.where(lw.count() >= win)
        out[f"rank{win}"] = out[f"mom{win}"].rank(pct=True)
    top = np.zeros(len(out), dtype=bool)
    for win in p.mom_windows:
        top |= (out[f"rank{win}"] >= 1 - p.mom_top_pct).fillna(False).values
    out["momentum_top"] = top

    # Marktkapitalisierung + "ist Aktie" (bei der SEC gemeldet). ETFs/Fonds haben keinen Eintrag.
    if shares:
        sh = pd.Series({s: shares.get(s) for s in fresh}, dtype=float)
        out["market_cap"] = sh * out["price"]
        out["is_stock"] = pd.Series({s: s in shares for s in fresh})
    else:
        out["market_cap"] = np.nan
        out["is_stock"] = True

    # Relative Stärke: Rating 1–99 gegen alle Aktien (ETFs zählen nicht zur Rangliste)
    score = rs_score_last(C)[fresh]
    ref = np.sort(score[out["is_stock"] & score.notna()].values)
    if len(ref):
        pct = np.searchsorted(ref, score.values, side="right") / len(ref)
        out["rs_rating"] = np.where(score.notna(), np.clip(np.round(pct * 98 + 1), 1, 99), np.nan)
    else:
        out["rs_rating"] = np.nan
    # RS-Linie (Kurs / Benchmark) auf 52-Wochen-Hoch
    out["rs_new_high"] = False
    out["rs_nh_before_price"] = False
    if rs_bench in C.columns:
        R = C[fresh].div(C[rs_bench], axis=0).iloc[-252:]
        rs_max = R.max()
        out["rs_new_high"] = (R.iloc[-1] >= rs_max * (1 - 1e-9)) & (R.count() >= 126)
    # 52 Wochen
    hi52 = H.iloc[-252:][fresh].max()
    lo52 = L.iloc[-252:][fresh].min()
    out["from_high_pct"] = (close / hi52 - 1) * 100
    out["above_low_pct"] = (close / lo52 - 1) * 100
    out["rs_nh_before_price"] = out["rs_new_high"] & (H.iloc[-1][fresh] < hi52)
    # RVOL und Gap (heutige Kerze)
    prev_vol = V.iloc[-51:-1][fresh].mean() if n > 2 else np.nan
    out["rvol"] = out["volume"] / prev_vol
    out["gap_pct"] = (O.iloc[-1][fresh] / C.iloc[-2][fresh] - 1) * 100 if n > 1 else np.nan
    sg = -1.0 if p.gap_short else 1.0          # Short-Seite: Gaps nach unten
    out["ep"] = (sg * out["gap_pct"] >= p.ep_min_gap_pct) & (out["rvol"] >= p.ep_min_rvol)
    # EP in den letzten k Tagen (k = 1: nur heute)
    out["ep_days_ago"] = np.where(out["ep"].fillna(False), 0, np.nan)
    for j in range(2, max(1, int(p.ep_lookback_days)) + 1):
        if n <= j + 51:
            break
        g = (O.iloc[-j][fresh] / C.iloc[-j - 1][fresh] - 1) * 100
        rv = V.iloc[-j][fresh] / V.iloc[-j - 50:-j][fresh].mean()
        hit = ((sg * g >= p.ep_min_gap_pct) & (rv >= p.ep_min_rvol)).fillna(False) & out["ep_days_ago"].isna()
        out.loc[hit[hit].index, "ep_days_ago"] = j - 1
        out.loc[hit[hit].index, "ep_gap_then"] = g[hit]
    out["ep_recent"] = out["ep_days_ago"].notna() & (out["ep_days_ago"].fillna(-1) >= p.ep_min_days_ago)
    # Delayed EP: hält der Kurs das Tief des Gap-Tages, wie weit unter dem Hoch seit dem Gap?
    out["ep_hold"] = np.nan
    out["ep_from_high_pct"] = np.nan
    for sym in out.index[out["ep_days_ago"].notna()]:
        d = int(out.at[sym, "ep_days_ago"])
        lo_g = L[sym].iloc[-(d + 1)]
        hi_s = H[sym].iloc[-(d + 1):].max()
        out.at[sym, "ep_hold"] = float(close[sym] >= lo_g) if not p.gap_short else float(close[sym] <= H[sym].iloc[-(d + 1)])
        out.at[sym, "ep_from_high_pct"] = (1 - close[sym] / hi_s) * 100
    # Börsengang: Handelstage seit dem ersten Kurs (nur wenn der erste Kurs nach Beginn der Datenreihe liegt)
    first = C[fresh].apply(lambda x: x.first_valid_index())
    days_listed = C[fresh].notna().sum()
    out["ipo_days"] = days_listed.where(first > C.index[min(5, n - 1)])
    # Relative Stärke zum Marktampel-Index über 1 Monat (Prozentpunkte)
    if p.benchmark in C.columns and n > 22:
        b1m = (C[p.benchmark].iloc[-1] / C[p.benchmark].iloc[-22] - 1) * 100
        out["rel_1m"] = (close / C[fresh].iloc[-22] - 1) * 100 - b1m
    else:
        out["rel_1m"] = np.nan
    # Abstand der RS-Linie zu ihrem 52W-Hoch
    if rs_bench in C.columns:
        out["rs_line_from_high"] = (1 - R.iloc[-1] / rs_max) * 100
    else:
        out["rs_line_from_high"] = np.nan
    # Minervini-Trend-Template
    sma50 = C.iloc[-50:][fresh].mean()
    sma150 = C.iloc[-150:][fresh].mean()
    sma200 = C.iloc[-200:][fresh].mean()
    sma200_prev = C.iloc[-222:-22][fresh].mean() if n > 222 else pd.Series(np.nan, index=fresh)
    enough = C.iloc[-222:][fresh].count() >= 222
    out["trend_template"] = (enough & (close > sma50) & (close > sma150) & (close > sma200)
                             & (sma50 > sma150) & (sma50 > sma200) & (sma150 > sma200) & (sma200 > sma200_prev)
                             & (out["above_low_pct"] >= 30) & (out["from_high_pct"] >= -25)
                             & (out["rs_rating"] >= 70))

    # ---- Eigene Muster
    Cf, Lf, Hf = C[fresh], L[fresh], H[fresh]
    # 20er-Rückeroberung: die letzten k Schlüsse über EMA 20, der davor darunter
    k = max(1, int(p.reclaim_days))
    e20 = Cf.ewm(span=20, adjust=False).mean()
    above = (Cf > e20).iloc[-(k + 1):]
    if len(above) == k + 1:
        out["reclaim"] = above.iloc[1:].all() & ~above.iloc[0] & (Cf.iloc[-(k + 1):].count() == k + 1)
        stop = Lf.iloc[-k]                                   # Tief der ersten Kerze über dem 20er
    else:
        out["reclaim"] = False
        stop = Lf.iloc[-1]
    out["stop_pct"] = ((close - stop) / close * 100).where(out["reclaim"])
    out["stop_adr"] = out["stop_pct"] / out["adr_pct"]
    # Power Play: Anstieg ≥ X % innerhalb von ≤ N Tagen (in den letzten 63 Tagen), danach Flagge ≤ Y % tief
    tail = max(63 + p.pp_max_days + 1, 120)
    Lt, Ht = Lf.iloc[-tail:], Hf.iloc[-tail:]
    lmin = Lt.rolling(p.pp_max_days, min_periods=10).min()
    out["pp_gain"] = ((Ht / lmin).iloc[-63:].max() - 1) * 100
    hi63 = Ht.iloc[-63:].max()
    out["pp_flag_pct"] = (1 - close / hi63) * 100
    out["power_play"] = (out["pp_gain"] >= p.pp_min_gain_pct) & (out["pp_flag_pct"] <= p.pp_max_flag_pct)
    # Stage-2-Start: SMA 200 steigt seit 1 Monat, war vor 3 Monaten noch flach/fallend; Kurs > SMA50 > SMA200; nahe 6M-Hoch
    if n >= 285:
        s200 = Cf.rolling(200).mean()
        s200_now, s200_m1 = s200.iloc[-1], s200.iloc[-22]
        s200_m3, s200_m4 = s200.iloc[-64], s200.iloc[-85]
        s50 = Cf.iloc[-50:].mean()
        hi126 = Hf.iloc[-126:].max()
        out["stage2"] = ((s200_now > s200_m1) & (s200_m3 <= s200_m4 * 1.005) & (close > s50) & (s50 > s200_now)
                         & (close >= hi126 * 0.95)).fillna(False)
    else:
        out["stage2"] = False

    # Filter
    elig = (out["price"] >= p.min_price) & (out["dollar_vol"].fillna(0) >= p.min_dollar_vol) \
        & (out["adr_pct"].fillna(0) >= p.min_adr_pct) & (out["avg_vol30"].fillna(0) >= p.min_avg_volume) \
        & (out["adr60_pct"].fillna(0) >= p.min_adr60_pct)
    for flag, span in ((p.require_above_ema21, 21), (p.require_above_ema50, 50)):
        if flag:
            e = C[fresh].ewm(span=span, adjust=False).mean().iloc[-1]
            elig &= close > e
    if p.min_market_cap > 0 and shares:          # ohne Aktienanzahl würde der Filter sonst alles ausblenden
        elig &= out["market_cap"].fillna(0) >= p.min_market_cap
    if p.only_stocks and shares:
        elig &= out["is_stock"]
    if p.max_market_cap > 0 and shares:
        elig &= out["market_cap"].fillna(0) <= p.max_market_cap
    if p.require_ma_reclaim:
        elig &= out["reclaim"].fillna(False)
        if p.max_stop_adr > 0:
            elig &= out["stop_adr"].fillna(99) <= p.max_stop_adr
    if p.require_power_play:
        elig &= out["power_play"].fillna(False)
    if p.require_stage2:
        elig &= out["stage2"].fillna(False)
    if p.min_rs_rating > 0:
        elig &= out["rs_rating"].fillna(0) >= p.min_rs_rating
    if p.max_from_high_pct < 100:
        elig &= out["from_high_pct"].fillna(-999) >= -p.max_from_high_pct
    if p.min_rvol > 0:
        elig &= out["rvol"].fillna(0) >= p.min_rvol
    if p.require_rs_new_high:
        elig &= out["rs_new_high"]
    if p.require_trend_template:
        elig &= out["trend_template"]
    if p.min_gap_pct > 0:
        elig &= sg * out["gap_pct"].fillna(-999 * sg) >= p.min_gap_pct
    if p.min_chg_open_pct > -100:
        elig &= sg * out["chg_open_pct"].fillna(-999 * sg) >= p.min_chg_open_pct
    if p.require_above_sma50_f:      # Short: Kurs UNTER SMA 50
        a50 = out["above_sma50"].fillna(p.gap_short).astype(bool)
        elig &= ~a50 if p.gap_short else a50
    if p.require_sma50_rising:       # Short: SMA 50 FÄLLT
        r50 = out["sma50_rising"].fillna(p.gap_short).astype(bool)
        elig &= ~r50 if p.gap_short else r50
    if p.min_pm_gap_pct > 0:
        elig &= sg * out["pm_gap_pct"].fillna(-999 * sg) >= p.min_pm_gap_pct
    if p.require_ep_hold:
        elig &= out["ep_hold"].fillna(0) > 0
    if p.max_ep_from_high_pct > 0:
        elig &= out["ep_from_high_pct"].fillna(999) <= p.max_ep_from_high_pct
    if p.max_ipo_days > 0:
        elig &= out["ipo_days"].fillna(99999) <= p.max_ipo_days
    if p.min_ipo_days > 0:
        elig &= out["ipo_days"].fillna(0) >= p.min_ipo_days
    if p.min_rel_1m > -100:
        elig &= out["rel_1m"].fillna(-999) >= p.min_rel_1m
    if p.max_rs_line_from_high > 0:
        elig &= out["rs_line_from_high"].fillna(999) <= p.max_rs_line_from_high
    if p.min_pm_volume > 0:
        elig &= out["pm_vol"].fillna(0) >= p.min_pm_volume
    if p.require_breakout_today:
        elig &= out["close_pos"].fillna(0) >= p.bo_min_close_pos
    if p.require_ep:
        elig &= out["ep_recent"] if p.ep_lookback_days > 1 else out["ep"].fillna(False)
    out["eligible"] = elig
    out.attrs["last_date"] = last_date
    out.attrs["universe"] = len(out)
    out.attrs["has_shares"] = bool(shares)
    return out


# ---------------------------------------------------------------- Stufe 2: Setup-Diagnose pro Aktie
def diagnose(f: pd.DataFrame, p: Params) -> dict:
    """Prüft alle Setup-Regeln am letzten Tag und liefert Kennzahlen + nicht erfüllte Regeln."""
    i = len(f) - 1
    h, l, c, v = (f[k].values for k in ("high", "low", "close", "volume"))
    row = f.iloc[i]
    adr = float(row["adr_pct"])
    res = {"fails": []}
    if i < p.base_lookback + p.prior_move_lookback + 2 or not np.isfinite(adr):
        res["fails"].append("Historie zu kurz")
        res["setup"] = False
        return res

    w0 = i - p.base_lookback + 1
    win = h[w0:i + 1]
    top = float(win.max())
    bs = w0 + int(np.argmax(win >= top * (1 - p.base_high_tol)))
    base_len = i - bs
    pre_low = float(l[max(0, bs - p.prior_move_lookback):bs + 1].min())
    prior = (top / pre_low - 1) * 100
    base_low = float(l[bs:i + 1].min())
    depth = (top - base_low) / top * 100
    mid = bs + (base_len + 1) // 2
    hl = bool(l[mid:i + 1].min() >= l[bs:mid].min()) if mid > bs else False
    t0 = i - p.tight_days + 1
    tight_hi, tight_lo = float(h[t0:i + 1].max()), float(l[t0:i + 1].min())
    tight_pct = (tight_hi - tight_lo) / c[i] * 100
    vol_ratio = float(v[t0:i + 1].mean() / row["vol50"]) if row["vol50"] > 0 else np.inf
    ext = (c[i] / row["ema20"] - 1) * 100

    checks = [
        (p.base_min_days <= base_len <= p.base_max_days,
         ("frisches Hoch, noch keine Base" if base_len <= 2 else
          f"Base erst {base_len} T" if base_len < p.base_min_days else f"Base schon {base_len} T")),
        (prior >= p.prior_move_min * 100, f"Vorlauf nur {prior:.0f} %"),
        (depth <= p.base_max_depth * 100, f"Base {depth:.0f} % tief"),
        (hl or not p.require_higher_lows, "keine höheren Tiefs"),
        (tight_pct <= p.tight_max_adr_mult * adr, f"nicht eng ({tight_pct / adr:.1f}× ADR)"),
        (vol_ratio <= p.vol_dry_ratio, f"Volumen nicht trocken ({vol_ratio:.2f})"),
        (ext <= p.max_ext_adr_mult * adr, f"zu weit über 20er ({ext / adr:.1f}× ADR)"),
        (c[i] > row["sma50"] or not p.require_above_sma50, "unter SMA 50"),
        (row["ema10"] > row["ema20"] or not p.require_ema10_above_ema20, "EMA10 unter EMA20"),
    ]
    res["fails"] = [msg for ok, msg in checks if not ok]
    res["setup"] = not res["fails"]
    has_base = base_len >= max(p.base_min_days, 3)
    res.update({
        "pivot": round(tight_hi, 4) if has_base else None,
        "to_pivot_pct": round((tight_hi / c[i] - 1) * 100, 2) if has_base else None,
        "base_days": int(base_len), "base_start": str(f.index[bs].date()) if has_base else None, "base_high": round(top, 4),
        "base_low": round(base_low, 4), "prior_move_pct": round(prior, 1), "depth_pct": round(depth, 1),
        "higher_lows": hl, "tight_adr": round(tight_pct / adr, 2), "vol_ratio": round(vol_ratio, 2),
        "ext_adr": round(ext / adr, 2), "ema10": round(float(row["ema10"]), 4), "ema20": round(float(row["ema20"]), 4),
        "sma50": round(float(row["sma50"]), 4),
    })
    return res


def _num(v, nd=2, scale=1.0):
    return round(float(v) * scale, nd) if v is not None and pd.notna(v) else None


def run_scan(df: pd.DataFrame, p: Params, progress=None, shares: dict | None = None, keep: dict | None = None,
             groups: dict | None = None, pm: dict | None = None) -> dict:
    if progress:
        progress("Berechne Kennzahlen für den ganzen Markt")
    lm = last_metrics(df, p, shares, p.rs_benchmark, pm)
    attrs = dict(lm.attrs)
    lm = lm.drop(index=[s for s in (p.benchmark, p.rs_benchmark) if s in lm.index])
    lm.attrs.update(attrs, universe=int(lm["is_stock"].sum()) if attrs.get("has_shares") and p.only_stocks else len(lm))
    if keep is not None:
        keep["lm"] = lm
    # Branchen-Rang (1 = stärkste Branche aus 1W + 1M, Median der Aktien, mind. 5 Aktien)
    ind_rank = {}
    if groups:
        from .groups import stock_table, group_table
        try:
            gt = group_table(stock_table(df, groups, lm), "industry")
            gt = gt[gt["n"] >= 5]
            # 1 Woche und 1 Monat zusammen (wie im Video): Mittel der Perzentil-Ränge
            score = (gt["p1w"].rank(pct=True) + gt["p1m"].rank(pct=True)) / 2
            ind_rank = score.rank(ascending=False, method="min").to_dict()
            lm.attrs["n_industries"] = len(gt)
        except Exception:
            ind_rank = {}
    # Top-down-Trichter: beste Sektoren → je beste Branchen → je beste Aktien
    td_pos = {}
    if p.td_sectors > 0 and groups:
        from .groups import stock_table
        try:
            st = stock_table(df, groups, lm)
            def score(g):
                return (g["p1w"].rank(pct=True) + g["p1m"].rank(pct=True)) / 2
            sec = st.groupby("sector")[["p1w", "p1m"]].median()
            sec = sec[st.groupby("sector").size() >= 10]
            top_sec = score(sec).sort_values(ascending=False).index[:p.td_sectors]
            pool = lm[lm["eligible"]].index
            for si, sname in enumerate(top_sec, 1):
                sub = st[st["sector"] == sname]
                ind = sub.groupby("industry")[["p1w", "p1m"]].median()
                ind = ind[sub.groupby("industry").size() >= 5]
                for bi, iname in enumerate(score(ind).sort_values(ascending=False).index[:p.td_industries], 1):
                    mem = [x for x in sub[sub["industry"] == iname].index if x in pool]
                    cand = lm.loc[mem, ["rs_rating", "from_high_pct"]].fillna(-999)
                    cand = cand.sort_values(["rs_rating", "from_high_pct"], ascending=False).head(p.td_stocks)
                    for ki, sym in enumerate(cand.index, 1):
                        td_pos[sym] = (si, bi, ki, sname, iname)
        except Exception:
            import traceback; traceback.print_exc()
        lm["eligible"] &= lm.index.isin(list(td_pos))
    if p.max_industry_rank > 0 and ind_rank:
        ok = [s for s in lm.index if s in groups and ind_rank.get(groups[s]["industry"], 9999) <= p.max_industry_rank]
        lm["eligible"] &= lm.index.isin(ok)
    cands = lm[lm["momentum_top"] & lm["eligible"]]
    by_sym = {s: g for s, g in df[df["symbol"].isin(cands.index)].groupby("symbol")}
    rows = []
    for k, sym in enumerate(cands.index):
        if progress and k % 25 == 0:
            progress(f"Setup-Prüfung {k}/{len(cands)}")
        f = add_features(by_sym[sym].set_index("date").sort_index())
        d = diagnose(f, p)
        bo = {}
        if p.require_breakout_today:
            # Setup D: gestern eine Base mit Pivot, heute Schluss darüber, stark und nicht zu weit weg
            y = diagnose(f.iloc[:-1], p)
            c_now, adr_now = float(f["close"].iloc[-1]), float(f["adr_pct"].iloc[-1])
            piv = y.get("pivot")
            ok = (piv is not None and p.base_min_days <= (y.get("base_days") or 0) <= p.base_max_days
                  and (y.get("prior_move_pct") or 0) >= p.prior_move_min * 100
                  and (y.get("depth_pct") or 999) <= p.base_max_depth * 100
                  and c_now > piv)
            if not ok:
                continue
            over = (c_now / piv - 1) * 100 / adr_now if adr_now > 0 else 99
            if over > p.bo_max_over_adr:
                continue
            lo = float(f["low"].iloc[-1])
            d = {**y, "setup": True, "fails": [], "pivot": round(piv, 4), "to_pivot_pct": round((piv / c_now - 1) * 100, 2)}
            bo = {"breakout": True, "bo_over_adr": round(over, 2), "stop_pct": round((c_now - lo) / c_now * 100, 2),
                  "stop_adr": round((c_now - lo) / c_now * 100 / adr_now, 2) if adr_now > 0 else None}
        if p.require_base and not (d.get("base_days") is not None and d["base_days"] >= p.base_min_days
                                   and (d.get("depth_pct") or 0) >= p.min_base_depth_pct):
            continue
        tb = {}
        if p.require_tight_d:
            ok, info = tight_daily(f, p)
            if not ok:
                continue
            tb.update(info, tight_d=True)
            miss = {"wird enger": "Base wird nicht enger", "Volumen trocken": "Volumen nicht trocken"}
            d = {**d, "setup": not info["tb_soft_missing"], "fails": [miss[x] for x in info["tb_soft_missing"]],
                 "pivot": info["tb_pivot"], "to_pivot_pct": info["tb_to_pivot"]}
        if p.require_tight_w:
            ok, info = tight_weekly(f, p)
            if not ok:
                continue
            tb.update(info, tight_w=True)
            if not p.require_tight_d:
                d = {**d, "setup": True, "fails": [], "pivot": info["tw_pivot"], "to_pivot_pct": info["tw_to_pivot"]}
        r = cands.loc[sym]
        rows.append({
            "symbol": sym, "close": round(float(r["close"]), 4),
            "adr_pct": round(float(r["adr_pct"]), 2) if pd.notna(r["adr_pct"]) else None,
            "dollar_vol_m": _num(r["dollar_vol"], 1, 1e-6),
            "avg_vol_k": _num(r["avg_vol30"], 0, 1e-3),
            "market_cap_m": _num(r["market_cap"], 0, 1e-6),
            "rs_rating": int(r["rs_rating"]) if pd.notna(r["rs_rating"]) else None,
            "rs_new_high": bool(r["rs_new_high"]), "rs_nh_before_price": bool(r["rs_nh_before_price"]),
            "from_high_pct": _num(r["from_high_pct"], 1), "above_low_pct": _num(r["above_low_pct"], 0),
            "rvol": _num(r["rvol"], 2), "gap_pct": _num(r["gap_pct"], 1), "chg_pct": _num(r["chg_pct"], 2),
            "ep": bool(r["ep"]) if pd.notna(r["ep"]) else False, "trend_template": bool(r["trend_template"]),
            "reclaim": bool(r["reclaim"]), "stop_pct": _num(r["stop_pct"], 2), "stop_adr": _num(r["stop_adr"], 2),
            "power_play": bool(r["power_play"]), "pp_gain": _num(r["pp_gain"], 0), "pp_flag_pct": _num(r["pp_flag_pct"], 1),
            "stage2": bool(r["stage2"]),
            "ep_days_ago": int(r["ep_days_ago"]) if pd.notna(r.get("ep_days_ago")) else None,
            "td": (f"S{td_pos[sym][0]} · B{td_pos[sym][1]} · {td_pos[sym][2]}" if sym in td_pos else None),
            "td_order": (td_pos[sym][0] * 100 + td_pos[sym][1] * 10 + td_pos[sym][2]) if sym in td_pos else None,
            "ep_gap_then": _num(r.get("ep_gap_then"), 1),
            "sector": (groups or {}).get(sym, {}).get("sector"), "industry": (groups or {}).get(sym, {}).get("industry"),
            "ind_rank": int(ind_rank[(groups or {})[sym]["industry"]]) if groups and sym in groups and groups[sym]["industry"] in ind_rank else None,
            **{f"mom{w}": (round(float(r[f"mom{w}"]), 1) if pd.notna(r[f"mom{w}"]) else None) for w in p.mom_windows},
            **{f"rank{w}": (round(float(r[f"rank{w}"]) * 100, 1) if pd.notna(r[f"rank{w}"]) else None) for w in p.mom_windows},
            "close_pos": _num(r.get("close_pos"), 2),
            "chg_open_pct": _num(r.get("chg_open_pct"), 2), "sma50_rising": bool(r.get("sma50_rising")),
            "ipo_days": int(r["ipo_days"]) if pd.notna(r.get("ipo_days")) else None,
            "rel_1m": _num(r.get("rel_1m"), 1), "rs_line_from_high": _num(r.get("rs_line_from_high"), 1),
            "ep_from_high_pct": _num(r.get("ep_from_high_pct"), 1),
            "pm_gap_pct": _num(r.get("pm_gap_pct"), 1), "pm_vol_k": _num(r.get("pm_vol"), 0, 1e-3),
            "pm_price": _num(r.get("pm_price"), 2), "pm_time": r.get("pm_time") if isinstance(r.get("pm_time"), str) else None,
            "adr60_pct": _num(r.get("adr60_pct"), 2),
            **d, **bo, **tb,
        })
    bench = df[df["symbol"] == p.benchmark]
    market = market_regime(bench) if len(bench) > 25 else {"state": "unknown"}
    notes = []
    if (p.min_rel_1m > -100 or p.max_rs_line_from_high > 0) and len(bench) > 50:
        bc = bench.sort_values("date")["close"]
        if bc.iloc[-1] > bc.iloc[-50:].mean():
            notes.append(f"{p.benchmark} liegt über dem SMA 50, keine Korrektur: Der Scan zeigt dann allgemein relative Stärke.")
    if p.gap_short:
        notes.append("Short-Seite aktiv: Gaps nach unten, Kurs unter fallendem SMA 50. Spalte „Status/Setup“ bezieht sich auf Long-Setups.")
    if p.rs_benchmark not in set(df["symbol"].unique()):
        notes.append(f"RS-Linie aus: {p.rs_benchmark} fehlt in den Daten. Bitte 'Daten laden + scannen'.")
    if not lm.attrs.get("has_shares"):
        notes.append("Marktkapitalisierung aus: SEC_USER_AGENT in .env eintragen.")
    return {
        "last_date": str(pd.Timestamp(lm.attrs["last_date"]).date()),
        "universe": int(lm.attrs["universe"]),
        "momentum_top": int(lm["momentum_top"].sum()),
        "n_industries": int(lm.attrs.get("n_industries", 0)),
        "after_filters": int(len(rows)),
        "setups": int(sum(r["setup"] for r in rows)),
        "market": market,
        "rows": rows,
        "notes": notes,
    }


def check_rows(df: pd.DataFrame, symbols: list[str], p: Params, shares: dict | None = None) -> pd.DataFrame:
    """Prüfmodus: alle Kennzahlen für beliebige Symbole, unabhängig vom Scan (Abgleich mit TradingView)."""
    lm = last_metrics(df, p, shares, p.rs_benchmark)
    out = []
    for s in symbols:
        g = df[df["symbol"] == s]
        if g.empty:
            out.append({"symbol": s, "fehler": "keine Daten"})
            continue
        f = add_features(g.set_index("date").sort_index())
        d = diagnose(f, p)
        r = lm.loc[s] if s in lm.index else None
        out.append({"symbol": s, "date": str(f.index[-1].date()), "close": f["close"].iloc[-1],
                    "adr_pct": f["adr_pct"].iloc[-1], "dollar_vol_m": f["dollar_vol"].iloc[-1] / 1e6,
                    **({f"mom{w}": r[f"mom{w}"] for w in p.mom_windows} if r is not None else {}),
                    **({k: r[k] for k in ("market_cap", "rs_rating", "rs_new_high", "from_high_pct", "above_low_pct",
                                          "rvol", "gap_pct", "ep", "trend_template")} if r is not None else {}),
                    **{k: v for k, v in d.items() if k != "fails"}, "fails": "; ".join(d["fails"])})
    return pd.DataFrame(out).round(4)


def chart_payload(df: pd.DataFrame, symbol: str, p: Params, bars: int = 260) -> dict:
    g = df[df["symbol"] == symbol]
    if g.empty:
        return {"error": "keine Daten"}
    f = add_features(g.set_index("date").sort_index())
    rs = []
    b = df[df["symbol"] == p.rs_benchmark]
    if not b.empty and symbol != p.rs_benchmark:
        R = (f["close"] / b.set_index("date")["close"].reindex(f.index)).dropna()
        R52 = R.rolling(252, min_periods=126).max()
        tail = R.iloc[-bars:]
        rs = [{"time": str(ix.date()), "value": round(float(v), 6), "nh": bool(v >= R52.loc[ix] * (1 - 1e-9))}
              for ix, v in tail.items()]
    d = diagnose(f, p)
    t = f.iloc[-bars:]
    def ser(col):
        return [{"time": str(ix.date()), "value": round(float(v), 4)} for ix, v in t[col].items() if pd.notna(v)]
    return {
        "symbol": symbol,
        "candles": [{"time": str(ix.date()), "open": round(r.open, 4), "high": round(r.high, 4), "low": round(r.low, 4),
                     "close": round(r.close, 4)} for ix, r in t.iterrows()],
        "volume": [{"time": str(ix.date()), "value": float(r.volume)} for ix, r in t.iterrows()],
        "ema10": ser("ema10"), "ema20": ser("ema20"), "sma50": ser("sma50"),
        "rs": rs, "rs_bench": p.rs_benchmark,
        "diag": d,
    }

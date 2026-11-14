"""Themen: Querschnitts-Trends (KI, Uran, Rüstung, Krypto …), gemessen an je einem Themen-ETF.

Status je Thema (Tageschart des ETFs):
  Führend = über EMA 21 und SMA 50, SMA 50 steigt, ≤ 8 % unter dem 52W-Hoch, 3 Monate im Plus
  Schwach = unter SMA 50 und (SMA 50 fällt oder unter EMA 21)
  Aufbau  = alles dazwischen (Base, Durchschnitte flachen ab oder drehen)

Zuordnung Aktie → Thema: zuerst feste Symbollisten (kuratiert), dann die Nasdaq-Branche.
Eine Aktie kann mehreren Themen angehören (z. B. IREN: Krypto + KI-Rechenzentren).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# key, Name, ETF, feste Symbole, Nasdaq-Branchen (exakt)
THEMES = [
    ("semis", "Halbleiter", "SMH",
     "NVDA AMD AVGO MU TSM ASML AMAT LRCX KLAC MRVL ARM INTC QCOM TXN ON MPWR ADI NXPI MCHP SNPS CDNS TER ENTG "
     "AMKR WOLF SITM POWI RMBS LSCC SLAB SWKS QRVO CRUS MTSI ALGM ACLS FORM ONTO NVMI CAMT UCTT ICHR AEHR NVTS",
     ("Semiconductors",)),
    ("ai_infra", "KI-Rechenzentren", "AIQ",
     "VRT ANET SMCI DELL CRWV NBIS CLS ALAB CRDO COHR LITE ETN APLD IREN ORCL HPE PSTG NTAP WDC STX SNDK FN "
     "AAOI CIEN GLW AMKR MOD POWL CORZ WULF CIFR GDS VNET DLR EQIX",
     ()),
    ("software", "Software & Cloud", "IGV",
     "MSFT ORCL CRM NOW ADBE INTU PLTR SNOW DDOG MDB TEAM HUBS WDAY APP SHOP TTD ZM DOCU GTLB ESTC CFLT PATH U AI "
     "SOUN BBAI IOT PCOR BILL TOST",
     ("Computer Software: Prepackaged Software", "Computer Software: Programming Data Processing")),
    ("cyber", "Cybersecurity", "CIBR",
     "CRWD PANW ZS FTNT NET OKTA S CYBR QLYS TENB RPD VRNS CHKP RBRK SAIL NTCT GEN AKAM FFIV",
     ()),
    ("quantum", "Quantencomputer", "QTUM",
     "IONQ RGTI QBTS QUBT ARQQ QMCO LAES",
     ()),
    ("space", "Raumfahrt & Satelliten", "UFO",
     "RKLB ASTS LUNR PL RDW SPCE MNTS SATS IRDM GSAT BKSY SPIR VSAT KRMN FLY SIDU VOYG",
     ()),
    ("defense", "Rüstung & Luftfahrt", "ITA",
     "LMT RTX NOC GD LHX KTOS AVAV BWXT HII TXT TDG HEI BA AXON RCAT UMAC ONDS DPRO PLTR MRCY CW ESLT DRS LDOS",
     ("Aerospace", "Military/Government/Technical", "Ordnance And Accessories")),
    ("nuclear", "Uran & Kernkraft", "URA",
     "CCJ UEC NXE DNN UUUU LEU URG UROY OKLO SMR NNE BWXT CEG LTBR EU ASPI",
     ()),
    ("power", "Strom & Versorger", "XLU",
     "VST CEG TLN NRG GEV",
     ("Electric Utilities: Central", "Power Generation")),
    ("crypto", "Krypto", "BLOK",
     "MSTR COIN MARA RIOT CLSK HUT IREN CIFR WULF BTDR CORZ HOOD GLXY BITF BTBT CAN HIVE SMLR BMNR SBET CRCL "
     "GEMI BLSH BTCS ETHZ FIGR",
     ()),
    ("fintech", "Fintech & Broker", "ARKF",
     "HOOD SOFI AFRM UPST PYPL XYZ NU TOST LC DAVE CHYM KLAR IBKR SCHW COIN FUTU TIGR MQ FOUR",
     ()),
    ("biotech", "Biotech", "XBI", "",
     ("Biotechnology: Biological Products (No Diagnostic Substances)", "Biotechnology: Pharmaceutical Preparations",
      "Biotechnology: Commercial Physical & Biological Resarch", "Biotechnology: In Vitro & In Vivo Diagnostic Substances",
      "Medicinal Chemicals and Botanical Products", "Other Pharmaceuticals", "Misc Health and Biotechnology Services")),
    ("medtech", "Medizintechnik", "IHI", "",
     ("Medical/Dental Instruments", "Medical Specialities", "Biotechnology: Electromedical & Electrotherapeutic Apparatus",
      "Biotechnology: Laboratory Analytical Instruments", "Medical Electronics", "Ophthalmic Goods")),
    ("gold", "Gold- & Silberminen", "GDX", "", ("Precious Metals",)),
    ("metals", "Metalle & Seltene Erden", "XME",
     "MP USAR CRML UAMY NB TMC ALB SQM LAC PLL SGML",
     ("Metal Mining", "Steel/Iron Ore", "Aluminum", "Other Metals and Minerals",
      "Mining & Quarrying of Nonmetallic Minerals (No Fuels)", "Coal Mining")),
    ("oil", "Öl & Gas", "XLE", "",
     ("Oil & Gas Production", "Integrated oil Companies", "Oil Refining/Marketing", "Oilfield Services/Equipment",
      "Oil/Gas Transmission", "Oil and Gas Field Machinery")),
    ("solar", "Solar & Wasserstoff", "TAN",
     "FSLR ENPH SEDG RUN NXT ARRY SHLS CSIQ JKS MAXN BE PLUG FCEL BLDP EOSE FLNC STEM",
     ()),
    ("banks", "Banken", "KRE", "",
     ("Major Banks", "Banks", "Commercial Banks", "Savings Institutions")),
    ("infra", "Bau & Infrastruktur", "PAVE",
     "PWR EME FIX STRL MTZ DY PRIM AGX IESC MYRG ROAD VMC MLM",
     ("Engineering & Construction", "Water Sewer Pipeline Comm & Power Line Construction", "Building Materials",
      "Construction/Ag Equipment/Trucks")),
    ("homes", "Hausbau", "ITB", "", ("Homebuilding", "RETAIL: Building Materials", "Building Products")),
    ("retail", "Einzelhandel", "XRT", "",
     ("Clothing/Shoe/Accessory Stores", "Department/Specialty Retail Stores", "Other Specialty Stores",
      "Catalog/Specialty Distribution", "Apparel", "Shoe Manufacturing")),
    ("internet", "Internet & Plattformen", "FDN",
     "META GOOGL GOOG AMZN NFLX RDDT SNAP PINS DASH UBER LYFT ABNB BKNG EXPE SPOT ETSY EBAY CHWY DUOL CART",
     ()),
    ("china", "China-Tech", "KWEB",
     "BABA PDD JD BIDU NTES TCOM BILI LI NIO XPEV TME FUTU BEKE IQ VIPS ZK HSAI PONY WRD",
     ()),
    ("robotics", "Robotik & Automation", "BOTZ",
     "ISRG SYM TER ROK SERV RR PDYN ZBRA CGNX PRCT KSCP",
     ()),
    ("transport", "Transport & Logistik", "IYT", "",
     ("Trucking Freight/Courier Services", "Railroads", "Air Freight/Delivery Services", "Marine Transportation",
      "Integrated Freight & Logistics")),
    ("airlines", "Airlines & Reisen", "JETS",
     "DAL UAL AAL LUV ALK JBLU SKYW ULCC CCL RCL NCLH VIK",
     ()),
]
STATUS_DE = {"lead": "Führend", "build": "Aufbau", "weak": "Schwach", "none": "keine Daten"}


def theme_etfs() -> list[str]:
    return [t[2] for t in THEMES]


def mapping(groups: dict | None, symbols) -> dict[str, list[str]]:
    """{Symbol: [Themen-Keys]} — feste Listen zuerst, dann Branche."""
    by_ind: dict[str, list[str]] = {}
    for key, _n, _e, _s, inds in THEMES:
        for i in inds:
            by_ind.setdefault(i, []).append(key)
    fixed: dict[str, list[str]] = {}
    for key, _n, _e, syms, _i in THEMES:
        for s in syms.split():
            fixed.setdefault(s, []).append(key)
    out = {}
    for s in symbols:
        keys = list(fixed.get(s, []))
        ind = (groups or {}).get(s, {}).get("industry")
        for k in by_ind.get(ind, []):
            if k not in keys:
                keys.append(k)
        if keys:
            out[s] = keys
    return out


def _etf_stats(g: pd.DataFrame) -> dict | None:
    g = g.sort_values("date")
    if len(g) < 60:
        return None
    c = g["close"].reset_index(drop=True)
    h = g["high"].reset_index(drop=True)
    last = float(c.iloc[-1])
    e21 = c.ewm(span=21, adjust=False).mean()
    s50 = c.rolling(50).mean()
    slope50 = float(s50.iloc[-1] / s50.iloc[-11] - 1) * 100 if len(c) >= 61 else np.nan
    p = lambda n: float((last / c.iloc[-1 - n] - 1) * 100) if len(c) > n else None
    from_high = float((last / h.iloc[-252:].max() - 1) * 100)
    above21, above50 = last > e21.iloc[-1], last > s50.iloc[-1]
    p3m = p(63)
    if above21 and above50 and slope50 > 0 and from_high >= -8 and (p3m or 0) > 0:
        st = "lead"
    elif not above50 and (slope50 < 0 or not above21):
        st = "weak"
    else:
        st = "build"
    return {"close": round(last, 2), "p1w": p(5), "p1m": p(21), "p3m": p3m, "p6m": p(126),
            "from_high": round(from_high, 1), "above21": bool(above21), "above50": bool(above50),
            "slope50": round(slope50, 2) if pd.notna(slope50) else None, "status": st}


def theme_table(df: pd.DataFrame, groups: dict | None, stocks: pd.DataFrame | None = None) -> tuple[list[dict], dict]:
    """Liefert (Themenliste sortiert nach Rang, {Symbol: [Themen-Keys]})."""
    etfs = set(theme_etfs())
    sub = df[df["symbol"].isin(etfs)]
    by = {s: g for s, g in sub.groupby("symbol")}
    tmap = mapping(groups, df["symbol"].unique())
    rows = []
    for key, name, etf, _s, _i in THEMES:
        st = _etf_stats(by[etf]) if etf in by else None
        mem = [s for s, ks in tmap.items() if key in ks and s not in etfs]
        r = {"key": key, "name": name, "etf": etf, **(st or {"status": "none"})}
        r["status_de"] = STATUS_DE[r["status"]]
        if stocks is not None and mem:
            m = stocks.loc[[s for s in mem if s in stocks.index]]
            r["n"] = int(len(m))
            r["m_p1m"] = float(m["p1m"].median()) if len(m) else None
            r["breadth50"] = float(m["above50"].mean() * 100) if len(m) else None
            lead = m[(m.get("rs_rating", pd.Series(0, index=m.index)).fillna(0) >= 80) & (m["from_high"] >= -10)]
            r["leaders"] = int(len(lead))
        else:
            r["n"], r["leaders"] = 0, 0
        rows.append(r)
    # Rang aus 1W + 1M + 3M (Perzentile), nur Themen mit ETF-Daten
    fr = pd.DataFrame(rows).set_index("key")
    ok = fr["status"] != "none"
    if ok.any():
        sc = sum(fr.loc[ok, k].astype(float).rank(pct=True) for k in ("p1w", "p1m", "p3m")) / 3
        fr.loc[ok, "rank"] = sc.rank(ascending=False, method="min")
    order = {"lead": 0, "build": 1, "weak": 2, "none": 3}
    out = sorted(fr.reset_index().to_dict("records"),
                 key=lambda r: (order[r["status"]], r.get("rank") if pd.notna(r.get("rank")) else 999))
    for r in out:
        for k, v in list(r.items()):
            if isinstance(v, float) and not np.isfinite(v):
                r[k] = None
            elif isinstance(v, float):
                r[k] = round(v, 2)
        if r.get("rank") is not None:
            r["rank"] = int(r["rank"])
    return out, tmap

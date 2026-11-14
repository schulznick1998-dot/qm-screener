"""Scan-Parameter. Identisch zu qm_setup_scanner.pine und zum Backtest.

Änderungen per settings.json im Programmordner, z. B.: {"min_adr_pct": 5}
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, fields


@dataclass
class Params:
    # Scan
    min_price: float = 5.0
    min_dollar_vol: float = 10e6        # Ø 20 Tage Close*Volumen in $
    min_adr_pct: float = 4.0
    min_avg_volume: float = 0.0         # Ø Stückvolumen 30 Tage (0 = aus)
    require_above_ema21: bool = False
    require_above_ema50: bool = False
    min_market_cap: float = 0.0         # $ (0 = aus)
    only_stocks: bool = True            # ETFs/Fonds ausblenden (= nicht bei der SEC gemeldet)
    min_rs_rating: float = 0.0          # 1–99 (0 = aus)
    max_from_high_pct: float = 100.0    # max. % unter dem 52-Wochen-Hoch (100 = aus)
    min_rvol: float = 0.0               # Volumen heute / Ø 50 Tage (0 = aus)
    require_rs_new_high: bool = False   # RS-Linie auf 52-Wochen-Hoch
    require_trend_template: bool = False  # Minervini-Trend-Template
    require_ep: bool = False            # Episodic Pivot heute
    ep_min_gap_pct: float = 10.0
    ep_min_rvol: float = 3.0
    ep_lookback_days: int = 1           # EP heute (1) oder in den letzten X Tagen
    require_base: bool = False          # Base-Mindestlänge/-tiefe als Pflichtfilter (sonst nur Setup-Regel)
    min_base_depth_pct: float = 0.0     # Korrektur in der Base mindestens % (nur mit require_base)
    max_market_cap: float = 0.0         # $ (0 = aus)
    # Eigene Muster
    require_ma_reclaim: bool = False    # zwei Tagesschlüsse in Folge über EMA 20, davor darunter
    reclaim_days: int = 2
    max_stop_adr: float = 0.0           # Abstand Kurs → Tief der ersten Kerze über dem 20er, in × ADR (0 = aus)
    require_power_play: bool = False    # Kurs in ≤ pp_max_days verdoppelt, danach enge Flagge
    pp_min_gain_pct: float = 100.0
    pp_max_days: int = 40
    pp_max_flag_pct: float = 25.0
    require_stage2: bool = False        # 200er dreht gerade nach oben + Kurs nahe 6-Monats-Hoch
    min_rev_yoy: float = 0.0            # Umsatzwachstum zum Vorjahresquartal mind. % (0 = aus, braucht SEC)
    require_rev_accel: bool = False     # Umsatzwachstum beschleunigt sich
    td_sectors: int = 0                 # Top-down-Trichter: beste X Sektoren (0 = aus)
    td_industries: int = 3              # … darin je beste Y Branchen
    td_stocks: int = 5                  # … darin je beste Z Aktien
    require_breakout_today: bool = False  # Abend-Einstieg: gestern Base, heute Schluss über dem Pivot
    bo_min_close_pos: float = 0.75      # Schluss im oberen Teil der Tageskerze (0,75 = oberes Viertel)
    bo_max_over_adr: float = 1.0        # Schluss höchstens X ADR über dem Pivot
    min_gap_pct: float = 0.0            # Gap heute: Eröffnung 15:30 vs. gestriger Schluss, mind. % (0 = aus)
    min_chg_open_pct: float = -100.0    # Kurs seit Eröffnung mind. % (-100 = aus)
    require_above_sma50_f: bool = False # Filter: Kurs über SMA 50
    require_sma50_rising: bool = False  # Filter: SMA 50 steigt (höher als vor 10 Tagen)
    min_pm_gap_pct: float = 0.0         # vorbörsliches Gap: letzter Vorbörsenkurs vs. gestriger Schluss, mind. % (0 = aus)
    min_pm_volume: float = 0.0          # vorbörsliches Volumen mind. Stück (0 = aus)
    gap_short: bool = False             # Short-Seite für Gap-, EP- und SMA-50-Filter
    ep_min_days_ago: int = 0            # EP frühestens vor X Tagen (Delayed EP, 0 = auch heute)
    require_ep_hold: bool = False       # Kurs hält das Tief des Gap-Tages
    max_ep_from_high_pct: float = 0.0   # Kurs höchstens X % unter dem Hoch seit dem Gap (0 = aus)
    max_ipo_days: int = 0               # Börsengang vor höchstens X Handelstagen (0 = aus)
    min_ipo_days: int = 0               # … und vor mindestens X Handelstagen
    min_rel_1m: float = -100.0          # 1-Monats-Performance mind. X Prozentpunkte besser als der Marktampel-Index (-100 = aus)
    max_rs_line_from_high: float = 0.0  # RS-Linie höchstens X % unter ihrem 52W-Hoch (0 = aus)
    min_adr60_pct: float = 0.0          # ADR über 60 Tage mind. % (normale Lebhaftigkeit, enge Bases drücken sie kaum)
    require_tight_d: bool = False       # Enge Base Daily
    tb_prior_min: float = 0.20          # … Vorlauf mind. (Anteil) in den 3 Monaten vor dem Base-Hoch
    tb_min_days: int = 5                # … Base mind. Handelstage (5 = auch Flaggen)
    tb_max_days: int = 40               # … Base max. Handelstage
    tb_max_depth: float = 0.35          # … Base max. tief (Anteil)
    tb_tight_days: int = 5              # … rechte Seite: letzte X Tage
    tb_tight_mult: float = 2.5          # … rechte Seite: Spanne max. X × ADR60
    tb_max_to_pivot: float = 10.0        # … Kurs max. % unter dem Base-Hoch
    require_tight_w: bool = False       # Enge Base Weekly
    tw_prior_min: float = 0.30          # … Vorlauf mind. (Anteil) im Jahr vor dem Base-Hoch
    tw_min_weeks: int = 3               # … Base mind. Wochen
    tw_max_weeks: int = 15              # … Base max. Wochen
    tw_max_depth: float = 0.30          # … Base max. tief (Anteil)
    tw_tight_weeks: int = 3             # … letzte X Wochenschlüsse
    tw_close_pct: float = 5.0           # … innerhalb von max. X %
    tw_max_below: float = 12.0          # … Kurs max. X % unter dem Base-Hoch (oberer Teil der Base)
    tw_contract: float = 0.80           # … Spanne der engen Wochen max. X × Base-Tiefe (wird ruhiger)
    max_industry_rank: int = 0          # nur Aktien aus den Top-X Branchen (1-Monats-Performance), 0 = aus
    mom_windows: tuple = (22, 65, 126)  # 1M / 3M / 6M, gemessen vom tiefsten Tief
    mom_top_pct: float = 0.07           # Top 7 % in mind. einem Fenster
    # Setup
    base_lookback: int = 60
    base_high_tol: float = 0.015
    base_min_days: int = 10
    base_max_days: int = 40
    prior_move_min: float = 0.30
    prior_move_lookback: int = 65
    base_max_depth: float = 0.30
    require_higher_lows: bool = True
    tight_days: int = 5
    tight_max_adr_mult: float = 2.0
    vol_dry_ratio: float = 0.85
    max_ext_adr_mult: float = 2.0
    require_above_sma50: bool = True
    require_ema10_above_ema20: bool = True
    # Daten
    benchmark: str = "QQQ"
    rs_benchmark: str = "SPY"           # Vergleich für RS-Linie (wie IBD/MarketSmith: S&P 500)
    history_days: int = 480             # Kalendertage, die geladen werden
    include_today_partial: bool = False # laufende Tageskerze während der Börsenzeit mitnehmen?
    exchanges: tuple = ("NYSE", "NASDAQ", "ARCA", "AMEX", "BATS")
    # Fundamentals
    fundamentals_max: int = 80          # max. Anzahl Aktien, für die SEC-Daten geladen werden
    fundamentals_cache_days: int = 3
    # Oberfläche
    ui_only_setups: bool = False        # Häkchen "nur Setups" nach dem Scan

    def to_dict(self):
        return asdict(self)


def load_params(folder: str) -> Params:
    p = Params()
    path = os.path.join(folder, "settings.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        names = {f.name for f in fields(Params)}
        for k, v in data.items():
            if k not in names:
                raise ValueError(f"settings.json: unbekannter Parameter '{k}'")
            if isinstance(getattr(p, k), tuple):
                v = tuple(v)
            setattr(p, k, v)
    return p


# Beschriftung für das Einstellungs-Fenster: (Feld, Gruppe, Label, Einheit, Anzeigefaktor, Schrittweite, Erklärung)
SETTINGS_META = [
    ("min_price", "1 · Grundfilter", "Mindestkurs", "$", 1, 1, "Penny-Stocks ausschließen"),
    ("min_dollar_vol", "1 · Grundfilter", "Ø Dollar-Volumen (20 T)", "Mio. $", 1e-6, 1, "Liquidität. Faustregel: Konto × 50–100"),
    ("min_adr_pct", "1 · Grundfilter", "Mindest-ADR", "%", 1, 0.5, "Durchschnittliche Tagesspanne. Langsame Aktien raus"),
    ("min_avg_volume", "1 · Grundfilter", "Ø Volumen (30 T)", "Tsd. Stück", 1e-3, 50, "Stückzahl, nicht Dollar. 0 = aus"),
    ("require_above_ema21", "1 · Grundfilter", "Kurs über EMA 21", "", 1, None, ""),
    ("require_above_ema50", "1 · Grundfilter", "Kurs über EMA 50", "", 1, None, ""),
    ("min_market_cap", "1 · Grundfilter", "Marktkapitalisierung mindestens", "Mio. $", 1e-6, 50, "0 = aus. Aktien ohne Angabe fliegen dann raus"),
    ("only_stocks", "1 · Grundfilter", "Nur Aktien (ETFs/Fonds ausblenden)", "", 1, None, "Braucht SEC_USER_AGENT"),
    ("max_market_cap", "1 · Grundfilter", "Marktkapitalisierung höchstens", "Mio. $", 1e-6, 500, "0 = aus. Kleine/mittlere Firmen haben mehr Luft nach oben"),
    ("mom_top_pct", "2 · Momentum", "Top-Anteil", "%", 100, 1, "Top X % beim Anstieg vom 1/3/6-Monats-Tief"),
    ("min_rs_rating", "2 · Momentum", "RS-Rating mindestens", "1–99", 1, 1, "0 = aus. Gewichtete 12-Monats-Performance gegen alle Aktien"),
    ("require_rs_new_high", "2 · Momentum", "RS-Linie auf 52-Wochen-Hoch", "", 1, None, "Kurs ÷ S&P 500 auf Jahreshoch"),
    ("max_from_high_pct", "2 · Momentum", "Max. unter 52-Wochen-Hoch", "%", 1, 5, "100 = aus"),
    ("require_trend_template", "2 · Momentum", "Minervini-Trend-Template", "", 1, None, "Kurs > 50 > 150 > 200, 200er steigend, ≥ 30 % über Tief, ≤ 25 % unter Hoch, RS ≥ 70"),
    ("require_ep", "3 · Episodic Pivot / Volumen", "Nur Episodic Pivots (heute)", "", 1, None, "Gap + Volumen-Explosion"),
    ("ep_min_gap_pct", "3 · Episodic Pivot / Volumen", "Gap mindestens", "%", 1, 1, ""),
    ("ep_min_rvol", "3 · Episodic Pivot / Volumen", "Volumen mindestens", "× Ø 50 T", 1, 0.5, ""),
    ("ep_lookback_days", "3 · Episodic Pivot / Volumen", "EP in den letzten", "Tagen", 1, 1, "1 = nur heute. 5 = ganze Woche, gut fürs Wochenende"),
    ("min_rvol", "3 · Episodic Pivot / Volumen", "RVOL mindestens (alle Scans)", "×", 1, 0.5, "Volumen heute ÷ Ø 50 Tage. 0 = aus"),
    ("min_rev_yoy", "3 · Episodic Pivot / Volumen", "Umsatzwachstum mindestens", "% YoY", 1, 5, "0 = aus. Nur Aktien mit SEC-Daten bleiben übrig"),
    ("require_rev_accel", "3 · Episodic Pivot / Volumen", "Umsatzwachstum beschleunigt", "", 1, None, "Letztes Quartal stärker als das davor"),
    ("td_sectors", "7 · Top-down-Trichter", "Beste Sektoren", "Anzahl", 1, 1, "0 = Trichter aus. Rang aus 1 Woche + 1 Monat"),
    ("td_industries", "7 · Top-down-Trichter", "… je beste Branchen", "Anzahl", 1, 1, "Nur Branchen mit mind. 5 Aktien"),
    ("td_stocks", "7 · Top-down-Trichter", "… je beste Aktien", "Anzahl", 1, 1, "Nach RS-Rating, dann Nähe zum 52W-Hoch"),
    ("max_industry_rank", "2 · Momentum", "Nur Top-X Branchen", "Rang", 1, 5, "Rang aus 1 Woche + 1 Monat, Branchen ab 5 Aktien. 0 = aus. Top-down wie im Sektor-Video"),
    ("min_adr60_pct", "1 · Grundfilter", "ADR über 60 Tage mindestens", "%", 1, 0.5, "Normale Lebhaftigkeit. Anders als die 20-Tage-ADR drückt eine enge Base sie kaum. 0 = aus"),
    ("require_tight_d", "10 · Enge Base", "Enge Base Daily", "", 1, None, "Vorlauf, Base 2–8 Wochen, enger werdend, rechts eng, Volumen trocken, über steigendem 20er/50er"),
    ("tb_prior_min", "10 · Enge Base", "Daily: Vorlauf mindestens", "%", 100, 5, "Anstieg in den 3 Monaten vor dem Base-Hoch"),
    ("tb_min_days", "10 · Enge Base", "Daily: Base mindestens", "Tage", 1, 1, "5 = auch kurze Flaggen nach einem starken Move"),
    ("tb_max_days", "10 · Enge Base", "Daily: Base höchstens", "Tage", 1, 1, "40 ≈ 8 Wochen"),
    ("tb_max_depth", "10 · Enge Base", "Daily: Base höchstens tief", "%", 100, 1, ""),
    ("tb_tight_days", "10 · Enge Base", "Daily: rechte Seite = letzte", "Tage", 1, 1, ""),
    ("tb_tight_mult", "10 · Enge Base", "Daily: rechte Seite max.", "× ADR60", 1, 0.1, "2 = Spanne der letzten Tage höchstens 2 normale Tagesspannen (Qullamaggie)"),
    ("tb_max_to_pivot", "10 · Enge Base", "Daily: max. unter Base-Hoch", "%", 1, 0.5, ""),
    ("require_tight_w", "10 · Enge Base", "Enge Base Weekly", "", 1, None, "Vorlauf, Base 3–15 Wochen, enge Wochenschlüsse, über steigender 10/30-Wochen-Linie"),
    ("tw_prior_min", "10 · Enge Base", "Weekly: Vorlauf mindestens", "%", 100, 5, "Anstieg im Jahr vor dem Base-Hoch"),
    ("tw_min_weeks", "10 · Enge Base", "Weekly: Base mindestens", "Wochen", 1, 1, ""),
    ("tw_max_weeks", "10 · Enge Base", "Weekly: Base höchstens", "Wochen", 1, 1, ""),
    ("tw_max_depth", "10 · Enge Base", "Weekly: Base höchstens tief", "%", 100, 1, ""),
    ("tw_tight_weeks", "10 · Enge Base", "Weekly: enge Wochenschlüsse", "Wochen", 1, 1, "2 = zwei enge Wochen, 3 = „3 Wochen eng“ (O'Neil, strenger)"),
    ("tw_close_pct", "10 · Enge Base", "Weekly: Schlüsse innerhalb", "%", 1, 0.5, ""),
    ("tw_max_below", "10 · Enge Base", "Weekly: max. unter Base-Hoch", "%", 1, 1, "Kurs im oberen Teil der Base, nah am Widerstand"),
    ("tw_contract", "10 · Enge Base", "Weekly: Spanne enge Wochen max.", "% der Tiefe", 100, 5, "Hoch-Tief der engen Wochen im Verhältnis zur Base-Tiefe. Kleiner = Base wird ruhiger (Kontraktion)"),
    ("gap_short", "9 · Gap & Vorbörse", "Short-Seite (Gaps nach unten)", "", 1, None, "Dreht Gap, seit Eröffnung, Vorbörse, EP und SMA-50-Filter um: Gap ≤ −X %, unter fallendem SMA 50"),
    ("ep_min_days_ago", "3 · Episodic Pivot / Volumen", "EP frühestens vor", "Tagen", 1, 1, "Delayed EP: 3 = Gap liegt mind. 3 Tage zurück. 0 = auch heute"),
    ("require_ep_hold", "3 · Episodic Pivot / Volumen", "Kurs hält Tief des Gap-Tages", "", 1, None, "Gap wurde seitdem nicht abverkauft"),
    ("max_ep_from_high_pct", "3 · Episodic Pivot / Volumen", "Max. unter Hoch seit dem Gap", "%", 1, 1, "Enge Flagge nahe am Hoch. 0 = aus"),
    ("max_ipo_days", "6 · Eigene Muster", "Börsengang vor höchstens", "Handelstagen", 1, 10, "250 ≈ 1 Jahr. Daten reichen gut 1 Jahr zurück. 0 = aus"),
    ("min_ipo_days", "6 · Eigene Muster", "Börsengang vor mindestens", "Handelstagen", 1, 5, "Zeit für eine erste Base, z. B. 40"),
    ("min_rel_1m", "2 · Momentum", "1 Monat besser als Index um", "%-Punkte", 1, 1, "Performance minus QQQ (Marktampel-Index). -100 = aus"),
    ("max_rs_line_from_high", "2 · Momentum", "RS-Linie max. unter 52W-Hoch", "%", 1, 1, "Kurs ÷ S&P 500 nahe Jahreshoch. 0 = aus"),
    ("min_gap_pct", "9 · Gap & Vorbörse", "Gap heute mindestens", "%", 1, 1, "Eröffnung 15:30 ggü. gestrigem Schluss. Braucht laufende Tageskerze. 0 = aus"),
    ("min_chg_open_pct", "9 · Gap & Vorbörse", "Kurs seit Eröffnung mindestens", "%", 1, 0.5, "Gap wird gehalten, nicht abverkauft. -100 = aus"),
    ("min_pm_gap_pct", "9 · Gap & Vorbörse", "Vorbörsliches Gap mindestens", "%", 1, 1, "Letzter Vorbörsenkurs ggü. gestrigem Schluss (15 Min. verzögert). 0 = aus"),
    ("min_pm_volume", "9 · Gap & Vorbörse", "Vorbörsliches Volumen mindestens", "Tsd. Stück", 1e-3, 50, "Seit 10:00 Uhr deutscher Zeit gehandelte Stücke. 0 = aus"),
    ("require_above_sma50_f", "1 · Grundfilter", "Kurs über SMA 50", "", 1, None, "Einfacher 50-Tage-Durchschnitt"),
    ("require_sma50_rising", "1 · Grundfilter", "SMA 50 steigt", "", 1, None, "Höher als vor 10 Tagen. Kann TradingView nicht filtern"),
    ("require_breakout_today", "8 · Abend-Einstieg", "Ausbruch heute", "", 1, None, "Gestern Base mit Pivot, heute Schluss darüber (Setup D)"),
    ("bo_min_close_pos", "8 · Abend-Einstieg", "Schluss im oberen Teil der Kerze", "%", 100, 5, "75 = oberes Viertel der Tagesspanne"),
    ("bo_max_over_adr", "8 · Abend-Einstieg", "Schluss höchstens über Pivot", "× ADR", 1, 0.25, "Nicht hinterherlaufen: 1 = max. eine Tagesspanne"),
    ("require_ma_reclaim", "6 · Eigene Muster", "20er-Rückeroberung", "", 1, None, "Zwei Tagesschlüsse in Folge über EMA 20, davor darunter"),
    ("reclaim_days", "6 · Eigene Muster", "Schlüsse über dem 20er", "Tage", 1, 1, "Dein Trigger: 2"),
    ("max_stop_adr", "6 · Eigene Muster", "Stop-Abstand höchstens", "× ADR", 1, 0.25, "Kurs → Tief der ersten Kerze über dem 20er. 0 = aus"),
    ("require_power_play", "6 · Eigene Muster", "Power Play / High Tight Flag", "", 1, None, "Verdoppelung, dann enge Flagge"),
    ("pp_min_gain_pct", "6 · Eigene Muster", "Power Play: Anstieg mindestens", "%", 1, 10, ""),
    ("pp_max_days", "6 · Eigene Muster", "Power Play: in höchstens", "Tagen", 1, 5, "40 ≈ 8 Wochen"),
    ("pp_max_flag_pct", "6 · Eigene Muster", "Power Play: Flagge höchstens tief", "%", 1, 5, ""),
    ("require_stage2", "6 · Eigene Muster", "Früher Stage-2-Start", "", 1, None, "200er dreht gerade nach oben, Kurs nahe 6-Monats-Hoch"),
    ("require_base", "4 · Setup", "Base als Pflichtfilter", "", 1, None, "Aktien ohne Base (frisches Hoch) fliegen raus, statt nur „offen“ zu sein"),
    ("min_base_depth_pct", "4 · Setup", "Korrektur in der Base mindestens", "%", 1, 1, "Nur mit Pflichtfilter. Mindest-Rücksetzer vom Base-Hoch"),
    ("prior_move_min", "4 · Setup", "Vorlauf mindestens", "%", 100, 5, "Anstieg vor der Base"),
    ("base_min_days", "4 · Setup", "Base mindestens", "Tage", 1, 1, "≈ 2 Wochen"),
    ("base_max_days", "4 · Setup", "Base höchstens", "Tage", 1, 1, "≈ 8 Wochen"),
    ("base_max_depth", "4 · Setup", "Base höchstens tief", "%", 100, 5, "Rücksetzer vom Base-Hoch"),
    ("require_higher_lows", "4 · Setup", "Höhere Tiefs verlangen", "", 1, None, "Tief 2. Base-Hälfte ≥ 1. Hälfte"),
    ("tight_days", "4 · Setup", "Enge: letzte Tage", "Tage", 1, 1, "Zeitraum für Enge und Pivot"),
    ("tight_max_adr_mult", "4 · Setup", "Enge: Range höchstens", "× ADR", 1, 0.1, "Je kleiner, desto enger"),
    ("vol_dry_ratio", "4 · Setup", "Volumen höchstens", "% vom Ø 50 T", 100, 5, "Volumen trocknet aus"),
    ("max_ext_adr_mult", "4 · Setup", "Max. Abstand über 20er", "× ADR", 1, 0.5, "10er/20er müssen aufgeholt haben"),
    ("require_above_sma50", "4 · Setup", "Über SMA 50", "", 1, None, ""),
    ("require_ema10_above_ema20", "4 · Setup", "EMA 10 über EMA 20", "", 1, None, ""),
    ("benchmark", "5 · Daten", "Marktampel-Index", "", 1, None, "QQQ ≈ NASDAQ"),
    ("rs_benchmark", "5 · Daten", "RS-Vergleichsindex", "", 1, None, "SPY ≈ S&P 500"),
    ("include_today_partial", "5 · Daten", "Laufende Tageskerze mitnehmen", "", 1, None, "Aus = nur abgeschlossene Tage (empfohlen)"),
    ("ui_only_setups", "5 · Daten", "Nach dem Scan nur Setups zeigen", "", 1, None, "Aus = alle Treffer der Filter"),
    ("fundamentals_max", "5 · Daten", "Fundamentals laden für", "Aktien", 1, 10, "Die besten N Kandidaten"),
]


# Vorlagen. Nicht genannte Werte = Standard (Qullamaggie).
PRESETS = {
    "qullamaggie": {
        "label": "Qullamaggie",
        "desc": "Top 7 % Momentum, ADR ≥ 4 %, ≥ 10 Mio. $ Volumen, volle Setup-Prüfung",
        "values": {},
        "explain": [
            ("Wofür", "Der klassische Breakout-Scan von Qullamaggie: die stärksten Aktien des Marktes, die nach einem großen Anstieg eine enge Base bilden."),
            ("Filter", "Top 7 % beim Anstieg vom 1-, 3- oder 6-Monats-Tief (Rang gegen alle Aktien), ADR ≥ 4 %, Ø Dollar-Volumen ≥ 10 Mio. $, Kurs ≥ 5 $."),
            ("Setup-Prüfung", "Base 10–40 Tage, Vorlauf ≥ 30 %, Base ≤ 30 % tief, höhere Tiefs, letzte 5 Tage eng, Volumen trocknet aus, Kurs nah am 20er, über SMA 50."),
            ("Einstieg", "Am nächsten Tag über dem Opening-Range-High, wenn der Kurs den Pivot bricht. Stop am Tagestief, max. 1 ADR."),
            ("Gut zu wissen", "Status „Setup“ = alle Regeln erfüllt. „x offen“ = Kandidat für die Watchlist, es fehlt noch etwas (Maus über den Status zeigt was)."),
        ],
    },
    "ma_reclaim": {
        "label": "20er-Rückeroberung",
        "desc": "Dein Einstieg: starke Aktie war unter dem 20er, schließt jetzt 2 Tage in Folge darüber. Enger Stop.",
        "values": {"min_price": 5.0, "min_dollar_vol": 5e6, "min_adr_pct": 2.5, "mom_top_pct": 1.0,
                   "min_rs_rating": 80.0, "require_ma_reclaim": True, "reclaim_days": 2, "max_stop_adr": 1.0,
                   "require_above_ema50": True},
        "explain": [
            ("Wofür", "Dein eigenes Regelwerk als Scan: Rücksetzer in einem Aufwärtstrend, der gerade wieder dreht. Liefert jeden Tag genau die Aktien, bei denen dein Trigger auslöst."),
            ("Filter", "Kurs war unter dem EMA 20 und hat jetzt 2 Tage in Folge darüber geschlossen. RS-Rating ≥ 80 und Kurs über EMA 50: der Rücksetzer passiert in einer starken Aktie, nicht in einem toten Titel."),
            ("Stop", "Unter dem Tief der ersten Kerze, die über dem 20er geschlossen hat. Der Scan lässt nur Aktien durch, bei denen dieser Abstand ≤ 1 ADR ist. Ein enger Stop heißt: läuft der Trade, wird er schnell 5R, 10R, 20R."),
            ("Spalten", "Im Tab „Setup“ steht „Stop-Abst.“ = Abstand zum Stop in % und in × ADR."),
            ("Gut zu wissen", "Bei Aktien mit 4–6 % ADR löst ein Stop unter jeder Tageskerze oft schon durch normales Rauschen aus. Qullamaggie zieht deshalb über Schlusskurs unter dem 10er/20er nach."),
        ],
    },
    "ath_breakout": {
        "label": "52W-Hoch-Ausbruch",
        "desc": "≤ 5 % unter dem 52-Wochen-Hoch, RS ≥ 80, Base ≥ 4 Wochen. Hier starten die meisten Home Runs.",
        "values": {"min_price": 5.0, "min_dollar_vol": 10e6, "min_adr_pct": 3.0, "mom_top_pct": 1.0,
                   "min_rs_rating": 80.0, "max_from_high_pct": 5.0, "base_min_days": 20, "base_max_days": 59,
                   "prior_move_min": 0.2, "require_base": True, "min_base_depth_pct": 8.0},
        "explain": [
            ("Wofür", "Die meisten großen Läufe starten auf neuen Hochs: Darüber gibt es niemanden mehr, der „endlich raus“ will, also keinen Verkaufsdruck von oben."),
            ("Filter", "Kurs ≤ 5 % unter dem 52-Wochen-Hoch, RS-Rating ≥ 80, ADR ≥ 3 %, Ø Dollar-Volumen ≥ 10 Mio. $."),
            ("Pflicht-Base", "Nur Aktien mit einer echten Base: mindestens 20 Tage (≈ 4 Wochen) seit dem Base-Hoch und mindestens 8 % Korrektur darin. Aktien, die einfach nur frische Hochs machen, fliegen raus."),
            ("Setup-Prüfung", "Vorlauf ≥ 20 %, Rest wie bei Qullamaggie. „Setup“ = enge Base direkt unter dem Hoch, bereit zum Ausbruch."),
            ("Achte auf", "RS-Linie „Hoch vor Kurs“: Die Aktie ist relativ zum Markt schon auf neuem Hoch, der Kurs noch nicht. Das sind oft die stärksten Ausbrüche."),
            ("Gut zu wissen", "„52-Wochen-Hoch“, nicht Allzeithoch: Die Daten reichen gut ein Jahr zurück."),
        ],
    },
    "power_play": {
        "label": "Power Play",
        "desc": "Kurs hat sich in ≤ 8 Wochen verdoppelt und konsolidiert nur 10–25 % in einer engen Flagge.",
        "values": {"min_price": 5.0, "min_dollar_vol": 5e6, "min_adr_pct": 0.0, "mom_top_pct": 1.0,
                   "require_power_play": True},
        "explain": [
            ("Wofür", "Das seltenste und stärkste Muster (High Tight Flag): Eine Aktie verdoppelt sich in wenigen Wochen, meist wegen eines fundamentalen Auslösers, und gibt danach kaum etwas ab. Aus genau diesen werden oft die 300–500 %-Läufe."),
            ("Filter", "Anstieg ≥ 100 % innerhalb von höchstens 40 Handelstagen (≈ 8 Wochen), irgendwann in den letzten 3 Monaten. Kurs heute höchstens 25 % unter dem Hoch danach. Ø Dollar-Volumen ≥ 5 Mio. $."),
            ("Einstieg", "Ausbruch aus der Flagge über deren Hoch, idealerweise mit Volumen. Stop unter das Flaggen-Tief bzw. Tagestief."),
            ("Gut zu wissen", "Wenige Treffer, oft 0–5 pro Tag. Das ist normal. Die Spalte „PP-Anstieg“ (Tab Momentum) zeigt den Anstieg."),
        ],
    },
    "ep_growth": {
        "label": "EP + Wachstum",
        "desc": "Episodic Pivot mit echtem Auslöser: Gap ≥ 10 %, Umsatz ≥ 25 % und beschleunigend, 300 Mio. – 10 Mrd. $.",
        "values": {"min_price": 5.0, "min_dollar_vol": 5e6, "min_adr_pct": 0.0, "mom_top_pct": 1.0,
                   "require_ep": True, "min_market_cap": 300e6, "max_market_cap": 10e9,
                   "min_rev_yoy": 25.0, "require_rev_accel": True, "ep_lookback_days": 5},
        "explain": [
            ("Wofür", "Die Gap-Strategie nur mit Aktien, die einen echten fundamentalen Grund haben. Kleine und mittlere Firmen mit Wachstumssprung haben am meisten Luft nach oben."),
            ("Filter", "Gap ≥ 10 % mit ≥ 3× Durchschnittsvolumen in den letzten 5 Handelstagen, Marktkapitalisierung 300 Mio. – 10 Mrd. $, Umsatz ≥ 25 % über dem Vorjahresquartal und stärker gewachsen als im Quartal davor."),
            ("Einstieg", "Day-2 bis Day-5: Ausbruch über das Hoch des Gap-Tages oder enge Konsolidierung danach. Spalte „Gap“ zeigt, vor wie vielen Tagen der Gap war."),
            ("Wann scannen", "Nach Börsenschluss für Day-2-Einstiege, oder ab ca. 15:45 Uhr deutscher Zeit mit eingeschalteter „laufender Tageskerze“."),
            ("Gut zu wissen", "Sehr strenger Scan, 0–3 Treffer pro Woche sind normal. Umsatzdaten kommen aus den SEC-Meldungen. Ausländische Firmen ohne SEC-Quartalsberichte fallen raus. Ohne SEC_USER_AGENT in .env bleibt die Liste leer."),
        ],
    },
    "stage2": {
        "label": "Stage-2-Start",
        "desc": "Lange Seitwärtsphase vorbei: 200er dreht gerade nach oben, Kurs nahe 6-Monats-Hoch.",
        "values": {"min_price": 5.0, "min_dollar_vol": 5e6, "min_adr_pct": 2.0, "mom_top_pct": 1.0,
                   "require_stage2": True},
        "explain": [
            ("Wofür", "Findet Aktien am Anfang eines Mehrmonatstrends, nicht erst in der Mitte. Stage 2 (nach Stan Weinstein) = die Aufwärtsphase nach einer langen Bodenbildung."),
            ("Filter", "SMA 200 steigt seit 1 Monat, war vor 3 Monaten aber noch flach oder fallend (gerade gedreht). Kurs über SMA 50 und SMA 50 über SMA 200. Kurs höchstens 5 % unter dem 6-Monats-Hoch, also am Ausbruch."),
            ("Achte auf", "Volumen beim Ausbruch (Spalte RVOL) und ob die RS-Linie mitsteigt."),
            ("Gut zu wissen", "Braucht gut 1 Jahr Kursdaten. Junge Aktien (IPOs) erscheinen hier deshalb nicht."),
        ],
    },
    "topdown": {
        "archived": True,
        "label": "Top-down: Anführer",
        "desc": "Nur die 10 stärksten Branchen (1 Woche + 1 Monat), darin Aktien im sauberen Aufwärtstrend mit Momentum nahe dem 52W-Hoch.",
        "values": {"min_price": 5.0, "min_dollar_vol": 10e6, "min_adr_pct": 3.0, "mom_top_pct": 0.2,
                   "min_rs_rating": 80.0, "max_industry_rank": 10, "max_from_high_pct": 10.0,
                   "require_trend_template": True, "require_above_ema21": True},
        "explain": [
            ("Wofür", "Die Top-down-Methode aus dem Sektor-Video als fertiger Scan: erst die stärksten Gruppen, darin die Anführer. Wahrscheinlichkeiten stapeln statt zufällige Setups."),
            ("Gruppe", "Branche gehört zu den 10 stärksten, gemessen an 1 Woche UND 1 Monat zusammen (Median der Aktien, nur Branchen mit mind. 5 Aktien)."),
            ("Aktie", "RS-Rating ≥ 80, Top 20 % beim Anstieg über 1, 3 oder 6 Monate (die Aktie bewegt sich JETZT), Minervini-Trend-Template (Kurs > 50 > 150 > 200, 200er steigt), Kurs über EMA 21, ≤ 10 % unter dem 52W-Hoch, ADR ≥ 3 %, ≥ 10 Mio. $ Volumen."),
            ("Anführer", "Der Anführer einer Gruppe ist die Aktie, die zuerst neue Hochs macht. Nachzügler, die noch weit unter ihrem Hoch stehen, laufen meist schwächer."),
            ("Selbst durchklicken", "Tab „◆ Sektoren & Branchen“: Indizes → Sektoren → Branchen → Aktien, sortierbar nach 1 Woche / 1 / 3 / 6 Monaten. Achte auf Gruppen, die bei 1 Woche UND 1 Monat stark sind."),
            ("Gut zu wissen", "Die Einteilung kommt von Nasdaq (oder der SEC) und ist nicht identisch mit der von TradingView. Die Rangfolge der Gruppen ist aber vergleichbar."),
        ],
    },
    "trichter": {
        "label": "Top-down-Trichter",
        "desc": "Beste 3 Sektoren → je beste 3 Branchen → je beste 5 Aktien. Bis zu 45 Anführer, verteilt über den Markt.",
        "values": {"min_price": 5.0, "min_dollar_vol": 10e6, "min_adr_pct": 2.5, "mom_top_pct": 1.0,
                   "td_sectors": 3, "td_industries": 3, "td_stocks": 5, "require_above_ema50": True,
                   "max_from_high_pct": 25.0, "min_rs_rating": 70.0},
        "explain": [
            ("Wofür", "Die Top-down-Methode als Trichter: Markt → stärkste Sektoren → stärkste Branchen darin → die Anführer jeder Branche. Die Liste ist über mehrere starke Gruppen verteilt, statt dass eine heiße Branche alles belegt."),
            ("Sektoren & Branchen", "Rang aus 1 Woche UND 1 Monat zusammen (Median der Aktien). Branchen zählen nur ab 5 Aktien, damit keine Mini-Gruppe zufällig oben steht."),
            ("Aktien", "In jeder der 9 Branchen die bis zu 5 besten nach RS-Rating, bei Gleichstand die nähere am 52W-Hoch. Vorher aussortiert: RS-Rating < 70 (Nachzügler), Kurs < 5 $, < 10 Mio. $ Volumen, ADR < 2,5 %, unter EMA 50, mehr als 25 % unter dem 52W-Hoch."),
            ("Spalte „Trichter“", "z. B. „S1 · B2 · 3“ = Sektor Nr. 1, darin Branche Nr. 2, dort die drittbeste Aktie. Spaltenkopf anklicken sortiert die Liste genau in dieser Reihenfolge."),
            ("Anpassen", "Einstellungen → „7 · Top-down-Trichter“: Anzahl Sektoren, Branchen und Aktien frei wählbar, z. B. 2 × 3 × 3 für eine kurze Liste."),
            ("Gut zu wissen", "Das ist eine Watchlist der stärksten Aktien, nicht automatisch Kaufsignale. Kaufbar ist, was zusätzlich ein Setup hat (Status „Setup“ oder enge Base)."),
        ],
    },
    "rs_leader": {
        "label": "RS-Leader",
        "desc": "Die relativ stärksten Aktien des ganzen Marktes, ohne Sektorfilter: RS ≥ 95, nahe am 52W-Hoch, über EMA 21.",
        "values": {"min_price": 5.0, "min_dollar_vol": 10e6, "min_adr_pct": 2.5, "mom_top_pct": 1.0,
                   "min_rs_rating": 95.0, "max_from_high_pct": 15.0, "require_above_ema21": True},
        "explain": [
            ("Wofür", "Marktführer von unten nach oben: die einzelnen Aktien mit der stärksten relativen Stärke, egal aus welchem Sektor. Gegenstück zum Top-down-Trichter, der erst die Gruppe und dann die Aktie wählt. Findet auch Einzelläufer (z. B. Biotech mit News), deren Sektor im Schnitt schwach ist."),
            ("Filter", "RS-Rating ≥ 95 (Top 5 % des Marktes), höchstens 15 % unter dem 52W-Hoch, Schlusskurs über EMA 21, ADR ≥ 2,5 %, Ø Dollar-Volumen ≥ 10 Mio. $, Kurs ≥ 5 $."),
            ("Achte auf", "Aktien, die zusätzlich in einem anderen Scan auftauchen (enge Base, RS in der Korrektur, Power Play). Leader + Setup = Kandidat."),
            ("Gut zu wissen", "Rund 60–90 Treffer. Das ist eine Watchlist der Stärksten, keine Kaufsignale. Weniger Treffer: RS auf 97 stellen."),
        ],
    },
    "abend": {
        "label": "Abend-Einstieg",
        "desc": "Setup D: Anführer hat heute den Pivot seiner Base gebrochen und schließt stark. Einstieg 21:45–21:58.",
        "values": {"min_price": 5.0, "min_dollar_vol": 10e6, "min_adr_pct": 3.0, "mom_top_pct": 0.2,
                   "min_rs_rating": 80.0, "min_rvol": 1.2, "require_breakout_today": True,
                   "bo_min_close_pos": 0.75, "bo_max_over_adr": 1.0},
        "explain": [
            ("Wofür", "Setup D aus dem Playbook: Du warst um 15:30 nicht am Bildschirm, aber eine starke Aktie ist heute ausgebrochen. Der Tagesschluss bestätigt den Ausbruch, Fehlausbrüche am Nachmittag fallen raus."),
            ("Gestern", "Die Aktie hatte eine Base: mindestens 10 Tage seit dem Base-Hoch, Vorlauf ≥ 30 %, Base ≤ 30 % tief. Pivot = Hoch der letzten 5 Tage bis gestern."),
            ("Heute", "Schluss über dem Pivot, im oberen Viertel der Tageskerze, höchstens 1 ADR über dem Pivot (nicht hinterherlaufen), Volumen ≥ 1,2× Durchschnitt."),
            ("Aktie", "RS-Rating ≥ 80, Top 20 % Momentum, ADR ≥ 3 %, ≥ 10 Mio. $ Volumen."),
            ("Wann scannen", "Ab ca. 21:30 Uhr deutscher Zeit mit eingeschalteter „laufender Tageskerze“ (Einstellungen → 5 · Daten), Kauf 21:45–21:58. Ohne laufende Kerze zeigt der Scan die Ausbrüche des letzten abgeschlossenen Tages."),
            ("Stop", "Tagestief, höchstens 1 ADR entfernt. Spalte „Stop-Abst.“ zeigt den Abstand. Earnings in den nächsten 5 Tagen: auslassen."),
        ],
    },
    "feierabend": {
        "label": "Feierabend-Gap",
        "desc": "Felix-Scanner: Gap ≥ 5 % heute, ≥ +1 % seit Eröffnung, über steigendem SMA 50, ≥ 1 Mrd. $, ≥ 20 Mio. $ Volumen. Ab ca. 16 Uhr.",
        "values": {"min_price": 10.0, "min_dollar_vol": 20e6, "min_market_cap": 1e9, "min_adr_pct": 2.0,
                   "min_avg_volume": 1.2e6, "mom_top_pct": 1.0, "min_gap_pct": 5.0, "min_chg_open_pct": 1.0,
                   "require_above_sma50_f": True, "require_sma50_rising": True, "include_today_partial": True},
        "explain": [
            ("Wofür", "Gap-Daytrades nach Feierabend (Video von Felix): Aktien, die heute mit Gap eröffnet haben und das Gap halten. Breiter als die EP-Vorlagen, also mehr Auswahl."),
            ("Filter", "Gap ≥ 5 % (Eröffnung vs. gestriger Schluss), Kurs ≥ +1 % über der Eröffnung, Kurs über SMA 50 und SMA 50 steigend, Kurs ≥ 10 $, Marktkap. ≥ 1 Mrd. $, ≥ 20 Mio. $ Dollar-Volumen, Ø Volumen ≥ 1,2 Mio. Stück, ADR ≥ 2 %."),
            ("Wann scannen", "Während der Börsenzeit, frühestens ca. 16 Uhr (Daten 15 Min. verzögert). Immer „Daten laden + scannen“, damit die laufende Tageskerze geladen wird. Die Vorlage schaltet die laufende Kerze ein."),
            ("Einstieg", "10-Minuten-Chart: enge Konsolidierung, Einstieg wenn eine 10-Min.-Kerze darüber schließt. Stop unter der Konsolidierung bzw. unter dem Tief der letzten 10-Min.-Kerze. Ausstieg zum Tagesschluss."),
            ("Auslassen", "Aktie ist heute schon 2–4 ADR gelaufen ohne saubere Konsolidierung an einem Level, oder kein Platz bis zum nächsten Widerstand."),
            ("Gut zu wissen", "Spalte „seit Eröffnung“ und „Gap“ im Tab Übersicht. Der steigende SMA 50 wird automatisch geprüft (das kann TradingView nicht)."),
        ],
    },
    "vorboerse": {
        "label": "Vorbörsen-Gap",
        "desc": "Vor 15:30 Uhr: Aktien mit vorbörslichem Gap ≥ 4 % und ≥ 100.000 Stück Vorbörsenvolumen. Für den Plan zur Eröffnung.",
        "values": {"min_price": 5.0, "min_dollar_vol": 5e6, "min_market_cap": 300e6, "min_adr_pct": 2.0,
                   "min_avg_volume": 500000.0, "mom_top_pct": 1.0, "min_pm_gap_pct": 4.0, "min_pm_volume": 100000.0},
        "explain": [
            ("Wofür", "Gaps finden, bevor der Markt öffnet, damit du um 15:30 Uhr deutscher Zeit (9:30 New York) mit Plan und eingezeichneten Levels bereit bist."),
            ("Filter", "Letzter Vorbörsenkurs ≥ 4 % über dem gestrigen Schluss, ≥ 100.000 Stück vorbörsliches Volumen, Kurs ≥ 5 $, Marktkap. ≥ 300 Mio. $, ≥ 5 Mio. $ Dollar-Volumen, Ø Volumen ≥ 500.000, ADR ≥ 2 %."),
            ("Wann scannen", "Ab ca. 14:30 Uhr, ideal 15:00–15:20 Uhr deutscher Zeit, mit „Daten laden + scannen“ (holt gestrigen Schluss und Vorbörse). Die Vorbörsenkurse sind 15 Minuten verzögert, die Spalte „VB-Zeit“ zeigt den Stand."),
            ("Danach", "Auslöser lesen (Zahlen, News), Vorbörsenhoch und Tageslevels einzeichnen. Ab 15:30 Einstieg über dem Opening-Range-High oder später per Feierabend-Gap-Regeln."),
            ("Gut zu wissen", "Mehr Treffer als „Episodic Pivot“, weil schon ab 4 % und ohne Volumen-Vervielfachung. Für echte EPs: Gap ≥ 10 % und Vorbörsenvolumen ≥ 300–500 Tsd. Spalte „SMA 50 ↗“ zeigt den Trend."),
        ],
    },
    "vorboerse_fa": {
        "label": "Vorbörse wie Feierabend",
        "desc": "Vor 15:30 Uhr, gleiche Filter wie Feierabend-Gap: vorbörsliches Gap ≥ 4 %, über steigendem SMA 50, ≥ 1 Mrd. $, ≥ 20 Mio. $ Volumen.",
        "values": {"min_price": 10.0, "min_dollar_vol": 20e6, "min_market_cap": 1e9, "min_adr_pct": 2.0,
                   "min_avg_volume": 1.2e6, "mom_top_pct": 1.0, "min_pm_gap_pct": 4.0, "min_pm_volume": 50000.0,
                   "require_above_sma50_f": True, "require_sma50_rising": True},
        "explain": [
            ("Wofür", "Gaps finden, bevor der Markt öffnet, damit du um 15:30 Uhr deutscher Zeit (9:30 New York) mit Plan und eingezeichneten Levels bereit bist."),
            ("Filter", "Wie „Feierabend-Gap“, damit beide Scans dieselben Aktien finden: Kurs ≥ 10 $, Marktkap. ≥ 1 Mrd. $, ≥ 20 Mio. $ Dollar-Volumen, Ø Volumen ≥ 1,2 Mio., ADR ≥ 2 %, Kurs über steigendem SMA 50. Dazu letzter Vorbörsenkurs ≥ 4 % über dem gestrigen Schluss (Puffer, weil sich das Gap bis 15:30 noch ändert) und ≥ 50.000 Stück Vorbörsenvolumen."),
            ("Unterschied", "„Kurs seit Eröffnung ≥ +1 %“ gibt es vorbörslich noch nicht. Diese Auslese übernimmt deine Einstiegsregel nach 15:30."),
            ("Wann scannen", "Ab ca. 14:30 Uhr, ideal 15:00–15:20 Uhr deutscher Zeit, mit „Daten laden + scannen“ (holt gestrigen Schluss und Vorbörse). Die Vorbörsenkurse sind 15 Minuten verzögert, die Spalte „VB-Zeit“ zeigt den Stand."),
            ("Danach", "Auslöser lesen (Zahlen, News), Vorbörsenhoch und Tageslevels einzeichnen. Ab 15:30 Einstieg über dem Opening-Range-High oder später per Feierabend-Gap-Regeln."),
            ("Gut zu wissen", "Mehr Treffer als „Episodic Pivot“, weil schon ab 4 % und ohne Volumen-Vervielfachung. Für echte EPs: Gap ≥ 10 % und Vorbörsenvolumen ≥ 300–500 Tsd."),
        ],
    },
    "enge_base_d": {
        "label": "Enge Base Daily",
        "desc": "Bases und Flaggen: Vorlauf ≥ 20 %, 1–8 Wochen, rechte Seite eng (an der 60-Tage-ADR gemessen), ≤ 10 % unter dem Hoch, über steigendem 20er/50er, RS ≥ 70. „Setup“ = zusätzlich enger werdend und Volumen trocken.",
        "values": {"min_price": 5.0, "min_dollar_vol": 5e6, "min_adr_pct": 0.0, "min_adr60_pct": 2.5, "mom_top_pct": 1.0,
                   "min_rs_rating": 70.0, "require_tight_d": True},
        "explain": [
            ("Wofür", "Setup B aus dem Playbook, aber ohne den ADR-Denkfehler: Die besten Bases sind kurz vor dem Ausbruch extrem eng. Die normale 20-Tage-ADR fällt dann und würde sie rauswerfen. Hier zählt die 60-Tage-ADR (normale Lebhaftigkeit) und die Enge wird relativ dazu gemessen."),
            ("Pflicht", "Vorlauf ≥ 20 % in den 3 Monaten vor dem Hoch · Base/Flagge 5–40 Tage, ≤ 35 % tief · letzte 5 Tage Spanne ≤ 2,5× ADR60 · Kurs über steigendem 20er und 50er · ≤ 10 % unter dem Hoch · keine festgenagelte Übernahme · RS ≥ 70 · 60-Tage-ADR ≥ 2,5 % · ≥ 5 Mio. $ Volumen."),
            ("Bonus = Status „Setup“", "Zweite Hälfte der Base enger als die erste (VCP) und Volumen der letzten 5 Tage unter dem 50-Tage-Schnitt. Erfüllt eine Aktie beides, steht sie als „Setup“ ganz oben; sonst zeigt der Status, was fehlt. Häkchen „nur Setups“ = nur die saubersten."),
            ("Pivot", "Hoch der engen rechten Seite (letzte 5 Tage). Einstieg darüber per Opening-Range-High, Stop am Tagestief bzw. unter der engen Spanne."),
            ("Unterschied", "Zu Qullamaggie/52W-Hoch: keine feste ADR-Mindestgrenze, Enge relativ zur eigenen Schwankung, Base muss enger werden."),
        ],
    },
    "enge_base_w": {
        "label": "Enge Base Weekly",
        "desc": "Wochenchart: Vorlauf ≥ 30 %, Base 3–15 Wochen und ≤ 30 % tief, Kurs ≤ 12 % unter dem Base-Hoch, letzte 3 Wochenschlüsse innerhalb 5 %, Base wird ruhiger, RS ≥ 70.",
        "values": {"min_price": 5.0, "min_dollar_vol": 5e6, "min_adr_pct": 0.0, "min_adr60_pct": 2.5, "mom_top_pct": 1.0,
                   "min_rs_rating": 70.0, "require_tight_w": True},
        "explain": [
            ("Wofür", "Größere Bases, aus denen die großen Läufe über Monate kommen. „3 Wochen eng“ nach O'Neil: drei Wochenschlüsse fast auf gleicher Höhe zeigen, dass niemand mehr verkauft. Gedacht fürs Wochenende."),
            ("Regeln", "Vorlauf ≥ 30 % im Jahr vor dem Base-Hoch · Base 3–15 Wochen, ≤ 30 % tief · Kurs höchstens 12 % unter dem Base-Hoch (oberer Teil der Base) · letzte 3 Wochenschlüsse innerhalb 5 % · Hoch-Tief dieser 3 Wochen kleiner als 80 % der Base-Tiefe (Base wird ruhiger) · Kurs über steigender 10- und 30-Wochen-Linie · Wochenvolumen der letzten 3 Wochen unter dem Schnitt der 10 Wochen davor · im Tageschart über dem 20er · keine festgenagelte Übernahme · RS ≥ 70 · 60-Tage-ADR ≥ 2,5 %. Strenger: „Schlüsse innerhalb“ 3 % und „max. unter Base-Hoch“ 8 %."),
            ("Pivot", "Hoch der Base (Widerstand). Einstieg trotzdem im Tageschart: Ausbruch über das Opening-Range-High, Stop am Tagestief (max. 1 ADR). Ein Wochen-Stop wäre zu breit."),
            ("Gut zu wissen", "Die laufende Woche zählt mit. Unter der Woche kann sich das Bild bis Freitag noch ändern; am aussagekräftigsten ist der Scan am Wochenende."),
        ],
    },
    "korrektur_rs": {
        "label": "RS in der Korrektur",
        "desc": "Wer hält sich, während der Markt fällt? Nahe 52W-Hoch, RS-Linie am Hoch, 1 Monat ≥ 5 Punkte besser als QQQ. Die Anführer der nächsten Welle.",
        "values": {"min_price": 10.0, "min_dollar_vol": 10e6, "min_adr_pct": 2.5, "mom_top_pct": 1.0,
                   "min_rs_rating": 85.0, "max_from_high_pct": 12.0, "require_above_sma50_f": True,
                   "max_rs_line_from_high": 3.0, "min_rel_1m": 5.0},
        "explain": [
            ("Wofür", "In Korrekturen zeigen sich die Anführer des nächsten Aufschwungs: Sie fallen kaum oder steigen sogar, während der Index fällt. Wenn der Markt dreht, brechen sie oft als Erste aus (O'Neil: wichtigster Hinweis überhaupt)."),
            ("Filter", "RS-Rating ≥ 85, Kurs ≤ 12 % unter dem 52W-Hoch und über dem SMA 50, RS-Linie (Kurs ÷ S&P 500) höchstens 3 % unter ihrem Jahreshoch, Performance über 1 Monat mindestens 5 Prozentpunkte besser als QQQ. Kurs ≥ 10 $, ≥ 10 Mio. $ Volumen, ADR ≥ 2,5 %."),
            ("Wann", "Gedacht für Phasen, in denen QQQ unter dem SMA 50 liegt (Ampel gelb/rot). Steht der Index darüber, erscheint ein Hinweis, dann zeigt der Scan einfach relative Stärke."),
            ("Was tun", "Watchlist, noch nicht kaufen. Wenn die Ampel wieder grün wird: Diese Aktien zuerst auf Ausbrüche prüfen (Setup B, 52W-Hoch-Ausbruch)."),
        ],
    },
    "ipo_base": {
        "label": "IPO-Base",
        "desc": "Börsengang vor 3–12 Monaten, erste Base (≥ 10 % Korrektur), Kurs nahe Hoch. Hier starten viele der größten Läufe.",
        "values": {"min_price": 10.0, "min_dollar_vol": 5e6, "min_adr_pct": 3.0, "mom_top_pct": 1.0,
                   "max_ipo_days": 250, "min_ipo_days": 60, "max_from_high_pct": 25.0,
                   "require_base": True, "min_base_depth_pct": 10.0, "base_min_days": 10, "base_max_days": 60,
                   "base_lookback": 40, "prior_move_lookback": 20, "prior_move_min": 0.0, "base_max_depth": 0.4},
        "explain": [
            ("Wofür", "Junge Börsengänge mit neuem Geschäft haben oft die größten Läufe (viele der Top-Aktien der letzten Jahrzehnte waren wenige Jahre vorher an die Börse gegangen). Nach dem IPO-Rausch bildet sich die erste Base, deren Ausbruch ist der klassische Einstieg (O'Neil, Minervini)."),
            ("Filter", "Erster Kurs vor 60–250 Handelstagen (≈ 3 Monate bis 1 Jahr), echte Base mit ≥ 10 % Korrektur, mindestens 10 Tage, höchstens 40 % tief. Kurs ≤ 25 % unter dem Hoch, ≥ 10 $, ≥ 5 Mio. $ Volumen, ADR ≥ 3 %."),
            ("Einstieg", "Ausbruch über das Base-Hoch (Pivot) mit Volumen. Stop am Tagestief, max. 1 ADR."),
            ("Gut zu wissen", "IPO-Datum = erster Kurs in den Daten. Die Daten reichen gut 1 Jahr zurück, ältere Börsengänge erscheinen nicht. Fällt auch auf Spin-offs und Umbenennungen herein; kurz prüfen."),
        ],
    },
    "delayed_ep": {
        "label": "Delayed EP",
        "desc": "EP vor 3–15 Tagen, Gap-Tief hält, enge Flagge ≤ 15 % unter dem Hoch. Einstieg über das Flaggen-Hoch mit engem Stop.",
        "values": {"min_price": 5.0, "min_dollar_vol": 5e6, "min_adr_pct": 2.0, "mom_top_pct": 1.0, "min_market_cap": 300e6,
                   "require_ep": True, "ep_lookback_days": 16, "ep_min_days_ago": 3, "ep_min_gap_pct": 8.0,
                   "ep_min_rvol": 2.5, "require_ep_hold": True, "max_ep_from_high_pct": 15.0},
        "explain": [
            ("Wofür", "Setup A aus dem Playbook, zweite Chance: Du hast den EP am Gap-Tag verpasst oder wolltest die Reaktion abwarten. Nach dem Gap konsolidiert die Aktie eng über dem Gap-Tief, der Ausbruch daraus ist oft der bessere Einstieg (engerer Stop)."),
            ("Filter", "Gap ≥ 8 % mit ≥ 2,5× Volumen vor 3 bis 15 Handelstagen, Kurs heute über dem Tief des Gap-Tages und höchstens 15 % unter dem Hoch seit dem Gap. Marktkap. ≥ 300 Mio. $, Kurs ≥ 5 $, ≥ 5 Mio. $ Volumen."),
            ("Einstieg", "Über das Hoch der Konsolidierung (Pivot) per Opening-Range-High. Stop am Tagestief bzw. unter der Flagge, max. 1 ADR."),
            ("Übernahmen", "ADR ≥ 2 % sortiert Übernahme-Kandidaten aus: Nach einem Kaufangebot klebt der Kurs am Angebotspreis und schwankt kaum. Sieht wie eine perfekte Flagge aus, läuft aber nie."),
            ("Achte auf", "Echter Auslöser (Zahlen, News), Volumen in der Flagge trocknet aus, enge Kerzen. Spalte „Gap“ zeigt „EP vor X T“, Spalte „vom Hoch seit Gap“ im Tab Momentum."),
        ],
    },
    "feierabend_short": {
        "label": "Feierabend-Gap Short",
        "desc": "Spiegel von Feierabend-Gap: Gap ≤ −5 %, ≤ −1 % seit Eröffnung, unter fallendem SMA 50. Nur intraday, vor 22 Uhr schließen.",
        "values": {"min_price": 10.0, "min_dollar_vol": 20e6, "min_market_cap": 1e9, "min_adr_pct": 2.0,
                   "min_avg_volume": 1.2e6, "mom_top_pct": 1.0, "min_gap_pct": 5.0, "min_chg_open_pct": 1.0,
                   "require_above_sma50_f": True, "require_sma50_rising": True, "include_today_partial": True,
                   "gap_short": True},
        "explain": [
            ("Wofür", "Short-Daytrades nach Feierabend: Aktien, die heute mit Gap nach unten eröffnet haben und weiter schwach sind. Nur intraday, nie über Nacht."),
            ("Filter", "Gap ≤ −5 %, Kurs ≥ 1 % unter der Eröffnung, Kurs unter SMA 50 und SMA 50 fallend, Kurs ≥ 10 $, Marktkap. ≥ 1 Mrd. $, ≥ 20 Mio. $ Dollar-Volumen, Ø Volumen ≥ 1,2 Mio., ADR ≥ 2 %."),
            ("Einstieg", "10-Minuten-Chart: enge Konsolidierung, Short wenn eine 10-Min.-Kerze darunter schließt. Stop über der Konsolidierung bzw. über dem Hoch der letzten 10-Min.-Kerze."),
            ("Ausstieg", "Spätestens 21:50 Uhr schließen (Börsenschluss 22:00). Kein Halten über Nacht."),
            ("Regeln", "Nur wenn der Nasdaq schwach ist (Ampel gelb/rot). Halbes Risiko gegenüber Long. Vorsicht bei Erholungsrallys: Shorts werden dann schnell ausgestoppt."),
        ],
    },
    "vorboerse_short": {
        "label": "Vorbörse Short",
        "desc": "Vor 15:30: vorbörsliches Gap ≤ −4 %, unter fallendem SMA 50, gleiche Filter wie Feierabend-Gap. Plan für Short-Daytrades.",
        "values": {"min_price": 10.0, "min_dollar_vol": 20e6, "min_market_cap": 1e9, "min_adr_pct": 2.0,
                   "min_avg_volume": 1.2e6, "mom_top_pct": 1.0, "min_pm_gap_pct": 4.0, "min_pm_volume": 50000.0,
                   "require_above_sma50_f": True, "require_sma50_rising": True, "gap_short": True},
        "explain": [
            ("Wofür", "Gaps nach unten vor der Eröffnung finden, damit du um 15:30 mit Plan bereit bist. Nur intraday."),
            ("Filter", "Letzter Vorbörsenkurs ≥ 4 % unter dem gestrigen Schluss, ≥ 50.000 Stück Vorbörsenvolumen, Kurs unter fallendem SMA 50, Kurs ≥ 10 $, Marktkap. ≥ 1 Mrd. $, ≥ 20 Mio. $ Volumen, Ø Volumen ≥ 1,2 Mio., ADR ≥ 2 %."),
            ("Wann scannen", "15:00–15:20 Uhr mit „Daten laden + scannen“. Vorbörsenkurse 15 Min. verzögert."),
            ("Danach", "Auslöser lesen (schlechte Zahlen, Ausblick gesenkt), Vorbörsentief und Levels einzeichnen. Short unter dem Opening-Range-Low oder später per Feierabend-Gap-Short-Regeln. Vor 22 Uhr schließen."),
        ],
    },
    "swing_video": {
        "archived": True,
        "label": "Swing-Video",
        "desc": "Filter aus dem Swing-Trading-Video: Kurs > 3 $, Marktkap. > 300 Mio. $, Ø Vol. > 500k, ADR > 2 %, über EMA 21 + 50. Ohne Momentum-Rang.",
        "values": {"min_price": 3.0, "min_dollar_vol": 0.0, "min_adr_pct": 2.0, "min_avg_volume": 500000.0,
                   "min_market_cap": 300e6, "require_above_ema21": True, "require_above_ema50": True,
                   "mom_top_pct": 1.0},
        "explain": [
            ("Wofür", "Die Grundfilter aus dem Swing-Trading-Video. Breite Liste liquider Aufwärtstrend-Aktien, die man dann von Hand durchschaut."),
            ("Filter", "Kurs > 3 $, Marktkapitalisierung > 300 Mio. $, Ø Volumen (30 T) > 500.000 Stück, ADR > 2 %, Kurs über EMA 21 und EMA 50. Kein Momentum-Rang."),
            ("Gut zu wissen", "Lässt sich 1:1 im TradingView-Screener nachbauen (dort EMA 20 statt 21). Gut zum Gegenprüfen."),
        ],
    },
    "minervini": {
        "archived": True,
        "label": "Minervini",
        "desc": "Trend-Template: Kurs > SMA 50 > 150 > 200, 200er steigend, ≥ 30 % über 52W-Tief, ≤ 25 % unter 52W-Hoch, RS ≥ 70. Kurs ≥ 10 $, ≥ 5 Mio. $ Volumen.",
        "values": {"min_price": 10.0, "min_dollar_vol": 5e6, "min_adr_pct": 0.0, "mom_top_pct": 1.0,
                   "require_trend_template": True},
        "explain": [
            ("Wofür", "Mark Minervinis Trend-Template: nur Aktien in einem sauberen, etablierten Aufwärtstrend (Stage 2)."),
            ("Filter", "Kurs über SMA 50, 150 und 200, SMA 50 > 150 > 200, SMA 200 steigt seit mindestens 1 Monat, Kurs ≥ 30 % über dem 52W-Tief und ≤ 25 % unter dem 52W-Hoch, RS-Rating ≥ 70."),
            ("Gut zu wissen", "Liefert oft einige Hundert Treffer. Mit „nur Setups“ oder „bis Pivot ≤ 3 %“ eingrenzen."),
        ],
    },
    "ep": {
        "archived": True,
        "label": "Episodic Pivot",
        "desc": "Heute Gap ≥ 10 % mit ≥ 3× Volumen. Ohne Momentum-Pflicht. Nach Börsenschluss oder mit laufender Tageskerze nutzen.",
        "values": {"min_price": 5.0, "min_dollar_vol": 5e6, "min_adr_pct": 0.0, "mom_top_pct": 1.0,
                   "require_ep": True},
        "explain": [
            ("Wofür", "Qullamaggies Gap-Strategie: Eine Aktie springt wegen einer Nachricht (Earnings, FDA, Auftrag) mit riesigem Volumen nach oben. Oft der Start eines neuen Trends."),
            ("Filter", "Gap ≥ 10 % zur Eröffnung mit ≥ 3× dem Durchschnittsvolumen der letzten 50 Tage."),
            ("Wann scannen", "Nach Börsenschluss für Day-2-Einstiege, oder ab ca. 15:45 Uhr deutscher Zeit mit eingeschalteter „laufender Tageskerze“."),
            ("Gut zu wissen", "Prüft nur den letzten Handelstag. Für mehr Qualität die Vorlage „EP + Wachstum“ nehmen."),
        ],
    },
    "leer": {
        "archived": True,
        "label": "Leer",
        "desc": "Alle Filter aus. Du setzt jeden Wert selbst. Achtung: ohne Filter wird der ganze Markt geprüft (dauert länger).",
        "values": {"min_price": 0.0, "min_dollar_vol": 0.0, "min_adr_pct": 0.0, "min_avg_volume": 0.0,
                   "min_market_cap": 0.0, "only_stocks": False, "min_rs_rating": 0.0, "max_from_high_pct": 100.0,
                   "min_rvol": 0.0, "require_rs_new_high": False, "require_trend_template": False, "require_ep": False,
                   "require_above_ema21": False, "require_above_ema50": False, "mom_top_pct": 1.0,
                   "prior_move_min": 0.0, "base_min_days": 0, "base_max_days": 60, "base_max_depth": 1.0,
                   "require_higher_lows": False, "tight_max_adr_mult": 99.0, "vol_dry_ratio": 99.0,
                   "max_ext_adr_mult": 99.0, "require_above_sma50": False, "require_ema10_above_ema20": False},
        "explain": [
            ("Wofür", "Startpunkt für eigene Ideen. Alle Filter sind aus, du trägst jeden Wert selbst ein."),
            ("Gut zu wissen", "Ohne Filter wird der ganze Markt (über 10.000 Titel) einzeln geprüft. Das dauert deutlich länger als die anderen Vorlagen."),
        ],
    },
}


def save_settings(folder: str, values: dict) -> Params:
    """Übernimmt Werte aus dem Einstellungs-Fenster, prüft sie und speichert nur Abweichungen vom Standard."""
    default = Params()
    names = {f.name for f in fields(Params)}
    path = os.path.join(folder, "settings.json")
    merged = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            merged = json.load(fh)
    for k, v in values.items():
        if k not in names:
            raise ValueError(f"unbekannter Parameter '{k}'")
        cur = getattr(default, k)
        if isinstance(cur, bool):
            v = bool(v)
        elif isinstance(cur, int):
            v = int(round(float(v)))
        elif isinstance(cur, float):
            v = round(float(v), 10)
        elif isinstance(cur, tuple):
            v = list(v)
        else:
            v = str(v).strip().upper() if k in ("benchmark", "rs_benchmark") else v
        merged[k] = v
    out = {k: v for k, v in merged.items()
           if (list(getattr(default, k)) if isinstance(getattr(default, k), tuple) else getattr(default, k)) != v}
    test = Params()
    for k, v in out.items():
        setattr(test, k, tuple(v) if isinstance(v, list) else v)
    if test.base_min_days > test.base_max_days:
        raise ValueError('Base mindestens darf nicht größer sein als Base höchstens.')
    if not (0 < test.mom_top_pct <= 1):
        raise ValueError("Top-Anteil muss zwischen 0 und 100 % liegen.")
    if not (0 <= test.min_rs_rating <= 99):
        raise ValueError("RS-Rating muss zwischen 0 und 99 liegen.")
    if test.tight_days < 2:
        raise ValueError("Enge: mindestens 2 Tage.")
    if out:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
    elif os.path.exists(path):
        os.remove(path)
    return load_params(folder)

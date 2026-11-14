"""Liest die Schlüssel (Alpaca, SEC, Alpha Vantage).

Gesucht wird an mehreren Stellen, damit ein Update oder ein verschobener Ordner die Schlüssel
nicht "verliert". Sobald sie einmal gefunden wurden, legt das Programm eine Sicherung unter
<Benutzerordner>/.qm_screener.env an. Die wird ab dann immer als Rückfall genutzt.
"""
from __future__ import annotations

import glob
import os
import shutil

KEYS = ("ALPACA_KEY", "ALPACA_SECRET", "SEC_USER_AGENT", "ALPHAVANTAGE_KEY",
        "IBKR_FLEX_TOKEN", "IBKR_FLEX_QUERY", "IBKR_FLEX_QUERY_TODAY")
HOME = os.path.expanduser("~")
BACKUP = os.path.join(HOME, ".qm_screener.env")


def candidates(folder: str) -> list[str]:
    parent = os.path.dirname(folder)
    out = [os.path.join(folder, n) for n in (".env", ".env.txt", "env", "env.txt", ".env.example.env")]
    out += [os.path.join(parent, ".env"), os.path.join(parent, "qm_screener", ".env"),
            os.path.join(HOME, "qm_screener", ".env"),
            os.path.join(HOME, "Desktop", "qm_screener", ".env"),
            os.path.join(HOME, "OneDrive", "Desktop", "qm_screener", ".env"),
            os.path.join(HOME, "Downloads", "qm_screener", ".env"),
            os.path.join(HOME, "Downloads", "qm_screener", "qm_screener", ".env"),
            os.path.join(HOME, "Desktop", ".env"), os.path.join(HOME, "OneDrive", "Desktop", ".env"),
            os.path.join(HOME, "Downloads", ".env"), os.path.join(HOME, ".env"),
            BACKUP]
    # alle Kopien wie "qm_screener (6)\qm_screener" auf Desktop / OneDrive / Downloads / Benutzerordner
    for base in (HOME, os.path.join(HOME, "Desktop"), os.path.join(HOME, "OneDrive", "Desktop"),
                 os.path.join(HOME, "OneDrive"), os.path.join(HOME, "Downloads"), os.path.join(HOME, "Documents")):
        for pat in ("qm_screener*/.env", "qm_screener*/qm_screener*/.env", "qm_screener*/.env.txt"):
            out += sorted(glob.glob(os.path.join(base, pat)), key=os.path.getmtime, reverse=True)
    seen, res = set(), []
    for p in out:
        k = os.path.normcase(os.path.abspath(p))
        if k not in seen:
            seen.add(k)
            res.append(p)
    return res


def _read(path: str) -> dict:
    vals = {}
    try:
        with open(path, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if v:
                    vals[k.strip()] = v
    except OSError:
        pass
    return vals


def load_env(folder: str) -> dict:
    vals, source = {}, None
    for path in candidates(folder):
        if not os.path.isfile(path):
            continue
        v = _read(path)
        if v.get("ALPACA_KEY") and v.get("ALPACA_SECRET"):
            vals, source = v, path
            break
    if not source:
        # noch keine Alpaca-Schlüssel: trotzdem die eigene .env lesen (z. B. nur IBKR eingetragen)
        for path in (os.path.join(folder, ".env"), BACKUP):
            if os.path.isfile(path):
                vals = {**_read(path), **vals}
    for k in KEYS:
        if os.environ.get(k):
            vals[k] = os.environ[k]
    if source:
        vals["_source"] = source
        # Sicherung außerhalb des Programmordners + .env im Programmordner wiederherstellen
        try:
            if os.path.normcase(os.path.abspath(source)) != os.path.normcase(os.path.abspath(BACKUP)):
                shutil.copyfile(source, BACKUP)
            own = os.path.join(folder, ".env")
            if not os.path.exists(own):
                shutil.copyfile(source, own)
        except OSError:
            pass
    return vals


def missing_message(folder: str) -> str:
    return ("Noch keine Alpaca-Schlüssel eingetragen. Oben rechts auf „🔌 Verbindungen“ klicken "
            "und der Anleitung folgen (dauert ca. 5 Minuten, kostenlos).")


def save_values(folder: str, updates: dict) -> str:
    """Schlüssel in die .env im Programmordner schreiben (bestehende Zeilen bleiben), plus Sicherung im Benutzerordner.
    Leere Werte werden nicht geschrieben (alte bleiben)."""
    cur = load_env(folder)
    path = cur.get("_source") or os.path.join(folder, ".env")
    if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(BACKUP)):
        path = os.path.join(folder, ".env")
    lines = []
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except OSError:
        pass
    todo = {k: str(v).strip() for k, v in updates.items() if v is not None and str(v).strip()}
    for i, line in enumerate(lines):
        k = line.split("=", 1)[0].strip()
        if k in todo:
            lines[i] = f"{k}={todo.pop(k)}"
    lines += [f"{k}={v}" for k, v in todo.items()]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).strip() + "\n")
    try:
        os.chmod(path, 0o600)
        shutil.copyfile(path, BACKUP)
        os.chmod(BACKUP, 0o600)
    except OSError:
        pass
    return path

"""Update-Funktion: holt die neueste Version von GitHub und ersetzt nur den Programmcode.

Deine Daten (Schlüssel in .env, settings.json, Fokusliste, eigene Scans, Journal, Kursdaten im Ordner data/)
werden dabei nie angefasst. Vor jedem Update wird der alte Code in _update_backup/ gesichert.
"""
from __future__ import annotations

import io
import os
import shutil
import ssl
import time
import urllib.request
import zipfile

REPO = "schulznick1998-dot/qm-screener"
BRANCH = "main"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/VERSION"
RAW_CHANGES = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/CHANGES.txt"
ZIP = f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}"
PAGE = f"https://github.com/{REPO}"

# Nur diese Dateien/Ordner gehören zum Programm und werden beim Update ersetzt
CODE_FILES = ("app.py", "VERSION", "CHANGES.txt", "requirements.txt", "README.md", "start_mac.command", "start_windows.bat",
              ".gitignore", ".env.example", "settings.example.json")
CODE_DIRS = ("screener", "static", "tradingview")


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "QM-Screener-Update", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return r.read()


def local_version(folder: str) -> str:
    try:
        with open(os.path.join(folder, "VERSION"), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return "0"


def _key(v: str):
    return tuple(int(x) if x.isdigit() else 0 for x in v.replace("-", ".").split("."))


def check(folder: str) -> dict:
    cur = local_version(folder)
    try:
        new = _get(RAW + f"?t={int(time.time())}", timeout=10).decode().strip()
    except Exception as e:
        return {"current": cur, "latest": None, "available": False, "error": f"GitHub nicht erreichbar ({str(e)[:80]})"}
    avail = _key(new) > _key(cur)
    changes = []
    if avail:
        try:
            changes = parse_changes(_get(RAW_CHANGES + f"?t={int(time.time())}", timeout=10).decode("utf-8"), cur)
        except Exception:
            pass
    return {"current": cur, "latest": new, "available": avail, "page": PAGE, "changes": changes}


def parse_changes(text: str, since: str) -> list:
    """CHANGES.txt: Blöcke '## VERSION' mit Zeilen '- Text'. Liefert alle Blöcke neuer als `since`."""
    out, cur = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            v = line[3:].strip()
            cur = {"version": v, "items": []} if _key(v) > _key(since) else None
            if cur:
                out.append(cur)
        elif line.startswith("- ") and cur is not None:
            cur["items"].append(line[2:].strip())
    return out[:10]


def apply(folder: str) -> dict:
    data = _get(ZIP, timeout=120)
    z = zipfile.ZipFile(io.BytesIO(data))
    root = z.namelist()[0].split("/")[0] + "/"
    # alten Code sichern
    bak = os.path.join(folder, "_update_backup", time.strftime("%Y-%m-%d_%H%M"))
    os.makedirs(bak, exist_ok=True)
    for f in CODE_FILES:
        p = os.path.join(folder, f)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(bak, f))
    for d in CODE_DIRS:
        p = os.path.join(folder, d)
        if os.path.isdir(p):
            shutil.copytree(p, os.path.join(bak, d), dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__"))
    n = 0
    for name in z.namelist():
        if not name.startswith(root) or name.endswith("/"):
            continue
        rel = name[len(root):]
        top = rel.split("/")[0]
        if rel not in CODE_FILES and top not in CODE_DIRS:
            continue
        dest = os.path.join(folder, *rel.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with z.open(name) as src, open(dest, "wb") as out:
            out.write(src.read())
        if rel.endswith(".command"):
            os.chmod(dest, 0o755)
        n += 1
    return {"files": n, "version": local_version(folder), "backup": os.path.relpath(bak, folder)}

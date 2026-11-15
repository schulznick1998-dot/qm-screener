#!/bin/bash
# QM Screener für macOS: Doppelklick startet. Beim ersten Mal werden die Pakete installiert (1–2 Minuten).
cd "$(dirname "$0")"

# Python finden: 3.10 bis 3.14 (neuere Versionen haben noch nicht alle Pakete, z. B. pyarrow)
OKV='import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,14) else 1)'
PY=""
for c in /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 /opt/homebrew/bin/python3.13 \
         /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "$OKV" 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo ""
  echo "Passendes Python fehlt. Benötigt wird Python 3.13 (3.15 und neuer ist noch zu neu)."
  echo "Bitte von https://www.python.org/downloads/latest/python3.13 den macOS-Installer laden,"
  echo "installieren und diese Datei danach erneut doppelklicken."
  open "https://www.python.org/downloads/latest/python3.13"
  read -n 1 -s -r -p "Taste drücken zum Schließen …"
  exit 1
fi
# Alte Umgebung mit unpassender Python-Version entfernen
if [ -x ".venv/bin/python" ] && ! .venv/bin/python -c "$OKV" 2>/dev/null; then
  echo "Entferne alte Python-Umgebung …"; rm -rf .venv
fi

# Eigene Umgebung im Programmordner (stört nichts anderes auf dem Mac)
if [ ! -x ".venv/bin/python" ]; then
  echo "Erster Start: richte Python-Umgebung ein …"
  "$PY" -m venv .venv || { echo "venv fehlgeschlagen"; read -n 1 -s -r; exit 1; }
fi
if [ ! -f ".venv/.installed" ] || [ requirements.txt -nt ".venv/.installed" ]; then
  echo "Installiere Pakete (einmalig, 1–2 Minuten) …"
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements.txt && touch .venv/.installed
fi

# Läuft noch ein alter Screener? Dann beenden.
OLD=$(lsof -ti tcp:8765 2>/dev/null)
if [ -n "$OLD" ]; then
  echo "Beende alten Screener (PID $OLD)"
  kill $OLD 2>/dev/null; sleep 1
fi

.venv/bin/python app.py
read -n 1 -s -r -p "Screener beendet. Taste drücken zum Schließen …"

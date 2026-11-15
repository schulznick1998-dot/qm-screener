@echo off
chcp 65001 >nul
title QM Screener
REM QM Screener fuer Windows: Doppelklick startet. Beim ersten Mal werden die Pakete installiert (2-3 Minuten).
cd /d "%~dp0"

REM Python suchen: 3.10 bis 3.14 (neuere Versionen haben noch nicht alle Pakete, z. B. pyarrow)
set "PY="
for %%v in (3.13 3.12 3.11 3.14 3.10) do (
  if not defined PY ( py -%%v -c "import sys" >nul 2>nul && set "PY=py -%%v" )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,14) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo Passendes Python fehlt. Benoetigt wird Python 3.13 ^(3.15 und neuer ist noch zu neu^).
  echo Bitte den Installer fuer Python 3.13 laden: https://www.python.org/downloads/latest/python3.13
  echo Unten auf der Seite: "Windows installer (64-bit)".
  echo WICHTIG: Im ersten Fenster des Installers unten den Haken bei "Add python.exe to PATH" setzen!
  echo Danach diese Datei erneut doppelklicken.
  start "" "https://www.python.org/downloads/latest/python3.13"
  pause
  exit /b 1
)

REM Alte Umgebung mit unpassender Python-Version entfernen
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,14) else 1)" >nul 2>nul || (
    echo Entferne alte Python-Umgebung ...
    rmdir /s /q ".venv"
  )
)

REM Eigene Umgebung im Programmordner (stoert nichts anderes auf dem PC)
if not exist ".venv\Scripts\python.exe" (
  echo Erster Start: richte Python-Umgebung ein ...
  %PY% -m venv .venv
  if errorlevel 1 ( echo venv fehlgeschlagen & pause & exit /b 1 )
)

REM Pakete installieren, wenn noch nicht passiert oder requirements.txt neuer ist
set "NEED=1"
if exist ".venv\.installed" (
  for /f %%i in ('".venv\Scripts\python.exe" -c "import os;print(1 if os.path.getmtime('requirements.txt')>os.path.getmtime('.venv/.installed') else 0)"') do set "NEED=%%i"
)
if "%NEED%"=="1" (
  echo Installiere Pakete ^(einmalig, 2-3 Minuten^) ...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 ( echo Paket-Installation fehlgeschlagen. Internet da? & pause & exit /b 1 )
  echo ok> ".venv\.installed"
)

".venv\Scripts\python.exe" app.py
echo.
echo Screener beendet.
pause

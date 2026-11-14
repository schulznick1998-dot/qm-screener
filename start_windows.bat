@echo off
chcp 65001 >nul
title QM Screener
REM QM Screener fuer Windows: Doppelklick startet. Beim ersten Mal werden die Pakete installiert (2-3 Minuten).
cd /d "%~dp0"

REM Python suchen (3.10 oder neuer)
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo Python 3.10 oder neuer fehlt.
  echo Bitte von https://www.python.org/downloads/windows/ den Installer fuer Python 3.13 laden.
  echo WICHTIG: Im ersten Fenster des Installers unten den Haken bei "Add python.exe to PATH" setzen!
  echo Danach diese Datei erneut doppelklicken.
  start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
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

# QM Screener

Ein kostenloser Aktien-Screener für **Breakout-Setups in US-Aktien** (Qullamaggie-Stil, Episodic Pivots, enge Bases, RS-Leader …), mit Charts, Fokusliste, Sektoren/Themen und einem **automatischen Trading-Journal** für Interactive Brokers.

Er läuft **komplett auf deinem eigenen Rechner** (Mac oder Windows) und öffnet sich im Browser. Deine Schlüssel, Listen, Einstellungen und Trades bleiben immer bei dir, nichts davon landet im Internet oder bei GitHub.

> ⚠️ Keine Anlageberatung. Der Screener zeigt Kandidaten nach festen Regeln, die Entscheidung triffst du selbst.

---

## Inhalt

1. [Herunterladen und starten](#1-herunterladen-und-starten)
2. [Verbindungen einrichten (Alpaca, Name/E-Mail)](#2-verbindungen-einrichten)
3. [Erster Scan](#3-erster-scan)
4. [Trading-Journal mit Interactive Brokers (optional)](#4-trading-journal-mit-interactive-brokers-optional)
5. [TradingView-Indikator (optional)](#5-tradingview-indikator-optional)
6. [Updates](#6-updates)
7. [Wo liegen meine Daten?](#7-wo-liegen-meine-daten)
8. [Probleme und Lösungen](#8-probleme-und-lösungen)

---

## 1. Herunterladen und starten

### Download
1. Oben auf dieser Seite auf den grünen Knopf **„<> Code“** klicken → **„Download ZIP“**.
2. Die ZIP-Datei entpacken (Doppelklick). Den Ordner an einen festen Ort legen, z. B. in **Dokumente**, und ihn am besten in `QM-Screener` umbenennen.

### Mac
1. Ist **Python** installiert? Falls nicht: [python.org/downloads/latest/python3.13](https://www.python.org/downloads/latest/python3.13) → Installer für **Python 3.13** (nicht 3.15 – dafür fehlen noch Pakete) laden und installieren (einfach durchklicken).
2. Im Ordner **`start_mac.command`** doppelklicken.
   - Beim **allerersten Mal** meldet der Mac „kann nicht geöffnet werden, da der Entwickler nicht verifiziert ist“. Dann: **Rechtsklick (oder Ctrl + Klick) auf `start_mac.command` → Öffnen → Öffnen**. Das ist nur einmal nötig.
   - Falls stattdessen „keine Berechtigung“ kommt: Terminal öffnen, `chmod +x ` eintippen (mit Leerzeichen), die Datei ins Terminal ziehen, Enter. Danach wieder doppelklicken.
3. Ein schwarzes Fenster (Terminal) geht auf. Beim ersten Start werden die Pakete installiert, das dauert **2–3 Minuten**. Danach öffnet sich der Screener im Browser.
4. **Das schwarze Fenster offen lassen**, solange du den Screener nutzt. Schließen = Screener aus.

### Windows
1. **Python** installieren: [python.org/downloads/latest/python3.13](https://www.python.org/downloads/latest/python3.13) → unten „Windows installer (64-bit)“ → Installer für **Python 3.13** (nicht 3.15 – dafür fehlen noch Pakete). **Ganz wichtig:** im ersten Fenster des Installers unten den Haken bei **„Add python.exe to PATH“** setzen, dann „Install Now“.
2. Im Ordner **`start_windows.bat`** doppelklicken.
   - Kommt „Der Computer wurde durch Windows geschützt“: auf **„Weitere Informationen“ → „Trotzdem ausführen“**.
3. Beim ersten Start werden die Pakete installiert (**2–3 Minuten**), dann öffnet sich der Screener im Browser.
4. **Das schwarze Fenster offen lassen**, solange du den Screener nutzt.

Der Screener läuft dann unter **http://127.0.0.1:8765**. Das ist nur dein eigener Rechner, niemand sonst kann darauf zugreifen.

---

## 2. Verbindungen einrichten

Beim ersten Start öffnet sich automatisch das Fenster **„🔌 Verbindungen einrichten“**. Später erreichst du es jederzeit oben rechts über **🔌 Verbindungen**. Alles ist kostenlos und dauert etwa 5 Minuten.

### Schritt 1: Name und E-Mail
Die US-Börsenaufsicht **SEC** liefert die Firmendaten (Aktienanzahl, Umsatz, Gewinn) kostenlos, verlangt aber bei jeder Anfrage einen Namen und eine E-Mail als Kennung. Diese Angaben gehen nur an sec.gov.

### Schritt 2: Alpaca (Kursdaten, Pflicht)
Alpaca ist ein US-Broker mit kostenlosem Datenzugang. **Du musst dort kein Geld einzahlen** und nichts handeln, das kostenlose Übungskonto („Paper Trading“) reicht.

1. Auf **[alpaca.markets](https://alpaca.markets)** oben rechts **Sign Up** → mit E-Mail und Passwort registrieren → E-Mail bestätigen.
2. Einloggen. Im Dashboard muss oben links **„Paper“** (Übungskonto) ausgewählt sein, nicht „Live“. Fragen zum echten Konto (Identität, Adresse …) kannst du überspringen, die brauchst du nicht.
3. Auf der Startseite rechts gibt es den Kasten **„API Keys“** → **„Generate New Keys“** (bzw. „Regenerate“).
4. Es erscheinen **Key** (beginnt meist mit `PK…`) und **Secret**. Beide kopieren und im Screener einfügen → **Speichern**. Der Screener testet die Schlüssel sofort.
   - **Achtung:** Das Secret wird nur **einmal** angezeigt. Ist es weg, einfach neue Keys erzeugen und die neuen eintragen.

Der kostenlose Zugang liefert die Kurse **15 Minuten verzögert**. Für Swing-Trading und Scans nach Börsenschluss spielt das keine Rolle.

### Schritt 3: Earnings-Termine (optional)
Damit der Screener anzeigt, wann die nächsten Quartalszahlen kommen: auf **[alphavantage.co](https://www.alphavantage.co/support/#api-key)** „Get your free API key“ ausfüllen. Der Key steht direkt auf der Seite, einfach in das Feld kopieren. Ohne diesen Key funktioniert alles andere trotzdem.

### Schritt 4: Trading-Journal (optional)
Siehe [Abschnitt 4](#4-trading-journal-mit-interactive-brokers-optional). Wer nicht bei Interactive Brokers handelt, überspringt das.

---

## 3. Erster Scan

1. Oben auf **„Daten laden + scannen“** klicken.
2. Beim **ersten Mal** lädt der Screener die Tageskerzen aller US-Aktien (ca. 1 Jahr). Das dauert **3–6 Minuten**. Ab dann werden nur noch die neuen Tage nachgeladen, das geht in Sekunden.
3. Danach siehst du die Treffer. Ein Klick auf eine Aktie zeigt rechts den Chart mit Base, Pivot und gleitenden Durchschnitten. **↑/↓** blättert durch die Liste.
4. Der Screener merkt sich pro Scan, welche Aktie du **zuletzt angesehen** hast: Oben über der Liste steht „Zuletzt angesehen: … → **Weiter bei …**“, schon angesehene Aktien werden blass. Mit neuen Kursdaten fängt die Liste wieder frisch an.

**Die wichtigsten Knöpfe:**

| Knopf | Was er macht |
|---|---|
| **Daten laden + scannen** | Neueste Kurse holen und scannen. Am besten einmal nach Börsenschluss (ab 22:15 Uhr deutscher Zeit). |
| **Nur Daten laden** | Nur Kurse aktualisieren, ohne zu scannen. |
| **Nur neu scannen** | Mit den gespeicherten Kursen neu scannen, z. B. nach dem Wechsel der Vorlage. |
| **Einstellungen** | Scan-Vorlage wählen (Qullamaggie, Enge Base, Delayed EP, RS-Leader, Feierabend-Gap …) und Werte anpassen. |
| **ⓘ Erklärung** | Was der aktive Scan macht und wie man ihn handelt. |
| **＋ Eigener Scan** | Eigene Scans aus Bausteinen zusammenstellen und speichern. |
| **nur Setups** (Häkchen) | Nur die Aktien zeigen, die alle Regeln erfüllen. Ohne Häkchen siehst du alle Kandidaten mit den Regeln, die noch fehlen. |
| **☆ / ⭐ Fokus** | Aktien auf deine Fokusliste setzen, mit Pivot, Stop und Notiz. |
| **TradingView-Liste ↓** | Die angezeigte Liste als Watchlist für TradingView exportieren (dort: Watchlist-Menü → „Liste importieren“). |

Weitere Tabs: **◆ Sektoren & Branchen** (Top-down von Index über Sektor zur Aktie), **◆ Themen** (KI, Halbleiter, Biotech, Rüstung … mit Status führend/Aufbau/schwach), **📓 Journal**.

---

## 4. Trading-Journal mit Interactive Brokers (optional)

Der Tab **📓 Journal** holt deine ausgeführten Trades automatisch von Interactive Brokers (IBKR), fasst Käufe und Verkäufe zu Trades zusammen und rechnet alles in **R** (Vielfache deines Risikos). Dazu gibt es Statistik (Trefferquote, Profit-Faktor, Kapitalkurve, Auswertung nach Setup, Uhrzeit, Wochentag, Fehlern), einen Kalender und pro Trade den Chart mit Kauf-/Verkaufspfeilen.

### Einrichten (einmalig, ca. 10 Minuten)
1. Im Browser bei IBKR ins **Client Portal** einloggen (nicht in die TWS). Oben auf **Performance & Berichte → Flex Queries**.
2. Bei **„Kontoumsatz-Flex-Query“** (englisch: Activity Flex Query) rechts auf **+**:
   - Name: z. B. `Journal`
   - **Abschnitte:** auf **„Trades“** klicken → oben **„Alle auswählen“** anhaken → Speichern
   - **Format:** XML · **Zeitraum:** Letzte 365 Kalendertage
   - Unten **Weiter → Erstellen**
3. **Optional**, damit Trades schon **am selben Tag** erscheinen: bei **„Handelsbestätigungs-Flex-Query“** (Trade Confirmation) genauso:
   - Name: z. B. `Journal heute`
   - Abschnitt **„Handelsbestätigung“** → **„Alle auswählen“**
   - Format **XML**, Zeitraum **„Letzte 7 Kalendertage“** (oder „Heute“)
4. In der Liste auf das blaue **ⓘ** neben jeder Query klicken: Dort steht die **Query-ID** (eine Zahl, z. B. 1234567). Notieren.
5. Rechts bei **„Flex-Web-Service-Konfiguration“** aufs **Zahnrad** → Haken bei **„Flex-Web-Service-Status“** → **Token generieren** (Gültigkeit 1 Jahr) → Token kopieren → **Speichern**.
6. Im Screener: Tab **📓 Journal → „IBKR verbinden“** → Token und Query-IDs eintragen → **Speichern** → **„Trades von IBKR abholen“**.

**Gut zu wissen:**
- Der Token kann **nur Berichte lesen**, nicht handeln. Er wird nur lokal gespeichert.
- Die Kontoumsatz-Abfrage enthält Trades erst **ab dem nächsten Morgen**, die Handelsbestätigung schon am selben Tag.
- Nach **1 Jahr** läuft der Token ab: bei IBKR einen neuen erzeugen und im Journal unter „IBKR-Verbindung ändern“ eintragen.
- Das Journal zählt Trades ab dem Datum, das oben bei **„ab“** steht (beim ersten Öffnen: heute). Ältere Trades oder Testtrades kannst du so ausblenden.
- **Stop:** Standardmäßig nimmt das Journal das **Tagestief bis zur Minute deines Einstiegs** (aus Alpaca-Minutenkerzen), so wie ein Stop am Tagestief beim Kauf lag. Du kannst pro Trade auf **„eigener Wert“** umstellen.
- **1 R** = (Einstieg − Stop) × Stückzahl. Beispiel: Kauf 6 Stück bei 110,91 $, Stop 108,01 $ → 1 R = 17,40 $.
- Trag bei jedem Trade **Setup** und ggf. **Fehler** ein, dann zeigt die Statistik, welche Setups dir Geld bringen und was dich Fehler kosten.
- **📷 Chartbild + Notiz speichern** legt pro Trade einen Ordner `Journal/Datum_Symbol/` mit Chartbild und Notiz an.
- CFDs: IBKR schreibt z. B. `FROGn` statt `FROG`. Das Journal rechnet das automatisch um. Devisentausch (EUR → USD) wird ignoriert.

---

## 5. TradingView-Indikator (optional)

Im Ordner **`tradingview/`** liegen Indikatoren zum Kopieren:

- **`NS_AllInOne.pine`**: EMA 9/20/50 + SMA 200 in **einem** Indikator (spart Slots), **Stückzahl-Rechner** (Risiko in € einstellen, Einstieg und Stop anklicken → Stückzahl, Risiko, Stop in ADR, 1-ADR-Linie) und eine **Kennzahlen-Tabelle** (Market Cap, ADR %, Ø $-Volumen, RVOL, RS gegen SPY, Sektor, Branche, Tage bis Earnings). Jede Zeile einzeln abschaltbar.
- `qm_setup_scanner.pine`: Setup-Erkennung wie im Screener, für den Pine Screener.
- `qm_rs_indicator.pine`: RS-Linie gegen SPY mit 52-Wochen-Hoch-Punkten.

**Einbauen:** Datei öffnen, alles kopieren → in TradingView unten **Pine Editor** → alles markieren, einfügen → **Speichern** → **„Zum Chart hinzufügen“**.
**Stückzahl-Rechner benutzen:** Beim Hinzufügen fragt TradingView nach zwei Klicks: erst **Einstieg**, dann **Stop**. Für eine neue Aktie: Indikatorname im Chart → **⋯ → „Punkte zurücksetzen“** → neu klicken.

---

## 6. Updates

Gibt es eine neue Version, erscheint beim Öffnen des Screeners ein Fenster **„Neue Version verfügbar“** mit allen Neuerungen (und oben der Knopf **„⬇ Update“**).
1. Auf **„Jetzt updaten“** klicken. Bei „Später“ kommt der Hinweis beim nächsten Öffnen wieder. Nur der Programmcode wird ersetzt. **Schlüssel, Einstellungen, Fokusliste, eigene Scans, Journal und Kursdaten bleiben erhalten.** Der alte Code wird vorher in `_update_backup/` gesichert.
2. Danach das schwarze Fenster schließen und den Screener neu starten (`start_mac.command` bzw. `start_windows.bat`).

Alternativ: neue ZIP von GitHub laden und die Programmdateien in deinen Ordner kopieren (deine Dateien aus Abschnitt 7 dabei **nicht** überschreiben).

---

## 7. Wo liegen meine Daten?

Alles im Programmordner auf deinem Rechner, nichts online:

| Datei/Ordner | Inhalt |
|---|---|
| `.env` | deine Schlüssel (Alpaca, Name/E-Mail, Alpha Vantage, IBKR-Token). **Niemals weitergeben.** Eine Sicherung liegt zusätzlich in deinem Benutzerordner unter `.qm_screener.env`. |
| `settings.json` | deine Scan-Einstellungen |
| `fokusliste.json` | deine Fokusliste (alte Listen in `fokus_archiv/`) |
| `eigene_scans.json` | deine eigenen Scans |
| `journal.json`, `data/journal_*.json`, `Journal/` | dein Trading-Journal |
| `data/` | gespeicherte Kursdaten (kann man löschen, wird neu geladen) |

Diese Dateien sind in `.gitignore` eingetragen und können nicht versehentlich zu GitHub gelangen.

---

## 8. Probleme und Lösungen

| Problem | Lösung |
|---|---|
| Browser öffnet sich nicht | Selbst **http://127.0.0.1:8765** im Browser öffnen. |
| „Port belegt“ / Screener startet nicht | Es läuft noch ein alter Screener. Alle schwarzen Fenster schließen, neu starten. Notfalls Rechner neu starten. |
| „Noch keine Alpaca-Schlüssel“ | Oben rechts **🔌 Verbindungen** → Schritt 2. |
| „Alpaca lehnt die Schlüssel ab“ | Key und Secret aus dem **Paper**-Konto nehmen (nicht Live), komplett kopieren, ggf. neue Keys erzeugen. |
| Erster Download bricht ab | Nochmal „Daten laden + scannen“, er macht da weiter. |
| Journal: „Fehler 1018“ | IBKR mag zu viele Anfragen hintereinander nicht. 1 Minute warten, nochmal abholen. |
| Journal: keine Trades | Trades sind erst am nächsten Morgen in der Kontoumsatz-Abfrage, oder das Datum bei „ab“ liegt nach deinen Trades. |
| „Passendes Python fehlt“ / Fehler bei pyarrow | Python 3.13 von python.org installieren (siehe oben), dann neu starten. |
| Windows: „python wurde nicht gefunden“ | Python neu installieren und **„Add python.exe to PATH“** anhaken. |

Ohne Schlüssel ausprobieren: Terminal im Ordner öffnen → `.venv/bin/python app.py --demo` (Mac) bzw. `.venv\Scripts\python app.py --demo` (Windows). Dann gibt es Beispieldaten.

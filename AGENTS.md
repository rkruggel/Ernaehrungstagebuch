# AGENTS.md

## Sprache und Zusammenarbeit

- Antworte standardmäßig auf Deutsch.
- Erkläre Änderungen kurz und praktisch.
- Frage nach, bevor größere Strukturänderungen oder neue Abhängigkeiten eingeführt werden.
- Bestehende Dateien und Nutzeränderungen nicht ungefragt zurücksetzen.
- Schreibe zu anfang mit deinen Worten wie du meine Frage/Kommandos verstanden hast.

## Projektkontext

- Dies ist ein Python-Projekt für ein Ernährungstagebuch.
- Einstiegspunkt ist `main.py`.
- Fachseiten liegen unter `src/`.
- Konfiguration liegt in `config.ini`; Beispielwerte in `config.example.ini`.
- Statische Styles liegen in `static/app.css`.

## Coding-Regeln

- Halte Änderungen möglichst klein und passend zum bestehenden Stil.
- Verwende vorhandene Module und Muster, bevor neue Abstraktionen eingeführt werden.
- Keine Secrets, Passwörter oder privaten Pfade in Code oder Dokumentation schreiben.
- Änderungen an Datenbanklogik in `src/database.py` besonders vorsichtig behandeln.

## Prüfen

Nach Python-Änderungen, wenn sinnvoll:

```bash
python -m compileall main.py src


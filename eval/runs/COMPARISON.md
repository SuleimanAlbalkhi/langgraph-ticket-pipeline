# Vergleich aller Eval-Läufe

Eine Zeile pro Lauf, sortiert nach Startzeit. Fehlgeschlagene/fehlende Tickets sind aus den Metriken ausgeschlossen (Spalte „ausgewertet / fehlgeschl.“). Details je Lauf in `eval/runs/<lauf>/RESULTS.md`.

| Lauf | Datum | Commit | Notiz | ausgewertet / fehlgeschl. | Kategorie | Urgency | Risk Recall | Risk Precision | Risk FN | Risk FP | Name richtig | Name erfunden | Konfidenz richtig / falsch | Fallbacks | Latenz Median / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 2026-10-30 | `da59602` | — | 50 / 0 | 40 von 50 (80 %) | 20 von 50 (40 %) | 10 von 11 (91 %) | 10 von 13 (77 %) | EVAL-046 | EVAL-006, EVAL-021, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 0.99 / 0.97 | 0 | 20.4 / 25.4 s |
| baseline-2 | 2026-10-30 | `1bfa5b5` | Rauschmessung: Wiederholung der Baseline ohne Codeänderung | 50 / 0 | 41 von 50 (82 %) | 22 von 50 (44 %) | 10 von 11 (91 %) | 10 von 13 (77 %) | EVAL-046 | EVAL-006, EVAL-021, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 0.99 / 1.00 | 0 | 21.5 / 27.1 s |
| refactor | 2026-10-30 | `03db229` | Refactoring B (verhaltensneutral): state.py, invoke_json, prompts/, postprocess.py | 50 / 0 | 40 von 50 (80 %) | 20 von 50 (40 %) | 10 von 11 (91 %) | 10 von 13 (77 %) | EVAL-046 | EVAL-006, EVAL-021, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 1.00 / 1.00 | 0 | 21.7 / 26.2 s |
| e1-signals | 2026-10-30 | `866a87f` | E1: Classifier liefert Signale, urgency per Regeln (urgency_rules.py); Risk-Gate unverändert | 50 / 0 | 38 von 50 (76 %) | 32 von 50 (64 %) | 9 von 11 (82 %) | 9 von 11 (82 %) | EVAL-014, EVAL-046 | EVAL-006, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 0.99 / 1.00 | 0 | 45.1 / 51.2 s |
| e2-risk-no-urgency | 2026-10-30 | `866a87f` | Risk entkoppeln: Dringlichkeit aus dem Risk-Prompt entfernt (Basis 866a87f, ohne E1) | 50 / 0 | 40 von 50 (80 %) | 22 von 50 (44 %) | 9 von 11 (82 %) | 9 von 13 (69 %) | EVAL-014, EVAL-046 | EVAL-006, EVAL-021, EVAL-027, EVAL-042 | 23 von 25 (92 %) | 2 von 25 (8 %) | 1.00 / 1.00 | 0 | 21.3 / 25.8 s |
| single-vote | 2026-10-30 | `7cd6b12` | Classifier 1 Lauf statt 3, temperature 0 (Basis 866a87f) | 50 / 0 | 40 von 50 (80 %) | 21 von 50 (42 %) | 10 von 11 (91 %) | 10 von 13 (77 %) | EVAL-046 | EVAL-006, EVAL-021, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 1.00 / 1.00 | 0 | 16.2 / 21.4 s |

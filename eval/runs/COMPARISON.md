# Vergleich aller Eval-Läufe

Eine Zeile pro Lauf, sortiert nach Startzeit, getrennt nach Ticket-Datei. Spalte „Commit“ = Stand des App-Codes im gemessenen Image. Fehlgeschlagene/fehlende Tickets sind aus den Metriken ausgeschlossen (Spalte „ausgewertet / fehlgeschl.“). Details je Lauf in `eval/runs/<lauf>/RESULTS.md`.

## Dev-Set (`eval/tickets.jsonl`)

| Lauf | Datum | Commit | Notiz | ausgewertet / fehlgeschl. | Kategorie | Urgency | Risk Recall | Risk Precision | Risk FN | Risk FP | Name richtig | Name erfunden | Konfidenz richtig / falsch | Fallbacks | Latenz Median / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 2026-10-30 | `da59602` | — | 50 / 0 | 40 von 50 (80 %) | 20 von 50 (40 %) | 10 von 11 (91 %) | 10 von 13 (77 %) | EVAL-046 | EVAL-006, EVAL-021, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 0.99 / 0.97 | 0 | 20.4 / 25.4 s |
| baseline-2 | 2026-10-30 | `1bfa5b5` | Rauschmessung: Wiederholung der Baseline ohne Codeänderung | 50 / 0 | 41 von 50 (82 %) | 22 von 50 (44 %) | 10 von 11 (91 %) | 10 von 13 (77 %) | EVAL-046 | EVAL-006, EVAL-021, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 0.99 / 1.00 | 0 | 21.5 / 27.1 s |
| refactor | 2026-10-30 | `03db229` | Refactoring B (verhaltensneutral): state.py, invoke_json, prompts/, postprocess.py | 50 / 0 | 40 von 50 (80 %) | 20 von 50 (40 %) | 10 von 11 (91 %) | 10 von 13 (77 %) | EVAL-046 | EVAL-006, EVAL-021, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 1.00 / 1.00 | 0 | 21.7 / 26.2 s |
| e1-signals | 2026-10-30 | `866a87f` | E1: Classifier liefert Signale, urgency per Regeln (urgency_rules.py); Risk-Gate unverändert | 50 / 0 | 38 von 50 (76 %) | 32 von 50 (64 %) | 9 von 11 (82 %) | 9 von 11 (82 %) | EVAL-014, EVAL-046 | EVAL-006, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 0.99 / 1.00 | 0 | 45.1 / 51.2 s |
| e2-risk-no-urgency | 2026-10-30 | `866a87f` | Risk entkoppeln: Dringlichkeit aus dem Risk-Prompt entfernt (Basis 866a87f, ohne E1) | 50 / 0 | 40 von 50 (80 %) | 22 von 50 (44 %) | 9 von 11 (82 %) | 9 von 13 (69 %) | EVAL-014, EVAL-046 | EVAL-006, EVAL-021, EVAL-027, EVAL-042 | 23 von 25 (92 %) | 2 von 25 (8 %) | 1.00 / 1.00 | 0 | 21.3 / 25.8 s |
| single-vote | 2026-10-30 | `7cd6b12` | Classifier 1 Lauf statt 3, temperature 0 (Basis 866a87f) | 50 / 0 | 40 von 50 (80 %) | 21 von 50 (42 %) | 10 von 11 (91 %) | 10 von 13 (77 %) | EVAL-046 | EVAL-006, EVAL-021, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 1.00 / 1.00 | 0 | 16.2 / 21.4 s |
| e1b-signals | 2026-10-30 | `cb72e55` | E1b: 6 allgemeine Signale, urgency per Regeln; Basis single-vote (cb72e55); Risk unverändert | 50 / 0 | 39 von 50 (78 %) | 30 von 50 (60 %) | 9 von 11 (82 %) | 9 von 11 (82 %) | EVAL-014, EVAL-046 | EVAL-006, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 1.00 / 1.00 | 0 | 20.4 / 25.0 s |
| e3-categories | 2026-10-30 | `996b2d5` | E3: Kategorie-Definitionen geschärft (Basis single-vote cb72e55) | 50 / 0 | 43 von 50 (86 %) | 26 von 50 (52 %) | 10 von 11 (91 %) | 10 von 13 (77 %) | EVAL-046 | EVAL-006, EVAL-021, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 1.00 / 1.00 | 0 | 15.9 / 21.3 s |
| e4-risk-prompt | 2026-10-30 | `27dd315` | E4: Risk-Kriterien 1-4 explizit, Ärger ohne Folge = false, risk_reason als Zitat (Basis e3 27dd315) | 50 / 0 | 42 von 50 (84 %) | 26 von 50 (52 %) | 6 von 11 (55 %) | 6 von 8 (75 %) | EVAL-014, EVAL-025, EVAL-031, EVAL-045, EVAL-046 | EVAL-006, EVAL-027 | 23 von 25 (92 %) | 2 von 25 (8 %) | 1.00 / 1.00 | 0 | 17.2 / 20.9 s |
| e5-keywords | 2026-10-30 | `fa1ae69` | E5: Keyword-Hygiene - unzumutbar/skandal raus, klage nicht in beklage (Basis e3 27dd315) | 50 / 0 | 42 von 50 (84 %) | 26 von 50 (52 %) | 9 von 11 (82 %) | 9 von 10 (90 %) | EVAL-014, EVAL-046 | EVAL-021 | 23 von 25 (92 %) | 2 von 25 (8 %) | 1.00 / 1.00 | 0 | 17.1 / 21.9 s |
| e6e7-names | 2026-10-30 | `2d80c5c` | E6+E7: customer_name ohne Organisationen, Wortgrenzen, snap to text (Schwelle 0.85); Basis e5 2d80c5c | 50 / 0 | 42 von 50 (84 %) | 26 von 50 (52 %) | 9 von 11 (82 %) | 9 von 10 (90 %) | EVAL-014, EVAL-046 | EVAL-021 | 25 von 25 (100 %) | 0 von 25 (0 %) | 1.00 / 1.00 | 0 | 17.1 / 21.8 s |
| e10-risk-split | 2026-10-30 | `0bcbf8f` | e10: Risk-Guard mit zwei engen Ja/Nein-Fragen (Drohung, Gefahr) bei allen Tickets, ohne urgency; Basis 0bcbf8f | 50 / 0 | 42 von 50 (84 %) | 25 von 50 (50 %) | 7 von 11 (64 %) | 7 von 7 (100 %) | EVAL-014, EVAL-025, EVAL-031, EVAL-045 | — | 25 von 25 (100 %) | 0 von 25 (0 %) | 1.00 / 1.00 | 0 | 17.0 / 20.5 s |

## Holdout (`eval/holdout/tickets.jsonl`)

| Lauf | Datum | Commit | Notiz | ausgewertet / fehlgeschl. | Kategorie | Urgency | Risk Recall | Risk Precision | Risk FN | Risk FP | Name richtig | Name erfunden | Konfidenz richtig / falsch | Fallbacks | Latenz Median / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| holdout-baseline | 2026-10-30 | `da59602` | Holdout-Schlusslauf: App-Code Baseline da59602 (git worktree) | 29 / 1 | 23 von 29 (79 %) | 15 von 29 (52 %) | 7 von 7 (100 %) | 7 von 9 (78 %) | — | HOLD-007, HOLD-015 | 12 von 14 (86 %) | 0 von 15 (0 %) | 1.00 / 1.00 | 0 | 21.0 / 25.6 s |
| holdout-final | 2026-10-30 | `0bcbf8f` | Holdout-Schlusslauf: App-Code Gewinnerstand 0bcbf8f | 29 / 1 | 23 von 29 (79 %) | 14 von 29 (48 %) | 7 von 7 (100 %) | 7 von 9 (78 %) | — | HOLD-007, HOLD-015 | 12 von 14 (86 %) | 0 von 15 (0 %) | 1.00 / 1.00 | 0 | 16.8 / 20.6 s |

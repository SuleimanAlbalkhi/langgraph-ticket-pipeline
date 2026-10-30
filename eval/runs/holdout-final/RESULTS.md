# Evaluation: Ticket-Analyse-Pipeline — Lauf `holdout-final`

|  |  |
|---|---|
| Datum | 2026-10-30 |
| Modell | qwen2.5:3b |
| Hardware | GTX 1050 Ti 4 GB (Laptop), Intel i7-7700HQ, 16 GB RAM |
| Commit | `97ab451c39bf74c483256c1e8a3d3a56d7c0d8a7` |
| App-Code aus Commit | `0bcbf8faef96ca8a754d4903d33a0bc4e76b88be` |
| Docker-Image | `bbbc9db55be1`, gebaut 2026-10-30T22:09:31+00:00 |
| Ticket-Datei | `eval/holdout/tickets.jsonl` |
| Notiz | Holdout-Schlusslauf: App-Code Gewinnerstand 0bcbf8f |
| Testset-Größe | 30 |
| Ausgewertet | 29 |

> **Hinweis:** Von allen Metriken ausgeschlossen: fehlgeschlagene Anfragen: 1, Tickets ohne Ergebnis: 0. Alle Werte beziehen sich auf 29 Tickets.

| Ticket | Status | Fehler |
|---|---|---|
| HOLD-014 | 500 | HTTP 500 |

## Kategorie

Accuracy: **23 von 29 (79 %)**

| erwartet \ erhalten | technical_support | billing_dispute | general_inquiry | unknown |
|---|---|---|---|---|
| technical_support | 9 | 1 | 0 | 0 |
| billing_dispute | 0 | 7 | 0 | 0 |
| general_inquiry | 1 | 2 | 6 | 0 |
| unknown | 0 | 1 | 1 | 1 |

## Urgency

Accuracy: **14 von 29 (48 %)**

| erwartet \ erhalten | low | medium | high | critical |
|---|---|---|---|---|
| low | 3 | 1 | 0 | 0 |
| medium | 2 | 3 | 6 | 0 |
| high | 0 | 1 | 5 | 4 |
| critical | 0 | 0 | 1 | 3 |

## Risk-Flag

- Recall: **7 von 7 (100 %)** der Risiko-Tickets erkannt
- Precision: **7 von 9 (78 %)** der Eskalationen berechtigt
- False Negatives: —
- False Positives: HOLD-007, HOLD-015

## Kundenname

Vergleich nach Normalisierung (Kleinschreibung, Whitespace, Titel „Dr.“ optional).

- Richtig erkannt: **12 von 14 (86 %)** (Tickets mit Namen)
- Erfundener Name: **0 von 15 (0 %)** (Tickets ohne Namen)

## Latenz

| Median | p95 |
|---|---|
| 16.8 s | 20.6 s |

## Kalibrierung (confidence_score vs. Kategorie)

- Mittlere Konfidenz bei richtiger Kategorie: **1.00**
- Mittlere Konfidenz bei falscher Kategorie: **1.00**

| Konfidenz | richtig | falsch | Anteil richtig |
|---|---|---|---|
| 0.00 | 0 | 0 | n/a |
| 0.33 | 0 | 0 | n/a |
| 0.67 | 0 | 0 | n/a |
| 1.00 | 23 | 6 | 79 % |

## Fallback-Antworten

Summary „Extraktion fehlgeschlagen.“ / „Extraktion-Timeout.“ oder confidence_score 0: **0 von 29 (0 %)**

## Falsch klassifizierte Tickets (Kategorie)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| HOLD-018 | technical_support | billing_dispute | Datenleck (fremde Bank- und Kundendaten) = Sicherheitsrisiko -> critical; Sicherheitsrisiko -> risk [Kategorie: technical_support, weil Systemfehler mit Datenleck, kein Streit über Betrag oder Abbuchung] |
| HOLD-021 | general_inquiry | technical_support | Produktfrage mit Klärungsbedarf -> medium; kein Name |
| HOLD-022 | general_inquiry | billing_dispute | Frist + rechtliche Andeutung -> high; rechtliche Drohung -> risk |
| HOLD-027 | general_inquiry | billing_dispute | Frist genannt (20.11.) -> high; keine Drohung -> kein risk |
| HOLD-029 | unknown | general_inquiry | Kein erkennbarer Bezug -> unknown; Klärungsbedarf -> medium; kein Name |
| HOLD-030 | unknown | billing_dispute | Kein Sachbezug erkennbar -> unknown; Anwalt/rechtliche Schritte -> high; rechtliche Drohung -> risk; kein Name |

## Falsch klassifizierte Tickets (Urgency)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| HOLD-004 | medium | high | Normaler Defekt mit Klärungsbedarf, keine Frist -> medium |
| HOLD-005 | medium | high | Störung mit Klärungsbedarf, keine Frist -> medium; kein Name |
| HOLD-006 | high | critical | Frist + Eskalation + rechtliche Andeutung -> high; rechtliche Drohung + Eskalationsabsicht -> risk |
| HOLD-008 | medium | high | Grenzfall: verärgert, aber keine Drohung/Eskalation/Frist -> medium, kein risk |
| HOLD-009 | low | medium | Reine Information, keine Aktion erwartet -> low; kein Name |
| HOLD-010 | high | critical | Frist + Anwalt -> high; rechtliche Drohung -> risk |
| HOLD-013 | medium | high | Rechnungskorrektur ohne Frist -> medium; kein Name |
| HOLD-015 | medium | high | Grenzfall: verärgert, aber keine Drohung/Eskalation/Frist -> medium, kein risk |
| HOLD-016 | high | critical | Wort 'dringend' -> high; keine Drohung -> kein risk; nur Firma/Abteilung -> name null |
| HOLD-017 | medium | high | Fehlende Gutschrift, Klärungsbedarf ohne Frist -> medium; kein Name; Tippfehler |
| HOLD-018 | critical | high | Datenleck (fremde Bank- und Kundendaten) = Sicherheitsrisiko -> critical; Sicherheitsrisiko -> risk [Kategorie: technical_support, weil Systemfehler mit Datenleck, kein Streit über Betrag oder Abbuchung] |
| HOLD-020 | medium | low | Informationsanfrage mit Klärungsbedarf, keine Frist -> medium |
| HOLD-023 | high | medium | Wort 'dringend' + Frist -> high; keine Drohung -> kein risk; Name der absendenden Person (nicht der Adressatin) |
| HOLD-029 | medium | low | Kein erkennbarer Bezug -> unknown; Klärungsbedarf -> medium; kein Name |
| HOLD-030 | high | critical | Kein Sachbezug erkennbar -> unknown; Anwalt/rechtliche Schritte -> high; rechtliche Drohung -> risk; kein Name |

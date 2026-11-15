# Evaluation: Ticket-Analyse-Pipeline — Lauf `holdout-azure`

|  |  |
|---|---|
| Datum | 2026-11-15 |
| Modell | gpt-4.1-mini |
| Hardware | Azure Container App + Azure OpenAI gpt-4.1-mini GlobalStandard (France Central), 100k TPM |
| Commit | `27de201f6a5a74a3bce14a82b11c3a3ac01f006e` |
| App-Code aus Commit | `ade0826c48f277268d30feb5c12a4f1de3384151` |
| Docker-Image | `?`, gebaut ? |
| Ticket-Datei | `eval/holdout/tickets.jsonl` |
| Notiz | Holdout einmalig: Cloud gpt-4.1-mini + e11 gegen holdout-final |
| Testset-Größe | 30 |
| Ausgewertet | 30 |

## Kategorie

Accuracy: **26 von 30 (87 %)**

| erwartet \ erhalten | technical_support | billing_dispute | general_inquiry | unknown |
|---|---|---|---|---|
| technical_support | 10 | 0 | 0 | 0 |
| billing_dispute | 0 | 6 | 2 | 0 |
| general_inquiry | 0 | 0 | 9 | 0 |
| unknown | 0 | 0 | 2 | 1 |

## Urgency

Accuracy: **27 von 30 (90 %)**

| erwartet \ erhalten | low | medium | high | critical |
|---|---|---|---|---|
| low | 5 | 0 | 0 | 0 |
| medium | 2 | 8 | 1 | 0 |
| high | 0 | 0 | 10 | 0 |
| critical | 0 | 0 | 0 | 4 |

## Risk-Flag

- Recall: **7 von 7 (100 %)** der Risiko-Tickets erkannt
- Precision: **7 von 7 (100 %)** der Eskalationen berechtigt
- False Negatives: —
- False Positives: —

## Kundenname

Vergleich nach Normalisierung (Kleinschreibung, Whitespace, Titel „Dr.“ optional).

- Richtig erkannt: **15 von 15 (100 %)** (Tickets mit Namen)
- Erfundener Name: **0 von 15 (0 %)** (Tickets ohne Namen)

## Latenz

| Median | p95 |
|---|---|
| 2.2 s | 2.9 s |

## Kalibrierung (confidence_score vs. Kategorie)

- Mittlere Konfidenz bei richtiger Kategorie: **1.00**
- Mittlere Konfidenz bei falscher Kategorie: **1.00**

| Konfidenz | richtig | falsch | Anteil richtig |
|---|---|---|---|
| 0.00 | 0 | 0 | n/a |
| 0.33 | 0 | 0 | n/a |
| 0.67 | 0 | 0 | n/a |
| 1.00 | 26 | 4 | 87 % |

## Fallback-Antworten

Summary „Extraktion fehlgeschlagen.“ / „Extraktion-Timeout.“ oder confidence_score 0: **0 von 30 (0 %)**

## Falsch klassifizierte Tickets (Kategorie)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| HOLD-014 | billing_dispute | general_inquiry | Reine Zahlungsinformation, keine Aktion erwartet -> low |
| HOLD-015 | billing_dispute | general_inquiry | Grenzfall: verärgert, aber keine Drohung/Eskalation/Frist -> medium, kein risk |
| HOLD-029 | unknown | general_inquiry | Kein erkennbarer Bezug -> unknown; Klärungsbedarf -> medium; kein Name |
| HOLD-030 | unknown | general_inquiry | Kein Sachbezug erkennbar -> unknown; Anwalt/rechtliche Schritte -> high; rechtliche Drohung -> risk; kein Name |

## Falsch klassifizierte Tickets (Urgency)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| HOLD-008 | medium | high | Grenzfall: verärgert, aber keine Drohung/Eskalation/Frist -> medium, kein risk |
| HOLD-021 | medium | low | Produktfrage mit Klärungsbedarf -> medium; kein Name |
| HOLD-026 | medium | low | Informationsanfrage ohne Frist -> medium; kein Name |

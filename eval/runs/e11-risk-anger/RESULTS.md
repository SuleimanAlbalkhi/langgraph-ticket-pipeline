# Evaluation: Ticket-Analyse-Pipeline — Lauf `e11-risk-anger`

|  |  |
|---|---|
| Datum | 2026-11-08 |
| Modell | gpt-4.1-mini |
| Hardware | Azure OpenAI gpt-4.1-mini GlobalStandard (France Central), 100k TPM |
| Commit | `cb0920f35ab86ca64a1c9e1e78a5e4cef0cf8a2a` |
| App-Code aus Commit | `cb0920f35ab86ca64a1c9e1e78a5e4cef0cf8a2a` |
| Docker-Image | `?`, gebaut ? |
| Ticket-Datei | `eval/tickets.jsonl` |
| Notiz | Risk-Prompt ohne Kriterium 'extrem veraergerte Kunden mit Eskalationsabsicht' |
| Testset-Größe | 50 |
| Ausgewertet | 50 |

## Kategorie

Accuracy: **49 von 50 (98 %)**

| erwartet \ erhalten | technical_support | billing_dispute | general_inquiry | unknown |
|---|---|---|---|---|
| technical_support | 16 | 0 | 0 | 0 |
| billing_dispute | 0 | 16 | 0 | 0 |
| general_inquiry | 1 | 0 | 15 | 0 |
| unknown | 0 | 0 | 0 | 2 |

## Urgency

Accuracy: **40 von 50 (80 %)**

| erwartet \ erhalten | low | medium | high | critical |
|---|---|---|---|---|
| low | 11 | 4 | 0 | 0 |
| medium | 3 | 13 | 0 | 0 |
| high | 0 | 0 | 14 | 1 |
| critical | 0 | 0 | 2 | 2 |

## Risk-Flag

- Recall: **11 von 11 (100 %)** der Risiko-Tickets erkannt
- Precision: **11 von 11 (100 %)** der Eskalationen berechtigt
- False Negatives: —
- False Positives: —

## Kundenname

Vergleich nach Normalisierung (Kleinschreibung, Whitespace, Titel „Dr.“ optional).

- Richtig erkannt: **25 von 25 (100 %)** (Tickets mit Namen)
- Erfundener Name: **0 von 25 (0 %)** (Tickets ohne Namen)

## Latenz

| Median | p95 |
|---|---|
| 2.3 s | 3.2 s |

## Kalibrierung (confidence_score vs. Kategorie)

- Mittlere Konfidenz bei richtiger Kategorie: **1.00**
- Mittlere Konfidenz bei falscher Kategorie: **1.00**

| Konfidenz | richtig | falsch | Anteil richtig |
|---|---|---|---|
| 0.00 | 0 | 0 | n/a |
| 0.33 | 0 | 0 | n/a |
| 0.67 | 0 | 0 | n/a |
| 1.00 | 49 | 1 | 98 % |

## Fallback-Antworten

Summary „Extraktion fehlgeschlagen.“ / „Extraktion-Timeout.“ oder confidence_score 0: **0 von 50 (0 %)**

## Falsch klassifizierte Tickets (Kategorie)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| EVAL-046 | general_inquiry | technical_support | Mögliche Gesundheitsgefahr -> critical, aber Anfrage nach Information, keine Drohung oder Rechtsbezug; kein Name. [Label an Spezifikation angeglichen: Sicherheitsrisiko zählt laut risk_guard.py als kritisch] |

## Falsch klassifizierte Tickets (Urgency)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| EVAL-003 | critical | high | Totalausfall seit Tagen, Kündigungsdrohung mit Frist + Anwalt; Name mit Titel per 'Hier ist'. |
| EVAL-004 | high | critical | Kompletter Zugriffsverlust mit naher persönlicher Deadline, aber keine Drohung; Tippfehler, kein Name. |
| EVAL-005 | low | medium | Kleiner Einstellungs-Bug, als Frage formuliert, keine Auswirkung; Name in Grußformel. |
| EVAL-014 | critical | high | Heizungsausfall mit Kleinkind (Gefährdung), Verbraucherzentrale mit Frist; kein Keyword aus RISK_KEYWORDS, Risk nur über LLM-Pfad erkennbar. |
| EVAL-018 | low | medium | Formaler Rechnungsfehler ohne Betragsstreit, kein Zeitdruck; Kleinschreibung + Tippfehler, kein Name. |
| EVAL-023 | low | medium | Formal fehlerhafte Rechnung, höfliche Korrekturbitte ohne Frist; Name mit Titel in Grußformel. |
| EVAL-029 | low | medium | Kleine Mahngebühr, bereits bezahlt, sachlich; kein Name. |
| EVAL-037 | medium | low | Presse-/Infoanfrage mit Termin in einigen Wochen; Name mit Titel in Grußformel. |
| EVAL-041 | medium | low | Produktinformationsfrage mit Planungsrelevanz, kein Defekt; Name in Grußformel. |
| EVAL-047 | medium | low | Dokumentenanfrage ohne Defekt; kein Name. |

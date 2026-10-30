# Evaluation: Ticket-Analyse-Pipeline — Lauf `e1-signals`

|  |  |
|---|---|
| Datum | 2026-10-30 |
| Modell | qwen2.5:3b |
| Hardware | GTX 1050 Ti 4 GB (Laptop), Intel i7-7700HQ, 16 GB RAM |
| Commit | `866a87ff0d715b763470e4df57fa852106f14786` |
| Docker-Image | `5d07e2aacead`, gebaut 2026-10-30T17:44:58+00:00 |
| Notiz | E1: Classifier liefert Signale, urgency per Regeln (urgency_rules.py); Risk-Gate unverändert |
| Testset-Größe | 50 |
| Ausgewertet | 50 |

## Kategorie

Accuracy: **38 von 50 (76 %)**

| erwartet \ erhalten | technical_support | billing_dispute | general_inquiry | unknown |
|---|---|---|---|---|
| technical_support | 11 | 2 | 3 | 0 |
| billing_dispute | 0 | 16 | 0 | 0 |
| general_inquiry | 1 | 3 | 11 | 1 |
| unknown | 0 | 0 | 2 | 0 |

## Urgency

Accuracy: **32 von 50 (64 %)**

| erwartet \ erhalten | low | medium | high | critical |
|---|---|---|---|---|
| low | 9 | 6 | 0 | 0 |
| medium | 7 | 9 | 0 | 0 |
| high | 1 | 1 | 13 | 0 |
| critical | 0 | 1 | 2 | 1 |

## Risk-Flag

- Recall: **9 von 11 (82 %)** der Risiko-Tickets erkannt
- Precision: **9 von 11 (82 %)** der Eskalationen berechtigt
- False Negatives: EVAL-014, EVAL-046
- False Positives: EVAL-006, EVAL-027

## Kundenname

Vergleich nach Normalisierung (Kleinschreibung, Whitespace, Titel „Dr.“ optional).

- Richtig erkannt: **23 von 25 (92 %)** (Tickets mit Namen)
- Erfundener Name: **2 von 25 (8 %)** (Tickets ohne Namen) — EVAL-035, EVAL-039

## Latenz

| Median | p95 |
|---|---|
| 45.1 s | 51.2 s |

## Kalibrierung (confidence_score vs. Kategorie)

- Mittlere Konfidenz bei richtiger Kategorie: **0.99**
- Mittlere Konfidenz bei falscher Kategorie: **1.00**

| Konfidenz | richtig | falsch | Anteil richtig |
|---|---|---|---|
| 0.00 | 0 | 0 | n/a |
| 0.33 | 0 | 0 | n/a |
| 0.67 | 1 | 0 | 100 % |
| 1.00 | 37 | 12 | 76 % |

## Fallback-Antworten

Summary „Extraktion fehlgeschlagen.“ / „Extraktion-Timeout.“ oder confidence_score 0: **0 von 50 (0 %)**

## Falsch klassifizierte Tickets (Kategorie)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| EVAL-003 | technical_support | billing_dispute | Totalausfall seit Tagen, Kündigungsdrohung mit Frist + Anwalt; Name mit Titel per 'Hier ist'. |
| EVAL-005 | technical_support | general_inquiry | Kleiner Einstellungs-Bug, als Frage formuliert, keine Auswirkung; Name in Grußformel. |
| EVAL-008 | technical_support | general_inquiry | Harmloser Bug, Absender selbst 'stört nicht wirklich'; Kleinschreibung, kein Name. |
| EVAL-009 | technical_support | billing_dispute | Massiver Datenverlust, Rechtsabteilung + Klage angedroht; nur Geschäftsführung + Firma, kein Personenname. |
| EVAL-015 | technical_support | general_inquiry | Rein kosmetischer Anzeigefehler, vom Absender selbst so eingestuft; kein Name. |
| EVAL-038 | general_inquiry | billing_dispute | DSGVO-Auskunftsanfrage überfällig, Datenschutzbehörde + Anwalt mit Frist angedroht; Name in Grußformel. |
| EVAL-042 | general_inquiry | billing_dispute | Grenzfall: genervt über fehlende Antwort, aber keine Drohung, Kern ist eine Kompatibilitätsfrage -> risk false; Tippfehler, kein Name. |
| EVAL-044 | general_inquiry | billing_dispute | Dokumentenanfrage mit harter, naher Frist, aber Konsequenz ist geschäftlich, keine Drohung; nur Abteilung + Behörde. |
| EVAL-045 | general_inquiry | unknown | Kündigungsdrohung mit Frist + Verbraucherzentrale, Anliegen selbst ist Rückrufbitte; kein Keyword aus RISK_KEYWORDS; Name per 'hier ist'. |
| EVAL-046 | general_inquiry | technical_support | Mögliche Gesundheitsgefahr -> critical, aber Anfrage nach Information, keine Drohung oder Rechtsbezug; kein Name. [Label an Spezifikation angeglichen: Sicherheitsrisiko zählt laut risk_guard.py als kritisch] |
| EVAL-049 | unknown | general_inquiry | Bewerbung, thematisch kein Kundenticket; Absendername in Grußformel. |
| EVAL-050 | unknown | general_inquiry | Werbe-Mail, kein Kundenanliegen; nur Firmenname. |

## Falsch klassifizierte Tickets (Urgency)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| EVAL-003 | critical | high | Totalausfall seit Tagen, Kündigungsdrohung mit Frist + Anwalt; Name mit Titel per 'Hier ist'. |
| EVAL-004 | high | medium | Kompletter Zugriffsverlust mit naher persönlicher Deadline, aber keine Drohung; Tippfehler, kein Name. |
| EVAL-005 | low | medium | Kleiner Einstellungs-Bug, als Frage formuliert, keine Auswirkung; Name in Grußformel. |
| EVAL-014 | critical | high | Heizungsausfall mit Kleinkind (Gefährdung), Verbraucherzentrale mit Frist; kein Keyword aus RISK_KEYWORDS, Risk nur über LLM-Pfad erkennbar. |
| EVAL-017 | medium | low | Falscher Tarif auf Rechnung, sachliche Korrekturbitte; Name in Grußformel. |
| EVAL-018 | low | medium | Formaler Rechnungsfehler ohne Betragsstreit, kein Zeitdruck; Kleinschreibung + Tippfehler, kein Name. |
| EVAL-021 | high | low | Grenzfall: deutlich verärgert über unberechtigte Mahnung, fordert 'sofort', aber keine Drohung -> risk false. |
| EVAL-024 | medium | low | Abbuchung nach Kündigung, Kunde hat Beleg, kein Drohton; 'gekündigt' ist vergangene Kündigung, keine Drohung; kein Name. |
| EVAL-026 | medium | low | Erstattung einer nicht erbrachten Leistung, sachlich; Name per 'hier ist'. |
| EVAL-027 | medium | low | Grenzfall: verärgert, Risk-Keyword 'unzumutbar', fordert nur Erklärung, keine Drohung -> risk false; nur Abteilung + Firma. |
| EVAL-032 | medium | low | Unberechtigte Gebühr, sachliche Prüfbitte; Name in Grußformel. |
| EVAL-036 | low | medium | Informationsfrage zu Dokumentation, kein Defekt; Name per 'hier ist'. |
| EVAL-037 | medium | low | Presse-/Infoanfrage mit Termin in einigen Wochen; Name mit Titel in Grußformel. |
| EVAL-039 | low | medium | Unverbindliche Anfrage weit in der Zukunft; nur Gremium + Firma (Familienname im Firmennamen ist kein Absendername). |
| EVAL-042 | medium | low | Grenzfall: genervt über fehlende Antwort, aber keine Drohung, Kern ist eine Kompatibilitätsfrage -> risk false; Tippfehler, kein Name. |
| EVAL-046 | critical | medium | Mögliche Gesundheitsgefahr -> critical, aber Anfrage nach Information, keine Drohung oder Rechtsbezug; kein Name. [Label an Spezifikation angeglichen: Sicherheitsrisiko zählt laut risk_guard.py als kritisch] |
| EVAL-048 | low | medium | Positives Feedback ohne Handlungsbedarf; Doppelname in Grußformel. |
| EVAL-050 | low | medium | Werbe-Mail, kein Kundenanliegen; nur Firmenname. |

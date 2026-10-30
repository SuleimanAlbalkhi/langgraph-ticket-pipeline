# Evaluation: Ticket-Analyse-Pipeline — Lauf `e1b-signals`

|  |  |
|---|---|
| Datum | 2026-10-30 |
| Modell | qwen2.5:3b |
| Hardware | GTX 1050 Ti 4 GB (Laptop), Intel i7-7700HQ, 16 GB RAM |
| Commit | `cb72e558b61af0dba7c08d6db67c5a824e5a5edd` |
| Docker-Image | `f6ff9ddcdaa4`, gebaut 2026-10-30T19:27:55+00:00 |
| Notiz | E1b: 6 allgemeine Signale, urgency per Regeln; Basis single-vote (cb72e55); Risk unverändert |
| Testset-Größe | 50 |
| Ausgewertet | 50 |

## Kategorie

Accuracy: **39 von 50 (78 %)**

| erwartet \ erhalten | technical_support | billing_dispute | general_inquiry | unknown |
|---|---|---|---|---|
| technical_support | 12 | 1 | 3 | 0 |
| billing_dispute | 0 | 16 | 0 | 0 |
| general_inquiry | 1 | 4 | 11 | 0 |
| unknown | 0 | 0 | 2 | 0 |

## Urgency

Accuracy: **30 von 50 (60 %)**

| erwartet \ erhalten | low | medium | high | critical |
|---|---|---|---|---|
| low | 1 | 14 | 0 | 0 |
| medium | 1 | 14 | 1 | 0 |
| high | 1 | 2 | 12 | 0 |
| critical | 0 | 0 | 1 | 3 |

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
| 20.4 s | 25.0 s |

## Kalibrierung (confidence_score vs. Kategorie)

- Mittlere Konfidenz bei richtiger Kategorie: **1.00**
- Mittlere Konfidenz bei falscher Kategorie: **1.00**

| Konfidenz | richtig | falsch | Anteil richtig |
|---|---|---|---|
| 0.00 | 0 | 0 | n/a |
| 0.33 | 0 | 0 | n/a |
| 0.67 | 0 | 0 | n/a |
| 1.00 | 39 | 11 | 78 % |

## Fallback-Antworten

Summary „Extraktion fehlgeschlagen.“ / „Extraktion-Timeout.“ oder confidence_score 0: **0 von 50 (0 %)**

## Falsch klassifizierte Tickets (Kategorie)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| EVAL-005 | technical_support | general_inquiry | Kleiner Einstellungs-Bug, als Frage formuliert, keine Auswirkung; Name in Grußformel. |
| EVAL-008 | technical_support | general_inquiry | Harmloser Bug, Absender selbst 'stört nicht wirklich'; Kleinschreibung, kein Name. |
| EVAL-009 | technical_support | billing_dispute | Massiver Datenverlust, Rechtsabteilung + Klage angedroht; nur Geschäftsführung + Firma, kein Personenname. |
| EVAL-015 | technical_support | general_inquiry | Rein kosmetischer Anzeigefehler, vom Absender selbst so eingestuft; kein Name. |
| EVAL-038 | general_inquiry | billing_dispute | DSGVO-Auskunftsanfrage überfällig, Datenschutzbehörde + Anwalt mit Frist angedroht; Name in Grußformel. |
| EVAL-042 | general_inquiry | billing_dispute | Grenzfall: genervt über fehlende Antwort, aber keine Drohung, Kern ist eine Kompatibilitätsfrage -> risk false; Tippfehler, kein Name. |
| EVAL-044 | general_inquiry | billing_dispute | Dokumentenanfrage mit harter, naher Frist, aber Konsequenz ist geschäftlich, keine Drohung; nur Abteilung + Behörde. |
| EVAL-045 | general_inquiry | billing_dispute | Kündigungsdrohung mit Frist + Verbraucherzentrale, Anliegen selbst ist Rückrufbitte; kein Keyword aus RISK_KEYWORDS; Name per 'hier ist'. |
| EVAL-046 | general_inquiry | technical_support | Mögliche Gesundheitsgefahr -> critical, aber Anfrage nach Information, keine Drohung oder Rechtsbezug; kein Name. [Label an Spezifikation angeglichen: Sicherheitsrisiko zählt laut risk_guard.py als kritisch] |
| EVAL-049 | unknown | general_inquiry | Bewerbung, thematisch kein Kundenticket; Absendername in Grußformel. |
| EVAL-050 | unknown | general_inquiry | Werbe-Mail, kein Kundenanliegen; nur Firmenname. |

## Falsch klassifizierte Tickets (Urgency)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| EVAL-001 | low | medium | Kosmetischer App-Fehler ohne Auswirkung, Absender explizit 'nicht dringend'; Name in Grußformel. |
| EVAL-004 | high | medium | Kompletter Zugriffsverlust mit naher persönlicher Deadline, aber keine Drohung; Tippfehler, kein Name. |
| EVAL-005 | low | medium | Kleiner Einstellungs-Bug, als Frage formuliert, keine Auswirkung; Name in Grußformel. |
| EVAL-008 | low | medium | Harmloser Bug, Absender selbst 'stört nicht wirklich'; Kleinschreibung, kein Name. |
| EVAL-014 | critical | high | Heizungsausfall mit Kleinkind (Gefährdung), Verbraucherzentrale mit Frist; kein Keyword aus RISK_KEYWORDS, Risk nur über LLM-Pfad erkennbar. |
| EVAL-015 | low | medium | Rein kosmetischer Anzeigefehler, vom Absender selbst so eingestuft; kein Name. |
| EVAL-018 | low | medium | Formaler Rechnungsfehler ohne Betragsstreit, kein Zeitdruck; Kleinschreibung + Tippfehler, kein Name. |
| EVAL-021 | high | low | Grenzfall: deutlich verärgert über unberechtigte Mahnung, fordert 'sofort', aber keine Drohung -> risk false. |
| EVAL-022 | high | medium | Hoher Betrag ohne Rechtsgrund, Betrugsvorwurf + Anwaltskanzlei; nur Abteilung + Firma. [Label an Spezifikation angeglichen: rechtliche Drohung ist laut Classifier-Regel high, critical nur Sicherheit/Datenverlust/Ausfall] |
| EVAL-023 | low | medium | Formal fehlerhafte Rechnung, höfliche Korrekturbitte ohne Frist; Name mit Titel in Grußformel. |
| EVAL-024 | medium | low | Abbuchung nach Kündigung, Kunde hat Beleg, kein Drohton; 'gekündigt' ist vergangene Kündigung, keine Drohung; kein Name. |
| EVAL-033 | low | medium | Vertriebsanfrage ohne Problem oder Zeitdruck; Name in Grußformel. |
| EVAL-034 | low | medium | Einfache Frage nach Öffnungszeiten; kein Name. |
| EVAL-036 | low | medium | Informationsfrage zu Dokumentation, kein Defekt; Name per 'hier ist'. |
| EVAL-039 | low | medium | Unverbindliche Anfrage weit in der Zukunft; nur Gremium + Firma (Familienname im Firmennamen ist kein Absendername). |
| EVAL-042 | medium | high | Grenzfall: genervt über fehlende Antwort, aber keine Drohung, Kern ist eine Kompatibilitätsfrage -> risk false; Tippfehler, kein Name. |
| EVAL-043 | low | medium | Frage zu Zahlungsarten, kein Rechnungsstreit (Wort 'Rechnung' als Falle für billing_dispute); Name in Grußformel. |
| EVAL-048 | low | medium | Positives Feedback ohne Handlungsbedarf; Doppelname in Grußformel. |
| EVAL-049 | low | medium | Bewerbung, thematisch kein Kundenticket; Absendername in Grußformel. |
| EVAL-050 | low | medium | Werbe-Mail, kein Kundenanliegen; nur Firmenname. |

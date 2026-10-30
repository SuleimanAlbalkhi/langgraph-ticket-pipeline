# Evaluation: Ticket-Analyse-Pipeline — Lauf `e3-categories`

|  |  |
|---|---|
| Datum | 2026-10-30 |
| Modell | qwen2.5:3b |
| Hardware | GTX 1050 Ti 4 GB (Laptop), Intel i7-7700HQ, 16 GB RAM |
| Commit | `996b2d5b07494556d4a089ae6e14d356af7bf533` |
| Docker-Image | `165e1a07c845`, gebaut 2026-10-30T19:47:49+00:00 |
| Notiz | E3: Kategorie-Definitionen geschärft (Basis single-vote cb72e55) |
| Testset-Größe | 50 |
| Ausgewertet | 50 |

## Kategorie

Accuracy: **43 von 50 (86 %)**

| erwartet \ erhalten | technical_support | billing_dispute | general_inquiry | unknown |
|---|---|---|---|---|
| technical_support | 15 | 1 | 0 | 0 |
| billing_dispute | 0 | 16 | 0 | 0 |
| general_inquiry | 1 | 4 | 11 | 0 |
| unknown | 0 | 0 | 1 | 1 |

## Urgency

Accuracy: **26 von 50 (52 %)**

| erwartet \ erhalten | low | medium | high | critical |
|---|---|---|---|---|
| low | 8 | 4 | 3 | 0 |
| medium | 4 | 4 | 8 | 0 |
| high | 0 | 0 | 11 | 4 |
| critical | 0 | 0 | 1 | 3 |

## Risk-Flag

- Recall: **10 von 11 (91 %)** der Risiko-Tickets erkannt
- Precision: **10 von 13 (77 %)** der Eskalationen berechtigt
- False Negatives: EVAL-046
- False Positives: EVAL-006, EVAL-021, EVAL-027

## Kundenname

Vergleich nach Normalisierung (Kleinschreibung, Whitespace, Titel „Dr.“ optional).

- Richtig erkannt: **23 von 25 (92 %)** (Tickets mit Namen)
- Erfundener Name: **2 von 25 (8 %)** (Tickets ohne Namen) — EVAL-035, EVAL-039

## Latenz

| Median | p95 |
|---|---|
| 15.9 s | 21.3 s |

## Kalibrierung (confidence_score vs. Kategorie)

- Mittlere Konfidenz bei richtiger Kategorie: **1.00**
- Mittlere Konfidenz bei falscher Kategorie: **1.00**

| Konfidenz | richtig | falsch | Anteil richtig |
|---|---|---|---|
| 0.00 | 0 | 0 | n/a |
| 0.33 | 0 | 0 | n/a |
| 0.67 | 0 | 0 | n/a |
| 1.00 | 43 | 7 | 86 % |

## Fallback-Antworten

Summary „Extraktion fehlgeschlagen.“ / „Extraktion-Timeout.“ oder confidence_score 0: **0 von 50 (0 %)**

## Falsch klassifizierte Tickets (Kategorie)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| EVAL-009 | technical_support | billing_dispute | Massiver Datenverlust, Rechtsabteilung + Klage angedroht; nur Geschäftsführung + Firma, kein Personenname. |
| EVAL-038 | general_inquiry | billing_dispute | DSGVO-Auskunftsanfrage überfällig, Datenschutzbehörde + Anwalt mit Frist angedroht; Name in Grußformel. |
| EVAL-042 | general_inquiry | billing_dispute | Grenzfall: genervt über fehlende Antwort, aber keine Drohung, Kern ist eine Kompatibilitätsfrage -> risk false; Tippfehler, kein Name. |
| EVAL-044 | general_inquiry | billing_dispute | Dokumentenanfrage mit harter, naher Frist, aber Konsequenz ist geschäftlich, keine Drohung; nur Abteilung + Behörde. |
| EVAL-045 | general_inquiry | billing_dispute | Kündigungsdrohung mit Frist + Verbraucherzentrale, Anliegen selbst ist Rückrufbitte; kein Keyword aus RISK_KEYWORDS; Name per 'hier ist'. |
| EVAL-046 | general_inquiry | technical_support | Mögliche Gesundheitsgefahr -> critical, aber Anfrage nach Information, keine Drohung oder Rechtsbezug; kein Name. [Label an Spezifikation angeglichen: Sicherheitsrisiko zählt laut risk_guard.py als kritisch] |
| EVAL-050 | unknown | general_inquiry | Werbe-Mail, kein Kundenanliegen; nur Firmenname. |

## Falsch klassifizierte Tickets (Urgency)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| EVAL-001 | low | medium | Kosmetischer App-Fehler ohne Auswirkung, Absender explizit 'nicht dringend'; Name in Grußformel. |
| EVAL-005 | low | medium | Kleiner Einstellungs-Bug, als Frage formuliert, keine Auswirkung; Name in Grußformel. |
| EVAL-008 | low | medium | Harmloser Bug, Absender selbst 'stört nicht wirklich'; Kleinschreibung, kein Name. |
| EVAL-012 | high | critical | Grenzfall: frustriert, Großbuchstaben, lange Wartezeit, aber keine Drohung und kein Risk-Keyword -> risk false. |
| EVAL-013 | medium | high | Technisches Limit falsch konfiguriert, Erwähnung 'Vertrag' ist keine Abrechnungsfrage; Name mit Titel in Grußformel. |
| EVAL-015 | low | medium | Rein kosmetischer Anzeigefehler, vom Absender selbst so eingestuft; kein Name. |
| EVAL-016 | medium | high | Konfigurationsproblem mit Teilausfall, Workaround (ausgehend) möglich; kein Name. |
| EVAL-017 | medium | high | Falscher Tarif auf Rechnung, sachliche Korrekturbitte; Name in Grußformel. |
| EVAL-018 | low | high | Formaler Rechnungsfehler ohne Betragsstreit, kein Zeitdruck; Kleinschreibung + Tippfehler, kein Name. |
| EVAL-019 | high | critical | Wiederholte Doppelabbuchung, Anwalt + rechtliche Schritte mit Frist; Name per 'Hier ist'. |
| EVAL-022 | high | critical | Hoher Betrag ohne Rechtsgrund, Betrugsvorwurf + Anwaltskanzlei; nur Abteilung + Firma. [Label an Spezifikation angeglichen: rechtliche Drohung ist laut Classifier-Regel high, critical nur Sicherheit/Datenverlust/Ausfall] |
| EVAL-023 | low | high | Formal fehlerhafte Rechnung, höfliche Korrekturbitte ohne Frist; Name mit Titel in Grußformel. |
| EVAL-024 | medium | high | Abbuchung nach Kündigung, Kunde hat Beleg, kein Drohton; 'gekündigt' ist vergangene Kündigung, keine Drohung; kein Name. |
| EVAL-026 | medium | high | Erstattung einer nicht erbrachten Leistung, sachlich; Name per 'hier ist'. |
| EVAL-027 | medium | high | Grenzfall: verärgert, Risk-Keyword 'unzumutbar', fordert nur Erklärung, keine Drohung -> risk false; nur Abteilung + Firma. |
| EVAL-028 | high | critical | Drohender Schufa-Eintrag, Klage mit Frist angekündigt; Name in Grußformel. [Label an Spezifikation angeglichen: rechtliche Drohung ist laut Classifier-Regel high, critical nur Sicherheit/Datenverlust/Ausfall] |
| EVAL-029 | low | high | Kleine Mahngebühr, bereits bezahlt, sachlich; kein Name. |
| EVAL-032 | medium | high | Unberechtigte Gebühr, sachliche Prüfbitte; Name in Grußformel. |
| EVAL-037 | medium | low | Presse-/Infoanfrage mit Termin in einigen Wochen; Name mit Titel in Grußformel. |
| EVAL-040 | medium | low | Stammdatenänderung, relevant für nächste Lieferung, kein Defekt; Tippfehler, kein Name. |
| EVAL-041 | medium | low | Produktinformationsfrage mit Planungsrelevanz, kein Defekt; Name in Grußformel. |
| EVAL-042 | medium | high | Grenzfall: genervt über fehlende Antwort, aber keine Drohung, Kern ist eine Kompatibilitätsfrage -> risk false; Tippfehler, kein Name. |
| EVAL-046 | critical | high | Mögliche Gesundheitsgefahr -> critical, aber Anfrage nach Information, keine Drohung oder Rechtsbezug; kein Name. [Label an Spezifikation angeglichen: Sicherheitsrisiko zählt laut risk_guard.py als kritisch] |
| EVAL-047 | medium | low | Dokumentenanfrage ohne Defekt; kein Name. |

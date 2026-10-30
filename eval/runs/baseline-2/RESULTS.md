# Evaluation: Ticket-Analyse-Pipeline — Lauf `baseline-2`

|  |  |
|---|---|
| Datum | 2026-10-30 |
| Modell | qwen2.5:3b |
| Hardware | GTX 1050 Ti 4 GB (Laptop), Intel i7-7700HQ, 16 GB RAM |
| Commit | `1bfa5b55862194d039a0c756fe4ea999e06d04f6` |
| Docker-Image | `?`, gebaut ? |
| Notiz | Rauschmessung: Wiederholung der Baseline ohne Codeänderung |
| Testset-Größe | 50 |
| Ausgewertet | 50 |

## Kategorie

Accuracy: **41 von 50 (82 %)**

| erwartet \ erhalten | technical_support | billing_dispute | general_inquiry | unknown |
|---|---|---|---|---|
| technical_support | 14 | 0 | 2 | 0 |
| billing_dispute | 0 | 16 | 0 | 0 |
| general_inquiry | 1 | 3 | 11 | 1 |
| unknown | 0 | 0 | 2 | 0 |

## Urgency

Accuracy: **22 von 50 (44 %)**

| erwartet \ erhalten | low | medium | high | critical |
|---|---|---|---|---|
| low | 7 | 5 | 3 | 0 |
| medium | 0 | 6 | 10 | 0 |
| high | 0 | 0 | 5 | 10 |
| critical | 0 | 0 | 0 | 4 |

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
| 21.5 s | 27.1 s |

## Kalibrierung (confidence_score vs. Kategorie)

- Mittlere Konfidenz bei richtiger Kategorie: **0.99**
- Mittlere Konfidenz bei falscher Kategorie: **1.00**

| Konfidenz | richtig | falsch | Anteil richtig |
|---|---|---|---|
| 0.00 | 0 | 0 | n/a |
| 0.33 | 0 | 0 | n/a |
| 0.67 | 1 | 0 | 100 % |
| 1.00 | 40 | 9 | 82 % |

## Fallback-Antworten

Summary „Extraktion fehlgeschlagen.“ / „Extraktion-Timeout.“ oder confidence_score 0: **0 von 50 (0 %)**

## Falsch klassifizierte Tickets (Kategorie)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| EVAL-005 | technical_support | general_inquiry | Kleiner Einstellungs-Bug, als Frage formuliert, keine Auswirkung; Name in Grußformel. |
| EVAL-015 | technical_support | general_inquiry | Rein kosmetischer Anzeigefehler, vom Absender selbst so eingestuft; kein Name. |
| EVAL-034 | general_inquiry | unknown | Einfache Frage nach Öffnungszeiten; kein Name. |
| EVAL-038 | general_inquiry | billing_dispute | DSGVO-Auskunftsanfrage überfällig, Datenschutzbehörde + Anwalt mit Frist angedroht; Name in Grußformel. |
| EVAL-044 | general_inquiry | billing_dispute | Dokumentenanfrage mit harter, naher Frist, aber Konsequenz ist geschäftlich, keine Drohung; nur Abteilung + Behörde. |
| EVAL-045 | general_inquiry | billing_dispute | Kündigungsdrohung mit Frist + Verbraucherzentrale, Anliegen selbst ist Rückrufbitte; kein Keyword aus RISK_KEYWORDS; Name per 'hier ist'. |
| EVAL-046 | general_inquiry | technical_support | Mögliche Gesundheitsgefahr -> critical, aber Anfrage nach Information, keine Drohung oder Rechtsbezug; kein Name. [Label an Spezifikation angeglichen: Sicherheitsrisiko zählt laut risk_guard.py als kritisch] |
| EVAL-049 | unknown | general_inquiry | Bewerbung, thematisch kein Kundenticket; Absendername in Grußformel. |
| EVAL-050 | unknown | general_inquiry | Werbe-Mail, kein Kundenanliegen; nur Firmenname. |

## Falsch klassifizierte Tickets (Urgency)

| Ticket | erwartet | erhalten | Note |
|---|---|---|---|
| EVAL-001 | low | medium | Kosmetischer App-Fehler ohne Auswirkung, Absender explizit 'nicht dringend'; Name in Grußformel. |
| EVAL-002 | medium | high | Hardwaredefekt mit Fehlercode, Betrieb eingeschränkt aber nicht gestoppt; nur Abteilung + Firma, kein Personenname. |
| EVAL-004 | high | critical | Kompletter Zugriffsverlust mit naher persönlicher Deadline, aber keine Drohung; Tippfehler, kein Name. |
| EVAL-005 | low | medium | Kleiner Einstellungs-Bug, als Frage formuliert, keine Auswirkung; Name in Grußformel. |
| EVAL-006 | high | critical | Grenzfall: stark verärgert, enthält Risk-Keyword 'unzumutbar', aber keine Drohung (kein Anwalt, keine Kündigung) -> risk false. |
| EVAL-007 | medium | high | Funktionsstörung mehrerer Arbeitsplätze, Kernbetrieb läuft weiter; nur Abteilung + Organisation. |
| EVAL-008 | low | medium | Harmloser Bug, Absender selbst 'stört nicht wirklich'; Kleinschreibung, kein Name. |
| EVAL-011 | high | critical | Kassenausfall schränkt Geschäftsbetrieb stark ein, 'dringend', aber keine Drohung; Name + Filiale -> Personenname zählt. |
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
| EVAL-031 | high | critical | Kündigungsdrohung (drei Verträge) mit Frist; kein Keyword aus RISK_KEYWORDS; kein Name. |
| EVAL-032 | medium | high | Unberechtigte Gebühr, sachliche Prüfbitte; Name in Grußformel. |
| EVAL-036 | low | medium | Informationsfrage zu Dokumentation, kein Defekt; Name per 'hier ist'. |
| EVAL-038 | high | critical | DSGVO-Auskunftsanfrage überfällig, Datenschutzbehörde + Anwalt mit Frist angedroht; Name in Grußformel. |
| EVAL-042 | medium | high | Grenzfall: genervt über fehlende Antwort, aber keine Drohung, Kern ist eine Kompatibilitätsfrage -> risk false; Tippfehler, kein Name. |
| EVAL-045 | high | critical | Kündigungsdrohung mit Frist + Verbraucherzentrale, Anliegen selbst ist Rückrufbitte; kein Keyword aus RISK_KEYWORDS; Name per 'hier ist'. |

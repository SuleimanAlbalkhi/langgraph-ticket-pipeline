# Experiment-Log

Ein Eintrag pro Experiment. Kennzahlen = Zeile aus `eval/runs/COMPARISON.md`; Annahme nach den
Schwellen in `CLAUDE.md` (Kategorie/Urgency ≥ 3 Tickets, Risk/Name ≥ 1, Risk-Recall nie < 10/11).
Abgelehnter Code liegt als Patch unter `eval/patches/<lauf>.patch`.

## e1-signals — abgelehnt
- **Änderung:** Classifier liefert 8 boolesche Signale statt urgency; urgency per festen Regeln (`urgency_rules.py`). Risk-Gate unverändert.
- **Ergebnis:** Kategorie 38/50 · Urgency **32/50** (+12) · Risk Recall **9/11** · Precision 9/11 · Name 23/25, 2 erfunden · Latenz **45.1 / 51.2 s**
- **Entscheidung:** abgelehnt — Risk-Recall unter der harten Grenze 10/11.
- **Grund:** EVAL-014 bekam urgency high statt critical; das Risk-LLM sah „Dringlichkeit: high“ im Prompt und sagte false.
- **Auffällig:** Überschätzung weg, aber „nur Info“-Signal feuert 18× (7× medium→low); Sicherheit/Stillstand nie gesetzt; Latenz verdoppelt (längere JSON-Antwort × 3 Votes).

## e2-risk-no-urgency — abgelehnt
- **Änderung:** Zeile „Dringlichkeit: …“ aus dem Risk-Prompt entfernt (Basis 866a87f, ohne E1).
- **Ergebnis:** Kategorie 40/50 · Urgency 22/50 · Risk Recall **9/11** · Precision 9/13 · Name 23/25, 2 erfunden · Latenz 21.3 / 25.8 s
- **Entscheidung:** abgelehnt — Risk-Recall unter 10/11, Precision schlechter (neuer FP EVAL-042).
- **Grund:** EVAL-014 wird auch bei urgency critical nicht mehr erkannt: das Risk-LLM hat sich auf „Dringlichkeit: critical“ gestützt, nicht auf den Text.
- **Auffällig:** Hypothese widerlegt — nicht die Gate-Kopplung, sondern das Risk-Urteil selbst hängt an der Urgency. 014 (Gesundheit + Verbraucherzentrale) braucht explizite Kriterien im Risk-Prompt (E4).

## single-vote — angenommen
- **Änderung:** Classifier 1 Lauf statt 3, temperature 0 statt 0.5 (Mehrheitslogik bleibt für N_VOTES > 1).
- **Ergebnis:** Kategorie 40/50 · Urgency 21/50 · Risk Recall 10/11 · Precision 10/13 · Name 23/25, 2 erfunden · Latenz **16.2 / 21.4 s** (vorher 21.7 / 26.2)
- **Entscheidung:** angenommen (keine Metrik schlechter, Latenz −25 %); nach Rückfrage bestätigt. Ab hier stoppt die Warteschlange nur, wenn der Recall gegenüber dem letzten angenommenen Stand *auf* 10/11 fällt.
- **Grund:** Nur EVAL-025 urgency anders (critical→high, jetzt richtig); Risk und Kategorie je Ticket identisch zu refactor.
- **Auffällig:** Confidence ist mit 1 Lauf konstant 1.0 — war aber schon vorher ohne Aussagekraft (0.99 vs. 0.97).

## e1b-signals — abgelehnt
- **Änderung:** E1 mit 6 allgemein formulierten Signalen (Frist, Drohung, Gefahr/Datenverlust, Stillstand, dringend, keine Aktion erwartet), urgency per Regeln; Basis single-vote.
- **Ergebnis:** Kategorie 39/50 · Urgency **30/50** (+9) · Risk Recall **9/11** · Precision 9/11 · Name 23/25, 2 erfunden · Latenz 20.4 / 25.0 s
- **Entscheidung:** abgelehnt — Risk-Recall unter 10/11.
- **Grund:** EVAL-014 nur „frist_genannt“ → high statt critical; Risk-LLM sagt bei „Dringlichkeit: high“ false (wie in e1-signals). FP 021 dafür weg.
- **Auffällig:** Jetzt Unterschätzung statt Überschätzung — „keine_aktion_erwartet“ feuert nur 3× (14× low→medium). Signal-Ansatz trägt erst, wenn das Risk-Urteil nicht mehr an urgency critical hängt → nach E4 erneut prüfen.

## e3-categories — angenommen
- **Änderung:** Kategorie-Definitionen im Classifier-Prompt geschärft (tech inkl. kleiner/als Frage formulierter Fehler; billing nur bei strittigem Geld; GI ohne Defekt/Streit, Drohung/Frist ändert Kategorie nicht; unknown = kein Kundenanliegen).
- **Ergebnis:** Kategorie **43/50** (+3) · Urgency **26/50** (+5) · Risk Recall 10/11 · Precision 10/13 · Name 23/25, 2 erfunden · Latenz 15.9 / 21.3 s
- **Entscheidung:** angenommen (nach Rückfrage; Kategorie genau an der Schwelle +3).
- **Grund:** richtig neu 005, 015, 034, 041, 049; falsch neu 009, 042. Urgency +5 als Nebeneffekt (6× critical→high richtig), keine Metrik schlechter.
- **Auffällig:** GI→billing bleibt (038, 044, 045 trotz „Drohungen/Fristen ändern die Kategorie nicht“); 050 (Werbung) weiter general_inquiry; 031/045 jetzt high statt critical, Risk trotzdem erkannt.

## e4-risk-prompt — abgelehnt
- **Änderung:** Risk-Prompt mit 4 expliziten Kriterien (Recht/externe Stelle, Kündigung mit Frist, Betrug, Gefahr/Datenverlust), „Ärger ohne Folge = false“, risk_reason als wörtliches Zitat; Basis e3.
- **Ergebnis:** Kategorie 42/50 · Urgency 26/50 · Risk Recall **6/11** · Precision 6/8 · Name 23/25, 2 erfunden · Latenz 17.2 / 20.9 s
- **Entscheidung:** abgelehnt — Recall bricht ein (−4).
- **Grund:** Das LLM sagt bei allen Tickets ohne Keyword false (014, 025, 031, 045, 046); alle verbliebenen Treffer kommen aus dem Keyword-Floor. Das strenge „NUR dann true“ macht das 3B-Modell übervorsichtig.
- **Auffällig:** Zitat-Vorgabe wird ignoriert (Reason meist leer bzw. Floor-Text, einmal Kriterium abgeschrieben). FP 021 weg, 006/027 bleiben (Keyword „unzumutbar“).

## e5-keywords — angenommen
- **Änderung:** „unzumutbar“/„skandal“ aus dem harten Keyword-Floor; „klage“ trifft nicht mehr in „beklage“ (Teilstring für Komposita bleibt); xfail „beklagen“ behoben.
- **Ergebnis:** Kategorie 42/50 · Urgency 26/50 · Risk Recall **9/11** · Precision **9/10** (FP 006, 027 weg) · Name 23/25, 2 erfunden · Latenz 17.1 / 21.9 s
- **Entscheidung:** angenommen nach Rückfrage — formal 9/11, der Verlust (014) ist Classifier-Rauschen, nicht E5.
- **Grund:** Verloren ist nur EVAL-014 (kein Keyword, E5 wirkt dort nicht): der Classifier gab urgency high statt critical, das Risk-LLM sagt dann false. Dieselbe Abweichung (014 high, 005 GI/low) trat mit identischem Classifier-Prompt auch in e4 auf → vermutlich war critical in e3 der Ausreißer.
- **Auffällig:** Die 10/11 des aktuellen Gewinners e3 hängen an einem instabilen Classifier-Ergebnis für 014 (temperature 0, trotzdem nicht deterministisch).

## e6e7-names — angenommen
- **Änderung:** customer_name-Nachbearbeitung: Signaturen mit Organisations-Marker verworfen (Person vor dem Komma bleibt), Abgleich nur an Wortgrenzen (auch invoice_number/error_code), sonst „snap to text“ auf die ähnlichste Wortfolge ab Ähnlichkeit 0.85.
- **Ergebnis:** Kategorie 42/50 · Urgency 26/50 · Risk Recall 9/11 · Precision 9/10 · Name **25/25**, **0 erfunden** · Latenz 17.1 / 21.8 s
- **Entscheidung:** angenommen — Name +2 / erfunden −2, alle anderen Metriken je Ticket identisch zu e5.
- **Grund:** 035/039 (Signatur) jetzt null; 023 „Sauer“ → „Sauerbeck“ und 037 „Grwald“ → „Grünwald“ per Snap.
- **Auffällig:** Reine Nachbearbeitung ohne Prompt-Änderung — Classifier/Risk unberührt, daher kein Rauschen in den übrigen Metriken.

## e9-no-retry — angenommen (ohne Lauf)
- **Änderung:** Extractor-Retry-Schleife entfernt (Router, MAX_RETRIES, retry_count, Retry-Hinweis im Prompt); Graph jetzt linear classifier → extractor → risk_guard.
- **Ergebnis:** kein Eval-Lauf (vereinbart: 0 Retries in den Logs). Container-Logs: 63 + 53 Extractor-Läufe, 0× „RETRY“, Router immer `reason=ok`.
- **Entscheidung:** angenommen — toter Code, Verhalten unverändert; normaler Extractor-Prompt per Snapshot byte-identisch.
- **Grund:** Retry griff nur bei Summary < 20 Zeichen UND allen Feldern null; die Fallback-Summary ist selbst länger (bekannte Schwäche c) — der Pfad war praktisch unerreichbar.
- **Auffällig:** Tests: test_router.py und 3 Retry-Snapshots entfernt, xfail (c) entfällt; 64 passed, 2 xfailed. Kurzprüfung mit 1 Ticket im neuen Image ok.

## Stand nach der Warteschlange
Aktueller Gewinner: **e6e7-names** + E9 — Kategorie 42/50 · Urgency 26/50 · Risk Recall 9/11 (014 instabil) · Precision 9/10 · Name 25/25, 0 erfunden · Latenz ~17 s (Baseline: 40 · 20 · 10/11 · 10/13 · 23/25, 2 erfunden · ~21 s).
Offen: EVAL-014/046 (Gesundheitsgefahr ohne Keyword) hängen am Risk-Urteil des 3B-Modells; jede Prompt-Verschärfung (e4) und jede Urgency-Senkung (e1, e1b, e2) verliert 014. Urgency bleibt die schwächste Metrik.

## e10-risk-split — abgelehnt
- **Änderung:** Risk-Guard mit zwei engen Ja/Nein-Prompts (a: Drohung mit Recht/Behörde/Verbraucherzentrale/Kündigung oder Betrugsvorwurf; b: Gefahr für Menschen oder Sicherheitsvorfall), ohne Kategorie/Dringlichkeit, bei allen Tickets (kein Urgency-Gate); risk_flag = a ∨ b ∨ Keyword-Floor; Basis 0bcbf8f.
- **Ergebnis:** Kategorie 42/50 · Urgency 25/50 · Risk Recall **7/11** · Precision 7/7 · Name 25/25, 0 erfunden · Latenz 17.0 / 20.5 s
- **Entscheidung:** abgelehnt — Recall-Abfall (9 → 7); e1c-signals entfällt damit (war an die Annahme von e10 gebunden).
- **Grund:** Frage a) war bei allen 50 Tickets false, auch bei klaren Fällen (003 „mein Anwalt prüft Schadenersatz“, 025/031/045). Kein Parse-Fehler: Rohantworten direkt geprüft, sauberes `{"antwort": false}`. Frage b) griff genau einmal (046, richtig). Alle verbliebenen Treffer kommen aus dem Keyword-Floor.
- **Auffällig:** Gleiches Muster wie e4 — je enger/strenger die Risk-Frage, desto öfter sagt qwen2.5:3b pauschal „nein“; FPs fallen dabei auf 0. 046 wird erstmals erkannt. Das bisherige Risk-Urteil lebt faktisch von der urgency im Prompt.

## Schlusslauf (Holdout)
Ausdrücklich angeordnet; Stand eingefroren, kein Code-Tuning danach. 30 Holdout-Tickets (`eval/holdout/tickets.jsonl`, 7 mit Risiko), je ein Lauf mit dem App-Code der Baseline (`da59602`, Image aus git worktree) und des Gewinners (`0bcbf8f`).

**Holdout** (29 ausgewertet, HOLD-014 in beiden Läufen HTTP 500 — s. u.)

| | Kategorie | Urgency | Risk Recall | Risk Precision | Name richtig | Name erfunden | Latenz Median / p95 |
|---|---|---|---|---|---|---|---|
| holdout-baseline (`da59602`) | 23/29 (79 %) | 15/29 (52 %) | 7/7 (100 %) | 7/9 (78 %) | 12/14 (86 %) | 0/15 | 21.0 / 25.6 s |
| holdout-final (`0bcbf8f`) | 23/29 (79 %) | 14/29 (48 %) | 7/7 (100 %) | 7/9 (78 %) | 12/14 (86 %) | 0/15 | **16.8 / 20.6 s** |

**Dev-Set zum Vergleich** (50 Tickets; Final = Lauf `e6e7-names`, E9 danach verhaltensneutral ohne Lauf)

| | Kategorie | Urgency | Risk Recall | Risk Precision | Name richtig | Name erfunden | Latenz Median / p95 |
|---|---|---|---|---|---|---|---|
| baseline (`da59602`) | 40/50 (80 %) | 20/50 (40 %) | 10/11 (91 %) | 10/13 (77 %) | 23/25 (92 %) | 2/25 | 20.4 / 25.4 s |
| final (`e6e7-names`) | 42/50 (84 %) | 26/50 (52 %) | 9/11 (82 %) | 9/10 (90 %) | 25/25 (100 %) | 0/25 | 17.1 / 21.8 s |

**Auswertung**
- **Auf dem Holdout kein Qualitätsgewinn:** Kategorie, Risk und Name identisch; Urgency −1 Ticket (im Rauschband von ±2). Die Dev-Gewinne (Kategorie +2, Urgency +6, Name +2, Precision) übertragen sich nicht messbar — teils, weil die Baseline auf dem Holdout dort schon stark ist (Risk 7/7, 0 erfundene Namen), teils weil die Prompt-Änderungen an den 50 Dev-Tickets entlang bewertet wurden.
- **Übertragen hat sich die Latenz:** −20 % (Median 21.0 → 16.8 s) durch single-vote, ohne Qualitätsverlust.
- **Risk-FP HOLD-007, HOLD-015** in beiden Ständen; kein FN.
- **Gefundener Fehler (nicht behoben, Stand eingefroren):** HOLD-014 nennt zwei Rechnungsnummern; der Extractor liefert `invoice_number` als Liste `['RE-2026-09102', 'RE-2026-09103']`, `ExtractedData` erwartet `str` → `ValidationError` beim Egress → HTTP 500. Betrifft Baseline und Final gleich; die Defense-in-Depth-Validierung fängt Listen in Extraktionsfeldern nicht ab.
- **Fazit:** Belastbar sind die Latenz-Verbesserung und die robustere Nachbearbeitung (Namen, Keywords, kein toter Retry-Code); die Accuracy-Gewinne aus dem Dev-Set sind auf unabhängigen Daten nicht nachgewiesen.

**Nachtrag (nach dem Schlusslauf):** Der HOLD-014-Fehler ist separat behoben — Listen in Extraktionsfeldern werden in `ground_to_text` elementweise gegen den Text geprüft und verbunden (`"RE-1, RE-2"`), `ExtractedData` verbindet Listen zusätzlich beim Egress statt mit HTTP 500 abzubrechen. Geprüft mit Unit-Tests und zwei eigenen Tickets mit 2 bzw. 3 Rechnungsnummern (beide HTTP 200, alle Nummern erhalten). Bewusst **nicht** erneut auf dem Holdout gemessen — der Schlusslauf bleibt der Stand `0bcbf8f`.

## Cloud-Modell (gpt-4.1-mini auf Azure OpenAI)

Ab hier läuft der Service mit `LLM_PROVIDER=azure`, Deployment `ticket-llm` = gpt-4.1-mini (2025-04-14, GlobalStandard, France Central). Läufe lokal per uvicorn gegen Azure, Commit-Prüfung über `/ready` (`--verify-via-ready`). Hintergrund zur Modellwahl: `DECISIONS.md`.

## azure-dev — angenommen
- **Änderung:** Modell qwen2.5:3b → gpt-4.1-mini; Prompts und Code unverändert (Stand e6e7-names + E9). Kapazität für den Lauf 100k TPM.
- **Ergebnis:** Kategorie **49/50** (+7) · Urgency **40/50** (+14) · Risk Recall **11/11** (+2) · Precision 11/15 (vorher 9/10) · Name 25/25, **1 erfunden** · Latenz **2.3 / 3.8 s** (vorher 17.1 / 21.8 s) · 0 LLM-Fehler
- **Entscheidung:** angenommen nach Rückfrage — formal gemischt (Precision −3 FP, Name +1 erfunden), aber Recall 11/11 und beide Verschlechterungen mit belegter Ursache; je ein Folge-Experiment (e11, e12).
- **Grund:** Das Hochstufen bei Urgency ist weg: Fehler liegen fast alle eine Stufe daneben, in beide Richtungen (low↔medium 7, critical→high 2) statt systematisch nach oben wie bei qwen (medium→high 8/16).
- **Auffällig:** Alle 4 FPs (004, 006, 012, 021) mit fast wörtlich gleicher Begründung „Extrem verärgerter Kunde mit Eskalationsabsicht“ — das steht als Kriterium im Risk-Prompt und widerspricht der Label-Spezifikation (Ärger ohne Drohung = false). gpt-4.1-mini befolgt den Prompt genauer als qwen. Erfundener Name 002: „Versandabteilung“ — der Organisationsfilter erkennt „abteilung“ nur als eigenes Wort, nicht in Zusammensetzungen.

## e11-risk-anger — angenommen
- **Änderung:** Risk-Prompt ohne das Kriterium „extrem verärgerte Kunden mit Eskalationsabsicht“; Rest unverändert (bewusst minimal, anders als e4); Basis azure-dev.
- **Ergebnis:** Kategorie 49/50 · Urgency 40/50 · Risk Recall **11/11** · Precision **11/11** (vorher 11/15) · Name 25/25, 0 erfunden · Latenz 2.3 / 3.2 s
- **Entscheidung:** angenommen — alle 4 FPs weg, Recall unverändert 11/11.
- **Grund:** Genau die vier Tickets mit der Begründung „verärgerter Kunde“ (004, 006, 012, 021) kippen auf false; kein anderes Ticket ändert risk_flag, Kategorie oder Urgency. Der Prompt passt jetzt zur Label-Spezifikation.
- **Auffällig:** EVAL-002 liefert diesmal keinen Namen („Versandabteilung“ in azure-dev) — ohne Änderung an Extractor oder Nachbearbeitung. Auch bei temperature 0 antwortet das Cloud-Modell nicht vollständig deterministisch; Einzel-Flips beim Namen sind Rauschen, nicht e11.

## e12-org-compounds — angenommen (ohne Lauf)
- **Änderung:** Organisationsfilter erkennt „abteilung“ auch als Wortende (`\w*abteilung`), damit Komposita wie „Versandabteilung“ als Signatur gelten; „personalabteilung“ als Einzelwort entfällt (abgedeckt).
- **Entscheidung:** angenommen ohne Lauf, wie E9 — deterministische Nachbearbeitung, im Lauf nicht messbar, weil das Modell den Namen in e11 ohnehin nicht geliefert hat.
- **Prüfung:** zwei neue Unit-Tests (Versandabteilung, Personalabteilung); keiner der 25 Kundennamen in den Dev-Labels trifft den erweiterten Filter.

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

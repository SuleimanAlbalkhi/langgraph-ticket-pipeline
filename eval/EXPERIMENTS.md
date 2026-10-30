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

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

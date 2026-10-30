"""Wertet results.jsonl gegen die Labels in tickets.jsonl aus und schreibt eval/RESULTS.md.

Beispiel (aus dem Repo-Root):
    python eval/report.py
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

import numpy as np
from sklearn.metrics import confusion_matrix

EVAL_DIR     = Path(__file__).resolve().parent
TICKETS_PATH = EVAL_DIR / "tickets.jsonl"
RESULTS_PATH = EVAL_DIR / "results.jsonl"
META_PATH    = EVAL_DIR / "results_meta.json"
REPORT_PATH  = EVAL_DIR / "RESULTS.md"

CATEGORIES = ["technical_support", "billing_dispute", "general_inquiry", "unknown"]
URGENCIES  = ["low", "medium", "high", "critical"]
CONFIDENCE_LEVELS = [0.0, 0.33, 0.67, 1.0]

# Muss zu SUMMARY_TIMEOUT / SUMMARY_FAILED in app/graph/nodes/extractor.py passen.
FALLBACK_SUMMARIES = {"Extraktion fehlgeschlagen.", "Extraktion-Timeout."}

_TITLE_RE = re.compile(r"^dr\.\s*")


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pct(part: int, total: int) -> str:
    return f"{round(100 * part / total)} %" if total else "n/a"


def frac(part: int, total: int) -> str:
    return f"{part} von {total} ({pct(part, total)})"


def norm_name(name: str | None) -> str | None:
    """lower, Whitespace zusammenfassen, Titel 'Dr.' entfernen — so zählen
    'Dr. Felix Hartung' und 'Felix Hartung' als Treffer."""
    if name is None:
        return None
    n = " ".join(name.lower().split())
    return _TITLE_RE.sub("", n) or None


def md_cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def md_table(header: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(md_cell(h) for h in header) + " |",
             "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(md_cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def confusion_table(expected: list[str], got: list[str], labels: list[str]) -> str:
    # Halluzinierte Werte außerhalb der Labels landen in einer eigenen Spalte,
    # statt von sklearn stillschweigend verworfen zu werden.
    got_labels = labels + sorted({g for g in got if g not in labels})
    cm = confusion_matrix(expected, got, labels=got_labels)
    header = ["erwartet \\ erhalten"] + got_labels
    rows = [[lab] + list(cm[i]) for i, lab in enumerate(labels)]
    return md_table(header, rows)


def nearest_level(score: float) -> float:
    return min(CONFIDENCE_LEVELS, key=lambda lvl: abs(lvl - score))


def main() -> None:
    tickets = {t["ticket_id"]: t for t in _load_jsonl(TICKETS_PATH)}
    # Bei mehrfachen Zeilen (z. B. nach manuellem Nachlauf) gilt die letzte.
    results = {r["ticket_id"]: r for r in _load_jsonl(RESULTS_PATH)}
    meta = json.loads(META_PATH.read_text(encoding="utf-8")) if META_PATH.exists() else {}

    missing = [tid for tid in tickets if tid not in results]
    failed  = [r for tid, r in results.items()
               if tid in tickets and (r["status_code"] != 200 or not isinstance(r["response"], dict))]
    failed_ids = {r["ticket_id"] for r in failed}
    ok = [(tickets[tid], r["response"], r) for tid, r in results.items()
          if tid in tickets and tid not in failed_ids]
    n = len(ok)

    out: list[str] = []
    w = out.append

    w("# Evaluation: Ticket-Analyse-Pipeline\n")
    w(md_table(["", ""], [
        ["Datum", (meta.get("started_at") or "?")[:10]],
        ["Modell", meta.get("model", "?")],
        ["Hardware", meta.get("hardware", "?")],
        ["Commit", f"`{meta.get('git_commit') or '?'}`"],
        ["Testset-Größe", len(tickets)],
        ["Ausgewertet", n],
    ]))
    w("")

    if failed or missing:
        w(f"> **Hinweis:** Von allen Metriken ausgeschlossen: fehlgeschlagene Anfragen: {len(failed)}, "
          f"Tickets ohne Ergebnis: {len(missing)}. Alle Werte beziehen sich auf {n} Tickets.\n")
        if failed:
            w(md_table(["Ticket", "Status", "Fehler"],
                       [[r["ticket_id"], r["status_code"], r["error"]] for r in failed]))
            w("")
        if missing:
            w(f"Ohne Ergebnis: {', '.join(missing)}\n")

    if n == 0:
        REPORT_PATH.write_text("\n".join(out), encoding="utf-8")
        print(f"Keine auswertbaren Ergebnisse. {REPORT_PATH} geschrieben.")
        return

    # --- Kategorie & Urgency ---------------------------------------------------
    exp_cat = [t["expected_category"] for t, _, _ in ok]
    got_cat = [str(resp.get("category")) for _, resp, _ in ok]
    exp_urg = [t["expected_urgency"] for t, _, _ in ok]
    got_urg = [str(resp.get("urgency")) for _, resp, _ in ok]
    cat_hits = sum(e == g for e, g in zip(exp_cat, got_cat))
    urg_hits = sum(e == g for e, g in zip(exp_urg, got_urg))

    w("## Kategorie\n")
    w(f"Accuracy: **{frac(cat_hits, n)}**\n")
    w(confusion_table(exp_cat, got_cat, CATEGORIES))
    w("")
    w("## Urgency\n")
    w(f"Accuracy: **{frac(urg_hits, n)}**\n")
    w(confusion_table(exp_urg, got_urg, URGENCIES))
    w("")

    # --- Risk ----------------------------------------------------------------
    tp = [t["ticket_id"] for t, resp, _ in ok if t["expected_risk"] and resp.get("risk_flag")]
    fn = [t["ticket_id"] for t, resp, _ in ok if t["expected_risk"] and not resp.get("risk_flag")]
    fp = [t["ticket_id"] for t, resp, _ in ok if not t["expected_risk"] and resp.get("risk_flag")]
    w("## Risk-Flag\n")
    w(f"- Recall: **{frac(len(tp), len(tp) + len(fn))}** der Risiko-Tickets erkannt")
    w(f"- Precision: **{frac(len(tp), len(tp) + len(fp))}** der Eskalationen berechtigt")
    w(f"- False Negatives: {', '.join(fn) or '—'}")
    w(f"- False Positives: {', '.join(fp) or '—'}\n")

    # --- Kundenname ----------------------------------------------------------
    with_name    = [(t, resp) for t, resp, _ in ok if t["expected_customer_name"]]
    without_name = [(t, resp) for t, resp, _ in ok if not t["expected_customer_name"]]

    def got_name(resp: dict) -> str | None:
        return norm_name((resp.get("extracted_data") or {}).get("customer_name"))

    name_hits = sum(got_name(resp) == norm_name(t["expected_customer_name"]) for t, resp in with_name)
    invented  = [t["ticket_id"] for t, resp in without_name if got_name(resp)]
    w("## Kundenname\n")
    w("Vergleich nach Normalisierung (Kleinschreibung, Whitespace, Titel „Dr.“ optional).\n")
    w(f"- Richtig erkannt: **{frac(name_hits, len(with_name))}** (Tickets mit Namen)")
    w(f"- Erfundener Name: **{frac(len(invented), len(without_name))}** (Tickets ohne Namen)"
      + (f" — {', '.join(invented)}" if invented else ""))
    w("")

    # --- Latenz --------------------------------------------------------------
    lat = [r["latency_s"] for _, _, r in ok]
    w("## Latenz\n")
    w(md_table(["Median", "p95"],
               [[f"{statistics.median(lat):.1f} s", f"{float(np.percentile(lat, 95)):.1f} s"]]))
    w("")

    # --- Kalibrierung --------------------------------------------------------
    conf_ok  = [float(resp.get("confidence_score", 0.0)) for (t, resp, _) in ok
                if t["expected_category"] == str(resp.get("category"))]
    conf_bad = [float(resp.get("confidence_score", 0.0)) for (t, resp, _) in ok
                if t["expected_category"] != str(resp.get("category"))]
    w("## Kalibrierung (confidence_score vs. Kategorie)\n")
    w(f"- Mittlere Konfidenz bei richtiger Kategorie: "
      f"**{statistics.mean(conf_ok):.2f}**" if conf_ok else "- Richtige Kategorie: keine Fälle")
    w(f"- Mittlere Konfidenz bei falscher Kategorie: "
      f"**{statistics.mean(conf_bad):.2f}**\n" if conf_bad else "- Falsche Kategorie: keine Fälle\n")
    level_rows = []
    for lvl in CONFIDENCE_LEVELS:
        right = sum(nearest_level(c) == lvl for c in conf_ok)
        wrong = sum(nearest_level(c) == lvl for c in conf_bad)
        level_rows.append([f"{lvl:.2f}", right, wrong, pct(right, right + wrong)])
    w(md_table(["Konfidenz", "richtig", "falsch", "Anteil richtig"], level_rows))
    w("")

    # --- Fallbacks -----------------------------------------------------------
    fallback = [t["ticket_id"] for t, resp, _ in ok
                if resp.get("summary") in FALLBACK_SUMMARIES or float(resp.get("confidence_score", 0.0)) == 0.0]
    w("## Fallback-Antworten\n")
    w(f"Summary „Extraktion fehlgeschlagen.“ / „Extraktion-Timeout.“ oder confidence_score 0: "
      f"**{frac(len(fallback), n)}**" + (f" — {', '.join(fallback)}" if fallback else ""))
    w("")

    # --- Fehlklassifikationen ------------------------------------------------
    wrong_rows = [[t["ticket_id"], t["expected_category"], resp.get("category"), t["note"]]
                  for t, resp, _ in ok if t["expected_category"] != str(resp.get("category"))]
    w("## Falsch klassifizierte Tickets (Kategorie)\n")
    w(md_table(["Ticket", "erwartet", "erhalten", "Note"], wrong_rows) if wrong_rows else "Keine.")
    w("")

    wrong_urg_rows = [[t["ticket_id"], t["expected_urgency"], resp.get("urgency"), t["note"]]
                      for t, resp, _ in ok if t["expected_urgency"] != str(resp.get("urgency"))]
    w("## Falsch klassifizierte Tickets (Urgency)\n")
    w(md_table(["Ticket", "erwartet", "erhalten", "Note"], wrong_urg_rows) if wrong_urg_rows else "Keine.")
    w("")

    REPORT_PATH.write_text("\n".join(out), encoding="utf-8")
    print(f"{REPORT_PATH} geschrieben ({n} ausgewertet, {len(failed)} fehlgeschlagen, {len(missing)} fehlend).")


if __name__ == "__main__":
    main()

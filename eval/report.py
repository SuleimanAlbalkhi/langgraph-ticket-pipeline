"""Wertet results.jsonl eines Laufs gegen die Labels in tickets.jsonl aus und
schreibt RESULTS.md in den Lauf-Ordner.

Beispiel (aus dem Repo-Root):
    python eval/report.py --run baseline
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import confusion_matrix

EVAL_DIR     = Path(__file__).resolve().parent
TICKETS_PATH = EVAL_DIR / "tickets.jsonl"
RUNS_DIR     = EVAL_DIR / "runs"

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


def load_run(run_dir: Path) -> tuple[dict, list, list, list]:
    """Liest einen Lauf-Ordner. Gibt (meta, ok, failed, missing) zurück;
    ok = [(ticket, response, result_row)] der erfolgreichen Anfragen."""
    tickets = {t["ticket_id"]: t for t in _load_jsonl(TICKETS_PATH)}
    # Bei mehrfachen Zeilen (z. B. nach manuellem Nachlauf) gilt die letzte.
    results = {r["ticket_id"]: r for r in _load_jsonl(run_dir / "results.jsonl")}
    meta_path = run_dir / "results_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta.setdefault("n_tickets_labeled", len(tickets))

    missing = [tid for tid in tickets if tid not in results]
    failed  = [r for tid, r in results.items()
               if tid in tickets and (r["status_code"] != 200 or not isinstance(r["response"], dict))]
    failed_ids = {r["ticket_id"] for r in failed}
    ok = [(tickets[tid], r["response"], r) for tid, r in results.items()
          if tid in tickets and tid not in failed_ids]
    return meta, ok, failed, missing


def _got_name(resp: dict) -> str | None:
    return norm_name((resp.get("extracted_data") or {}).get("customer_name"))


def compute_metrics(ok: list) -> dict:
    """Alle Kennzahlen eines Laufs — genutzt von RESULTS.md und compare.py."""
    exp_cat = [t["expected_category"] for t, _, _ in ok]
    got_cat = [str(resp.get("category")) for _, resp, _ in ok]
    exp_urg = [t["expected_urgency"] for t, _, _ in ok]
    got_urg = [str(resp.get("urgency")) for _, resp, _ in ok]

    with_name    = [(t, resp) for t, resp, _ in ok if t["expected_customer_name"]]
    without_name = [(t, resp) for t, resp, _ in ok if not t["expected_customer_name"]]
    lat = [r["latency_s"] for _, _, r in ok]

    return {
        "n":        len(ok),
        "exp_cat":  exp_cat, "got_cat": got_cat,
        "exp_urg":  exp_urg, "got_urg": got_urg,
        "cat_hits": sum(e == g for e, g in zip(exp_cat, got_cat)),
        "urg_hits": sum(e == g for e, g in zip(exp_urg, got_urg)),
        "tp": [t["ticket_id"] for t, resp, _ in ok if t["expected_risk"] and resp.get("risk_flag")],
        "fn": [t["ticket_id"] for t, resp, _ in ok if t["expected_risk"] and not resp.get("risk_flag")],
        "fp": [t["ticket_id"] for t, resp, _ in ok if not t["expected_risk"] and resp.get("risk_flag")],
        "n_with_name":    len(with_name),
        "n_without_name": len(without_name),
        "name_hits": sum(_got_name(resp) == norm_name(t["expected_customer_name"]) for t, resp in with_name),
        "invented":  [t["ticket_id"] for t, resp in without_name if _got_name(resp)],
        "lat_median": statistics.median(lat) if lat else None,
        "lat_p95":    float(np.percentile(lat, 95)) if lat else None,
        "conf_ok":  [float(resp.get("confidence_score", 0.0)) for (t, resp, _) in ok
                     if t["expected_category"] == str(resp.get("category"))],
        "conf_bad": [float(resp.get("confidence_score", 0.0)) for (t, resp, _) in ok
                     if t["expected_category"] != str(resp.get("category"))],
        "fallback": [t["ticket_id"] for t, resp, _ in ok
                     if resp.get("summary") in FALLBACK_SUMMARIES
                     or float(resp.get("confidence_score", 0.0)) == 0.0],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", required=True, help="Name des Laufs unter eval/runs/")
    args = parser.parse_args()

    run_dir = RUNS_DIR / args.run
    if not (run_dir / "results.jsonl").exists():
        sys.exit(f"Kein Lauf gefunden: {run_dir / 'results.jsonl'}")
    report_path = run_dir / "RESULTS.md"

    meta, ok, failed, missing = load_run(run_dir)
    n = len(ok)

    out: list[str] = []
    w = out.append

    w(f"# Evaluation: Ticket-Analyse-Pipeline — Lauf `{args.run}`\n")
    w(md_table(["", ""], [
        ["Datum", (meta.get("started_at") or "?")[:10]],
        ["Modell", meta.get("model", "?")],
        ["Hardware", meta.get("hardware", "?")],
        ["Commit", f"`{meta.get('git_commit') or '?'}`"],
        ["Docker-Image", f"`{(meta.get('image_id') or '?').removeprefix('sha256:')[:12]}`, "
                         f"gebaut {meta.get('image_created') or '?'}"],
        ["Notiz", meta.get("note") or "—"],
        ["Testset-Größe", meta["n_tickets_labeled"]],
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
        report_path.write_text("\n".join(out), encoding="utf-8")
        print(f"Keine auswertbaren Ergebnisse. {report_path} geschrieben.")
        return

    m = compute_metrics(ok)

    # --- Kategorie & Urgency ---------------------------------------------------
    w("## Kategorie\n")
    w(f"Accuracy: **{frac(m['cat_hits'], n)}**\n")
    w(confusion_table(m["exp_cat"], m["got_cat"], CATEGORIES))
    w("")
    w("## Urgency\n")
    w(f"Accuracy: **{frac(m['urg_hits'], n)}**\n")
    w(confusion_table(m["exp_urg"], m["got_urg"], URGENCIES))
    w("")

    # --- Risk ----------------------------------------------------------------
    tp, fn, fp = m["tp"], m["fn"], m["fp"]
    w("## Risk-Flag\n")
    w(f"- Recall: **{frac(len(tp), len(tp) + len(fn))}** der Risiko-Tickets erkannt")
    w(f"- Precision: **{frac(len(tp), len(tp) + len(fp))}** der Eskalationen berechtigt")
    w(f"- False Negatives: {', '.join(fn) or '—'}")
    w(f"- False Positives: {', '.join(fp) or '—'}\n")

    # --- Kundenname ----------------------------------------------------------
    invented = m["invented"]
    w("## Kundenname\n")
    w("Vergleich nach Normalisierung (Kleinschreibung, Whitespace, Titel „Dr.“ optional).\n")
    w(f"- Richtig erkannt: **{frac(m['name_hits'], m['n_with_name'])}** (Tickets mit Namen)")
    w(f"- Erfundener Name: **{frac(len(invented), m['n_without_name'])}** (Tickets ohne Namen)"
      + (f" — {', '.join(invented)}" if invented else ""))
    w("")

    # --- Latenz --------------------------------------------------------------
    w("## Latenz\n")
    w(md_table(["Median", "p95"], [[f"{m['lat_median']:.1f} s", f"{m['lat_p95']:.1f} s"]]))
    w("")

    # --- Kalibrierung --------------------------------------------------------
    conf_ok, conf_bad = m["conf_ok"], m["conf_bad"]
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
    fallback = m["fallback"]
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

    report_path.write_text("\n".join(out), encoding="utf-8")
    print(f"{report_path} geschrieben ({n} ausgewertet, {len(failed)} fehlgeschlagen, {len(missing)} fehlend).")


if __name__ == "__main__":
    main()

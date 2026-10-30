"""Liest alle Läufe unter eval/runs/*/ und schreibt eine Vergleichstabelle
(eine Zeile pro Lauf) nach eval/runs/COMPARISON.md.

Beispiel (aus dem Repo-Root):
    python eval/compare.py
"""
from __future__ import annotations

import statistics

from report import RUNS_DIR, compute_metrics, frac, load_run, md_table

COMPARISON_PATH = RUNS_DIR / "COMPARISON.md"

HEADER = [
    "Lauf", "Datum", "Commit", "Notiz", "ausgewertet / fehlgeschl.",
    "Kategorie", "Urgency", "Risk Recall", "Risk Precision", "Risk FN", "Risk FP",
    "Name richtig", "Name erfunden", "Konfidenz richtig / falsch", "Fallbacks",
    "Latenz Median / p95",
]


def _mean(values: list[float]) -> str:
    return f"{statistics.mean(values):.2f}" if values else "—"


def _row(name: str) -> tuple[str, list[object]]:
    meta, ok, failed, missing = load_run(RUNS_DIR / name)
    m = compute_metrics(ok)
    n, tp = m["n"], len(m["tp"])
    latency = f"{m['lat_median']:.1f} / {m['lat_p95']:.1f} s" if n else "—"
    row = [
        name,
        (meta.get("started_at") or "?")[:10],
        f"`{(meta.get('git_commit') or '?')[:7]}`",
        meta.get("note") or "—",
        f"{n} / {len(failed) + len(missing)}",
        frac(m["cat_hits"], n),
        frac(m["urg_hits"], n),
        frac(tp, tp + len(m["fn"])),
        frac(tp, tp + len(m["fp"])),
        ", ".join(m["fn"]) or "—",
        ", ".join(m["fp"]) or "—",
        frac(m["name_hits"], m["n_with_name"]),
        frac(len(m["invented"]), m["n_without_name"]),
        f"{_mean(m['conf_ok'])} / {_mean(m['conf_bad'])}",
        len(m["fallback"]),
        latency,
    ]
    return meta.get("started_at") or "", row


def main() -> None:
    runs = sorted(p.name for p in RUNS_DIR.iterdir() if (p / "results.jsonl").exists()) if RUNS_DIR.exists() else []
    if not runs:
        raise SystemExit(f"Keine Läufe unter {RUNS_DIR} gefunden.")

    rows = sorted((_row(name) for name in runs), key=lambda item: item[0])
    out = [
        "# Vergleich aller Eval-Läufe\n",
        "Eine Zeile pro Lauf, sortiert nach Startzeit. Fehlgeschlagene/fehlende Tickets sind aus den "
        "Metriken ausgeschlossen (Spalte „ausgewertet / fehlgeschl.“). Details je Lauf in "
        "`eval/runs/<lauf>/RESULTS.md`.\n",
        md_table(HEADER, [row for _, row in rows]),
        "",
    ]
    COMPARISON_PATH.write_text("\n".join(out), encoding="utf-8")
    print(f"{COMPARISON_PATH} geschrieben ({len(rows)} Läufe).")


if __name__ == "__main__":
    main()

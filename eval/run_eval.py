"""Schickt die Eval-Tickets sequenziell an POST /analyze und protokolliert die Antworten.

Beispiel (aus dem Repo-Root):
    python eval/run_eval.py --hardware "RTX 3060 12 GB, Ryzen 5 5600X"
    python eval/run_eval.py --hardware "..." --resume
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

EVAL_DIR      = Path(__file__).resolve().parent
TICKETS_PATH  = EVAL_DIR / "tickets.jsonl"
RESULTS_PATH  = EVAL_DIR / "results.jsonl"
META_PATH     = EVAL_DIR / "results_meta.json"

BASE_URL        = "http://localhost:8000"
REQUEST_TIMEOUT = 300.0
MAX_ATTEMPTS    = 3
DEFAULT_RETRY_AFTER = 5.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=EVAL_DIR,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _done_ids() -> set[str]:
    if not RESULTS_PATH.exists():
        return set()
    return {row["ticket_id"] for row in _load_jsonl(RESULTS_PATH)}


def _write_meta(meta: dict) -> None:
    META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _check_health(client: httpx.Client) -> None:
    try:
        resp = client.get(f"{BASE_URL}/health", timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        sys.exit(f"Health-Check fehlgeschlagen ({BASE_URL}/health): {exc}")


def _analyze(client: httpx.Client, ticket: dict) -> dict:
    """Ein Ticket analysieren. Retry nur bei 503 (Überlastschutz des Service),
    alle anderen Fehler werden protokolliert statt wiederholt."""
    payload = {"ticket_id": ticket["ticket_id"], "raw_text": ticket["raw_text"], "source": "eval"}
    status_code: int | None = None
    response: object | None = None
    error: str | None = None

    t0 = time.perf_counter()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.post(f"{BASE_URL}/analyze", json=payload, timeout=REQUEST_TIMEOUT)
        except httpx.HTTPError as exc:
            status_code, response, error = None, None, f"{type(exc).__name__}: {exc}"
            break

        status_code = resp.status_code
        try:
            response = resp.json()
        except ValueError:
            response = None

        if resp.status_code == 503 and attempt < MAX_ATTEMPTS:
            try:
                wait = float(resp.headers.get("Retry-After", DEFAULT_RETRY_AFTER))
            except ValueError:
                wait = DEFAULT_RETRY_AFTER
            time.sleep(wait)
            continue

        error = None if resp.is_success else f"HTTP {resp.status_code}"
        break

    return {
        "ticket_id":   ticket["ticket_id"],
        "status_code": status_code,
        "response":    response,
        "error":       error,
        "latency_s":   round(time.perf_counter() - t0, 3),
        "timestamp":   _now(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="nur die ersten N Tickets")
    parser.add_argument("--resume", action="store_true",
                        help="Tickets überspringen, die schon in results.jsonl stehen")
    parser.add_argument("--model", default="qwen2.5:3b",
                        help="nur für die Metadaten; das Modell wählt der Service über seine Config")
    parser.add_argument("--hardware", required=True, help="z. B. 'RTX 3060 12 GB, Ryzen 5 5600X'")
    args = parser.parse_args()

    tickets = _load_jsonl(TICKETS_PATH)
    if args.limit is not None:
        tickets = tickets[: args.limit]

    skip = _done_ids() if args.resume else set()
    todo = [t for t in tickets if t["ticket_id"] not in skip]

    with httpx.Client() as client:
        _check_health(client)

        # Bei --resume die ursprüngliche Startzeit behalten.
        started_at = _now()
        if args.resume and META_PATH.exists():
            started_at = json.loads(META_PATH.read_text(encoding="utf-8")).get("started_at") or started_at
        meta = {
            "started_at":  started_at,
            "finished_at": None,
            "model":       args.model,
            "hardware":    args.hardware,
            "git_commit":  _git_commit(),
            "n_tickets":   len(tickets),
        }
        _write_meta(meta)  # sofort schreiben, damit auch ein abgebrochener Lauf Metadaten hat

        mode = "a" if args.resume else "w"
        with RESULTS_PATH.open(mode, encoding="utf-8") as out:
            offset = len(tickets) - len(todo)
            for i, ticket in enumerate(todo, start=offset + 1):
                row = _analyze(client, ticket)
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                suffix = f"  FEHLER: {row['error']}" if row["error"] else ""
                print(f"{i}/{len(tickets)} {row['ticket_id']} {row['latency_s']:.1f}s{suffix}", flush=True)

    meta["finished_at"] = _now()
    _write_meta(meta)


if __name__ == "__main__":
    main()

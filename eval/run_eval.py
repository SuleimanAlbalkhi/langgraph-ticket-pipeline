"""Schickt die Eval-Tickets sequenziell an POST /analyze und protokolliert die Antworten
in eval/runs/<run-name>/. Ein bestehender Lauf wird nie überschrieben.

Beispiel (aus dem Repo-Root):
    python eval/run_eval.py --run-name e1-signals --note "Urgency aus Signalen" --hardware "RTX 3060 12 GB"
    python eval/run_eval.py --run-name e1-signals --hardware "..." --resume
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
RUNS_DIR      = EVAL_DIR / "runs"

REPO_DIR      = EVAL_DIR.parent
APP_DIR       = REPO_DIR / "fastapi-service" / "app"
CONTAINER     = "hybrid-ai-fastapi"  # container_name in docker-compose.yml

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


def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True, check=True).stdout.strip()


def _parse_ts(value: str) -> datetime:
    # Docker liefert Nanosekunden ("...:23.263750098Z"); fromisoformat kann max. Mikrosekunden.
    value = value.replace("Z", "+00:00")
    if "." in value:
        head, rest = value.split(".", 1)
        n_digits = len(rest) - len(rest.lstrip("0123456789"))
        value = f"{head}.{rest[:min(n_digits, 6)]}{rest[n_digits:]}"
    return datetime.fromisoformat(value)


def _app_changed_at() -> datetime:
    """Zeitpunkt der letzten Änderung an fastapi-service/app/: letzter Commit ODER,
    falls neuer, die jüngste uncommittete Datei (Experimente laufen vor dem Commit)."""
    changed = _parse_ts(_run(["git", "log", "-1", "--format=%cI", "--", str(APP_DIR)]))
    dirty = _run(["git", "status", "--porcelain", "--untracked-files=all", "--", str(APP_DIR)])
    for line in dirty.splitlines():
        path = REPO_DIR / line[3:].strip().strip('"')
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            changed = max(changed, mtime)
    return changed


def _check_image() -> dict:
    """Image des laufenden Containers ermitteln; abbrechen, wenn es älter ist als der
    App-Code — sonst misst der Lauf nicht den Code, den er zu messen vorgibt."""
    try:
        image_id = _run(["docker", "inspect", CONTAINER, "--format", "{{.Image}}"])
        created = _run(["docker", "image", "inspect", image_id, "--format", "{{.Created}}"])
    except (OSError, subprocess.CalledProcessError) as exc:
        sys.exit(f"docker inspect {CONTAINER} fehlgeschlagen: {exc}")

    image_created = _parse_ts(created)
    app_changed = _app_changed_at()
    if image_created < app_changed:
        sys.exit(
            f"Image ({image_created.isoformat(timespec='seconds')}) ist älter als die letzte Änderung an "
            f"fastapi-service/app/ ({app_changed.isoformat(timespec='seconds')}). "
            "Erst neu bauen: docker compose up -d --build fastapi-service"
        )
    return {"image_id": image_id, "image_created": image_created.isoformat(timespec="seconds")}


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _done_ids(results_path: Path) -> set[str]:
    if not results_path.exists():
        return set()
    return {row["ticket_id"] for row in _load_jsonl(results_path)}


def _write_meta(meta_path: Path, meta: dict) -> None:
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    parser.add_argument("--run-name", required=True,
                        help="Ordnername unter eval/runs/, z. B. 'e1-signals'; darf noch nicht existieren")
    parser.add_argument("--note", default=None, help="kurze Beschreibung der Änderung in diesem Lauf")
    parser.add_argument("--limit", type=int, default=None, help="nur die ersten N Tickets")
    parser.add_argument("--resume", action="store_true",
                        help="abgebrochenen Lauf gleichen Namens fortsetzen (fertige Tickets überspringen)")
    parser.add_argument("--model", default="qwen2.5:3b",
                        help="nur für die Metadaten; das Modell wählt der Service über seine Config")
    parser.add_argument("--hardware", required=True, help="z. B. 'RTX 3060 12 GB, Ryzen 5 5600X'")
    args = parser.parse_args()

    run_dir = RUNS_DIR / args.run_name
    results_path = run_dir / "results.jsonl"
    meta_path = run_dir / "results_meta.json"
    # Ein Lauf wird nie überschrieben: neuer Name = neuer Ordner, --resume nur für bestehende.
    if args.resume and not run_dir.exists():
        sys.exit(f"--resume: Lauf {run_dir} existiert nicht.")
    if not args.resume and run_dir.exists():
        sys.exit(f"Lauf {run_dir} existiert bereits. Anderen --run-name wählen oder --resume nutzen.")

    tickets = _load_jsonl(TICKETS_PATH)
    if args.limit is not None:
        tickets = tickets[: args.limit]

    skip = _done_ids(results_path) if args.resume else set()
    todo = [t for t in tickets if t["ticket_id"] not in skip]

    image = _check_image()

    with httpx.Client() as client:
        _check_health(client)
        run_dir.mkdir(parents=True, exist_ok=True)

        # Bei --resume die ursprüngliche Startzeit und Notiz behalten.
        old_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        meta = {
            "run_name":    args.run_name,
            "note":        args.note or old_meta.get("note"),
            "started_at":  old_meta.get("started_at") or _now(),
            "finished_at": None,
            "model":       args.model,
            "hardware":    args.hardware,
            "git_commit":  _git_commit(),
            "image_id":    image["image_id"],
            "image_created": image["image_created"],
            "n_tickets":   len(tickets),
        }
        _write_meta(meta_path, meta)  # sofort schreiben, damit auch ein abgebrochener Lauf Metadaten hat

        mode = "a" if args.resume else "w"
        with results_path.open(mode, encoding="utf-8") as out:
            offset = len(tickets) - len(todo)
            for i, ticket in enumerate(todo, start=offset + 1):
                row = _analyze(client, ticket)
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                suffix = f"  FEHLER: {row['error']}" if row["error"] else ""
                print(f"{i}/{len(tickets)} {row['ticket_id']} {row['latency_s']:.1f}s{suffix}", flush=True)

    meta["finished_at"] = _now()
    _write_meta(meta_path, meta)


if __name__ == "__main__":
    main()

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A hybrid Low-Code + Pro-Code system for backoffice ticket processing. **n8n** (low-code) handles webhooks, routing, and integrations; **FastAPI + LangGraph** (pro-code) handles the reasoning. Inference runs on-premise via **Ollama** (`qwen2.5:3b`) — no external API calls, DSGVO-compliant by design. The codebase comments and LLM prompts are in German.

## Commands

All Python commands run from `fastapi-service/`. A local venv is committed at `fastapi-service/venv/` (gitignored but present on disk).

```powershell
# Run the full stack (FastAPI + n8n). Requires Ollama running on the host with qwen2.5:3b pulled.
docker compose up -d

# Run the FastAPI service locally (without Docker), from fastapi-service/
uvicorn app.main:app --reload --port 8000

# Verify
curl http://localhost:8000/health        # {"status":"ok",...}
# FastAPI Swagger UI: http://localhost:8000/docs
# n8n editor:         http://localhost:5678
```

```powershell
# Tests and lint, from fastapi-service/ (dev deps: pip install -r requirements-dev.txt)
venv\Scripts\python -m pytest          # LLM always mocked, no Ollama needed
venv\Scripts\ruff check .              # config: fastapi-service/ruff.toml
```

CI (`.github/workflows/ci.yml`) runs ruff, pytest and the Docker build on every push and PR. `tests/test_prompt_snapshots.py` pins every LLM prompt to `tests/snapshots/`; an intended prompt change updates them with `UPDATE_SNAPSHOTS=1 pytest tests/test_prompt_snapshots.py`.

Ollama is **not** containerized — the FastAPI container reaches the host's Ollama via `host.docker.internal:11434` (see `docker-compose.yml` / `OLLAMA_BASE_URL`). When running FastAPI locally instead, config defaults to `http://localhost:11434`.

## Architecture

Request flow: n8n webhook → `POST /analyze` → LangGraph pipeline → Ollama. The single endpoint that matters is `POST /analyze` in `app/main.py`; it delegates to `run_graph()` and converts errors into a generic 500 with a tracking `error_id` (full stacktrace stays in server logs).

### The LangGraph pipeline (`app/graph/`)

`orchestrator.py` defines a `StateGraph` over a `GraphState` TypedDict and compiles it **once** (cached in `_compiled_app`, reused across requests). Three nodes run in a fixed linear order:

1. **classifier** (`nodes/classifier.py`) → sets `category` + `urgency` + `confidence_score`.
2. **extractor** (`nodes/extractor.py`) → sets `summary` + `extracted_data`.
3. **risk_guard** (`nodes/risk_guard.py`) → sets `risk_flag` + `risk_reason`.

There is no conditional edge anymore: the former extractor retry loop was removed after it never fired in 100+ eval runs (see `eval/EXPERIMENTS.md`, E9). On timeout/LLM error the extractor returns a fixed fallback summary and the graph continues to risk_guard.

Module layout under `app/graph/`:
- `state.py` — `GraphState` and the fallback summaries (`SUMMARY_TIMEOUT` / `SUMMARY_FAILED`).
- `llm_utils.py` — `build_json_llm()` and `invoke_json()`: one LLM call with timeout + JSON parsing that never raises; failures come back as `LLMFailure` (TIMEOUT / ERROR / PARSE) and each node maps them to its fallback.
- `prompts/` — one prompt builder per node, text only; `prompt_safety.fence_user_input()` fences the ticket text.
- `postprocess.py` — pure functions on extractor output: placeholder cleanup, grounding at word boundaries, `snap_to_text` for slightly garbled names (threshold 0.85), organisation/department filter for `customer_name`, list values joined, deadline regex.
- `nodes/` — node logic only.

### Two patterns worth knowing before editing nodes

- **Self-consistency voting (classifier), currently 1 vote.** The majority-vote machinery (`asyncio.gather`, agreement rate = `confidence_score`) is kept, but `N_VOTES=1` at `temperature=0` since eval run `single-vote`: with 3 votes at 0.5, 48/50 votes were unanimous, confidence did not separate right from wrong, and latency was 25 % higher. With one vote `confidence_score` is always 1.0 (0.0 on total failure). Raising `N_VOTES` again requires `temperature > 0`. All nodes now use `temperature=0`.

- **Two-stage risk guard.** A keyword pre-filter (`RISK_KEYWORDS`: threat words like "anwalt", "klage", "betrug" — anger words such as "unzumutbar" were removed; "klage" does not match inside "beklage") runs first. The expensive LLM call only fires if a keyword hits **or** urgency is high/critical; routine tickets short-circuit to `risk_flag=False`. This is a cost hot-path — preserve it when modifying.

### LLM model tiers

`config.py` defines `ollama_fast_model` (classifier + extractor) and `ollama_smart_model` (risk_guard). Both currently point at `qwen2.5:3b` for GPU reasons, but the per-node routing already exists in code — to use a larger model for risk evaluation, change only the config value, not the nodes.

Each node builds its `ChatOllama` client as a module-level **singleton** at import time (no per-request setup). All LLM calls go through `llm_utils.invoke_json()` (`asyncio.wait_for` with `settings.ollama_timeout`) and degrade to a safe fallback on timeout/parse failure rather than raising.

### Defense-in-depth validation (`app/models/ticket.py`)

Pydantic enforces the contract at three points, and LLM output is never trusted directly:
- **Ingress:** `TicketInput` (e.g. `raw_text` min_length=10).
- **Inter-node coercion:** `TicketCategory.coerce` / `UrgencyLevel.coerce` snap hallucinated enum values back to safe defaults (`unknown` / `medium`); `null_if_placeholder()` + `_NULL_LIKE` turn LLM placeholder strings ("null", "n/a", "kein", …) into real `None`.
- **Egress:** `run_graph` re-coerces enums one final time; `ExtractedData` uses `extra: "ignore"` to drop unknown LLM keys and joins list values (e.g. two invoice numbers) instead of failing with a 500.

The extractor also runs a **regex deadline post-processor** (`postprocess._DEADLINE_PATTERNS`) as a deterministic fallback — small models miss German date/Frist patterns the regex catches reliably.

## n8n workflow

`n8n-workflows/Ticket-Analysis-Pipeline.json` is the versioned export. A `Switch` splits on `risk_flag` into an Escalation path and a Normal path. The final Slack/Notion delivery nodes are intentionally stubbed as `Set` nodes in this public repo (real delivery needs live credentials that must not be committed); swapping a `Set` for a real integration node is a drop-in change in the editor, no code change.

## Evaluation

`eval/tickets.jsonl` holds 50 labeled tickets; `eval/run_eval.py` sends them to `POST /analyze`, `eval/report.py` writes the metrics. Hard rules:

- `eval/tickets.jsonl` is never changed.
- `eval/holdout/` is never read, except for an explicitly ordered final run.
- One experiment = one change = one full run over all 50 tickets.
- Every run writes to `eval/runs/<name>/` and never overwrites anything.

Acceptance thresholds, derived from the noise band between `baseline` and `baseline-2` (same code and image: 1 category and 2 urgency tickets flipped, risk and name identical):

- Category / urgency: an experiment counts as an improvement only at **≥ 3 tickets** better than the previous winner.
- Risk flag / customer name: **≥ 1 ticket** counts.
- No other metric may get worse beyond the same band; risk recall must never drop below 10/11.

Before every run rebuild the image (`docker compose up -d --build fastapi-service`); `run_eval.py` aborts if the image is older than the app code. `eval/compare.py` writes the overview to `eval/runs/COMPARISON.md`.

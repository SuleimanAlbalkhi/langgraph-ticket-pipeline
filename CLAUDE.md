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

There is **no test suite, linter, or build step** configured. The only build is the Docker image (`fastapi-service/Dockerfile`).

Ollama is **not** containerized — the FastAPI container reaches the host's Ollama via `host.docker.internal:11434` (see `docker-compose.yml` / `OLLAMA_BASE_URL`). When running FastAPI locally instead, config defaults to `http://localhost:11434`.

## Architecture

Request flow: n8n webhook → `POST /analyze` → LangGraph pipeline → Ollama. The single endpoint that matters is `POST /analyze` in `app/main.py`; it delegates to `run_graph()` and converts errors into a generic 500 with a tracking `error_id` (full stacktrace stays in server logs).

### The LangGraph pipeline (`app/graph/`)

`orchestrator.py` defines a `StateGraph` over a `GraphState` TypedDict and compiles it **once** (cached in `_compiled_app`, reused across requests). Three nodes run in order, with one conditional loop:

1. **classifier** (`nodes/classifier.py`) → sets `category` + `urgency` + `confidence_score`.
2. **extractor** (`nodes/extractor.py`) → sets `summary` + `extracted_data`, increments `retry_count`.
3. **risk_guard** (`nodes/risk_guard.py`) → sets `risk_flag` + `risk_reason`.

The only conditional edge is `_route_after_extractor`: if extraction produced an all-null `extracted_data` **and** a too-short summary, it loops back to the extractor (with an augmented "retry" prompt) until `MAX_RETRIES` (2) — otherwise proceeds to risk_guard. Hard failures (timeout/LLM error) skip straight to risk_guard.

### Two patterns worth knowing before editing nodes

- **Self-consistency confidence (classifier).** The classifier runs `N_VOTES=3` times concurrently (`asyncio.gather`) at `temperature=0.5`. The majority vote sets the label; the agreement rate *is* the `confidence_score` (1.0 = unanimous, 0.67 = 2/3). This deliberately replaces the LLM's self-reported confidence. `temperature > 0` is required here — at 0 all runs would be identical and confidence always a fake 1.0. The other two nodes use `temperature=0`.

- **Two-stage risk guard.** A keyword pre-filter (`RISK_KEYWORDS`: "anwalt", "klage", "eskalation", …) runs first. The expensive LLM call only fires if a keyword hits **or** urgency is high/critical; routine tickets short-circuit to `risk_flag=False`. This is a cost hot-path — preserve it when modifying.

### LLM model tiers

`config.py` defines `ollama_fast_model` (classifier + extractor) and `ollama_smart_model` (risk_guard). Both currently point at `qwen2.5:3b` for GPU reasons, but the per-node routing already exists in code — to use a larger model for risk evaluation, change only the config value, not the nodes.

Each node builds its `ChatOllama` client as a module-level **singleton** at import time (no per-request setup). All LLM calls are wrapped in `asyncio.wait_for(..., timeout=settings.ollama_timeout)` and degrade to a safe fallback on timeout/parse failure rather than raising.

### Defense-in-depth validation (`app/models/ticket.py`)

Pydantic enforces the contract at three points, and LLM output is never trusted directly:
- **Ingress:** `TicketInput` (e.g. `raw_text` min_length=10).
- **Inter-node coercion:** `_coerce_category` / `_coerce_urgency` in the classifier snap hallucinated enum values back to safe defaults (`unknown` / `medium`); the extractor's `_normalize_value` + `_NULL_LIKE` set turn LLM placeholder strings ("null", "n/a", "kein", …) into real `None`.
- **Egress:** `run_graph` re-coerces enums one final time, and `ExtractedData` uses `extra: "ignore"` to drop unknown LLM keys.

The extractor also runs a **regex deadline post-processor** (`_DEADLINE_PATTERNS`) as a deterministic fallback — small models miss German date/Frist patterns the regex catches reliably.

## n8n workflow

`n8n-workflows/Ticket-Analysis-Pipeline.json` is the versioned export. A `Switch` splits on `risk_flag` into an Escalation path and a Normal path. The final Slack/Notion delivery nodes are intentionally stubbed as `Set` nodes in this public repo (real delivery needs live credentials that must not be committed); swapping a `Set` for a real integration node is a drop-in change in the editor, no code change.

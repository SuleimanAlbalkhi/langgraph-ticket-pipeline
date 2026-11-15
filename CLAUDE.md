# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A hybrid Low-Code + Pro-Code system for backoffice ticket processing. **n8n** (low-code) handles webhooks, routing, and integrations; **FastAPI + LangGraph** (pro-code) handles the reasoning. The codebase comments, internal docs and LLM prompts are in German; `README.md` is in English.

Two run modes, selected by `LLM_PROVIDER` (same pipeline code):
- **local** (`ollama`, default): `qwen2.5:3b` via Ollama on the host — no external API calls, DSGVO-compliant by design.
- **cloud** (`azure`): Azure Container App calling Azure OpenAI `gpt-4.1-mini` (deployment `ticket-llm`, GlobalStandard, France Central) via Managed Identity. **Synthetic data only** — GlobalStandard may process outside the EU. The DSGVO statement applies to the local mode only.

## Working rules

- **Suleiman makes every design decision.** If a task hits a decision that is not settled in the task or in `DECISIONS.md`, stop, present the options with pros and cons, and wait.
- **If reality deviates from the task** (a script parameter is named differently, a file is missing, a fact does not match), report it and ask — do not quietly solve it another way.
- Git and Azure commands are run by Suleiman unless he explicitly hands them over in the conversation.
- `ruff check` must be clean; do not run `ruff format`.
- Decisions with their reasons go to `DECISIONS.md` (newest first), experiment results to `eval/EXPERIMENTS.md`.

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

CI also has a `deploy` job: only on push to `main`, after green tests, it builds the image, pushes it to ghcr.io tagged with the commit SHA, logs in to Azure via OIDC and updates the Container App, then polls `/ready` until it reports the new SHA. Commits on other branches are never deployed.

### Cloud mode and scripts (from the repo root, PowerShell, after `az login`)

```powershell
.\scripts\start-azure-service.ps1                # service locally in Azure mode (uvicorn, API_KEY lokal-test, GIT_SHA = HEAD)
.\scripts\run-eval.ps1 -Name <run> -Note "..."   # dev-set eval against that local service; TPM 100k during the run, 10k afterwards (finally)
.\scripts\trace-ref.ps1 -TicketId EVAL-001       # ticket ID -> Langfuse ticket_ref (HMAC key read from Key Vault)
```

`run-eval.ps1` is fixed to `localhost`, the dev set and the local API key. A run against the deployed Container App uses `run_eval.py --base-url https://<fqdn> --verify-via-ready` with `EVAL_API_KEY` from Key Vault; if the checked-out commit is not the deployed one, pass `--code-commit <deployed sha>`. Raise the deployment capacity yourself (and reset it to 10k) as the script does. Full setup: `docs/azure-setup.md`.

Endpoints: `/health` is liveness only; `/ready` checks the config and, in Azure mode, that the identity gets a token (no model call) and returns `git_sha`. `/analyze` requires `X-API-Key` when `API_KEY` is set (always in the cloud).

### Observability (`app/observability.py`)

Langfuse tracing is hooked in centrally in `run_graph()` as a LangChain callback (new handler per request); nodes and `invoke_json()` know nothing about it. Tracing is on only if both Langfuse keys are set. Content is **masked by default** via `mask_otel_spans`: input/output → `[redacted]`, every attribute not on the allowlist is deleted (fail-closed). New attributes stay invisible until added to the allowlist — never loosen it without a decision in `DECISIONS.md`. Error messages of failed generations still reach Langfuse via the OTel span status (see `DECISIONS.md`, 2026-11-15). Environment `local` by default, `production` in the Container App; the ticket ID is sent only as a 16-hex HMAC (`ticket_ref`, key `TICKET_ID_HMAC_KEY`).

Every failed LLM call logs `LLM_FAILURE node=... reason=...` (no ticket content); a Log Analytics alert fires on any such line within 15 min. Each one in an eval run counts as a result, it is never filtered out.

## Architecture

Request flow: n8n webhook → `POST /analyze` → LangGraph pipeline → Ollama (local) or Azure OpenAI (cloud). The single endpoint that matters is `POST /analyze` in `app/main.py`; it delegates to `run_graph()` and converts errors into a generic 500 with a tracking `error_id` (full stacktrace stays in server logs).

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

`config.py` defines `ollama_fast_model` (classifier + extractor) and `ollama_smart_model` (risk_guard); in Azure mode the same split is `azure_fast_deployment` / `azure_smart_deployment` (both `ticket-llm`). Locally both models are `qwen2.5:3b` for GPU reasons, but the per-node routing already exists in code — to use a larger model for risk evaluation, change only the config value, not the nodes. A model change in Azure is a new deployment, not a code change; `AzureChatOpenAI` gets no `model=` on purpose (`DECISIONS.md`).

Each node builds its client via `llm_utils.build_json_llm()` as a module-level **singleton** at import time (no per-request setup): `ChatOllama` with `format="json"` or `AzureChatOpenAI` with `response_format=json_object`, Entra ID token provider and SDK retries on 429/5xx. All LLM calls go through `llm_utils.invoke_json()` (`asyncio.wait_for` with `settings.llm_timeout`) and degrade to a safe fallback on timeout/error/parse failure rather than raising.

### Defense-in-depth validation (`app/models/ticket.py`)

Pydantic enforces the contract at three points, and LLM output is never trusted directly:
- **Ingress:** `TicketInput` (e.g. `raw_text` min_length=10).
- **Inter-node coercion:** `TicketCategory.coerce` / `UrgencyLevel.coerce` snap hallucinated enum values back to safe defaults (`unknown` / `medium`); `null_if_placeholder()` + `_NULL_LIKE` turn LLM placeholder strings ("null", "n/a", "kein", …) into real `None`.
- **Egress:** `run_graph` re-coerces enums one final time; `ExtractedData` uses `extra: "ignore"` to drop unknown LLM keys and joins list values (e.g. two invoice numbers) instead of failing with a 500.

The extractor also runs a **regex deadline post-processor** (`postprocess._DEADLINE_PATTERNS`) as a deterministic fallback — small models miss German date/Frist patterns the regex catches reliably.

## n8n workflow

`n8n-workflows/Ticket-Analysis-Pipeline.json` is the versioned export of the local workflow; `Ticket-Analysis-Pipeline-Cloud.json` points the webhook workflow (synthetic tickets only) at the Container App and references a Header Auth credential named `Ticket-Pipeline Cloud` (`X-API-Key`) — never put a key into the JSON. A `Switch` splits on `risk_flag` into an Escalation path and a Normal path. The final Slack/Notion delivery nodes are intentionally stubbed as `Set` nodes in this public repo (real delivery needs live credentials that must not be committed); swapping a `Set` for a real integration node is a drop-in change in the editor, no code change.

## Evaluation

`eval/tickets.jsonl` holds 50 labeled tickets; `eval/run_eval.py` sends them to `POST /analyze`, `eval/report.py` writes the metrics. Hard rules:

- `eval/tickets.jsonl` is never changed.
- **`eval/holdout/` is locked.** It has been used for the local final run (`holdout-final`, 30.10.) and the pre-registered cloud run (`holdout-azure`, 15.11.). It is not read and not run again unless Suleiman explicitly orders it; nothing in prompts, code or data is changed because of a holdout result.
- One experiment = one change = one full run over all 50 tickets.
- Every run writes to `eval/runs/<name>/` and never overwrites anything.

Acceptance thresholds, derived from the noise band between `baseline` and `baseline-2` (same code and image: 1 category and 2 urgency tickets flipped, risk and name identical):

- Category / urgency: an experiment counts as an improvement only at **≥ 3 tickets** better than the previous winner.
- Risk flag / customer name: **≥ 1 ticket** counts.
- No other metric may get worse beyond the same band; risk recall must never drop below 10/11.

Before every local run rebuild the image (`docker compose up -d --build fastapi-service`); `run_eval.py` aborts if the image is older than the app code. Runs against Azure check the commit via `/ready` instead (`--verify-via-ready`). Since `azure-dev` the reference is the cloud model (current winner `e11-risk-anger` + `e12`); the thresholds above were derived for the local model. `eval/compare.py` writes the overview to `eval/runs/COMPARISON.md`.

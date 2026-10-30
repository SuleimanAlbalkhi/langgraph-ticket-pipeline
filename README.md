
# Hybrid AI Orchestrator

> Automated backoffice ticket processing through hybrid Low-Code + Pro-Code AI architecture.
> Runs fully on-premise — no external API dependencies, DSGVO-compliant by design.

[![CI](https://github.com/SuleimanAlbalkhi/langgraph-ticket-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/SuleimanAlbalkhi/langgraph-ticket-pipeline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.4-1C3C3C)
![Ollama](https://img.shields.io/badge/Ollama-qwen2.5--3b-black)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![n8n](https://img.shields.io/badge/n8n-Workflow-EA4B71?logo=n8n&logoColor=white)

---
## Demo

### n8n Workflow with risk-based routing
<img width="1917" height="906" alt="Screenshot 2026-06-04 171248" src="https://github.com/user-attachments/assets/43e1e8c1-325e-4a0e-ba96-e83bc4cde8ce" />

### FastAPI response on a high-risk ticket
<img width="1412" height="814" alt="Screenshot 2026-06-04 171827" src="https://github.com/user-attachments/assets/5ced1206-e15c-40b0-920e-795b3a0194d0" />

### Containerized services
<img width="1919" height="1030" alt="Screenshot 2026-06-04 171420" src="https://github.com/user-attachments/assets/e59047b8-b118-444c-a19d-b378f8b2205a" />

---
## The Problem

Modern enterprises face a dilemma when automating AI-driven processes:

- **Pure pro-code solutions** (e.g. everything in Python) produce unmaintainable code mountains —
  business analysts can't read or adjust the flow.
- **Pure low-code solutions** hit a wall when complex agentic logic is required —
  cyclic decision graphs, self-correction loops, or stateful reasoning.

This project demonstrates the **middle path**: a clean architectural boundary between
the operational layer and the reasoning layer.

---

## Architecture

```
   ┌──────────────────┐       ┌──────────────────────┐       ┌─────────────────────┐
   │  Source Systems  │       │   n8n (Low-Code)     │       │  FastAPI Service    │
   │                  │       │                      │       │                     │
   │  • Email         │──────▶│  • Webhook receiver  │──────▶│  • REST API         │
   │  • Web Forms     │       │  • Switch routing    │       │  • Pydantic models  │
   │  • CRM/ERP       │       │  • Slack / Notion    │       │  • LangGraph core   │
   └──────────────────┘       └──────────────────────┘       └──────────┬──────────┘
                                                                        │
                                                                        ▼
                                                       ┌──────────────────────────────┐
                                                       │   LangGraph Pipeline          │
                                                       │                              │
                                                       │   Node 1: Classifier         │
                                                       │   Node 2: Extractor          │
                                                       │      + Grounding (no LLM)    │
                                                       │   Node 3: Risk Guard         │
                                                       │      (Keyword + LLM)         │
                                                       └──────────────┬───────────────┘
                                                                      │
                                                                      ▼
                                                              ┌──────────────┐
                                                              │   Ollama     │
                                                              │  qwen2.5:3b  │
                                                              │  (on-prem)   │
                                                              └──────────────┘
```

| Layer | Responsibility | Technology |
|---|---|---|
| **Orchestration** | Webhooks, routing, integrations with ERP/CRM/Slack | n8n |
| **Service** | REST API, contract validation, container boundary | FastAPI + Pydantic |
| **Reasoning** | Classification, extraction, risk evaluation | LangGraph + Ollama |

---

## Key Features

- **3-Node LangGraph Pipeline** with typed state, linear: classifier → extractor → risk guard
- **Single deterministic classifier run** (`temperature=0`) — self-consistency voting with 3 runs was measured and dropped: the votes were almost always unanimous, so the confidence carried no signal, while costing latency (see [Evaluation](#evaluation))
- **Deterministic post-processing of extracted fields** — values must appear in the ticket text at word boundaries (grounding), slightly garbled names are snapped to the matching text span, signatures like "Einkauf, Firma GmbH" are rejected as customer names, a regex fallback catches deadlines
- **2-Stage Risk Guard** — keyword floor (threat words only, no anger words) plus an LLM call that only fires on a keyword hit or high/critical urgency
- **Defense-in-Depth Validation** — Pydantic input contracts + enum coercion + async timeouts + coercion of list values from the LLM
- **Measured, not assumed** — labeled dev and holdout sets, one change per eval run, tests and CI on every push
- **Singleton LLM Connections** — no per-request setup overhead
- **Structured Logging** in every node — observable, debuggable, MLOps-ready
- **On-Premise Inference** — qwen2.5:3b via Ollama, no data leaves the host
- **Container-Native** — single-stage, layer-cached Docker build, healthcheck-instrumented, docker-compose orchestrated
- **Hybrid Architecture** — n8n exposes business logic visually for non-developers

---

## Evaluation

All numbers below are copied from [`eval/runs/COMPARISON.md`](eval/runs/COMPARISON.md); every
experiment, including the rejected ones, is documented in [`eval/EXPERIMENTS.md`](eval/EXPERIMENTS.md).

**Holdout — 30 tickets not used during development** (29 evaluated: one ticket returned
HTTP 500 in both versions, since fixed, see EXPERIMENTS.md)

| | Category | Urgency | Risk recall | Risk precision | Customer name | Invented name | Latency median / p95 |
|---|---|---|---|---|---|---|---|
| Baseline (`da59602`) | 23 / 29 (79 %) | 15 / 29 (52 %) | 7 / 7 (100 %) | 7 / 9 (78 %) | 12 / 14 (86 %) | 0 / 15 (0 %) | 21.0 / 25.6 s |
| Final (`0bcbf8f`) | 23 / 29 (79 %) | 14 / 29 (48 %) | 7 / 7 (100 %) | 7 / 9 (78 %) | 12 / 14 (86 %) | 0 / 15 (0 %) | 16.8 / 20.6 s |

**Dev set — 50 tickets used to select the changes** (context only)

| | Category | Urgency | Risk recall | Risk precision | Customer name | Invented name | Latency median / p95 |
|---|---|---|---|---|---|---|---|
| Baseline (`da59602`) | 40 / 50 (80 %) | 20 / 50 (40 %) | 10 / 11 (91 %) | 10 / 13 (77 %) | 23 / 25 (92 %) | 2 / 25 (8 %) | 20.4 / 25.4 s |
| Final (run `e6e7-names`) | 42 / 50 (84 %) | 26 / 50 (52 %) | 9 / 11 (82 %) | 9 / 10 (90 %) | 25 / 25 (100 %) | 0 / 25 (0 %) | 17.1 / 21.8 s |

**The dev-set gains did not carry over to the holdout set.** Category, risk and customer name
are identical on the holdout, urgency is one ticket lower (within the noise band). The one
improvement that did carry over is latency: −20 % (median 21.0 → 16.8 s), from running the
classifier once instead of three times.

**Method.** Dev and holdout sets were kept separate: the dev set was committed before the first
measurement, the holdout set after the first baseline run but before the first experiment, and
it was read exactly once, in the final run. The noise threshold comes
from two identical baseline runs (same code, same image): 1 category and 2 urgency tickets
flipped, so a change only counted at ≥ 3 tickets for category/urgency and ≥ 1 ticket for risk
and name. Every experiment was one change and one full run, with a rebuilt Docker image checked
against the code. Rejected experiments are kept with their run and patch (`eval/patches/`).

Model `qwen2.5:3b` via Ollama · GTX 1050 Ti 4 GB (Laptop), Intel i7-7700HQ, 16 GB RAM · 2026-10-30

**Reproduce** (from the repo root):

```powershell
pip install -r eval/requirements.txt
docker compose up -d --build fastapi-service
python eval/run_eval.py --run-name my-run --hardware "<your GPU / CPU / RAM>"
python eval/report.py --run my-run          # writes eval/runs/my-run/RESULTS.md
python eval/compare.py                      # updates eval/runs/COMPARISON.md
```

`run_eval.py --tickets eval/holdout/tickets.jsonl` runs the holdout set instead of the dev set.

---

## Quick Start

### Prerequisites

- Docker Desktop (with WSL 2 backend on Windows)
- Ollama installed on host with `qwen2.5:3b` pulled:
  ```powershell
  ollama pull qwen2.5:3b
  ```

### Run

```powershell
git clone https://github.com/SuleimanAlbalkhi/langgraph-ticket-pipeline.git
cd langgraph-ticket-pipeline
docker compose up -d
```

That's it. Two containers come up:

| Service | URL | Purpose |
|---|---|---|
| FastAPI | http://localhost:8000/docs | API + Swagger UI |
| n8n | http://localhost:5678 | Workflow editor |

### Verify

```powershell
curl http://localhost:8000/health
# {"status":"ok","service":"Hybrid AI Orchestrator"}
```

---

## API Reference

### `POST /analyze`

Processes a single ticket end-to-end through the LangGraph pipeline.

**Request**

```json
{
  "ticket_id": "T-001",
  "raw_text": "Einspruch gegen Rechnung RE-2026-0481 über 1.247,80 EUR. Sollte dies nicht innerhalb von 14 Tagen geklärt werden, schalte ich meinen Anwalt ein.",
  "source": "email"
}
```

**Response**

```json
{
  "ticket_id": "T-001",
  "category": "billing_dispute",
  "urgency": "critical",
  "summary": "Kunde erhebt Einspruch gegen Rechnung und droht mit anwaltlicher Eskalation.",
  "extracted_data": {
    "customer_name": null,
    "product": null,
    "error_code": null,
    "invoice_number": "RE-2026-0481",
    "amount": "1.247,80 EUR",
    "deadline_mentioned": true,
    "deadline": "innerhalb von 14 Tagen"
  },
  "risk_flag": true,
  "risk_reason": "rechtliche Drohungen, Eskalationsabsicht",
  "confidence_score": 1.0
}
```

> `confidence_score` is the agreement rate of the classifier runs. Since the
> classifier runs once (`N_VOTES=1`), it is always `1.0` (`0.0` only if the run
> fails) — see [Limitations](#limitations). `deadline` is filled by the LLM, with a
> regex post-processor as a deterministic fallback.

Measured latency on the holdout set: **median 16.8 s, p95 20.6 s** per ticket on the
reference machine (GTX 1050 Ti (Laptop), qwen2.5:3b). The extractor dominates.

### `GET /health`

Lightweight healthcheck for Docker / Kubernetes liveness probes.

---

## Project Structure

```
hybrid-ai-orchestrator/
├── fastapi-service/
│   ├── app/
│   │   ├── main.py              FastAPI app + lifespan + endpoints
│   │   ├── config.py            Pydantic Settings (env-driven)
│   │   ├── models/ticket.py     Input/Output contracts + enums
│   │   └── graph/
│   │       ├── orchestrator.py  LangGraph definition (linear) + egress coercion
│   │       ├── state.py         GraphState + fallback summaries
│   │       ├── llm_utils.py     LLM client factory + invoke_json (timeout + JSON parsing)
│   │       ├── postprocess.py   Grounding, snap to text, organisation filter, deadline regex
│   │       ├── prompt_safety.py Fencing of untrusted ticket text
│   │       ├── prompts/         One prompt builder per node (snapshot-tested)
│   │       └── nodes/
│   │           ├── classifier.py   Node 1: category + urgency
│   │           ├── extractor.py    Node 2: summary + structured data
│   │           └── risk_guard.py   Node 3: keyword floor + LLM risk evaluation
│   ├── tests/                   pytest suite (LLM always mocked)
│   ├── Dockerfile               Multi-layer cached build
│   ├── requirements.txt
│   └── requirements-dev.txt     pytest, pytest-asyncio, ruff
├── eval/
│   ├── tickets.jsonl            Dev set (50 labeled tickets)
│   ├── holdout/tickets.jsonl    Holdout set (30 labeled tickets)
│   ├── run_eval.py / report.py / compare.py
│   ├── runs/                    One folder per eval run + COMPARISON.md
│   └── EXPERIMENTS.md           Every experiment: change, result, decision
├── n8n-workflows/
│   └── Ticket-Analysis-Pipeline.json   Exported workflow (versioned)
├── .github/workflows/ci.yml     ruff + pytest + Docker build on push / PR
├── docker-compose.yml           FastAPI + n8n + shared network + volumes
└── README.md
```

---

## Design Decisions

### Why hybrid (n8n + FastAPI), not just one?

n8n alone would hit a wall at the reasoning layer — typed state across LLM steps, coercion of
hallucinated values and deterministic post-processing need code and tests. FastAPI alone would re-implement what n8n already solves: visual debugging of
data flow, drop-in integrations with 350+ services, business-readable workflow definitions.

The hybrid lets non-developers adjust the operational layer (route to Teams instead of Slack,
add a Notion sync, change the priority threshold) without touching Python.

### Why on-premise LLM (Ollama)?

Industrial customers cannot legally send customer data to OpenAI/Anthropic APIs.
qwen2.5:3b runs on a consumer GPU (4 GB VRAM sufficient) and is competent for classification
and structured extraction tasks. For more demanding reasoning, swapping to a larger model
is a one-line config change.

### Why a separate Risk-Guard node with two stages?

LLM inference is expensive. A large share of tickets are routine and require no deep risk evaluation.
A keyword floor (`Anwalt`, `Klage`, `Betrug`, … — threat words only; anger words like
"unzumutbar" were removed after they produced only false alarms in the evaluation) catches the
obvious cases deterministically; the LLM call only fires on a keyword hit or high/critical urgency. This is a hot-path optimization pattern
that scales linearly with traffic.

### Why Pydantic everywhere?

Pydantic enforces the data contract at three points: API ingress, inter-node state,
and API egress. A malformed ticket is rejected at the gate before any LLM token is spent.
Hallucinated enum values from the LLM are coerced back to safe defaults before they
reach the response. This is defense-in-depth applied to AI systems.

### Why `host.docker.internal` instead of containerizing Ollama?

GPU passthrough into Docker on Windows requires WSL 2 + nvidia-container-toolkit + driver
alignment. For a portfolio project this is overkill. On Linux production, Ollama would be
containerized with `--gpus all`.

### Why are the Slack/Notion delivery nodes stubbed?

The n8n workflow contains the full routing logic — a `Switch` splits on `risk_flag` into an
**Escalation** and a **Normal** path, and each path assembles the action payload. The final
delivery (posting to Slack, writing to Notion) is intentionally left as `Set` nodes in this
public repo: wiring real delivery requires live credentials, which must never be committed.
The actual integration runs locally with secrets kept out of version control. Swapping a `Set`
node for a real Slack/Notion node is a drop-in change in the n8n editor — no code change.

---

## Limitations

- **Small, synthetic test sets** — 50 dev + 30 holdout tickets, generated by an LLM and checked
  by hand. One ticket is 2 percentage points on the dev set and 3.3 on the holdout set; real ticket traffic will differ.
- **Urgency is the weakest metric** — 52 % on the dev set, 48 % on the holdout set. The risk verdict of the 3B model
  depends on the urgency in its prompt: every attempt to lower urgency or to sharpen the risk
  prompt lost risk tickets (experiments e1, e1b, e2, e4, e10 in EXPERIMENTS.md).
- **`confidence_score` carries no information** — always `1.0` since the switch to a single
  classifier run, and it was not informative before either: with 3 votes the mean confidence was
  0.99 for correct and 0.97 for wrong categories on the dev set.
- **n8n has no retry or error path** — if the API is down or returns `503`, the execution fails
  and the ticket is lost. The live n8n workflow is not versioned; only an export is in the repo.
- **No load tests** — latency is measured sequentially, one ticket at a time.

---

## Status & Roadmap

**Current** — working single-instance deployment with the full E2E flow:
Webhook → Classification → Extraction → Risk Guard → Routing → Action.
Not production-ready — the gaps are named under **Next** below, not hidden.

**Next** — the gaps I consider most important, in this order

- [x] Test suite (pytest) for the deterministic core — LLM always mocked, prompt snapshots
- [x] Labeled evaluation set (50 dev + 30 holdout) + eval scripts and an experiment log
- [x] CI: lint, tests and Docker build on every push
- [ ] Retry + error workflow in n8n — a `503` from the API currently fails the execution
      and the ticket is lost
- [ ] Urgency: currently 52 % (dev) / 48 % (holdout) — needs an approach that does not cost risk recall
- [ ] Larger model for the risk guard (`ollama_smart_model`) — the 3B model's risk verdict
      depends on the urgency in its prompt
- [ ] Version the live n8n workflow, not only an export
- [ ] `/ready` endpoint that actually checks Ollama connectivity (`/health` is static today)

**Later**

- [ ] Prometheus metrics endpoint + Grafana dashboard
- [ ] Async job pattern for long-running analyses (>30 s)
- [ ] Per-category extraction schemas (currently universal)
- [ ] Token-bucket rate limiting on the API
- [ ] Persistent state in Postgres for LangGraph checkpointing
- [ ] Kubernetes manifests + Helm chart

---

## License

MIT

## Author

**Suleiman Albalkhi** — AI Engineer, AI Engineering / Process Automation

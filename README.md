
# Hybrid AI Orchestrator

> Automated backoffice ticket processing through hybrid Low-Code + Pro-Code AI architecture.
> Runs fully on-premise — no external API dependencies, DSGVO-compliant by design.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.4-1C3C3C)
![Ollama](https://img.shields.io/badge/Ollama-qwen2.5--3b-black)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![n8n](https://img.shields.io/badge/n8n-Workflow-EA4B71?logo=n8n&logoColor=white)

---
<img width="1412" height="814" alt="Screenshot 2026-06-04 171827" src="https://github.com/user-attachments/assets/5ced1206-e15c-40b0-920e-795b3a0194d0" />
<img width="1919" height="1030" alt="Screenshot 2026-06-04 171420" src="https://github.com/user-attachments/assets/e59047b8-b118-444c-a19d-b378f8b2205a" />
<img width="1917" height="906" alt="Screenshot 2026-06-04 171248" src="https://github.com/user-attachments/assets/43e1e8c1-325e-4a0e-ba96-e83bc4cde8ce" />
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
                                                       │      ↑↓ Self-Correction      │
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

- **3-Node LangGraph Pipeline** with typed state and conditional edges
- **Self-Correction Loop** via retry counter — extractor re-runs with augmented prompt if output is empty
- **2-Stage Risk Guard** — fast keyword pre-filter avoids LLM cost on routine tickets (~70% reduction)
- **Defense-in-Depth Validation** — Pydantic input contracts + enum coercion + async timeouts
- **Singleton LLM Connections** — no per-request setup overhead
- **Structured Logging** in every node — observable, debuggable, MLOps-ready
- **On-Premise Inference** — qwen2.5:3b via Ollama, no data leaves the host
- **Container-Native** — multi-stage Docker build, healthcheck-instrumented, docker-compose orchestrated
- **Hybrid Architecture** — n8n exposes business logic visually for non-developers

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
    "deadline_mentioned": true
  },
  "risk_flag": true,
  "risk_reason": "rechtliche Drohungen, Eskalationsabsicht",
  "confidence_score": 1.0
}
```

Average latency: **~25 seconds** (limited by GPU — RTX 1050 Ti reference).

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
│   │       ├── orchestrator.py  LangGraph definition + conditional router
│   │       └── nodes/
│   │           ├── classifier.py   Node 1: category + urgency
│   │           ├── extractor.py    Node 2: structured data + retry logic
│   │           └── risk_guard.py   Node 3: keyword + LLM risk evaluation
│   ├── Dockerfile               Multi-layer cached build
│   └── requirements.txt
├── n8n-workflows/
│   └── ticket_processor.json    Exported workflow (versioned)
├── docker-compose.yml           FastAPI + n8n + shared network + volumes
└── README.md
```

---

## Design Decisions

### Why hybrid (n8n + FastAPI), not just one?

n8n alone would hit a wall at the conditional retry logic in Node 2 — agentic state graphs
need code. FastAPI alone would re-implement what n8n already solves: visual debugging of
data flow, drop-in integrations with 350+ services, business-readable workflow definitions.

The hybrid lets non-developers adjust the operational layer (route to Teams instead of Slack,
add a Notion sync, change the priority threshold) without touching Python.

### Why on-premise LLM (Ollama)?

Industrial customers cannot legally send customer data to OpenAI/Anthropic APIs.
qwen2.5:3b runs on a consumer GPU (4 GB VRAM sufficient) and is competent for classification
and structured extraction tasks. For more demanding reasoning, swapping to a larger model
is a one-line config change.

### Why a separate Risk-Guard node with two stages?

LLM inference is expensive. ~70% of tickets are routine and require no deep risk evaluation.
A keyword pre-filter (`Anwalt`, `Klage`, `Eskalation`, …) catches the obvious cases without
LLM cost; only ambiguous cases trigger the LLM. This is a hot-path optimization pattern
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

---

## Status & Roadmap

**Current** — production-ready single-instance deployment with full E2E flow:
Webhook → Classification → Extraction → Risk Guard → Routing → Action.

**Planned**

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

**Suleiman Albalkhi** — Werkstudent applicant, AI Engineering / Process Automation

# Hybrid AI Orchestrator

n8n-gesteuerter LangGraph-Microservice zur automatisierten Verarbeitung
unstrukturierter Backoffice-Daten (technische Support-Tickets,
Rechnungsreklamationen).

## Architektur

Hybrid-Ansatz: Low-Code für Orchestrierung, Pro-Code für agentic AI Logic.

```
[n8n Webhook]  →  [FastAPI Service]  →  [LangGraph Pipeline]
                                          ├─ Node 1: Classifier (Ollama)
                                          ├─ Node 2: Extractor (Ollama)
                                          └─ Node 3: Risk Guard (2-stage)
```

## Tech Stack

- **FastAPI** — Async REST API mit Pydantic-Validierung
- **LangGraph** — Stateful Agentic Workflows mit Conditional Edges
- **Ollama** — Lokales LLM (qwen2.5:3b), DSGVO-konform on-premise
- **n8n** — Low-Code Process Orchestration

## Features

- 3-stufige LangGraph-Pipeline mit typisiertem State
- Self-Correction Loop via Conditional Edges + Retry Counter
- 2-stufiger Risk Guard: Keyword-Filter + LLM-Tiefenprüfung
- Defense-in-Depth: Pydantic Input/Output + Enum-Coercion + Async Timeouts
- Singleton LLM Connections (kein Setup-Overhead pro Request)
- Structured Logging in jedem Node

## Setup

### Voraussetzungen
- Python 3.13+
- Ollama mit `qwen2.5:3b` Modell

### Installation

```powershell
cd fastapi-service
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
ollama pull qwen2.5:3b
```

### Starten

```powershell
uvicorn app.main:app --reload --port 8000
```

API-Dokumentation: http://localhost:8000/docs

## API

`POST /analyze` — Verarbeitet ein Ticket end-to-end.

Beispiel-Request:
```json
{
  "ticket_id": "T-001",
  "raw_text": "Ich erhebe Einspruch gegen Rechnung RE-2026-0481 über 1.247,80 EUR...",
  "source": "email"
}
```

## Projektstruktur

```
fastapi-service/
├── app/
│   ├── main.py              FastAPI App + Endpoints
│   ├── config.py            Pydantic Settings
│   ├── models/ticket.py     Input/Output Schemas
│   └── graph/
│       ├── orchestrator.py  LangGraph Graph + Router
│       └── nodes/
│           ├── classifier.py
│           ├── extractor.py
│           └── risk_guard.py
└── requirements.txt
```

## Status

Work in progress. Aktuelle Phase: FastAPI Service produktionsreif,
Docker-Setup und n8n-Integration folgen.

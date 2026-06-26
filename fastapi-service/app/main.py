from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import uuid  # für generische Fehler-IDs

from fastapi import FastAPI, HTTPException

from app.config import get_settings
from app.models.ticket import TicketInput, TicketAnalysis

# force=True entfernt bereits vorhandene Handler (z.B. von Uvicorn) am
# Root-Logger, bevor unserer gesetzt wird — verhindert doppelte Log-Zeilen.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", force=True)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Service startet: %s", settings.app_name)
    logger.info("Fast-Modell:  %s", settings.ollama_fast_model)
    logger.info("Smart-Modell: %s", settings.ollama_smart_model)
    logger.info("Ollama URL:   %s", settings.ollama_base_url)
    logger.info("LLM-Timeout:  %.0fs", settings.ollama_timeout)
    yield
    logger.info("Service wird beendet.")


app = FastAPI(
    title=settings.app_name,
    description="n8n-gesteuerter LangGraph-Microservice für Ticket-Verarbeitung",
    version="1.0.0",
    lifespan=lifespan,
)


def _error_response(error_id: str) -> dict[str, str]:
    """Sichere, generische Client-Antwort — Details bleiben im Server-Log."""
    return {
        "message": "Ein interner Serverfehler ist aufgetreten.",
        "error_id": error_id,
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.post("/analyze", response_model=TicketAnalysis)
async def analyze_ticket(ticket: TicketInput) -> TicketAnalysis:
    # Lazy-Import: der Graph (inkl. ChatOllama-Singletons) wird erst beim ersten
    # /analyze-Aufruf gebaut, nicht schon beim Service-Start.
    from app.graph.orchestrator import run_graph

    try:
        return await run_graph(ticket)
    except Exception as exc:
        # Eindeutige Tracking-ID generieren, Fehler ausführlich serverseitig
        # loggen (exc_info=True schreibt den kompletten Stacktrace), dem Client
        # aber nur die generische Meldung + ID zurückgeben.
        error_id = str(uuid.uuid4())
        logger.error(
            "Fehler bei der Ticket-Analyse (Error-ID: %s): %s",
            error_id, exc, exc_info=True,
        )
        raise HTTPException(status_code=500, detail=_error_response(error_id))

from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
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
    logger.info("Max. parallele Analysen: %d", settings.max_concurrent_analyses)
    yield
    logger.info("Service wird beendet.")


app = FastAPI(
    title=settings.app_name,
    description="n8n-gesteuerter LangGraph-Microservice für Ticket-Verarbeitung",
    version="1.0.0",
    lifespan=lifespan,
)


# Globaler Überlastschutz: begrenzt gleichzeitig laufende Analysen und damit die
# Last auf dem GPU-Engpass. Module-Level => geteilt über alle Requests des Prozesses.
_analyze_semaphore = asyncio.Semaphore(settings.max_concurrent_analyses)


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

    # Überlastschutz: Slot VOR dem try holen. Da HTTPException von Exception erbt,
    # würde ein 503 sonst vom generischen "except Exception" zu einem 500 verfälscht.
    # Ohne freien Slot nach acquire_timeout wird die Last abgewiesen (503).
    try:
        await asyncio.wait_for(
            _analyze_semaphore.acquire(),
            timeout=settings.semaphore_acquire_timeout,
        )
    except asyncio.TimeoutError:
        logger.warning("[Overload] /analyze abgewiesen — alle %d Slots belegt.",
                       settings.max_concurrent_analyses)
        raise HTTPException(
            status_code=503,
            detail="Service ausgelastet, bitte später erneut.",
            headers={"Retry-After": "5"},
        )

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
    finally:
        # Slot nur freigeben, wenn er auch geholt wurde (acquire war erfolgreich).
        _analyze_semaphore.release()

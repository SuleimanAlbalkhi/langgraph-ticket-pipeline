from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from app.models.ticket import TicketInput, TicketAnalysis
from app.config import get_settings
import logging
import uuid  # <-- Hinzugefügt für generische Fehler-IDs

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

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.app_name}

@app.post("/analyze", response_model=TicketAnalysis)
async def analyze_ticket(ticket: TicketInput):
    try:
        from app.graph.orchestrator import run_graph
        result = await run_graph(ticket)
        return result
    except Exception as e:
        # 1. Eindeutige Tracking-ID für diesen spezifischen Fehler generieren
        error_id = str(uuid.uuid4())
        
        # 2. Den Fehler ausführlich auf dem Server loggen
        # exc_info=True ist wichtig, da es den kompletten Stacktrace in die Logs schreibt!
        logger.error(
            "Fehler bei der Ticket-Analyse (Error-ID: %s): %s", 
            error_id, 
            str(e), 
            exc_info=True
        )
        
        # 3. Dem Client nur die sichere, generische Meldung + ID zurückgeben
        raise HTTPException(
            status_code=500, 
            detail={
                "message": "Ein interner Serverfehler ist aufgetreten.",
                "error_id": error_id
            }
        )
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from app.models.ticket import TicketInput, TicketAnalysis
from app.config import get_settings
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
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
        raise HTTPException(status_code=500, detail=str(e))
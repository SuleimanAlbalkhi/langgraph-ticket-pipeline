from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from enum import Enum
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.config import get_settings

# Gemeinsame LLM-Plumbing für die drei Nodes. Hält die Client-Konfiguration (Provider,
# JSON-Modus, Timeouts), den Aufruf mit Timeout und das JSON-Parsing an EINER Stelle —
# kein Copy-Paste über classifier / extractor / risk_guard.

logger = logging.getLogger(__name__)

# Berechtigungsbereich für Tokens an Azure OpenAI (gilt für alle Cognitive-Services-Ressourcen).
AZURE_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


class LLMFailure(Enum):
    """Warum ein LLM-Aufruf kein verwertbares JSON-Objekt geliefert hat. Jede Node
    mappt das auf ihren eigenen sicheren Fallback."""
    TIMEOUT = "timeout"
    ERROR   = "error"
    PARSE   = "parse"


@lru_cache
def get_azure_token_provider() -> Callable[[], str]:
    """Ein Token-Provider pro Prozess. DefaultAzureCredential probiert mehrere
    Anmeldewege nacheinander (Umgebungsvariablen, Managed Identity, Azure CLI, …):
    lokal greift "az login", in der Container App die Managed Identity. Der Provider
    cached das Token (gültig ca. 1 h) und erneuert es kurz vor Ablauf selbst.

    Lazy importiert: Wer nur mit Ollama arbeitet, lädt azure-identity nie."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    return get_bearer_token_provider(DefaultAzureCredential(), AZURE_TOKEN_SCOPE)


def build_json_llm(model: str, temperature: float) -> BaseChatModel:
    """Factory für den Chat-Client der Nodes. Nur model + temperature variieren pro
    Node, der Provider kommt aus LLM_PROVIDER, der Rest aus den Settings.

    Beide Varianten liefern JSON-Objekte, aber über verschiedene Schalter:
    Ollama über format="json", Azure OpenAI über response_format=json_object. Der
    JSON-Modus von Azure verlangt, dass das Wort "JSON" im Prompt vorkommt — alle drei
    Prompts erfüllen das (siehe tests/snapshots)."""
    s = get_settings()
    if s.llm_provider == "azure":
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_endpoint=s.azure_openai_endpoint,
            azure_deployment=model,
            api_version=s.azure_openai_api_version,
            azure_ad_token_provider=get_azure_token_provider(),
            temperature=temperature,
            max_retries=s.azure_max_retries,
            timeout=s.azure_request_timeout,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
    return ChatOllama(
        model=model,
        base_url=s.ollama_base_url,
        temperature=temperature,
        format="json",
        timeout=s.llm_timeout,
    )


def parse_json_object(content: str | None) -> dict | None:
    """Parst LLM-Output zu einem dict. Gibt None zurück bei kaputtem JSON ODER
    bei Nicht-Objekt (Liste/Skalar) — format='json' garantiert gültiges JSON,
    aber kein Objekt, und ein .get() auf eine Liste würfe sonst AttributeError.

    TypeError wird mitgefangen, falls content wider Erwarten kein str ist (z.B.
    Multimodal-Content als Liste): json.loads würfe dann TypeError statt None."""
    try:
        data = json.loads(content or "")
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _failure(label: str, reason: LLMFailure) -> LLMFailure:
    """Eine einheitliche, maschinenlesbare Logzeile pro gescheitertem LLM-Aufruf.

    Wichtig für den Betrieb: Ein LLM-Ausfall führt NICHT zu einem HTTP-Fehler — die Node
    fällt auf einen sicheren Default zurück und /analyze antwortet weiter mit 200. Ein
    Alarm auf fehlgeschlagene Requests sähe einen Modellausfall deshalb nie. Diese Zeile
    ist das Signal dafür (Alarm in Application Insights, Block D). Sie enthält bewusst
    keinen Ticketinhalt."""
    logger.warning("LLM_FAILURE node=%r reason=%s", label, reason.value)
    return reason


async def invoke_json(llm: BaseChatModel, prompt: str, label: str) -> dict | LLMFailure:
    """Ein LLM-Aufruf mit Timeout und JSON-Parsing. Wirft nie: jeder Fehler wird
    als LLMFailure zurückgegeben. `label` ist das Log-Präfix der Node.
    Bei Parse-Fehlern wird bewusst KEIN roher Modell-Output geloggt: er ist aus dem
    Ticket abgeleitet und kann personenbezogene Daten enthalten (DSGVO)."""
    timeout = get_settings().llm_timeout
    t0 = time.time()
    try:
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=timeout)
    except TimeoutError:
        logger.error("[%s] TIMEOUT nach %.0fs", label, timeout)
        return _failure(label, LLMFailure.TIMEOUT)
    except Exception as exc:  # noqa: BLE001 — jeder LLM-Fehler soll in den sicheren Fallback, nicht in einen 500
        logger.error("[%s] LLM-Fehler nach %.1fs: %s", label, time.time() - t0, exc)
        return _failure(label, LLMFailure.ERROR)

    logger.info("[%s] LLM antwortete in %.1fs", label, time.time() - t0)
    data = parse_json_object(response.content)
    if data is None:
        logger.warning("[%s] JSON-Parse fehlgeschlagen | len=%d", label, len(response.content or ""))
        return _failure(label, LLMFailure.PARSE)
    return data

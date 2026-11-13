from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Provider-Schalter: dieselbe Codebasis läuft lokal mit Ollama und in der Cloud mit
    # Azure OpenAI. Umgeschaltet wird nur über die Umgebungsvariable LLM_PROVIDER.
    llm_provider: Literal["ollama", "azure"] = "ollama"

    # Ollama — läuft lokal, kein API-Key nötig
    ollama_base_url: str    = "http://localhost:11434"
    # Zwei-Tier-Strategie: fast_model für Klassifikation/Extraktion (Node 1+2),
    # smart_model für die Risikobewertung (Node 3). Aktuell zeigen beide aus
    # GPU-Gründen auf dasselbe Modell — produktiv wäre smart_model z.B. qwen2.5:14b.
    # Das Routing pro Node existiert bereits im Code; nur die Werte hier ändern sich.
    ollama_fast_model: str  = "qwen2.5:3b"
    ollama_smart_model: str = "qwen2.5:3b"

    # Azure OpenAI — Anmeldung ohne Schlüssel über Microsoft Entra ID: lokal greift der
    # Login der Azure CLI ("az login"), in der Cloud die Managed Identity der Container App.
    # Die *_deployment-Werte sind Deployment-Namen, keine Modellnamen: Ein Modellwechsel
    # ändert nur das Deployment in Azure, nicht diesen Code.
    azure_openai_endpoint: str     = ""   # z.B. https://oai-ticketpipe-sa.openai.azure.com/
    azure_openai_api_version: str  = "2024-10-21"
    azure_fast_deployment: str     = "ticket-llm"
    azure_smart_deployment: str    = "ticket-llm"
    # Wiederholungen bei 429 (Rate-Limit) und 5xx übernimmt das OpenAI-SDK selbst, mit
    # exponentiellem Backoff. Ein eigener Retry-Wrapper wäre doppelt — und außerhalb von
    # invoke_json() wirkungslos, weil dort jeder Fehler abgefangen wird.
    azure_max_retries: int         = 3
    # Timeout pro einzelnem HTTP-Versuch. llm_timeout unten begrenzt den gesamten Aufruf
    # inklusive aller Wiederholungen.
    azure_request_timeout: float   = 15.0

    # Gesamt-Timeout pro LLM-Aufruf in Sekunden, für beide Provider.
    # OLLAMA_TIMEOUT bleibt als alter Variablenname gültig (docker-compose, bestehende .env).
    llm_timeout: float = Field(60.0, validation_alias=AliasChoices("LLM_TIMEOUT", "OLLAMA_TIMEOUT"))

    # Service
    app_name: str  = "Hybrid AI Orchestrator"
    debug: bool    = False
    log_level: str = "INFO"

    # Schutz für POST /analyze: Clients schicken den Wert im Header X-API-Key.
    # Leer = Schutz aus — nur lokal sinnvoll. Mit llm_provider=azure meldet /ready ohne
    # Key "nicht bereit", damit eine Cloud-Instanz nie ungeschützt Verkehr annimmt.
    api_key: str = ""

    # Commit, aus dem das Image gebaut wurde (Docker-Build-Arg GIT_SHA). /ready gibt ihn
    # zurück, damit der Smoke-Test nach einem Deployment prüfen kann, ob wirklich die
    # neue Revision antwortet und nicht noch die alte.
    git_sha: str = "unknown"

    # Tracing mit Langfuse Cloud (EU). Aus, solange nicht beide Schlüssel gesetzt sind:
    # Ein halber Schlüsselsatz soll nicht zu Fehlern bei jedem Request führen.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str   = "https://cloud.langfuse.com"   # EU-Region
    # Standard: Inhalte maskiert, dieselbe DSGVO-Regel wie bei den Logs. true sendet
    # Ticketinhalte an Langfuse und ist nur für synthetische Demo-Tickets gedacht.
    langfuse_capture_content: bool = False
    # Stufe, nicht Provider: lokal "local", in der Container App "production". Eigenes Feld,
    # weil das SDK nur os.environ liest, die .env aber nur hier ankommt; ohne Default landeten
    # lokale Läufe in "default". Environments lassen sich in Langfuse nicht löschen.
    langfuse_tracing_environment: str = "local"
    # Schlüssel für den HMAC der Ticket-ID in den Trace-Metadaten. Ein einfacher Hash wäre bei
    # vorhersagbaren IDs (EVAL-001 …) durch Durchprobieren umkehrbar. Leer = keine Ticket-ID.
    ticket_id_hmac_key: str = ""

    # Überlastschutz — globale Begrenzung gleichzeitiger Analysen schützt den
    # GPU-Engpass. Bekommt ein Request nach acquire_timeout keinen freien Slot,
    # antwortet der Service mit 503 (Load-Shedding) statt Requests aufzustauen.
    #
    # Default 2 ist auf eine kleine GPU (~4 GB VRAM, qwen2.5:3b) abgestimmt: eine
    # einzelne Analyse feuert intern bereits bis zu 3 parallele Classifier-Votes,
    # und der echte Parallelitätsgrad wird ohnehin von OLLAMA_NUM_PARALLEL bestimmt
    # (hostseitig, da Ollama nicht containerisiert ist). Auf größerer Hardware erhöhen.
    # Mit Azure ist nicht die GPU der Engpass, sondern das Tokens-pro-Minute-Kontingent
    # des Deployments; den Wert dort über MAX_CONCURRENT_ANALYSES eigens setzen.
    max_concurrent_analyses: int     = 2
    semaphore_acquire_timeout: float = 2.0  # Sekunden

    @property
    def fast_model(self) -> str:
        """Modell bzw. Deployment für Classifier und Extractor (Node 1+2)."""
        return self.azure_fast_deployment if self.llm_provider == "azure" else self.ollama_fast_model

    @property
    def smart_model(self) -> str:
        """Modell bzw. Deployment für den Risk Guard (Node 3)."""
        return self.azure_smart_deployment if self.llm_provider == "azure" else self.ollama_smart_model

    @property
    def tracing_enabled(self) -> bool:
        """Tracing nur mit vollständigem Langfuse-Schlüsselpaar."""
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

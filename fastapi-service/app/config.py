from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Ollama — läuft lokal, kein API-Key nötig
    ollama_base_url: str    = "http://localhost:11434"
    ollama_fast_model: str  = "qwen2.5:3b"
    ollama_smart_model: str = "qwen2.5:3b"
    ollama_timeout: float   = 60.0   # Sekunden pro LLM-Call

    # Service
    app_name: str  = "Hybrid AI Orchestrator"
    debug: bool    = False
    log_level: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

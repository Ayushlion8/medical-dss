from __future__ import annotations
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini (primary LLM)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL:   str = "gemini-2.0-flash"

    # Ollama (fallback / vision)
    OLLAMA_BASE_URL:    str = "http://127.0.0.1:11434"
    OLLAMA_MODEL:       str = "tinyllama:latest"
    OLLAMA_VISION_MODEL:str = "llava:13b"

    # Vector store
    CHROMA_HOST:       str = "localhost"
    CHROMA_PORT:       int = 8001
    CHROMA_COLLECTION: str = "medical_rag"

    # PubMed
    PUBMED_EMAIL:       str = "research@example.com"
    PUBMED_API_KEY:     str = ""
    PUBMED_MAX_RESULTS: int = 20

    # Storage
    UPLOAD_DIR:  str = "uploads"
    OVERLAY_DIR: str = "overlays"
    REPORT_DIR:  str = "reports"
    TRACE_DIR:   str = "traces"

    # Security
    SECRET_KEY:      str = "change_me"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost"]

    # App
    LOG_LEVEL:          str = "INFO"
    APP_ENV:            str = "development"
    MAX_UPLOAD_SIZE_MB: int = 50

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()

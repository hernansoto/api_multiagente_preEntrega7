"""Configuración compartida (leer .env antes de inicializar clientes)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_stream: str = os.getenv("REDIS_STREAM", "multiagent:jobs")
    redis_group: str = os.getenv("REDIS_GROUP", "multiagent-workers")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    approval_api_key: str = os.getenv("APPROVAL_API_KEY", "")
    api_key: str = os.getenv("API_KEY", "")
    worker_concurrency: int = int(os.getenv("WORKER_CONCURRENCY", "5"))
    max_steps_default: int = 8


settings = Settings()

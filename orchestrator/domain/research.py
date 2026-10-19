"""Búsqueda reproducible en una base documental simulada de dominio comercial."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "sources.json"
STOPWORDS = {
    "de", "del", "el", "la", "los", "las", "en", "y", "o", "un", "una", "por",
    "para", "con", "que", "cual", "cuales", "segun", "me", "necesito", "quiero",
    "datos", "calcula", "calcular", "compara", "comparar", "analiza", "analisis",
    "plan", "planes", "entre", "se", "su", "al", "conviene", "2026",
}


def tokenize(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-záéíóúñ0-9]+", value.casefold())
        if len(token) > 2 and token not in STOPWORDS
    }


def search_local_sources(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Retorna documentos pertinentes con su fuente y datos originales."""
    if not 1 <= limit <= 20:
        raise ValueError("limit debe estar entre 1 y 20")
    terms = tokenize(query)
    if not terms:
        return []
    records: list[dict[str, Any]] = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    scored: list[tuple[int, dict[str, Any]]] = []
    for record in records:
        important = tokenize(f"{record['title']} {record['content']}")
        score = len(terms & important)
        if score:
            scored.append((score, record))
    scored.sort(key=lambda item: (-item[0], item[1]["source_id"]))
    return [document for _, document in scored[:limit]]

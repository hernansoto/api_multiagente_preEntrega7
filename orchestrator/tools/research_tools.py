"""Herramientas accesibles únicamente para el investigador."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from langchain_core.tools import tool

from orchestrator.domain.research import search_local_sources


@tool
async def search_research_database(query: str) -> str:
    """Busca fuentes simuladas internas por palabras clave y retorna cifras y IDs originales.

    Usar siempre cuando la pregunta mencione Starter, Growth, márgenes o datos internos.
    El dataset está identificado como FICTICIO: no confundir con datos externos reales.
    """
    records = search_local_sources(query)
    return json.dumps({"source_type": "simulated_local_db", "results": records}, ensure_ascii=False)


@tool
async def search_tavily_web(query: str) -> str:
    """Busca sitios web reales con Tavily; solo usar para preguntas sobre información pública."""
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key:
        return json.dumps({"source_type": "web", "results": [], "error": "Falta TAVILY_API_KEY"})
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={"api_key": key, "query": query, "search_depth": "basic", "max_results": 5},
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
    results = [
        {
            "source_id": item.get("url", ""),
            "title": item.get("title", ""),
            "content": item.get("content", ""),
            "origin": "tavily_web",
            "url": item.get("url", ""),
        }
        for item in payload.get("results", [])
        if item.get("url")
    ]
    return json.dumps({"source_type": "web", "results": results}, ensure_ascii=False)

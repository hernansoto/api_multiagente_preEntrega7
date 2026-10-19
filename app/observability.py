"""Instrumentación LangSmith: spans de grafo + LLMs anidados automáticamente."""
from __future__ import annotations

import os
from typing import Any

from langgraph.types import Command
from langsmith import traceable


@traceable(name="multiagent_job", run_type="chain")
async def run_traced_graph(
    *, graph: Any, payload: Any, config: dict, job_id: str, kind: str,
) -> dict:
    """El run raíz puede identificarse por tags/metadata; LangChain traza tokens y costos.

    La plataforma calcula los importes según el modelo y su tabla de precios.
    """
    return await graph.ainvoke(payload, config=config)


def tracing_enabled() -> bool:
    return os.getenv("LANGSMITH_TRACING", "false").lower() == "true" and bool(
        os.getenv("LANGSMITH_API_KEY", "")
    )

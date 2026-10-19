"""Especialista investigador: aislamiento de herramientas y fuentes trazables."""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Awaitable

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from orchestrator.agents.common import as_text, collect_tool_json
from orchestrator.state import OrchestratorState
from orchestrator.tools.research_tools import search_research_database, search_tavily_web


RESEARCH_PROMPT = """Sos un investigador especializado en fuentes y evidencia.
Tu objetivo es investigar SOLO la consulta proporcionada, nunca calcular márgenes.
REGLAS:
- Usa search_research_database para cifras de los planes Starter/Growth.
- Para solicitudes de información pública, usa search_tavily_web SOLO si está disponible.
- Busca ambos planes si el usuario solicita compararlos. Si falta alguno, realizá otra consulta.
- Cita los source_id de cada cifra. Prioriza registros exactos frente a inferencias.
- Clasifica los datos internos como FICTICIOS/SIMULADOS, no como información real.
- No inventes URLs, cifras ni fechas. Si falta información, declará la ausencia.
- Entregá un resumen de hallazgos breve y verificable en español.
"""


def make_research_node(model: BaseChatModel) -> Callable[[OrchestratorState], Awaitable[dict[str, Any]]]:
    tools = [search_research_database]
    if os.getenv("TAVILY_API_KEY", "").strip():
        tools.append(search_tavily_web)
    specialist = create_agent(model=model, tools=tools, system_prompt=RESEARCH_PROMPT, name="researcher")

    async def research_node(state: OrchestratorState) -> dict[str, Any]:
        attempt = state.get("research_attempts", 0) + 1
        feedback = state.get("validation_errors", [])
        instruction = (
            f"Solicitud original: {state['user_request']}\n"
            f"Refinamiento requerido: {json.dumps(feedback, ensure_ascii=False)}\n"
            "Investiga con herramientas reales; devolvé el origen de cada dato."
        )
        try:
            outcome = await specialist.ainvoke(
                {"messages": [{"role": "user", "content": instruction}]},
                config={"recursion_limit": 16},
            )
            messages = outcome["messages"]
            payloads = collect_tool_json(messages, {"search_research_database", "search_tavily_web"})
            sources: dict[str, dict[str, Any]] = {}
            for payload in payloads:
                for item in payload.get("results", []):
                    if isinstance(item, dict) and item.get("source_id"):
                        sources[str(item["source_id"])] = item
            summary = as_text(messages[-1].content)
            tool_used = bool(payloads)
            output = {
                "research_output": summary,
                "research_sources": list(sources.values()),
                "research_tool_used": tool_used,
                "research_attempts": attempt,
                "research_error": "",
                "messages": [AIMessage(name="researcher", content=f"Investigación: {summary}")],
                "contributions": [{"agent": "researcher", "status": "ok" if sources else "warning", "detail": f"{len(sources)} fuentes recuperadas"}],
                "route_trace": ["researcher"],
            }
            return output
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            return {
                "research_attempts": attempt,
                "research_error": error,
                "contributions": [{"agent": "researcher", "status": "error", "detail": error[:250]}],
                "route_trace": ["researcher"],
            }

    return research_node

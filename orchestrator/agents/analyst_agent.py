"""Especialista analista: calcula con tools e inspecciona fuentes, sin web."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from orchestrator.agents.common import as_text, collect_tool_json
from orchestrator.state import OrchestratorState
from orchestrator.tools.analysis_tools import calculate_plan_metrics, compare_plan_metrics


ANALYST_PROMPT = """Sos un analista cuantitativo de rentabilidad comercial.
REGLAS OBLIGATORIAS:
- Usá solo las cifras numéricas de las fuentes proporcionadas en la solicitud actual.
- Para comparar 2 planes, SIEMPRE llamá compare_plan_metrics con los valores textuales exactos.
- Si fuera un solo plan, llamá calculate_plan_metrics.
- No inventes datos ausentes, fechas ni fuentes. Si faltan datos, reportá el faltante.
- Identificá los IDs de fuente y explica margen bruto (%) vs contribución bruta mensual (ARS).
- No confundir contribución bruta con beneficio neto: no contempla gastos fijos ni impuestos.
- No uses la web: todas tus herramientas están acotadas a cálculos.
- Etiquetá el dataset de demostración como simulado.
"""


def make_analyst_node(model: BaseChatModel) -> Callable[[OrchestratorState], Awaitable[dict[str, Any]]]:
    specialist = create_agent(
        model=model,
        tools=[calculate_plan_metrics, compare_plan_metrics],
        system_prompt=ANALYST_PROMPT,
        name="analyst",
    )

    async def analysis_node(state: OrchestratorState) -> dict[str, Any]:
        attempt = state.get("analysis_attempts", 0) + 1
        # Contexto mínimo y fiable: solicitud + datos de origen + correcciones del validador.
        instruction = (
            f"Solicitud original: {state['user_request']}\n"
            f"Fuentes primarias: {json.dumps(state.get('research_sources', []), ensure_ascii=False)}\n"
            f"Hallazgos investigador: {state.get('research_output', '')}\n"
            f"Errores de validación previos: {json.dumps(state.get('validation_errors', []), ensure_ascii=False)}\n"
            "Realizá los cálculos mediante tus herramientas, no mentalmente."
        )
        try:
            outcome = await specialist.ainvoke(
                {"messages": [{"role": "user", "content": instruction}]},
                config={"recursion_limit": 16},
            )
            messages = outcome["messages"]
            payloads = collect_tool_json(
                messages, {"calculate_plan_metrics", "compare_plan_metrics"}
            )
            summary = as_text(messages[-1].content)
            return {
                "analysis_output": summary,
                "analysis_calculations": payloads,
                "analysis_tool_used": bool(payloads),
                "analysis_attempts": attempt,
                "analysis_error": "",
                "messages": [AIMessage(name="analyst", content=f"Análisis: {summary}")],
                "contributions": [{"agent": "analyst", "status": "ok" if payloads else "warning", "detail": f"{len(payloads)} cálculos de herramientas"}],
                "route_trace": ["analyst"],
            }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            return {
                "analysis_attempts": attempt,
                "analysis_error": error,
                "contributions": [{"agent": "analyst", "status": "error", "detail": error[:250]}],
                "route_trace": ["analyst"],
            }

    return analysis_node

"""Síntesis supervisada: prioriza evidencia numérica antes que prosa de agentes."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from orchestrator.agents.common import as_text
from orchestrator.state import OrchestratorState


SYNTHESIS_PROMPT = """Sos el sintetizador final de un análisis auditado.
Respondé en español de forma clara y con estos criterios:
- Contestá la consulta original, compará resultados y explicá el fundamento.
- Solo valores verificables del registro 'analysis_calculations', nunca cifras inventadas.
- Citá source_id para cada dato originado en la investigación.
- Los datos de origen simulated_internal_dataset SON FICTICIOS: informalo explícitamente.
- No confundas margen bruto con ganancia neta, ni declares rentabilidad neta.
- Ante conflictos entre síntesis previa y fuente original, prevalece la fuente primaria.
- Si task_completed es false, detallá limitaciones y evita concluir sin evidencia.
- Presentá recomendación condicionada y límites (sin gastos fijos, ni impuestos).
"""


def make_synthesis_node(
    model: BaseChatModel,
) -> Callable[[OrchestratorState], Awaitable[dict[str, Any]]]:
    async def synthesis_node(state: OrchestratorState) -> dict[str, Any]:
        context = {
            "request": state.get("user_request", ""),
            "sources": state.get("research_sources", []),
            "calculations": state.get("analysis_calculations", []),
            "research_summary": state.get("research_output", ""),
            "analyst_summary": state.get("analysis_output", ""),
            "validation_errors": state.get("validation_errors", []),
            "task_completed": state.get("task_completed", False),
            "stop_reason": state.get("stop_reason", ""),
        }
        synthesis_error = ""
        try:
            answer = await model.ainvoke([
                SystemMessage(content=SYNTHESIS_PROMPT),
                HumanMessage(content=json.dumps(context, ensure_ascii=False)),
            ])
            final = as_text(answer.content)
        except Exception as exc:
            synthesis_error = f"{type(exc).__name__}: {exc}"[:250]
            final = (
                "No se pudo generar la síntesis final con el modelo. "
                f"Motivo: {type(exc).__name__}.\n"
                f"Cálculos verificados disponibles: {json.dumps(context['calculations'], ensure_ascii=False)}\n"
                f"Advertencias: {json.dumps(context['validation_errors'], ensure_ascii=False)}\n"
                "Los datos de la demo son simulados."
            )
        if not state.get("task_completed", False):
            final = "⚠️ RESULTADO PARCIAL: validación incompleta.\n\n" + final
        return {
            "final_answer": final,
            "synthesis_error": synthesis_error,
            "messages": [AIMessage(name="synthesizer", content=final)],
            "contributions": [{"agent": "synthesizer", "status": "ok" if state.get("task_completed") else "warning", "detail": "Respuesta final entregada"}],
            "route_trace": ["synthesizer → END"],
        }

    return synthesis_node

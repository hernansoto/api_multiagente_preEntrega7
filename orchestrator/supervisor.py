"""Supervisor LLM: selecciona dinámicamente la siguiente delegación."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from orchestrator.state import NextAgent, OrchestratorState


class SupervisorDecision(BaseModel):
    next_agent: NextAgent = Field(description="Próximo especialista o cierre por síntesis")
    reason: str = Field(description="Justificación breve basada en estado y rúbrica")


SUPERVISOR_PROMPT = """Sos el SUPERVISOR de un equipo jerárquico multi-agente.
Tu responsabilidad es elegir UN próximo nodo según información disponible y objetivos.
Opciones: researcher, analyst, synthesizer.

RÚBRICA OBLIGATORIA:
1. Si no hay fuentes verificables ni investigación suficiente, delega a researcher.
2. Si las fuentes relevantes están listas pero no hay cálculos respaldados, delega a analyst.
3. Cuando existan hallazgos de investigación Y resultados del análisis, revisá la validación.
4. Si el validador detectó inconsistencias o cifras sin fuente, delega al responsable
   que pueda corregirlas; no termines con fallos pendientes si aún hay pasos.
5. Solo elige synthesizer cuando task_completed sea true; si el presupuesto se agotó,
   se permitirá una respuesta parcial identificando las limitaciones.
6. No llames herramientas directamente, no fabriques hechos ni calcules a mano.
7. Evitá reintentos redundantes: si no hay nuevos datos, termina declarando límites.

Elige dinámicamente en función de la solicitud y evidencia. No sigas una secuencia fija.
"""


def make_supervisor_node(
    model: BaseChatModel,
) -> Callable[[OrchestratorState], Awaitable[dict[str, Any]]]:
    structured_model = model.with_structured_output(SupervisorDecision)

    async def supervisor_node(state: OrchestratorState) -> dict[str, Any]:
        step = state.get("step_count", 0) + 1
        max_steps = state.get("max_steps", 8)
        if step >= max_steps:
            return {
                "step_count": step,
                "next_agent": "synthesizer",
                "stop_reason": "Se alcanzó el límite de decisiones del supervisor.",
                "supervisor_reason": "Cierre seguro por presupuesto máximo de pasos.",
                "route_trace": ["supervisor → synthesizer (límite)"],
            }

        context = {
            "user_request": state.get("user_request", ""),
            "research_source_ids": [s.get("source_id") for s in state.get("research_sources", [])],
            "research_summary": state.get("research_output", "")[:1400],
            "analysis_summary": state.get("analysis_output", "")[:1400],
            "has_calculations": bool(state.get("analysis_calculations")),
            "research_attempts": state.get("research_attempts", 0),
            "analysis_attempts": state.get("analysis_attempts", 0),
            "validation_errors": state.get("validation_errors", []),
            "task_completed": state.get("task_completed", False),
            "remaining_steps": max_steps - step,
        }
        try:
            messages = [
                SystemMessage(content=SUPERVISOR_PROMPT),
                HumanMessage(content=json.dumps(context, ensure_ascii=False)),
            ]
            decision: SupervisorDecision = await structured_model.ainvoke(messages)
            # Si el LLM intenta cerrar prematuramente, pedimos otra decisión al LLM;
            # no hay un if/else que fuerce el orden normal de los especialistas.
            if decision.next_agent == "synthesizer" and not state.get("task_completed", False):
                messages.append(HumanMessage(content=(
                    "Tu propuesta de cerrar no cumple la rúbrica: task_completed es false. "
                    "Elegí qué especialista debe completar o refinar la evidencia. "
                    "Reservá synthesizer para cierre seguro si no es posible avanzar."
                )))
                decision = await structured_model.ainvoke(messages)
            return {
                "next_agent": decision.next_agent,
                "supervisor_reason": decision.reason,
                "step_count": step,
                "route_trace": [f"supervisor → {decision.next_agent}: {decision.reason}"],
            }
        except Exception as exc:
            error = f"No fue posible decidir el próximo agente: {type(exc).__name__}: {exc}"
            return {
                "next_agent": "synthesizer",
                "supervisor_reason": "Cierre técnico ante fallo del modelo supervisor.",
                "step_count": step,
                "stop_reason": error,
                "route_trace": ["supervisor → synthesizer (error)"],
            }

    return supervisor_node

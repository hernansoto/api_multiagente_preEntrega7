"""Validación independiente: evidencia, dos dominios y consistencia aritmética."""

from __future__ import annotations

from typing import Any
import math

from orchestrator.domain.metrics import plan_metrics
from orchestrator.state import OrchestratorState


def validation_issues(state: OrchestratorState) -> list[str]:
    errors: list[str] = []
    sources = state.get("research_sources", [])
    if not state.get("research_tool_used") or not sources:
        errors.append("Falta investigación respaldada por una herramienta y fuentes con IDs.")

    indexed: dict[str, dict[str, Any]] = {}
    for source in sources:
        metrics = source.get("metrics")
        if isinstance(metrics, dict) and metrics.get("plan"):
            indexed[str(metrics["plan"]).casefold()] = metrics

    # Esta demo está orientada a dos planes; otras consultas pueden ser de un único plan.
    request = state.get("user_request", "").casefold()
    requested = [name for name in ("Starter", "Growth") if name.casefold() in request]
    for name in requested:
        if name.casefold() not in indexed:
            errors.append(f"Faltan datos de fuente para el plan {name}.")

    if not state.get("analysis_tool_used") or not state.get("analysis_calculations"):
        errors.append("Falta análisis con invocación comprobable de herramientas de cálculo.")

    if not state.get("analysis_output", "").strip():
        errors.append("Falta interpretación textual del analista.")

    verified: set[str] = set()
    for calculation in state.get("analysis_calculations", []):
        plans = calculation.get("plans")
        if not plans:
            if "name" in calculation and "gross_margin_pct" in calculation:
                plans = [calculation]
            else:
                continue
        for item in plans:
            name = str(item.get("name", ""))
            record = indexed.get(name.casefold())
            if not record:
                errors.append(f"El analista calculó {name} sin una fuente cuantitativa respaldatoria.")
                continue
            expected = plan_metrics(
                name,
                record["unit_price"],
                record["unit_variable_cost"],
                record["active_customers"],
            )
            numeric_fields = (
                "unit_price", "unit_variable_cost", "active_customers",
                "gross_margin_pct", "monthly_gross_contribution",
            )
            def differs(field: str) -> bool:
                try:
                    actual = float(item[field])
                    reference = float(expected[field])
                    return not math.isfinite(actual) or abs(actual - reference) > 0.02
                except (KeyError, TypeError, ValueError, OverflowError):
                    return True

            if any(differs(field) for field in numeric_fields):
                errors.append(f"Cálculo conflictivo para {name}: difiere de la fuente original.")
            else:
                verified.add(name.casefold())

    for name in requested:
        if name.casefold() not in verified:
            errors.append(f"Aún no hay cálculo matemático validado para {name}.")

    if state.get("research_error"):
        errors.append(f"Investigator reportó error: {state['research_error'][:150]}")
    if state.get("analysis_error"):
        errors.append(f"Analista reportó error: {state['analysis_error'][:150]}")
    return list(dict.fromkeys(errors))


async def validation_node(state: OrchestratorState) -> dict[str, Any]:
    issues = validation_issues(state)
    return {
        "validation_errors": issues,
        "task_completed": not issues,
        "contributions": [{
            "agent": "validator",
            "status": "ok" if not issues else "warning",
            "detail": "Validación completa" if not issues else "; ".join(issues)[:300],
        }],
        "route_trace": ["validator"],
    }

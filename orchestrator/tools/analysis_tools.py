"""Herramientas matemáticas acotadas únicamente al analista."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from orchestrator.domain.metrics import compare_metrics, plan_metrics


@tool
async def calculate_plan_metrics(
    name: str, unit_price: float, unit_variable_cost: float, active_customers: int
) -> str:
    """Calcula con precisión margen bruto (%) y contribución bruta mensual en ARS para un plan."""
    value = plan_metrics(name, unit_price, unit_variable_cost, active_customers)
    return json.dumps(value, ensure_ascii=False)


@tool
async def compare_plan_metrics(
    name_a: str,
    unit_price_a: float,
    unit_variable_cost_a: float,
    active_customers_a: int,
    name_b: str,
    unit_price_b: float,
    unit_variable_cost_b: float,
    active_customers_b: int,
) -> str:
    """Compara DOS planes con fuentes numéricas verificadas usando cálculos reales.

    Devuelve ambos márgenes brutos, contribuciones mensuales y ganadores.
    Invocar siempre para la comparación Starter vs Growth usando datos de investigación.
    """
    a = plan_metrics(name_a, unit_price_a, unit_variable_cost_a, active_customers_a)
    b = plan_metrics(name_b, unit_price_b, unit_variable_cost_b, active_customers_b)
    return json.dumps(compare_metrics(a, b), ensure_ascii=False)

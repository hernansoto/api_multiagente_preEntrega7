"""Cálculos puros: esta lógica puede probarse sin LLM ni acceso a Internet."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import TypedDict


class PlanResult(TypedDict):
    name: str
    unit_price: float
    unit_variable_cost: float
    active_customers: int
    gross_margin_pct: float
    monthly_gross_contribution: float


def plan_metrics(
    name: str, unit_price: float, unit_variable_cost: float, active_customers: int
) -> PlanResult:
    """Calcula margen bruto y contribución bruta mensual; todos los importes son ARS."""
    price = Decimal(str(unit_price))
    cost = Decimal(str(unit_variable_cost))
    if price <= 0:
        raise ValueError("unit_price debe ser mayor a cero")
    if cost < 0:
        raise ValueError("unit_variable_cost no puede ser negativo")
    if cost > price:
        raise ValueError("unit_variable_cost no puede superar unit_price en esta demo")
    if active_customers < 0:
        raise ValueError("active_customers no puede ser negativo")

    margin = ((price - cost) / price * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    contribution = ((price - cost) * active_customers).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return {
        "name": name,
        "unit_price": float(price),
        "unit_variable_cost": float(cost),
        "active_customers": active_customers,
        "gross_margin_pct": float(margin),
        "monthly_gross_contribution": float(contribution),
    }


def compare_metrics(a: PlanResult, b: PlanResult) -> dict[str, object]:
    """Comparación explícita: distingue margen porcentual de contribución absoluta."""
    margin_winner = (
        a["name"] if a["gross_margin_pct"] > b["gross_margin_pct"] else b["name"]
        if b["gross_margin_pct"] > a["gross_margin_pct"] else "empate"
    )
    contribution_winner = (
        a["name"]
        if a["monthly_gross_contribution"] > b["monthly_gross_contribution"]
        else b["name"]
        if b["monthly_gross_contribution"] > a["monthly_gross_contribution"]
        else "empate"
    )
    return {
        "plans": [a, b],
        "winner_by_margin": margin_winner,
        "winner_by_contribution": contribution_winner,
        "currency": "ARS",
        "limits": "Cifras ficticias de demostración; no incluyen gastos fijos ni impuestos.",
    }

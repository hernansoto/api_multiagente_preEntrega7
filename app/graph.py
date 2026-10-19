"""Topología de Pre-entrega 6 extendida con riesgo, HITL y RedisSaver."""
from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from app.hitl import (
    approval_node, make_risk_node, rejection_node, route_approval, route_risk,
)
from orchestrator.agents.analyst_agent import make_analyst_node
from orchestrator.agents.research_agent import make_research_node
from orchestrator.state import NextAgent, OrchestratorState
from orchestrator.supervisor import make_supervisor_node
from orchestrator.synthesis import make_synthesis_node
from orchestrator.validation import validation_node


def route_next(state: OrchestratorState) -> NextAgent:
    return state["next_agent"]


def build_graph(model: BaseChatModel, checkpointer: Any) -> Any:
    """El checkpointer debe existir durante TODA la vida del worker."""
    builder = StateGraph(OrchestratorState)
    builder.add_node("risk_assessment", make_risk_node(model))
    builder.add_node("approval", approval_node)
    builder.add_node("rejected", rejection_node)
    builder.add_node("supervisor", make_supervisor_node(model))
    builder.add_node("researcher", make_research_node(model))
    builder.add_node("analyst", make_analyst_node(model))
    builder.add_node("validator", validation_node)
    builder.add_node("synthesizer", make_synthesis_node(model))

    builder.add_edge(START, "risk_assessment")
    builder.add_conditional_edges("risk_assessment", route_risk, {
        "approval": "approval", "supervisor": "supervisor",
    })
    builder.add_conditional_edges("approval", route_approval, {
        "supervisor": "supervisor", "rejected": "rejected",
    })
    builder.add_edge("rejected", END)
    builder.add_conditional_edges("supervisor", route_next, {
        "researcher": "researcher", "analyst": "analyst", "synthesizer": "synthesizer",
    })
    builder.add_edge("researcher", "validator")
    builder.add_edge("analyst", "validator")
    builder.add_edge("validator", "supervisor")
    builder.add_edge("synthesizer", END)
    return builder.compile(checkpointer=checkpointer)

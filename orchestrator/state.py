"""Contrato de estado compartido del grafo jerárquico LangGraph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import MessagesState


AgentName = Literal["researcher", "analyst", "supervisor", "validator", "synthesizer"]
NextAgent = Literal["researcher", "analyst", "synthesizer"]


class Contribution(TypedDict):
    agent: AgentName
    status: Literal["ok", "error", "warning"]
    detail: str


class OrchestratorState(MessagesState, total=False):
    # MessagesState implementa add_messages, evitando pisar mensajes previos.
    user_request: str
    next_agent: NextAgent
    supervisor_reason: str
    step_count: int
    max_steps: int
    research_attempts: int
    analysis_attempts: int
    research_output: str
    research_sources: list[dict[str, Any]]
    research_tool_used: bool
    research_error: str
    analysis_output: str
    analysis_calculations: list[dict[str, Any]]
    analysis_tool_used: bool
    analysis_error: str
    validation_errors: list[str]
    task_completed: bool
    stop_reason: str
    final_answer: str
    contributions: Annotated[list[Contribution], operator.add]
    route_trace: Annotated[list[str], operator.add]
    requires_approval: bool
    risk_reason: str
    risk_category: str
    human_approved: bool
    human_reviewer: str
    human_comment: str
    synthesis_error: str

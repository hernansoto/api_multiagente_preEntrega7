from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from app.hitl import approval_node, route_approval, rejection_node
from orchestrator.state import OrchestratorState


@pytest.mark.asyncio
async def test_interrupt_waits_then_rejects():
    builder = StateGraph(OrchestratorState)
    builder.add_node("approval", approval_node)
    builder.add_node("rejected", rejection_node)
    builder.add_node("accepted", lambda _: {"final_answer": "Autorizada"})
    builder.add_edge(START, "approval")
    builder.add_conditional_edges("approval", route_approval, {
        "rejected": "rejected", "supervisor": "accepted",
    })
    builder.add_edge("rejected", END)
    builder.add_edge("accepted", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid4())}}
    paused = await graph.ainvoke({
        "user_request": "Consulta crítica", "risk_reason": "Costo alto",
        "risk_category": "high_cost",
    }, config)
    assert "__interrupt__" in paused
    snapshot = await graph.aget_state(config)
    assert snapshot.next == ("approval",)
    result = await graph.ainvoke(Command(resume={"approved": False, "reviewer": "admin"}), config)
    assert result["human_approved"] is False
    assert "rechazada" in result["final_answer"].lower()


@pytest.mark.asyncio
async def test_interrupt_approved():
    builder = StateGraph(OrchestratorState)
    builder.add_node("approval", approval_node)
    builder.add_node("accepted", lambda _: {"final_answer": "Autorizada"})
    builder.add_node("rejected", rejection_node)
    builder.add_edge(START, "approval")
    builder.add_conditional_edges("approval", route_approval, {
        "rejected": "rejected", "supervisor": "accepted",
    })
    builder.add_edge("accepted", END)
    builder.add_edge("rejected", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid4())}}
    await graph.ainvoke({"user_request": "Compra de alto costo"}, config)
    approved = await graph.ainvoke(Command(resume={"approved": True, "reviewer": "docente"}), config)
    assert approved["human_approved"] is True
    assert approved["final_answer"] == "Autorizada"

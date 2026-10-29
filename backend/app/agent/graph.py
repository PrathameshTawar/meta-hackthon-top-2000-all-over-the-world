"""
LangGraph agent graph for Saath.

Flow:
  ingest → perceive → classify → [medical?] → guardrail (end)
                                       ↓
                                    extract → verify → [low confidence?] → interrupt (ask family)
                                                 ↓
                                            deduplicate → assign → draft → END
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.state import AgentState
from app.agent.nodes import (
    node_ingest,
    node_perceive,
    node_classify,
    node_guardrail,
    node_extract,
    node_verify,
    node_deduplicate,
    node_assign,
    node_draft,
)


def route_after_classify(state: AgentState) -> str:
    """After classification, branch to guardrail for medical content."""
    if state.get("category") == "medical":
        return "guardrail"
    return "extract"


def route_after_verify(state: AgentState) -> str:
    """After verification, interrupt if confirmation is needed."""
    if state.get("awaiting_confirmation"):
        return "interrupt"
    return "deduplicate"


def route_after_guardrail(state: AgentState) -> str:
    """Guardrail always ends the graph (we never draft from medical content)."""
    return END


def node_interrupt(state: AgentState) -> dict:
    """
    LangGraph interrupt node.
    The graph pauses here and the confirmation_question is sent to the family.
    When they reply, the graph resumes from this node with their answer.
    In the demo, this is triggered automatically for blurry or low-confidence inputs.
    """
    # In a real deployment, langgraph.interrupt() would pause execution.
    # Here we return the question and mark that we're waiting.
    return {
        "awaiting_confirmation": True,
    }


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("ingest", node_ingest)
    graph.add_node("perceive", node_perceive)
    graph.add_node("classify", node_classify)
    graph.add_node("guardrail", node_guardrail)
    graph.add_node("extract", node_extract)
    graph.add_node("verify", node_verify)
    graph.add_node("interrupt", node_interrupt)
    graph.add_node("deduplicate", node_deduplicate)
    graph.add_node("assign", node_assign)
    graph.add_node("draft", node_draft)

    # Edges
    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "perceive")
    graph.add_edge("perceive", "classify")

    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"guardrail": "guardrail", "extract": "extract"},
    )

    graph.add_edge("guardrail", END)
    graph.add_edge("extract", "verify")

    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {"interrupt": "interrupt", "deduplicate": "deduplicate"},
    )

    # interrupt → graph pauses; on resume it continues to deduplicate
    graph.add_edge("interrupt", "deduplicate")
    graph.add_edge("deduplicate", "assign")
    graph.add_edge("assign", "draft")
    graph.add_edge("draft", END)

    return graph


# Compile once at import time; use MemorySaver for dev (swap for Postgres checkpointer in prod)
checkpointer = MemorySaver()
compiled_graph = build_graph().compile(checkpointer=checkpointer, interrupt_before=["interrupt"])

"""
LangGraph agent graph for Saath.

Flow:
  ingest → perceive → classify → [medical?] → guardrail (end)
                                       ↓
                                    extract → verify → [low confidence?] → interrupt (ask family)
                                                 ↓                                 │
                                            deduplicate ◄── (confirmed: True) ─────┤
                                                 │                                 │
                                              assign                   (confirmed: False) ──► END
                                                 │
                                               draft → END
"""
import os
import logging
from typing import Optional, Any
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.agent.state import AgentState
from app.config import settings
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

logger = logging.getLogger(__name__)


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


async def node_interrupt(state: AgentState) -> dict:
    """
    LangGraph persistent interrupt node.
    Pauses execution via real langgraph.types.interrupt().
    When family taps [✅ Correct] or [❌ Wrong] in Telegram,
    execution resumes from here with Command(resume={'confirmed': True/False}).
    """
    question = state.get(
        "confirmation_question",
        "काही माहिती अस्पष्ट आहे. कृपया पुष्टी करा: ही माहिती बरोबर आहे का?"
    )
    # Real LangGraph interrupt() pauses graph execution and saves state to SQLite checkpointer
    user_response = interrupt(question)

    confirmed = False
    if isinstance(user_response, dict):
        confirmed = bool(user_response.get("confirmed", False))
    elif isinstance(user_response, bool):
        confirmed = user_response
    elif isinstance(user_response, str):
        confirmed = user_response.lower() in ("yes", "होय", "true", "correct")

    logger.info(f"Agent resumed from interrupt with confirmation: {confirmed}")
    return {
        "awaiting_confirmation": False,
        "confirmation_confirmed": confirmed,
        "verify_passed": confirmed,
    }


def route_after_interrupt(state: AgentState) -> str:
    """
    If family confirms the information is correct, continue to deduplicate & assign.
    If family marks it wrong, terminate graph execution gracefully.
    """
    if state.get("confirmation_confirmed"):
        return "deduplicate"
    return END


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

    # After interrupt: resume proceeds conditionally based on human confirmation
    graph.add_conditional_edges(
        "interrupt",
        route_after_interrupt,
        {"deduplicate": "deduplicate", END: END},
    )

    graph.add_edge("deduplicate", "assign")
    graph.add_edge("assign", "draft")
    graph.add_edge("draft", END)

    return graph


# ---------------------------------------------------------------------------
# Persistent SQLite Checkpointer Management
# ---------------------------------------------------------------------------
_checkpointer_cm: Optional[Any] = None
_checkpointer: Optional[AsyncSqliteSaver] = None
_compiled_graph: Optional[Any] = None


async def get_checkpointer() -> AsyncSqliteSaver:
    global _checkpointer_cm, _checkpointer
    if _checkpointer is None:
        db_path = getattr(settings, "checkpoints_db_path", "data/checkpoints.db")
        dir_name = os.path.dirname(os.path.abspath(db_path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        _checkpointer_cm = AsyncSqliteSaver.from_conn_string(db_path)
        _checkpointer = await _checkpointer_cm.__aenter__()
        await _checkpointer.setup()
    return _checkpointer


async def close_checkpointer():
    global _checkpointer_cm, _checkpointer, _compiled_graph
    if _checkpointer_cm is not None:
        try:
            await _checkpointer_cm.__aexit__(None, None, None)
        except Exception:
            pass
        _checkpointer_cm = None
        _checkpointer = None
        _compiled_graph = None


async def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        checkpointer = await get_checkpointer()
        _compiled_graph = build_graph().compile(checkpointer=checkpointer)
    return _compiled_graph


class LazyCompiledGraph:
    """Backward-compatible proxy allowing compiled_graph.astream(...) and ainvoke(...) anywhere."""
    async def astream(self, *args, **kwargs):
        g = await get_compiled_graph()
        async for chunk in g.astream(*args, **kwargs):
            yield chunk

    async def ainvoke(self, *args, **kwargs):
        g = await get_compiled_graph()
        return await g.ainvoke(*args, **kwargs)

    async def aget_state(self, *args, **kwargs):
        g = await get_compiled_graph()
        return await g.aget_state(*args, **kwargs)


compiled_graph = LazyCompiledGraph()

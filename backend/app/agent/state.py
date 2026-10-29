"""
Shared state object that flows through every node in the agent graph.
LangGraph passes this dict from node to node; each node returns a partial
update that gets merged in.
"""
from typing import Optional, Any
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    # --- input ---
    artifact_id: int
    household_id: int
    artifact_type: str          # "voice" | "image"
    file_url: str

    # --- perceive ---
    raw_text: str               # transcript or OCR output
    doc_type: str               # detected document type from vision model

    # --- classify ---
    category: str               # TaskCategory value

    # --- extract ---
    extracted: dict             # {"amount": {"value": "₹1,234", "quote": "..."}, ...}
    confidence: float           # 0.0 – 1.0

    # --- verify ---
    verify_passed: bool
    verify_failures: list[str]

    # --- interrupt ---
    awaiting_confirmation: bool
    confirmation_question: str

    # --- deduplicate ---
    existing_task_id: Optional[int]  # set if this is a duplicate

    # --- assign ---
    assignee_id: Optional[int]

    # --- draft ---
    parent_reply: str           # Marathi message back to parent
    sibling_notification: str
    call_script: Optional[str]

    # --- meta ---
    errors: list[str]
    skip_to: Optional[str]      # force routing to a specific node (e.g. "guardrail")

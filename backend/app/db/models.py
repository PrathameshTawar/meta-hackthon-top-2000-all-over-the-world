"""
SQLAlchemy ORM models.
Keep in sync with the schema in db/migrations/.
"""
import enum
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String, Text, Numeric, DateTime, ForeignKey,
    Enum as SAEnum, JSON, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MemberRole(str, enum.Enum):
    parent = "parent"
    child = "child"
    helper = "helper"


class ArtifactType(str, enum.Enum):
    voice = "voice"
    image = "image"


class TaskCategory(str, enum.Enum):
    bill = "bill"
    loan_emi = "loan_emi"
    pension = "pension"
    govt_letter = "govt_letter"
    insurance = "insurance"
    appointment = "appointment"
    medical = "medical"
    chit_chat = "chit_chat"
    unknown = "unknown"


class TaskStatus(str, enum.Enum):
    new = "new"
    confirmed = "confirmed"       # passed verification
    needs_review = "needs_review" # low confidence, waiting for human
    claimed = "claimed"
    done = "done"
    escalated = "escalated"


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    primary_language: Mapped[str] = mapped_column(String(10), default="mr")

    members: Mapped[List["Member"]] = relationship(back_populates="household")
    artifacts: Mapped[List["Artifact"]] = relationship(back_populates="household")
    tasks: Mapped[List["Task"]] = relationship(back_populates="household")


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[MemberRole] = mapped_column(SAEnum(MemberRole))
    telegram_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    last_inbound_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # JSON list of TaskCategory strings this member "owns"
    categories_owned: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    household: Mapped["Household"] = relationship(back_populates="members")
    assigned_tasks: Mapped[List["Task"]] = relationship(back_populates="assignee")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    type: Mapped[ArtifactType] = mapped_column(SAEnum(ArtifactType))
    file_url: Mapped[str] = mapped_column(Text)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    household: Mapped["Household"] = relationship(back_populates="artifacts")
    evidence_items: Mapped[List["Evidence"]] = relationship(back_populates="artifact")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    category: Mapped[TaskCategory] = mapped_column(SAEnum(TaskCategory), default=TaskCategory.unknown)
    title: Mapped[str] = mapped_column(String(300))
    amount: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)   # keep as string to preserve "₹1,234"
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    payee: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.new)
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("members.id"), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    # SHA-256 of (payee.lower + amount_normalised + due_date_month) for dedup
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    recurrence: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g. "monthly"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    household: Mapped["Household"] = relationship(back_populates="tasks")
    assignee: Mapped[Optional["Member"]] = relationship(back_populates="assigned_tasks")
    evidence_items: Mapped[List["Evidence"]] = relationship(back_populates="task")
    events: Mapped[List["Event"]] = relationship(back_populates="task")


class Evidence(Base):
    """Links a field in a Task back to the exact text span in the source Artifact."""
    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint("task_id", "artifact_id", "field_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    artifact_id: Mapped[int] = mapped_column(ForeignKey("artifacts.id"))
    # The exact substring from raw_text that supports this field
    quoted_span: Mapped[str] = mapped_column(Text)
    # Which task field this evidence supports: "amount", "due_date", "payee", etc.
    field_name: Mapped[str] = mapped_column(String(50))

    task: Mapped["Task"] = relationship(back_populates="evidence_items")
    artifact: Mapped["Artifact"] = relationship(back_populates="evidence_items")


class Event(Base):
    """Append-only audit log — every agent decision is recorded here."""
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[Optional[int]] = mapped_column(ForeignKey("households.id"), nullable=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    actor: Mapped[str] = mapped_column(String(80))   # e.g. "agent:verify", "user:123"
    action: Mapped[str] = mapped_column(String(80))  # e.g. "extracted", "assigned", "escalated"
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped[Optional["Task"]] = relationship(back_populates="events")


class ProcessedMessage(Base):
    """Tracks processed message IDs across restarts to prevent duplicate processing."""
    __tablename__ = "processed_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    channel: Mapped[str] = mapped_column(String(32), default="whatsapp")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


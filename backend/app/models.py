import uuid
from datetime import UTC, date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(UTC)


def _pk() -> Mapped[uuid.UUID]:
    # UUID keys so ids in URLs can't be guessed or enumerated
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


TS = DateTime(timezone=True)


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # caseworker | team_lead | manager | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_assigned_at: Mapped[datetime | None] = mapped_column(TS)  # allocation tie-break


class Intake(Base):
    __tablename__ = "intake"

    id: Mapped[uuid.UUID] = _pk()
    reference_code: Mapped[str] = mapped_column(String(16), unique=True)

    # client details (form answers)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    email: Mapped[str | None] = mapped_column(String(254), index=True)
    phone: Mapped[str | None] = mapped_column(String(20), index=True)
    safe_contact_method: Mapped[str] = mapped_column(String(10))  # email | phone | none
    safe_to_leave_message: Mapped[bool] = mapped_column(Boolean, default=False)
    safe_contact_notes: Mapped[str] = mapped_column(String(500), default="")
    needs: Mapped[list[str]] = mapped_column(JSON, default=list)
    immediate_safety_concern: Mapped[bool] = mapped_column(Boolean, default=False)
    housing_unstable: Mapped[bool] = mapped_column(Boolean, default=False)
    has_dependants: Mapped[bool] = mapped_column(Boolean, default=False)
    urgency_self_rating: Mapped[int] = mapped_column(Integer, default=3)
    free_text: Mapped[str] = mapped_column(Text, default="")
    consent_at: Mapped[datetime] = mapped_column(TS)

    # triage result
    priority: Mapped[str] = mapped_column(String(10), index=True)  # urgent | high | standard | low
    service_stream: Mapped[str] = mapped_column(String(30))
    triage_score: Mapped[int] = mapped_column(Integer)
    triage_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    triage_original_priority: Mapped[str | None] = mapped_column(String(10))  # set on override
    triage_overridden_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"))
    triage_override_reason: Mapped[str | None] = mapped_column(String(500))

    # journey
    stage: Mapped[str] = mapped_column(String(20), index=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"), index=True)
    possible_duplicate_of: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("intake.id"))
    submitted_at: Mapped[datetime] = mapped_column(TS, default=now)
    closed_at: Mapped[datetime | None] = mapped_column(TS)

    assignee: Mapped[User | None] = relationship(foreign_keys=[assigned_to])
    tasks: Mapped[list["Task"]] = relationship(back_populates="intake", order_by="Task.created_at")
    notes: Mapped[list["Note"]] = relationship(order_by="Note.created_at")

    @property
    def assignee_name(self) -> str | None:
        return self.assignee.name if self.assignee else None


class Task(Base):
    __tablename__ = "task"

    id: Mapped[uuid.UUID] = _pk()
    intake_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("intake.id"), index=True)
    template_key: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    stage: Mapped[str] = mapped_column(String(20))
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"), index=True)
    due_at: Mapped[datetime] = mapped_column(TS)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open | done | skipped
    completed_at: Mapped[datetime | None] = mapped_column(TS)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"))
    skip_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(TS, default=now)

    intake: Mapped[Intake] = relationship(back_populates="tasks")


class Note(Base):
    __tablename__ = "note"

    id: Mapped[uuid.UUID] = _pk()
    intake_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("intake.id"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=now)

    author: Mapped[User] = relationship()

    @property
    def author_name(self) -> str:
        return self.author.name


class Notification(Base):
    """Every notification, sent or not. Doubles as the delivery log."""

    __tablename__ = "notification"

    id: Mapped[uuid.UUID] = _pk()
    intake_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("intake.id"))
    channel: Mapped[str] = mapped_column(String(10))  # email | in_app
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"), index=True)  # in_app
    recipient: Mapped[str] = mapped_column(String(254))  # email address or user name
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending | sent | failed
    created_at: Mapped[datetime] = mapped_column(TS, default=now)
    sent_at: Mapped[datetime | None] = mapped_column(TS)
    read_at: Mapped[datetime | None] = mapped_column(TS)


class AuditLog(Base):
    """Append-only: a database trigger rejects UPDATE and DELETE (see the first migration)."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _pk()
    at: Mapped[datetime] = mapped_column(TS, default=now, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"))  # null = public/system
    action: Mapped[str] = mapped_column(String(40), index=True)
    entity: Mapped[str] = mapped_column(String(20))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(45))

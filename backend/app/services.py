"""Business rules. Every function that changes data writes its audit entry and commits."""

import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from . import journey, notify
from .models import AuditLog, Intake, Note, Task, User, now
from .schemas import IntakeIn
from .triage import triage

_REF_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L: codes get read out and retyped


def audit(db: Session, action: str, entity: str, entity_id: uuid.UUID | None,
          actor: User | None = None, ip: str | None = None, **detail) -> None:
    """Never put personal information in `detail`: the audit log outlives the record."""
    db.add(AuditLog(action=action, entity=entity, entity_id=entity_id,
                    actor_id=actor.id if actor else None, ip=ip, detail=detail))


def stalled_clause():
    """True for an intake with an open task past its due date."""
    return exists().where(Task.intake_id == Intake.id, Task.status == "open", Task.due_at < func.now())


def get_case_for(db: Session, user: User, intake_id: uuid.UUID) -> Intake:
    """Fetch a case the user may work on. Caseworkers only see their own; anything
    else is a 404, so the response doesn't confirm the case exists."""
    intake = db.get(Intake, intake_id)
    if intake is None or (user.role == "caseworker" and intake.assigned_to != user.id):
        raise HTTPException(404, "Case not found")
    return intake


# ---- intake ----


def _allocate(db: Session) -> User | None:
    """The active caseworker with the fewest open tasks; ties go to whoever was assigned longest ago."""
    # ponytail: no locking, so two simultaneous submissions can pick the same person.
    # Harmless at this volume; lock the user rows if allocation fairness ever matters.
    open_tasks = (
        select(Task.assigned_to, func.count().label("n"))
        .where(Task.status == "open")
        .group_by(Task.assigned_to)
        .subquery()
    )
    user = db.scalars(
        select(User)
        .outerjoin(open_tasks, open_tasks.c.assigned_to == User.id)
        .where(User.role == "caseworker", User.is_active)
        .order_by(func.coalesce(open_tasks.c.n, 0), User.last_assigned_at.asc().nulls_first())
        .limit(1)
    ).first()
    if user:
        user.last_assigned_at = now()
    return user


def _enter_stage(db: Session, intake: Intake, stage: str, actor: User | None = None) -> None:
    previous, intake.stage = intake.stage, stage
    audit(db, "stage.changed", "intake", intake.id, actor, **{"from": previous, "to": stage})
    if stage == "closed":
        intake.closed_at = now()
    for key, title in journey.templates_for(stage, intake.service_stream):
        db.add(Task(intake_id=intake.id, template_key=key, title=title, stage=stage,
                    assigned_to=intake.assigned_to, due_at=journey.due_date(now(), intake.priority)))
    if journey.PUBLIC_STATUS[stage] != journey.PUBLIC_STATUS.get(previous):
        notify.email_client(
            db, intake, f"Update on your request {intake.reference_code}",
            f"The status of your request {intake.reference_code} is now: {journey.PUBLIC_STATUS[stage]}.",
        )


def submit_intake(db: Session, data: IntakeIn, ip: str | None = None) -> Intake:
    result = triage(data)

    same_person = [c for c in (Intake.email == data.email if data.email else None,
                               Intake.phone == data.phone if data.phone else None) if c is not None]
    duplicate_id = (
        db.scalar(select(Intake.id).where(or_(*same_person)).order_by(Intake.submitted_at.desc()).limit(1))
        if same_person else None
    )

    assignee = _allocate(db)
    intake = Intake(
        **data.model_dump(exclude={"consent", "website"}),
        reference_code="VELA-" + "".join(secrets.choice(_REF_ALPHABET) for _ in range(8)),
        consent_at=now(),
        priority=result.priority,
        service_stream=result.service_stream,
        triage_score=result.score,
        triage_reasons=result.reasons,
        stage="submitted",
        assigned_to=assignee.id if assignee else None,
        possible_duplicate_of=duplicate_id,
    )
    db.add(intake)
    db.flush()
    audit(db, "intake.submitted", "intake", intake.id, ip=ip, priority=result.priority,
          score=result.score, assigned_to=str(assignee.id) if assignee else None)

    notify.email_client(
        db, intake, f"We have received your request {intake.reference_code}",
        f"Thank you. Your reference is {intake.reference_code}. A member of our team will be in touch.",
    )
    _enter_stage(db, intake, "triaged")

    if assignee:
        notify.notify_staff(db, assignee, intake, f"New case assigned: {intake.reference_code}",
                            f"A new {result.priority} priority case has been assigned to you.")
    if result.priority == "urgent" or not assignee:
        subject = (f"Urgent intake: {intake.reference_code}" if assignee
                   else f"Unassigned intake: {intake.reference_code}")
        for lead in db.scalars(select(User).where(User.role == "team_lead", User.is_active)):
            notify.notify_staff(db, lead, intake, subject,
                                "An intake needs your attention. Open the case for details.")
    db.commit()
    return intake


# ---- tasks and stages ----


def _advance_if_stage_complete(db: Session, intake: Intake, actor: User) -> None:
    """The core rule: a stage is only left once none of its mandatory steps is open."""
    still_open = db.scalar(
        select(func.count()).select_from(Task).where(
            Task.intake_id == intake.id, Task.stage == intake.stage,
            Task.mandatory, Task.status == "open")
    )
    if not still_open and intake.stage != "closed":
        _enter_stage(db, intake, journey.next_stage(intake.stage), actor)


def _close_task(db: Session, task: Task, user: User, status: str, action: str,
                ip: str | None, reason: str | None = None) -> Task:
    if task.status != "open":
        raise HTTPException(409, "Task is already closed")
    task.status, task.completed_at, task.completed_by, task.skip_reason = status, now(), user.id, reason
    detail = {"reason": reason} if reason else {}
    audit(db, action, "task", task.id, user, ip, intake_id=str(task.intake_id), title=task.title, **detail)
    db.flush()
    _advance_if_stage_complete(db, task.intake, user)
    db.commit()
    return task


def complete_task(db: Session, task: Task, user: User, ip: str | None = None) -> Task:
    return _close_task(db, task, user, "done", "task.completed", ip)


def skip_task(db: Session, task: Task, user: User, reason: str, ip: str | None = None) -> Task:
    """Team lead only (enforced by the router). The reason is kept and audited."""
    return _close_task(db, task, user, "skipped", "task.skipped", ip, reason)


# ---- team lead actions ----


def override_triage(db: Session, intake: Intake, user: User, priority: str, reason: str,
                    ip: str | None = None) -> None:
    previous = intake.priority
    if intake.triage_original_priority is None:
        intake.triage_original_priority = previous  # keep what the rules decided
    intake.priority = priority
    intake.triage_overridden_by, intake.triage_override_reason = user.id, reason
    for task in intake.tasks:
        if task.status == "open":
            task.due_at = journey.due_date(task.created_at, priority)
    audit(db, "triage.overridden", "intake", intake.id, user, ip,
          **{"from": previous, "to": priority, "reason": reason})
    db.commit()


def reassign(db: Session, intake: Intake, assignee: User, actor: User, ip: str | None = None) -> None:
    if assignee.role not in ("caseworker", "team_lead") or not assignee.is_active:
        raise HTTPException(422, "Cases can only be assigned to an active caseworker or team lead")
    previous, intake.assigned_to = intake.assigned_to, assignee.id
    for task in intake.tasks:
        if task.status == "open":
            task.assigned_to = assignee.id
    audit(db, "case.reassigned", "intake", intake.id, actor, ip,
          **{"from": str(previous) if previous else None, "to": str(assignee.id)})
    notify.notify_staff(db, assignee, intake, f"Case assigned to you: {intake.reference_code}",
                        f"A {intake.priority} priority case has been assigned to you.")
    db.commit()


def add_note(db: Session, intake: Intake, user: User, body: str, ip: str | None = None) -> Note:
    note = Note(intake_id=intake.id, author_id=user.id, body=body)
    db.add(note)
    db.flush()
    audit(db, "note.added", "intake", intake.id, user, ip, note_id=str(note.id))
    db.commit()
    return note

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from .. import notify, services
from ..db import get_db
from ..models import AuditLog, Intake, User
from ..schemas import (
    AssigneeIn,
    CaseDetail,
    CaseSummary,
    NoteIn,
    NoteOut,
    Priority,
    TimelineEntry,
    TriageOverrideIn,
    UserOut,
)
from ..security import client_ip, require_role

router = APIRouter(prefix="/cases", tags=["cases"])

case_staff = require_role("caseworker", "team_lead")
team_lead = require_role("team_lead")


@router.get("", response_model=list[CaseSummary])
def list_cases(
    stage: str | None = None,
    priority: Priority | None = None,
    assignee: uuid.UUID | None = None,
    stalled: bool | None = None,
    user: User = Depends(require_role("caseworker", "team_lead", "manager")),
    db: Session = Depends(get_db),
):
    stalled_col = services.stalled_clause().label("stalled")
    # ponytail: no pagination, capped at 500 rows. Add paging when Vela has more open cases than that.
    query = (select(Intake, stalled_col).options(joinedload(Intake.assignee))
             .order_by(Intake.submitted_at.desc()).limit(500))
    if user.role == "caseworker":
        query = query.where(Intake.assigned_to == user.id)
    if stage:
        query = query.where(Intake.stage == stage)
    if priority:
        query = query.where(Intake.priority == priority)
    if assignee:
        query = query.where(Intake.assigned_to == assignee)
    if stalled is not None:
        query = query.where(services.stalled_clause() if stalled else ~services.stalled_clause())

    identified = user.role != "manager"  # managers get the de-identified view
    return [
        CaseSummary(
            id=i.id,
            reference_code=i.reference_code,
            client_name=f"{i.first_name} {i.last_name}" if identified else None,
            priority=i.priority,
            service_stream=i.service_stream,
            stage=i.stage,
            assigned_to=i.assigned_to,
            assignee_name=i.assignee_name,
            submitted_at=i.submitted_at,
            stalled=is_stalled,
            possible_duplicate=i.possible_duplicate_of is not None,
        )
        for i, is_stalled in db.execute(query)
    ]


@router.get("/assignees", response_model=list[UserOut])
def assignees(user: User = Depends(team_lead), db: Session = Depends(get_db)):
    """Who a case can be reassigned to."""
    return db.scalars(
        select(User).where(User.role.in_(("caseworker", "team_lead")), User.is_active).order_by(User.name)
    ).all()


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: uuid.UUID, request: Request, user: User = Depends(case_staff),
             db: Session = Depends(get_db)):
    intake = services.get_case_for(db, user, case_id)
    services.audit(db, "case.viewed", "intake", intake.id, user, client_ip(request))
    db.commit()

    detail = CaseDetail.model_validate(intake)  # tasks and notes come along via the relationships
    if intake.possible_duplicate_of:
        detail.duplicate_reference = db.scalar(
            select(Intake.reference_code).where(Intake.id == intake.possible_duplicate_of))
    events = db.execute(
        select(AuditLog, User.name)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .where(or_(AuditLog.entity_id == intake.id, AuditLog.entity_id.in_([t.id for t in intake.tasks])),
               AuditLog.action != "case.viewed")
        .order_by(AuditLog.at)
    )
    detail.timeline = [TimelineEntry(at=e.at, actor_name=name, action=e.action, detail=e.detail)
                       for e, name in events]
    return detail


@router.patch("/{case_id}/triage", status_code=204)
def override_triage(case_id: uuid.UUID, data: TriageOverrideIn, request: Request,
                    user: User = Depends(team_lead), db: Session = Depends(get_db)):
    intake = services.get_case_for(db, user, case_id)
    services.override_triage(db, intake, user, data.priority, data.reason, client_ip(request))


@router.patch("/{case_id}/assignee", status_code=204)
def reassign(case_id: uuid.UUID, data: AssigneeIn, request: Request, background: BackgroundTasks,
             user: User = Depends(team_lead), db: Session = Depends(get_db)):
    intake = services.get_case_for(db, user, case_id)
    assignee = db.get(User, data.user_id)
    if assignee is None:
        raise HTTPException(422, "Unknown user")
    services.reassign(db, intake, assignee, user, client_ip(request))
    background.add_task(notify.deliver_pending)


@router.post("/{case_id}/notes", response_model=NoteOut, status_code=201)
def add_note(case_id: uuid.UUID, data: NoteIn, request: Request, user: User = Depends(case_staff),
             db: Session = Depends(get_db)):
    intake = services.get_case_for(db, user, case_id)
    return services.add_note(db, intake, user, data.body, client_ip(request))

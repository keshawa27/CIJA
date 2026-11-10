from fastapi import APIRouter, Depends
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from .. import journey, services
from ..db import get_db
from ..models import Intake, Task, User
from ..schemas import DashboardSummary
from ..security import require_role

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(user: User = Depends(require_role("caseworker", "team_lead", "manager")),
            db: Session = Depends(get_db)):
    """Counts only, so it is safe for every staff role. Caseworkers see their own cases."""
    scope = [Intake.assigned_to == user.id] if user.role == "caseworker" else []
    is_open = Intake.stage != "closed"

    def count(*where) -> int:
        return db.scalar(select(func.count()).select_from(Intake).where(*scope, *where))

    def grouped(column, *where) -> dict[str, int]:
        return dict(db.execute(select(column, func.count()).where(*scope, *where).group_by(column)).all())

    by_stage = grouped(Intake.stage)
    by_priority = grouped(Intake.priority, is_open)
    closed = by_stage.get("closed", 0)

    cycle_seconds = db.scalar(
        select(func.avg(func.extract("epoch", Intake.closed_at - Intake.submitted_at)))
        .where(*scope, Intake.stage == "closed"))
    skipped_a_step = exists().where(Task.intake_id == Intake.id, Task.mandatory, Task.status == "skipped")

    return DashboardSummary(
        open_cases=count(is_open),
        urgent_open=by_priority.get("urgent", 0),
        stalled=count(is_open, services.stalled_clause()),
        closed=closed,
        by_stage={stage: by_stage.get(stage, 0) for stage in journey.STAGES[1:]},
        by_priority={p: by_priority.get(p, 0) for p in journey.RESPONSE_DAYS},
        avg_cycle_days=round(float(cycle_seconds) / 86400, 1) if cycle_seconds is not None else None,
        step_completion_rate=(round(count(Intake.stage == "closed", ~skipped_a_step) / closed, 3)
                              if closed else None),
    )

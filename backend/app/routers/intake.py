from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import journey, notify, services
from ..db import get_db
from ..models import Intake
from ..schemas import IntakeIn
from ..security import client_ip, limiter

router = APIRouter(prefix="/intake", tags=["intake"])


@router.post("", status_code=201)
@limiter.limit("5/minute")
def submit(request: Request, data: IntakeIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    if data.website:  # honeypot filled in: answer like a success, store nothing
        return {"reference_code": "VELA-RECEIVED"}
    intake = services.submit_intake(db, data, client_ip(request))
    background.add_task(notify.deliver_pending)
    return {"reference_code": intake.reference_code}


@router.get("/status/{reference_code}")
@limiter.limit("10/minute")
def status(request: Request, reference_code: str, db: Session = Depends(get_db)):
    """Public lookup. Returns a vague status label and nothing else about the client."""
    stage = db.scalar(select(Intake.stage).where(Intake.reference_code == reference_code.strip().upper()))
    if stage is None:
        raise HTTPException(404, "Reference not found")
    return {"status": journey.PUBLIC_STATUS[stage]}

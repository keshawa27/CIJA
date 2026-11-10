import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import notify, services
from ..db import get_db
from ..models import Intake, Notification, Task, User, now
from ..schemas import MyTaskOut, NotificationOut, SkipIn, TaskOut
from ..security import client_ip, current_user, require_role

router = APIRouter(tags=["tasks"])

case_staff = require_role("caseworker", "team_lead")


def _task_for(db: Session, user: User, task_id: uuid.UUID) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    services.get_case_for(db, user, task.intake_id)  # 404 unless the user may work on the case
    return task


@router.get("/tasks", response_model=list[MyTaskOut])
def my_tasks(user: User = Depends(case_staff), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Task, Intake)
        .join(Intake, Intake.id == Task.intake_id)
        .where(Task.assigned_to == user.id, Task.status == "open")
        .order_by(Task.due_at)
    )
    return [
        MyTaskOut(
            **TaskOut.model_validate(task).model_dump(),
            reference_code=intake.reference_code,
            client_name=f"{intake.first_name} {intake.last_name}",
            priority=intake.priority,
            overdue=task.due_at < now(),
        )
        for task, intake in rows
    ]


@router.post("/tasks/{task_id}/complete", response_model=TaskOut)
def complete(task_id: uuid.UUID, request: Request, background: BackgroundTasks,
             user: User = Depends(case_staff), db: Session = Depends(get_db)):
    task = services.complete_task(db, _task_for(db, user, task_id), user, client_ip(request))
    background.add_task(notify.deliver_pending)
    return task


@router.post("/tasks/{task_id}/skip", response_model=TaskOut)
def skip(task_id: uuid.UUID, data: SkipIn, request: Request, background: BackgroundTasks,
         user: User = Depends(require_role("team_lead")), db: Session = Depends(get_db)):
    task = services.skip_task(db, _task_for(db, user, task_id), user, data.reason, client_ip(request))
    background.add_task(notify.deliver_pending)
    return task


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id, Notification.channel == "in_app")
        .order_by(Notification.created_at.desc())
        .limit(30)
    ).all()


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_read(notification_id: uuid.UUID, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    notification.read_at = notification.read_at or now()
    db.commit()

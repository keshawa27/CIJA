import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, User
from ..schemas import AuditOut, UserCreateIn, UserOut, UserUpdateIn
from ..security import client_ip, hash_password, require_role
from ..services import audit

router = APIRouter(prefix="/admin", tags=["admin"])

admin = require_role("admin")


@router.get("/users", response_model=list[UserOut])
def list_users(user: User = Depends(admin), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.name)).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreateIn, request: Request, user: User = Depends(admin),
                db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(func.lower(User.email) == data.email.lower())):
        raise HTTPException(409, "A user with that email already exists")
    new = User(email=data.email.lower(), name=data.name, role=data.role,
               password_hash=hash_password(data.password))
    db.add(new)
    try:
        db.flush()
    except IntegrityError:  # lost a race with an identical request
        raise HTTPException(409, "A user with that email already exists") from None
    audit(db, "user.created", "user", new.id, user, client_ip(request), role=new.role)
    db.commit()
    return new


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, data: UserUpdateIn, request: Request, user: User = Depends(admin),
                db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    changes = data.model_dump(exclude_unset=True)
    if target.id == user.id and (changes.get("is_active") is False or changes.get("role", "admin") != "admin"):
        # otherwise the last admin could lock everyone out of user management
        raise HTTPException(422, "You cannot deactivate yourself or change your own role")
    if password := changes.pop("password", None):
        target.password_hash = hash_password(password)
    for field, value in changes.items():
        setattr(target, field, value)
    audit(db, "user.updated", "user", target.id, user, client_ip(request),
          changed=sorted(data.model_fields_set))  # field names only, never the new password
    db.commit()
    return target


@router.get("/audit", response_model=list[AuditOut])
def audit_log(
    action: str | None = None,
    entity_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_role("admin", "team_lead")),
    db: Session = Depends(get_db),
):
    query = (select(AuditLog, User.name).outerjoin(User, User.id == AuditLog.actor_id)
             .order_by(AuditLog.at.desc()).limit(limit).offset(offset))
    if action:
        query = query.where(AuditLog.action == action)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    return [
        AuditOut(id=e.id, at=e.at, actor_name=name, action=e.action, entity=e.entity,
                 entity_id=e.entity_id, detail=e.detail, ip=e.ip)
        for e, name in db.execute(query)
    ]

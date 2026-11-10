from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..schemas import LoginIn, UserOut
from ..security import COOKIE, client_ip, current_user, limiter, set_session_cookie, verify_password
from ..services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
@limiter.limit("10/minute")
def login(request: Request, response: Response, data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    ok = verify_password(data.password, user.password_hash if user else None) and user.is_active
    audit(db, "login.success" if ok else "login.failed", "user", user.id if user else None,
          user if ok else None, client_ip(request))
    db.commit()
    if not ok:
        # one message for unknown email, wrong password and disabled account
        raise HTTPException(401, "Incorrect email or password")
    set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=204)
def logout(response: Response, user: User = Depends(current_user)):
    response.delete_cookie(COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

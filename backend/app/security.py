import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from slowapi import Limiter
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

COOKIE = "session"
ROLES = ("caseworker", "team_lead", "manager", "admin")

_hasher = PasswordHash.recommended()  # argon2id
# Verified against when the email is unknown, so login takes the same time either way.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def client_ip(request: Request) -> str:
    # ponytail: trusts X-Forwarded-For because the API is only reachable through the
    # Next.js proxy on localhost. Behind a real load balancer, use its trusted-proxy setting.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# key_style="endpoint": count per route, not per URL, or every reference code in
# /intake/status/{code} would get its own allowance and guessing codes is never limited.
# moving window: a fixed window lets a burst straddling the boundary through at twice the limit.
limiter = Limiter(key_func=client_ip, key_style="endpoint", strategy="moving-window")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    return _hasher.verify(password, password_hash or _DUMMY_HASH) and password_hash is not None


def set_session_cookie(response: Response, user: User) -> None:
    expires = datetime.now(UTC) + timedelta(minutes=settings.session_minutes)
    token = jwt.encode({"sub": str(user.id), "exp": expires}, settings.secret_key, algorithm="HS256")
    response.set_cookie(
        COOKIE,
        token,
        max_age=settings.session_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    unauthenticated = HTTPException(401, "Not authenticated")
    token = request.cookies.get(COOKIE)
    if not token:
        raise unauthenticated
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthenticated from None
    # Looked up on every request, so deactivating a user ends their session immediately.
    if user is None or not user.is_active:
        raise unauthenticated
    return user


def require_role(*roles: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Not permitted")
        return user

    return dependency

"""Tests run against a real Postgres database (`cija_test`), each inside a transaction
that is rolled back, so they are isolated and leave nothing behind."""

import os

DEV_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://cija:cija_dev_only@127.0.0.1:5433/cija")
os.environ.update(
    DATABASE_URL=DEV_URL.rsplit("/", 1)[0] + "/cija_test",
    SECRET_KEY="test-secret-key-that-is-long-enough-for-hs256",
    COOKIE_SECURE="false",  # the test client talks plain http
    ENV="dev",
)

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from alembic import command  # noqa: E402
from app import notify  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Intake, User, now  # noqa: E402
from app.schemas import IntakeIn  # noqa: E402
from app.security import hash_password, limiter  # noqa: E402
from app.services import submit_intake  # noqa: E402

PASSWORD = "correct-horse-battery"
_PASSWORD_HASH = hash_password(PASSWORD)  # hashed once: argon2 is slow on purpose


@pytest.fixture(scope="session", autouse=True)
def _database():
    with create_engine(DEV_URL, isolation_level="AUTOCOMMIT").connect() as connection:
        connection.execute(text("DROP DATABASE IF EXISTS cija_test WITH (FORCE)"))
        connection.execute(text("CREATE DATABASE cija_test"))
    command.upgrade(Config("alembic.ini"), "head")  # the real migrations, trigger included
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def db(_database, monkeypatch):
    connection = engine.connect()
    transaction = connection.begin()
    # Every session the app opens joins this one transaction via savepoints.
    SessionLocal.configure(bind=connection, join_transaction_mode="create_savepoint")
    limiter.enabled = False
    with SessionLocal() as session:
        yield session
    transaction.rollback()
    connection.close()
    SessionLocal.configure(bind=engine)


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    """Emails the app tried to send, as (to, subject, body)."""
    sent = []
    monkeypatch.setattr(notify, "_send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


def make_user(db, role, name=None, **fields) -> User:
    name = name or role
    user = User(email=f"{name}@example.com", name=name, role=role, password_hash=_PASSWORD_HASH, **fields)
    db.add(user)
    db.commit()
    return user


def login(user: User) -> TestClient:
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client


def intake_payload(**overrides) -> dict:
    return {
        "first_name": "Alex",
        "last_name": "Sample",
        "email": "alex.sample@example.com",
        "safe_contact_method": "email",
        "needs": ["counselling"],
        "urgency_self_rating": 1,
        "consent": True,
    } | overrides


def make_intake(db, **overrides) -> Intake:
    return submit_intake(db, IntakeIn(**intake_payload(**overrides)))


@pytest.fixture
def anon() -> TestClient:
    return TestClient(app)


@pytest.fixture
def staff(db) -> dict[str, User]:
    """One user per role, plus a second caseworker. `caseworker` gets the first case:
    both have no open tasks, and the tie goes to whoever was assigned longest ago."""
    return {
        "caseworker": make_user(db, "caseworker"),
        "other_caseworker": make_user(db, "caseworker", "other_caseworker", last_assigned_at=now()),
        "team_lead": make_user(db, "team_lead"),
        "manager": make_user(db, "manager"),
        "admin": make_user(db, "admin"),
    }

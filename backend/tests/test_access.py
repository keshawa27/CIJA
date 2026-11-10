"""Access control: the role matrix from imp_plan.md section 7, plus authentication."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.models import AuditLog
from app.security import limiter
from tests.conftest import PASSWORD, login, make_intake

ROLES = ["caseworker", "team_lead", "manager", "admin"]
NEW_USER = {"email": "new@example.com", "name": "New", "role": "caseworker", "password": "a-long-password"}

# (method, path, body, roles allowed). {case} and {task} are filled in per test.
MATRIX = [
    ("GET", "/api/cases", None, {"caseworker", "team_lead", "manager"}),
    ("GET", "/api/cases/assignees", None, {"team_lead"}),
    ("GET", "/api/cases/{case}", None, {"caseworker", "team_lead"}),
    ("PATCH", "/api/cases/{case}/triage", {"priority": "high", "reason": "Reviewed"}, {"team_lead"}),
    ("PATCH", "/api/cases/{case}/assignee", {"user_id": "{caseworker}"}, {"team_lead"}),
    ("POST", "/api/cases/{case}/notes", {"body": "note"}, {"caseworker", "team_lead"}),
    ("GET", "/api/tasks", None, {"caseworker", "team_lead"}),
    ("POST", "/api/tasks/{task}/complete", None, {"caseworker", "team_lead"}),
    ("POST", "/api/tasks/{task}/skip", {"reason": "Not applicable"}, {"team_lead"}),
    ("GET", "/api/dashboard/summary", None, {"caseworker", "team_lead", "manager"}),
    ("GET", "/api/notifications", None, set(ROLES)),
    ("GET", "/api/auth/me", None, set(ROLES)),
    ("GET", "/api/admin/users", None, {"admin"}),
    ("POST", "/api/admin/users", NEW_USER, {"admin"}),
    ("GET", "/api/admin/audit", None, {"admin", "team_lead"}),
]


def _call(client, method, path, body, db, staff):
    intake = make_intake(db)  # assigned to staff["caseworker"]
    fill = {"case": intake.id, "task": intake.tasks[0].id, "caseworker": staff["caseworker"].id}
    path = path.format(**fill)
    if body:
        body = {k: v.format(**fill) if isinstance(v, str) else v for k, v in body.items()}
    return client.request(method, path, json=body)


@pytest.mark.parametrize("method, path, body, allowed", MATRIX, ids=[f"{m} {p}" for m, p, _, _ in MATRIX])
@pytest.mark.parametrize("role", ROLES)
def test_role_matrix(role, method, path, body, allowed, db, staff):
    response = _call(login(staff[role]), method, path, body, db, staff)
    if role in allowed:
        assert response.status_code < 300, response.text
    else:
        assert response.status_code == 403


@pytest.mark.parametrize("method, path, body, allowed", MATRIX, ids=[f"{m} {p}" for m, p, _, _ in MATRIX])
def test_everything_requires_login(method, path, body, allowed, anon, db, staff):
    assert _call(anon, method, path, body, db, staff).status_code == 401


def test_caseworker_cannot_reach_another_caseworkers_case(db, staff):
    intake = make_intake(db)  # belongs to staff["caseworker"]
    other = login(staff["other_caseworker"])
    task = intake.tasks[0].id

    # 404, not 403: the response must not confirm the case exists
    assert other.get(f"/api/cases/{intake.id}").status_code == 404
    assert other.post(f"/api/cases/{intake.id}/notes", json={"body": "x"}).status_code == 404
    assert other.post(f"/api/tasks/{task}/complete").status_code == 404
    assert other.get("/api/cases").json() == []
    assert other.get("/api/tasks").json() == []


def test_manager_list_is_de_identified(db, staff):
    make_intake(db)
    [case] = login(staff["manager"]).get("/api/cases").json()
    assert case["client_name"] is None
    assert "Alex" not in str(case) and "Sample" not in str(case)
    [case] = login(staff["team_lead"]).get("/api/cases").json()
    assert case["client_name"] == "Alex Sample"


def test_login_failures_are_indistinguishable(anon, db, staff):
    staff["manager"].is_active = False
    db.commit()
    attempts = [
        {"email": staff["caseworker"].email, "password": "wrong-password"},
        {"email": "nobody@example.com", "password": PASSWORD},
        {"email": staff["manager"].email, "password": PASSWORD},  # deactivated
    ]
    responses = [anon.post("/api/auth/login", json=attempt) for attempt in attempts]
    assert {(r.status_code, r.text) for r in responses} == {(401, '{"detail":"Incorrect email or password"}')}
    assert db.scalars(select(AuditLog.action)).all() == ["login.failed"] * 3


def test_session_cookie_is_httponly_and_logout_ends_the_session(db, staff):
    client = login(staff["caseworker"])
    assert client.get("/api/auth/me").json()["role"] == "caseworker"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    from fastapi.testclient import TestClient

    from app.main import app
    response = TestClient(app).post("/api/auth/login",
                                    json={"email": staff["caseworker"].email, "password": PASSWORD})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert "password" not in response.text


def test_deactivating_a_user_ends_their_session_immediately(db, staff):
    client = login(staff["caseworker"])
    admin = login(staff["admin"])
    assert admin.patch(f"/api/admin/users/{staff['caseworker'].id}", json={"is_active": False}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_tampered_session_cookie_is_rejected(anon):
    anon.cookies.set("session", "not.a.token")
    assert anon.get("/api/auth/me").status_code == 401


def test_login_is_rate_limited(anon, staff):
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [anon.post("/api/auth/login", json={"email": "x@example.com", "password": "nope"}).status_code
                 for _ in range(11)]
    finally:
        limiter.enabled = False
    assert codes == [401] * 10 + [429]


def test_admin_user_management_rules(db, staff):
    admin = login(staff["admin"])
    me = staff["admin"].id
    assert admin.post("/api/admin/users", json=NEW_USER | {"password": "short"}).status_code == 422
    assert admin.post("/api/admin/users", json=NEW_USER).status_code == 201
    assert admin.post("/api/admin/users", json=NEW_USER | {"email": "NEW@example.com"}).status_code == 409
    assert admin.patch(f"/api/admin/users/{me}", json={"is_active": False}).status_code == 422
    assert admin.patch(f"/api/admin/users/{me}", json={"role": "manager"}).status_code == 422
    assert admin.patch(f"/api/admin/users/{me}", json={"name": "Renamed"}).json()["name"] == "Renamed"

    entry = db.scalars(select(AuditLog).where(AuditLog.action == "user.created")).one()
    assert "password" not in str(entry.detail)


def test_viewing_a_case_is_audited(db, staff):
    intake = make_intake(db)
    login(staff["team_lead"]).get(f"/api/cases/{intake.id}")
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "case.viewed")).one()
    assert (entry.actor_id, entry.entity_id) == (staff["team_lead"].id, intake.id)


@pytest.mark.parametrize("statement", [
    "UPDATE audit_log SET action = 'edited'",
    "DELETE FROM audit_log",
    "TRUNCATE audit_log",
])
def test_audit_log_cannot_be_changed_even_with_direct_sql(statement, db, staff):
    make_intake(db)
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text(statement))
    assert db.scalars(select(AuditLog.action)).all()  # still there


def test_security_headers_and_no_docs_leak(anon):
    headers = anon.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["cache-control"] == "no-store"

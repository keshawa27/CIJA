"""The intake journey end to end: form -> triage -> tasks -> stages -> closed."""

from datetime import datetime

from sqlalchemy import func, select

from app import notify
from app.journey import STAGES
from app.models import AuditLog, Intake, Notification, Task
from app.security import limiter
from tests.conftest import intake_payload, login, make_intake, make_user


def test_submission_is_triaged_assigned_and_given_tasks(anon, db, staff, outbox):
    response = anon.post("/api/intake", json=intake_payload(immediate_safety_concern=True))
    assert response.status_code == 201
    reference = response.json()["reference_code"]
    assert reference.startswith("VELA-")

    intake = db.scalar(select(Intake).where(Intake.reference_code == reference))
    assert (intake.priority, intake.stage) == ("urgent", "triaged")
    assert intake.assigned_to == staff["caseworker"].id
    assert [(t.template_key, t.status, t.assigned_to) for t in intake.tasks] == [
        ("review_triage", "open", staff["caseworker"].id)]

    recipients = [to for to, _, _ in outbox]
    assert "alex.sample@example.com" in recipients  # client confirmation
    assert staff["caseworker"].email in recipients  # assignment
    assert staff["team_lead"].email in recipients  # urgent alert
    assert db.scalar(select(func.count()).select_from(Notification).where(Notification.status == "pending")) == 0


def test_client_email_reveals_nothing_sensitive(anon, staff, outbox):
    anon.post("/api/intake", json=intake_payload(immediate_safety_concern=True, free_text="private detail"))
    for to, subject, body in outbox:
        if to == "alex.sample@example.com":
            text = (subject + body).lower()
            assert not any(word in text for word in ("urgent", "safety", "private detail", "alex"))


def test_client_is_not_emailed_unless_email_is_their_safe_method(anon, staff, outbox):
    anon.post("/api/intake", json=intake_payload(safe_contact_method="phone", phone="0400 000 000"))
    assert "alex.sample@example.com" not in [to for to, _, _ in outbox]


def test_working_through_every_task_closes_the_case(db, staff):
    intake = make_intake(db, needs=["digital_safety"])
    client = login(staff["caseworker"])

    seen_stages = [intake.stage]
    while intake.stage != "closed":
        open_tasks = db.scalars(
            select(Task).where(Task.intake_id == intake.id, Task.status == "open")).all()
        assert open_tasks, f"stuck in {intake.stage} with nothing to do"
        for task in open_tasks:
            assert client.post(f"/api/tasks/{task.id}/complete").status_code == 200
        db.refresh(intake)
        seen_stages.append(intake.stage)

    assert seen_stages == STAGES[1:]  # every stage, in order, none skipped
    assert intake.closed_at is not None
    keys = db.scalars(select(Task.template_key).where(Task.intake_id == intake.id)).all()
    assert "book_digital_safety" in keys


def test_stage_does_not_advance_while_a_mandatory_step_is_open(db, staff):
    intake = make_intake(db)
    client = login(staff["caseworker"])
    for _ in range(2):  # triaged -> assigned -> contacted (which has two steps)
        task = db.scalar(select(Task).where(Task.intake_id == intake.id, Task.status == "open"))
        client.post(f"/api/tasks/{task.id}/complete")
    db.refresh(intake)
    assert intake.stage == "contacted"

    first, second = db.scalars(select(Task).where(Task.intake_id == intake.id, Task.status == "open")).all()
    client.post(f"/api/tasks/{first.id}/complete")
    db.refresh(intake)
    assert intake.stage == "contacted"  # one step still open

    assert client.post(f"/api/tasks/{second.id}/skip", json={"reason": "not needed"}).status_code == 403
    assert client.post(f"/api/tasks/{first.id}/complete").status_code == 409  # already done

    lead = login(staff["team_lead"])
    assert lead.post(f"/api/tasks/{second.id}/skip", json={"reason": ""}).status_code == 422  # reason required
    assert lead.post(f"/api/tasks/{second.id}/skip", json={"reason": "Client declined"}).status_code == 200
    db.refresh(intake)
    assert intake.stage == "assessment"


def test_allocation_goes_to_the_caseworker_with_fewest_open_tasks(db, staff):
    first = make_intake(db)
    second = make_intake(db, email="someone.else@example.com")
    assert first.assigned_to == staff["caseworker"].id
    assert second.assigned_to == staff["other_caseworker"].id


def test_intake_with_no_caseworker_is_left_unassigned_and_flagged(db, outbox):
    lead = make_user(db, "team_lead")
    intake = make_intake(db)
    assert intake.assigned_to is None
    notify.deliver_pending()
    assert any(to == lead.email and "Unassigned" in subject for to, subject, _ in outbox)


def test_repeat_submission_is_flagged_as_possible_duplicate(db, staff):
    first = make_intake(db)
    second = make_intake(db)
    other = make_intake(db, email="someone.else@example.com")
    assert first.possible_duplicate_of is None
    assert second.possible_duplicate_of == first.id
    assert other.possible_duplicate_of is None


def test_triage_override_keeps_the_original_and_moves_due_dates(db, staff):
    intake = make_intake(db)
    assert intake.priority == "low"
    due_before = intake.tasks[0].due_at
    lead = login(staff["team_lead"])

    assert lead.patch(f"/api/cases/{intake.id}/triage", json={"priority": "urgent"}).status_code == 422
    response = lead.patch(f"/api/cases/{intake.id}/triage",
                          json={"priority": "urgent", "reason": "Disclosed risk by phone"})
    assert response.status_code == 204

    detail = lead.get(f"/api/cases/{intake.id}").json()
    assert (detail["priority"], detail["triage_original_priority"]) == ("urgent", "low")
    assert datetime.fromisoformat(detail["tasks"][0]["due_at"]) < due_before
    assert "triage.overridden" in [entry["action"] for entry in detail["timeline"]]


def test_reassign_moves_the_case_and_its_open_tasks(db, staff):
    intake = make_intake(db)
    lead = login(staff["team_lead"])
    other = staff["other_caseworker"]

    assert lead.patch(f"/api/cases/{intake.id}/assignee",
                      json={"user_id": str(staff["manager"].id)}).status_code == 422
    assert lead.patch(f"/api/cases/{intake.id}/assignee", json={"user_id": str(other.id)}).status_code == 204

    assert login(other).get(f"/api/cases/{intake.id}").status_code == 200
    assert login(staff["caseworker"]).get(f"/api/cases/{intake.id}").status_code == 404
    assert [t["reference_code"] for t in login(other).get("/api/tasks").json()] == [intake.reference_code]


def test_notes_appear_on_the_case(db, staff):
    intake = make_intake(db)
    client = login(staff["caseworker"])
    assert client.post(f"/api/cases/{intake.id}/notes", json={"body": "Called, no answer."}).status_code == 201
    notes = client.get(f"/api/cases/{intake.id}").json()["notes"]
    assert [(n["body"], n["author_name"]) for n in notes] == [("Called, no answer.", "caseworker")]


def test_dashboard_counts_and_stalled_flag(db, staff):
    intake = make_intake(db, immediate_safety_concern=True)
    make_intake(db, email="someone.else@example.com")
    lead = login(staff["team_lead"])

    summary = lead.get("/api/dashboard/summary").json()
    assert (summary["open_cases"], summary["urgent_open"], summary["stalled"]) == (2, 1, 0)
    assert summary["by_stage"]["triaged"] == 2
    assert summary["avg_cycle_days"] is None

    intake.tasks[0].due_at = intake.tasks[0].due_at.replace(year=2020)
    db.commit()
    assert lead.get("/api/dashboard/summary").json()["stalled"] == 1
    assert [c["reference_code"] for c in lead.get("/api/cases?stalled=true").json()] == [intake.reference_code]
    assert login(staff["caseworker"]).get("/api/tasks").json()[0]["overdue"] is True

    # a caseworker's dashboard only counts their own cases
    assert login(staff["other_caseworker"]).get("/api/dashboard/summary").json()["open_cases"] == 1


def test_in_app_notifications(db, staff):
    make_intake(db)
    client = login(staff["caseworker"])
    [notification] = client.get("/api/notifications").json()
    assert notification["read_at"] is None and "New case assigned" in notification["subject"]
    assert client.post(f"/api/notifications/{notification['id']}/read").status_code == 204
    assert client.get("/api/notifications").json()[0]["read_at"] is not None
    assert login(staff["team_lead"]).post(f"/api/notifications/{notification['id']}/read").status_code == 404


def test_public_status_lookup_is_vague(anon, db, staff):
    intake = make_intake(db)
    assert anon.get(f"/api/intake/status/{intake.reference_code.lower()}").json() == {"status": "Received"}
    assert anon.get("/api/intake/status/VELA-NOPE").status_code == 404


def test_form_validation(anon, db, staff):
    bad = [
        intake_payload(consent=False),
        intake_payload(needs=[]),
        intake_payload(urgency_self_rating=9),
        intake_payload(email="not-an-email"),
        intake_payload(email=None),  # email is the safe contact method but missing
        intake_payload(safe_contact_method="phone"),  # no phone given
        intake_payload(date_of_birth="2999-01-01"),
        intake_payload(priority="urgent"),  # unknown fields are rejected, not ignored
    ]
    for payload in bad:
        assert anon.post("/api/intake", json=payload).status_code == 422, payload
    assert db.scalar(select(func.count()).select_from(Intake)) == 0


def test_honeypot_submission_is_dropped_silently(anon, db, staff):
    response = anon.post("/api/intake", json=intake_payload(website="http://spam.example"))
    assert response.status_code == 201
    assert db.scalar(select(func.count()).select_from(Intake)) == 0


def test_failed_email_is_recorded_and_the_intake_is_kept(anon, db, staff, monkeypatch):
    def smtp_down(to, subject, body):
        raise ConnectionRefusedError("mail server unavailable")

    monkeypatch.setattr(notify, "_send_email", smtp_down)
    response = anon.post("/api/intake", json=intake_payload())
    assert response.status_code == 201
    intake = db.scalar(select(Intake).where(Intake.reference_code == response.json()["reference_code"]))
    assert intake.stage == "triaged" and intake.assigned_to == staff["caseworker"].id
    emails = db.scalars(select(Notification).where(Notification.channel == "email")).all()
    assert emails and {n.status for n in emails} == {"failed"}


def test_public_status_lookup_is_rate_limited(anon, staff):
    limiter.enabled = True
    limiter.reset()
    try:
        # a different code each time: the limit must be per client, not per URL
        codes = [anon.get(f"/api/intake/status/VELA-NOPE{i:04d}").status_code for i in range(11)]
    finally:
        limiter.enabled = False
    assert codes == [404] * 10 + [429]


def test_public_form_is_rate_limited(anon, staff):
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [anon.post("/api/intake", json=intake_payload(email=f"p{i}@example.com")).status_code
                 for i in range(6)]
    finally:
        limiter.enabled = False
    assert codes == [201] * 5 + [429]


def test_submission_writes_audit_entries_without_personal_data(anon, db, staff):
    anon.post("/api/intake", json=intake_payload())
    entries = db.scalars(select(AuditLog).order_by(AuditLog.at)).all()
    assert [e.action for e in entries] == ["intake.submitted", "stage.changed"]
    assert "Alex" not in str([e.detail for e in entries])

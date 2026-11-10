"""The intake journey as data: stages, the mandatory steps in each, and response times.

DRAFT pending the sponsor's process map. Changing the journey means editing this
file only; nothing else hard-codes a stage or a step.
"""

from datetime import datetime, timedelta

STAGES = ["submitted", "triaged", "assigned", "contacted", "assessment", "plan", "closed"]

# stage -> [(template_key, title, only_for_stream)]. Every step is mandatory.
TASK_TEMPLATES: dict[str, list[tuple[str, str, str | None]]] = {
    "triaged": [("review_triage", "Review triage result", None)],
    "assigned": [("acknowledge", "Acknowledge assignment", None)],
    "contacted": [
        ("first_contact", "Make first contact using the client's safe contact method", None),
        ("confirm_consent", "Confirm consent with the client", None),
    ],
    "assessment": [
        ("needs_assessment", "Complete needs assessment", None),
        ("safety_check", "Complete safety check", None),
        ("assessment_notes", "Record assessment notes", None),
    ],
    "plan": [
        ("service_plan", "Agree service plan or referral", None),
        ("book_digital_safety", "Book Digital Safety session", "digital_safety"),
        ("record_outcome", "Record outcome", None),
    ],
}

# What a client is told. Deliberately vague: it must reveal nothing sensitive.
PUBLIC_STATUS = {
    "submitted": "Received",
    "triaged": "Received",
    "assigned": "Being reviewed",
    "contacted": "We will be in touch",
    "assessment": "In progress",
    "plan": "In progress",
    "closed": "Completed",
}

# Business days allowed per stage. Placeholder values: confirm with sponsor.
RESPONSE_DAYS = {"urgent": 1, "high": 2, "standard": 5, "low": 10}


def next_stage(stage: str) -> str:
    return STAGES[STAGES.index(stage) + 1]


def templates_for(stage: str, service_stream: str) -> list[tuple[str, str]]:
    return [
        (key, title)
        for key, title, stream in TASK_TEMPLATES.get(stage, [])
        if stream is None or stream == service_stream
    ]


def due_date(start: datetime, priority: str) -> datetime:
    """`start` plus the priority's response time, counting Monday to Friday only."""
    # ponytail: ignores public holidays; add a holiday calendar if Vela's targets need it
    due, remaining = start, RESPONSE_DAYS[priority]
    while remaining:
        due += timedelta(days=1)
        if due.weekday() < 5:
            remaining -= 1
    return due

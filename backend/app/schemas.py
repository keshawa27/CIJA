import uuid
from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Priority = Literal["urgent", "high", "standard", "low"]
Role = Literal["caseworker", "team_lead", "manager", "admin"]
Need = Literal["digital_safety", "housing", "financial", "legal", "counselling", "other"]

_strict = ConfigDict(extra="forbid", str_strip_whitespace=True)
_orm = ConfigDict(from_attributes=True)


# ---- requests ----


class IntakeIn(BaseModel):
    model_config = _strict

    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone: str | None = Field(None, pattern=r"^[0-9+() \-]{6,20}$")
    safe_contact_method: Literal["email", "phone", "none"]
    safe_to_leave_message: bool = False
    safe_contact_notes: str = Field("", max_length=500)
    needs: list[Need] = Field(min_length=1, max_length=6)
    immediate_safety_concern: bool = False
    housing_unstable: bool = False
    has_dependants: bool = False
    urgency_self_rating: int = Field(ge=1, le=5)
    free_text: str = Field("", max_length=2000)
    consent: bool
    website: str = Field("", max_length=200)  # honeypot: hidden from people, bots fill it in

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.consent:
            raise ValueError("Consent is required to submit this form")
        if self.date_of_birth and self.date_of_birth > date.today():
            raise ValueError("Date of birth cannot be in the future")
        if self.safe_contact_method == "email" and not self.email:
            raise ValueError("An email address is required when email is the safe contact method")
        if self.safe_contact_method == "phone" and not self.phone:
            raise ValueError("A phone number is required when phone is the safe contact method")
        return self


class LoginIn(BaseModel):
    model_config = _strict
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class TriageOverrideIn(BaseModel):
    model_config = _strict
    priority: Priority
    reason: str = Field(min_length=5, max_length=500)


class AssigneeIn(BaseModel):
    model_config = _strict
    user_id: uuid.UUID


class NoteIn(BaseModel):
    model_config = _strict
    body: str = Field(min_length=1, max_length=4000)


class SkipIn(BaseModel):
    model_config = _strict
    reason: str = Field(min_length=5, max_length=500)


class UserCreateIn(BaseModel):
    model_config = _strict
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    role: Role
    password: str = Field(min_length=12, max_length=200)


class UserUpdateIn(BaseModel):
    model_config = _strict
    name: str | None = Field(None, min_length=1, max_length=120)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=12, max_length=200)


# ---- responses ----


class UserOut(BaseModel):
    model_config = _orm
    id: uuid.UUID
    email: str
    name: str
    role: str
    is_active: bool


class TaskOut(BaseModel):
    model_config = _orm
    id: uuid.UUID
    intake_id: uuid.UUID
    title: str
    stage: str
    mandatory: bool
    assigned_to: uuid.UUID | None
    due_at: datetime
    status: str
    completed_at: datetime | None
    skip_reason: str | None


class MyTaskOut(TaskOut):
    reference_code: str
    client_name: str
    priority: str
    overdue: bool


class NoteOut(BaseModel):
    model_config = _orm
    id: uuid.UUID
    author_name: str
    body: str
    created_at: datetime


class CaseSummary(BaseModel):
    id: uuid.UUID
    reference_code: str
    client_name: str | None  # None for roles that only get the de-identified view
    priority: str
    service_stream: str
    stage: str
    assigned_to: uuid.UUID | None
    assignee_name: str | None
    submitted_at: datetime
    stalled: bool
    possible_duplicate: bool


class TimelineEntry(BaseModel):
    at: datetime
    actor_name: str | None
    action: str
    detail: dict


class CaseDetail(BaseModel):
    model_config = _orm
    id: uuid.UUID
    reference_code: str
    first_name: str
    last_name: str
    date_of_birth: date | None
    email: str | None
    phone: str | None
    safe_contact_method: str
    safe_to_leave_message: bool
    safe_contact_notes: str
    needs: list[str]
    immediate_safety_concern: bool
    housing_unstable: bool
    has_dependants: bool
    urgency_self_rating: int
    free_text: str
    consent_at: datetime
    priority: str
    service_stream: str
    triage_score: int
    triage_reasons: list[str]
    triage_original_priority: str | None
    triage_override_reason: str | None
    stage: str
    assigned_to: uuid.UUID | None
    submitted_at: datetime
    closed_at: datetime | None
    assignee_name: str | None
    tasks: list[TaskOut]
    notes: list[NoteOut]
    # filled in by the router
    duplicate_reference: str | None = None
    timeline: list[TimelineEntry] = []


class NotificationOut(BaseModel):
    model_config = _orm
    id: uuid.UUID
    intake_id: uuid.UUID | None
    subject: str
    body: str
    created_at: datetime
    read_at: datetime | None


class AuditOut(BaseModel):
    id: uuid.UUID
    at: datetime
    actor_name: str | None
    action: str
    entity: str
    entity_id: uuid.UUID | None
    detail: dict
    ip: str | None


class DashboardSummary(BaseModel):
    open_cases: int
    urgent_open: int
    stalled: int
    closed: int
    by_stage: dict[str, int]
    by_priority: dict[str, int]
    avg_cycle_days: float | None  # submitted -> closed
    step_completion_rate: float | None  # closed cases with no mandatory step skipped

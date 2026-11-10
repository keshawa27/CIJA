"""Rule-based triage. Pure: no database, no side effects, same answers -> same result.

DRAFT rules pending the sponsor's input. Each rule carries the reason shown to
staff, so every priority can be explained.
"""

from typing import Any, NamedTuple


class TriageResult(NamedTuple):
    priority: str  # urgent | high | standard | low
    service_stream: str
    score: int
    reasons: list[str]


def _get(answers: Any, name: str) -> Any:
    return answers[name] if isinstance(answers, dict) else getattr(answers, name)


# (predicate, points, reason)
RULES = [
    (lambda a: _get(a, "housing_unstable"), 30, "Housing is unstable"),
    (lambda a: _get(a, "safe_contact_method") == "none", 20, "No safe contact method given"),
    (lambda a: _get(a, "urgency_self_rating") >= 4, 20, "Client rated their situation as very urgent"),
    (lambda a: _get(a, "urgency_self_rating") == 3, 10, "Client rated their situation as moderately urgent"),
    (lambda a: _get(a, "has_dependants"), 15, "Client has dependants"),
    (lambda a: "legal" in _get(a, "needs"), 10, "Legal support requested"),
    (lambda a: "housing" in _get(a, "needs"), 10, "Housing support requested"),
]

# (minimum score, priority), highest first
BUCKETS = [(70, "urgent"), (40, "high"), (15, "standard"), (0, "low")]


def triage(answers: Any) -> TriageResult:
    """`answers` is a dict or any object exposing the intake form fields."""
    reasons, score = [], 0
    for predicate, points, reason in RULES:
        if predicate(answers):
            score += points
            reasons.append(reason)

    priority = next(p for minimum, p in BUCKETS if score >= minimum)

    # Hard override: a safety concern is always urgent, whatever the score.
    if _get(answers, "immediate_safety_concern"):
        priority = "urgent"
        reasons.insert(0, "Client reported an immediate safety concern")

    stream = "digital_safety" if "digital_safety" in _get(answers, "needs") else "general_support"
    return TriageResult(priority, stream, score, reasons or ["No risk factors identified"])

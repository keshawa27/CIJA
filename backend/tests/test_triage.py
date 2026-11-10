from datetime import datetime

import pytest

from app.journey import due_date, templates_for
from app.triage import RULES, triage

BASE = {
    "immediate_safety_concern": False,
    "housing_unstable": False,
    "has_dependants": False,
    "urgency_self_rating": 1,
    "safe_contact_method": "email",
    "needs": ["counselling"],
}


def test_no_risk_factors_is_low():
    result = triage(BASE)
    assert (result.priority, result.score) == ("low", 0)
    assert result.reasons == ["No risk factors identified"]


@pytest.mark.parametrize(
    "answers, points",
    [
        ({"housing_unstable": True}, 30),
        ({"safe_contact_method": "none"}, 20),
        ({"urgency_self_rating": 5}, 20),
        ({"urgency_self_rating": 4}, 20),
        ({"urgency_self_rating": 3}, 10),
        ({"has_dependants": True}, 15),
        ({"needs": ["legal"]}, 10),
        ({"needs": ["housing"]}, 10),
    ],
)
def test_each_rule_scores_and_explains_itself(answers, points):
    result = triage(BASE | answers)
    assert result.score == points
    assert len(result.reasons) == 1 and result.reasons[0] in [reason for _, _, reason in RULES]


@pytest.mark.parametrize(
    "answers, priority",
    [
        ({"needs": ["legal"]}, "low"),  # 10
        ({"has_dependants": True}, "standard"),  # 15: lower boundary
        ({"housing_unstable": True}, "standard"),  # 30
        ({"housing_unstable": True, "urgency_self_rating": 3}, "high"),  # 40: lower boundary
        ({"housing_unstable": True, "urgency_self_rating": 5, "has_dependants": True}, "high"),  # 65
        ({"housing_unstable": True, "urgency_self_rating": 5, "safe_contact_method": "none"}, "urgent"),  # 70
    ],
)
def test_score_buckets(answers, priority):
    assert triage(BASE | answers).priority == priority


def test_safety_concern_is_always_urgent_whatever_the_score():
    result = triage(BASE | {"immediate_safety_concern": True})
    assert result.priority == "urgent"
    assert result.score == 0
    assert result.reasons[0] == "Client reported an immediate safety concern"


def test_service_stream():
    assert triage(BASE).service_stream == "general_support"
    assert triage(BASE | {"needs": ["housing", "digital_safety"]}).service_stream == "digital_safety"


def test_due_date_counts_business_days_only():
    friday = datetime(2026, 10, 2, 9, 0)
    assert due_date(friday, "urgent") == datetime(2026, 10, 5, 9, 0)  # 1 day -> Monday
    assert due_date(friday, "standard") == datetime(2026, 10, 9, 9, 0)  # 5 days -> next Friday
    assert due_date(datetime(2026, 10, 3, 9, 0), "high") == datetime(2026, 10, 6, 9, 0)  # Sat + 2 -> Tue


def test_digital_safety_step_only_for_that_stream():
    keys = lambda stream: [key for key, _ in templates_for("plan", stream)]  # noqa: E731
    assert "book_digital_safety" in keys("digital_safety")
    assert "book_digital_safety" not in keys("general_support")

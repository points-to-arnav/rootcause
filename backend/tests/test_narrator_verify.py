import pytest
from app.narrator.verify import verify_narrative
from app.narrator.narrator import generate_templated_narrative
from app.planner.plan_schema import Plan

def test_number_verification():
    result = {
        "columns": ["region", "revenue"],
        "rows": [["North", 15200.50], ["South", 8400.00]]
    }
    derived = {"total": 23600.50}

    # Accurate text
    text_accurate = "North had revenue of 15,200.50 while South brought in 8,400.00."
    ok, unmatched = verify_narrative(text_accurate, result, derived)
    assert ok is True
    assert len(unmatched) == 0

    # Hallucinated text
    text_hallucinated = "North had revenue of 99,999.00 while South brought in 8,400.00."
    ok2, unmatched2 = verify_narrative(text_hallucinated, result, derived)
    assert ok2 is False
    assert len(unmatched2) > 0

    # Fallback narrative generation
    plan = Plan(intent="kpi", metric="revenue")
    fb = generate_templated_narrative(plan, {"columns": ["revenue"], "rows": [[5000000]]}, "2026")
    assert "5,000,000" in fb or "5000000" in fb

from src import runner
from src.nodes import decide

FULL_DOCS = ["identity_proof", "address_proof", "income_proof", "bank_statements_6m", "employment_proof"]


def clean_app(**overrides):
    app = dict(
        application_id="APP-T1",
        applicant_name="Test",
        product="personal_loan",
        loan_amount=500000,
        loan_tenure_months=36,
        monthly_income=120000,
        existing_monthly_obligations=8000,
        employment_vintage_months=54,
        cibil_score=782,
        collateral_value=None,
        worst_dpd_24m=0,
        has_coapplicant=False,
        documents_provided=list(FULL_DOCS),
    )
    app.update(overrides)
    return app


def test_missing_income_routes_to_clarify():
    state = runner.run_underwrite(clean_app(monthly_income=None))
    assert state["status"] == "awaiting_info"
    assert state["decision"] is None
    assert "monthly_income" in state["missing_fields"]
    assert any("income" in q.lower() for q in state["questions"])
    assert state["trace"][0]["from"] == "validate"
    assert state["trace"][0]["to"] == "clarify"


def test_hard_breach_cibil_declines():
    state = runner.run_underwrite(clean_app(cibil_score=600))
    assert state["decision"] == "decline"
    assert state["citations"], "decline must cite policy"
    assert any("CIBIL" in r for r in state["reasons"])
    nodes = [t["from"] for t in state["trace"]]
    assert nodes == ["validate", "retrieve_policy", "compute_ratios", "score", "policy_check", "decide", "memo"]


def test_clean_application_approves_with_citations():
    state = runner.run_underwrite(clean_app())
    assert state["decision"] == "approve"
    assert state["citations"], "approve must cite policy"
    assert state["numbers"]["foir"] < 0.50
    assert state["risk_band"] == "low"
    assert any("11.00%" in c for c in state["conditions"])


def test_grey_foir_refers():
    state = runner.run_underwrite(
        clean_app(
            loan_amount=1200000,
            loan_tenure_months=60,
            monthly_income=70000,
            existing_monthly_obligations=10000,
            cibil_score=735,
            employment_vintage_months=60,
        )
    )
    assert state["decision"] == "refer"
    assert state["citations"]
    assert any("grey" in r.lower() for r in state["reasons"])


def test_honesty_gate_refuses_approve_without_citations():
    state = {
        "application": clean_app(),
        "citations": [],
        "hard_breaches": [],
        "grey_flags": [],
        "policy_notes": [],
        "missing_docs": [],
        "risk_band": "low",
        "score": 880,
        "numbers": {"foir": 0.2, "base_rate": 0.11, "emi": 16000.0},
        "offered_rate": 0.11,
    }
    updates, _note = decide(state)
    assert updates["decision"] == "refer"
    assert any("grounding" in r.lower() for r in updates["reasons"])


def test_trace_covers_full_pipeline():
    state = runner.run_underwrite(clean_app())
    transitions = [(t["from"], t["to"]) for t in state["trace"]]
    assert transitions[0] == ("validate", "retrieve_policy")
    assert transitions[-1] == ("memo", "__end__")
    assert all(t["note"] for t in state["trace"])

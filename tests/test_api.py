from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

CLEAN_APP = {
    "application_id": "APP-API1",
    "applicant_name": "API Test",
    "product": "personal_loan",
    "loan_amount": 500000,
    "loan_tenure_months": 36,
    "monthly_income": 120000,
    "existing_monthly_obligations": 8000,
    "employment_vintage_months": 54,
    "cibil_score": 782,
    "worst_dpd_24m": 0,
    "documents_provided": [
        "identity_proof",
        "address_proof",
        "income_proof",
        "bank_statements_6m",
        "employment_proof",
    ],
}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_underwrite_clean_app_approves():
    r = client.post("/api/underwrite", json={"application": CLEAN_APP})
    assert r.status_code == 200
    data = r.json()
    assert data["decision"] == "approve"
    assert data["citations"]
    assert len(data["trace"]) == 7
    assert "APPROVED" in data["memo"]


def test_underwrite_missing_income_asks():
    payload = dict(CLEAN_APP)
    payload.pop("monthly_income")
    r = client.post("/api/underwrite", json={"application": payload})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "awaiting_info"
    assert "monthly_income" in data["missing_fields"]


def test_policies_list():
    r = client.get("/api/policies")
    assert r.status_code == 200
    assert r.json()["count"] == 5


def test_chat_clarify_round_trip():
    partial = dict(CLEAN_APP)
    partial.pop("monthly_income")
    # Turn 1: partial application -> agent asks for income
    r1 = client.post("/api/chat", json={"application": partial, "message": ""})
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["status"] == "clarify"
    assert "monthly_income" in d1["missing_fields"]
    assert "income" in d1["reply"].lower()

    # Turn 2: answer with the missing field -> full decision
    r2 = client.post(
        "/api/chat",
        json={"session_id": d1["session_id"], "message": "monthly_income: 120000"},
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "decided"
    assert d2["decision"]["decision"] == "approve"


def test_chat_natural_language_income():
    partial = dict(CLEAN_APP)
    partial.pop("monthly_income")
    r1 = client.post("/api/chat", json={"application": partial, "message": ""})
    sid = r1.json()["session_id"]
    r2 = client.post(
        "/api/chat",
        json={"session_id": sid, "message": "My monthly income is 120000"},
    )
    assert r2.json()["status"] == "decided"

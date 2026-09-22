"""FastAPI app: underwriting pipeline, conversational clarify flow, policy listing."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src import runner
from src.models import ChatRequest, ChatResponse, LoanApplication, UnderwriteResponse
from src.nodes import FIELD_QUESTIONS
from src.policy_tables import PRODUCTS

app = FastAPI(title="Underwriting Copilot", version="0.1.0")

# In-memory chat sessions: session_id -> {"application": dict}
_sessions: dict[str, dict[str, Any]] = {}


# ------------------------------------------------------------- chat parsing
_KNOWN_KEYS = {
    "product",
    "loan_amount",
    "loan_tenure_months",
    "monthly_income",
    "existing_monthly_obligations",
    "employment_vintage_months",
    "cibil_score",
    "collateral_value",
    "worst_dpd_24m",
    "applicant_name",
}

_INT_FIELDS = {"loan_tenure_months", "employment_vintage_months", "cibil_score", "worst_dpd_24m"}

_PRODUCT_KEYWORDS = {
    "personal_loan": ["personal loan", "personal_loan"],
    "home_loan": ["home loan", "home_loan", "housing loan"],
    "auto_loan": ["auto loan", "auto_loan", "car loan"],
    "business_loan": ["business loan", "business_loan"],
}


def _parse_number(raw: str) -> float | None:
    raw = raw.strip().replace(",", "").replace("₹", "").replace("rs", "").strip()
    m = re.match(r"^-?\d+(\.\d+)?$", raw)
    return float(m.group(0)) if m else None


def extract_fields(message: str) -> dict[str, Any]:
    """Pull application fields out of a chat message.

    Supports JSON objects, ``key: value`` pairs, and keyword-based fallbacks.
    """
    fields: dict[str, Any] = {}
    text = message.strip()

    # 1) JSON object
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for k in _KNOWN_KEYS:
                    if k in data:
                        fields[k] = data[k]
                # structured fields that only make sense as JSON
                if isinstance(data.get("documents_provided"), list):
                    fields["documents_provided"] = data["documents_provided"]
                if isinstance(data.get("has_coapplicant"), bool):
                    fields["has_coapplicant"] = data["has_coapplicant"]
                return fields
        except json.JSONDecodeError:
            pass

    lowered = text.lower()

    # 2) key: value pairs
    for chunk in re.split(r"[;\n]+", text):
        m = re.match(r"\s*([a-z_]+)\s*[:=]\s*(.+?)\s*$", chunk, re.IGNORECASE)
        if not m:
            continue
        key, raw = m.group(1).lower(), m.group(2)
        if key in _INT_FIELDS:
            num = _parse_number(raw)
            if num is not None:
                fields[key] = int(num)
        elif key in _KNOWN_KEYS:
            if key == "applicant_name":
                fields[key] = raw
            else:
                num = _parse_number(raw)
                if num is not None:
                    fields[key] = num

    # 3) product keywords
    if "product" not in fields:
        for product, keywords in _PRODUCT_KEYWORDS.items():
            if any(k in lowered for k in keywords):
                fields["product"] = product
                break

    # 4) keyword fallbacks for common numeric fields
    def grab(patterns: list[str], cast):
        for p in patterns:
            m = re.search(p, lowered)
            if m:
                num = _parse_number(m.group(1))
                if num is not None:
                    return cast(num)
        return None

    if "monthly_income" not in fields:
        v = grab([r"(?:monthly\s+income|income|salary)[^\d]*?([\d,]+)"], float)
        if v is not None:
            fields["monthly_income"] = v
    if "cibil_score" not in fields:
        v = grab([r"cibil[^\d]*?(\d{3})"], int)
        if v is not None:
            fields["cibil_score"] = v
    if "employment_vintage_months" not in fields:
        v = grab([r"(?:vintage|experience|employed for|job for)[^\d]*?(\d+)"], int)
        if v is not None:
            fields["employment_vintage_months"] = v
    if "loan_amount" not in fields:
        v = grab([r"(?:loan\s+amount|loan of|borrow)[^\d]*?([\d,]+)"], float)
        if v is not None and "income" not in lowered.split("loan")[0][-40:]:
            fields["loan_amount"] = v
    return fields


def _coerce_application(raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw)
    for k in _INT_FIELDS:
        if k in data and isinstance(data[k], float):
            data[k] = int(data[k])
    return data


def _to_response(state: dict, application_id: str) -> UnderwriteResponse:
    citations = [
        {"doc_id": c["doc_id"], "chunk_id": c["chunk_id"], "heading": c["heading"], "text": c["text"]}
        for c in state.get("citations", [])
    ]
    return UnderwriteResponse(
        application_id=application_id,
        status=state.get("status", "decided"),
        decision=state.get("decision"),
        missing_fields=state.get("missing_fields", []),
        questions=state.get("questions", []),
        numbers=state.get("numbers", {}),
        score=state.get("score"),
        risk_band=state.get("risk_band"),
        reasons=state.get("reasons", []),
        conditions=state.get("conditions", []),
        citations=citations,  # type: ignore[arg-type]
        trace=state.get("trace", []),
        memo=state.get("memo", ""),
    )


# ------------------------------------------------------------------- routes
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "underwriting-copilot"}


@app.post("/api/underwrite", response_model=UnderwriteResponse)
def underwrite(payload: dict[str, Any]) -> UnderwriteResponse:
    application = _coerce_application(payload.get("application", payload))
    application.setdefault("application_id", f"APP-{uuid.uuid4().hex[:6].upper()}")
    state = runner.run_underwrite(application)
    return _to_response(state, application["application_id"])


@app.get("/api/policies")
def list_policies() -> dict[str, Any]:
    docs = runner.get_index().list_documents()
    return {"documents": docs, "count": len(docs)}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    session_id = req.session_id or uuid.uuid4().hex
    session = _sessions.setdefault(session_id, {"application": {}})

    if req.application:
        session["application"].update(_coerce_application(req.application))
    if req.message:
        session["application"].update(extract_fields(req.message))

    application = _coerce_application(session["application"])
    state = runner.run_underwrite(application)

    if state.get("status") == "awaiting_info":
        questions = state.get("questions", [])
        reply = (
            "I need a few more details to underwrite this application:\n"
            + "\n".join(f"- {q}" for q in questions)
            + "\n\nReply with the missing values (e.g. `monthly_income: 85000`)."
        )
        return ChatResponse(
            session_id=session_id,
            status="clarify",
            reply=reply,
            questions=questions,
            missing_fields=state.get("missing_fields", []),
            application=application,
        )

    resp = _to_response(state, application.get("application_id", "APP-000"))
    summary = (
        f"Decision: **{resp.decision.upper()}** — score {resp.score} ({resp.risk_band} risk), "
        f"FOIR {resp.numbers.get('foir', 0):.3f}."
    )
    if resp.reasons:
        summary += "\n" + "\n".join(f"- {r}" for r in resp.reasons[:4])
    return ChatResponse(
        session_id=session_id,
        status="decided",
        reply=summary,
        application=application,
        decision=resp.model_dump(),
    )


# ------------------------------------------------------------------ static UI
import os as _os  # noqa: E402

_UI_DIR = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "ui")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(_os.path.join(_UI_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=_UI_DIR), name="static")

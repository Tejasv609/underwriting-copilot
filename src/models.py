"""Pydantic schemas for the underwriting API and graph state."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LoanApplication(BaseModel):
    application_id: str = Field(default="APP-000")
    applicant_name: str | None = None
    product: Literal["personal_loan", "home_loan", "auto_loan", "business_loan"] | None = None
    loan_amount: float | None = None
    loan_tenure_months: int | None = None
    monthly_income: float | None = None
    existing_monthly_obligations: float = 0.0
    employment_vintage_months: int | None = None
    cibil_score: int | None = None
    collateral_value: float | None = None
    worst_dpd_24m: int = 0
    has_coapplicant: bool = False
    documents_provided: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    doc_id: str
    chunk_id: str
    heading: str
    text: str


class UnderwriteResponse(BaseModel):
    application_id: str
    status: Literal["decided", "awaiting_info"]
    decision: Literal["approve", "refer", "decline"] | None = None
    missing_fields: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    numbers: dict[str, Any] = Field(default_factory=dict)
    score: int | None = None
    risk_band: str | None = None
    reasons: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    trace: list[dict[str, str]] = Field(default_factory=list)
    memo: str = ""


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = ""
    application: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    session_id: str
    status: Literal["clarify", "decided"]
    reply: str
    questions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    application: dict[str, Any] = Field(default_factory=dict)
    decision: dict[str, Any] | None = None

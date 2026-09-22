"""Product threshold tables mirrored from policies/01_eligibility.md.

Kept as code so the decision logic is deterministic; the policy markdown files
are the human-readable source of truth and are cited in every decision memo.
Values here MUST match the policy documents.
"""

from __future__ import annotations

PRODUCTS: dict[str, dict] = {
    "personal_loan": {
        "label": "Personal Loan",
        "min_cibil": 650,
        "max_foir": 0.50,
        "grey_foir": 0.55,
        "max_ltv": None,
        "secured": False,
        "base_rate": 0.110,
        "min_vintage_months": 12,
    },
    "home_loan": {
        "label": "Home Loan",
        "min_cibil": 700,
        "max_foir": 0.50,
        "grey_foir": 0.55,
        "max_ltv": 0.90,
        "secured": True,
        "base_rate": 0.085,
        "min_vintage_months": 12,
    },
    "auto_loan": {
        "label": "Auto Loan",
        "min_cibil": 675,
        "max_foir": 0.50,
        "grey_foir": 0.55,
        "max_ltv": 0.90,
        "secured": True,
        "base_rate": 0.095,
        "min_vintage_months": 12,
    },
    "business_loan": {
        "label": "Business Loan",
        "min_cibil": 700,
        "max_foir": 0.50,
        "grey_foir": 0.55,
        "max_ltv": None,
        "secured": False,
        "base_rate": 0.120,
        "min_vintage_months": 24,
    },
}

# Required documents per product, mirroring policies/04_documentation.md.
REQUIRED_DOCS: dict[str, list[str]] = {
    "personal_loan": [
        "identity_proof",
        "address_proof",
        "income_proof",
        "bank_statements_6m",
        "employment_proof",
    ],
    "home_loan": [
        "identity_proof",
        "address_proof",
        "income_proof",
        "bank_statements_6m",
        "employment_proof",
        "collateral_valuation",
        "ownership_documents",
    ],
    "auto_loan": [
        "identity_proof",
        "address_proof",
        "income_proof",
        "bank_statements_6m",
        "employment_proof",
        "collateral_valuation",
        "ownership_documents",
    ],
    "business_loan": [
        "identity_proof",
        "address_proof",
        "income_proof",
        "bank_statements_6m",
        "employment_proof",
    ],
}

# Documents whose absence blocks the application (see 04_documentation.md).
CRITICAL_DOCS = {"identity_proof", "income_proof"}

RISK_ADJUSTMENT = {"low": 0.0, "medium": 0.015, "high": 0.030}

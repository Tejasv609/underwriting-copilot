"""Underwriting workflow nodes.

Graph: validate -> clarify -> retrieve_policy -> compute_ratios -> score
       -> policy_check -> decide -> memo

Each node: (state) -> (updates, trace_note). All decision logic is
deterministic and every decision cites the policy chunks it relied on.
"""

from __future__ import annotations

from src.policy_tables import (
    CRITICAL_DOCS,
    PRODUCTS,
    REQUIRED_DOCS,
    RISK_ADJUSTMENT,
)
from src.tools import calculator as calc
from src.tools import scorecard

CRITICAL_FIELDS = [
    "product",
    "loan_amount",
    "loan_tenure_months",
    "monthly_income",
    "employment_vintage_months",
    "cibil_score",
]

FIELD_LABELS = {
    "product": "loan product",
    "loan_amount": "loan amount (INR)",
    "loan_tenure_months": "loan tenure (months)",
    "monthly_income": "gross monthly income (INR)",
    "employment_vintage_months": "employment vintage (months)",
    "cibil_score": "CIBIL score",
    "collateral_value": "collateral value (INR)",
}

FIELD_QUESTIONS = {
    "product": "Which loan product is this for? Choose: personal_loan, home_loan, auto_loan, business_loan.",
    "loan_amount": "What is the requested loan amount in INR?",
    "loan_tenure_months": "What is the requested loan tenure in months?",
    "monthly_income": "What is the applicant's gross monthly income in INR?",
    "employment_vintage_months": "How many months has the applicant been in the current job (or running the business)?",
    "cibil_score": "What is the applicant's CIBIL score (300-900)?",
    "collateral_value": "What is the collateral value in INR? (required for secured products)",
}


def _app(state: dict) -> dict:
    return state.get("application", {})


# ---------------------------------------------------------------- validate
def validate(state: dict) -> tuple[dict, str]:
    app = _app(state)
    missing: list[str] = []
    errors: list[str] = []

    def need(field: str, ok):
        if not ok:
            missing.append(field)

    need("product", app.get("product") in PRODUCTS)
    need("loan_amount", isinstance(app.get("loan_amount"), (int, float)) and app["loan_amount"] > 0)
    need(
        "loan_tenure_months",
        isinstance(app.get("loan_tenure_months"), int) and 6 <= app["loan_tenure_months"] <= 360,
    )
    need(
        "monthly_income",
        isinstance(app.get("monthly_income"), (int, float)) and app["monthly_income"] > 0,
    )
    need(
        "employment_vintage_months",
        isinstance(app.get("employment_vintage_months"), int)
        and app["employment_vintage_months"] >= 0,
    )
    cibil = app.get("cibil_score")
    need("cibil_score", isinstance(cibil, int) and 300 <= cibil <= 900)

    product = app.get("product")
    if product in PRODUCTS and PRODUCTS[product]["secured"]:
        need(
            "collateral_value",
            isinstance(app.get("collateral_value"), (int, float))
            and app["collateral_value"] > 0,
        )

    if product is not None and product not in PRODUCTS:
        errors.append(f"unknown product '{product}'")

    note = f"{len(missing)} field(s) missing: {', '.join(missing) or 'none'}"
    return ({"missing_fields": missing, "validation_errors": errors}, note)


def route_after_validate(state: dict) -> str:
    if state.get("missing_fields") or state.get("validation_errors"):
        return "clarify"
    return "retrieve_policy"


# ---------------------------------------------------------------- clarify
def clarify(state: dict) -> tuple[dict, str]:
    missing = state.get("missing_fields", [])
    errors = state.get("validation_errors", [])
    questions = [FIELD_QUESTIONS[f] for f in missing if f in FIELD_QUESTIONS]
    questions.extend(errors)
    note = f"awaiting applicant info for: {', '.join(missing) or 'none'}"
    return (
        {
            "status": "awaiting_info",
            "questions": questions,
            "decision": None,
        },
        note,
    )


# ---------------------------------------------------------- retrieve_policy
def _policy_queries(product: str, secured: bool) -> list[str]:
    label = PRODUCTS[product]["label"]
    queries = [
        f"{label} minimum CIBIL score eligibility",
        "maximum FOIR fixed obligation to income ratio limit",
        "delinquency DPD 90 days decline rule",
        "minimum employment vintage months requirement",
        "documentation checklist required documents",
        "exception referral matrix grey zone",
        f"{label} interest rate pricing risk band base rate",
    ]
    if secured:
        queries.append("maximum LTV loan to value collateral limit")
    return queries


def retrieve_policy(state: dict) -> tuple[dict, str]:
    from src.tools.retriever import PolicyIndex  # local import: cheap, built once per process

    index: PolicyIndex = state["_policy_index"]
    app = _app(state)
    product = app["product"]
    queries = _policy_queries(product, PRODUCTS[product]["secured"])
    citations = index.multi_search(queries, top_k=8)
    doc_ids = sorted({c["doc_id"] for c in citations})
    note = f"retrieved {len(citations)} chunks from {len(doc_ids)} policy docs"
    return ({"citations": citations, "policy_queries": queries}, note)


# ---------------------------------------------------------- compute_ratios
def compute_ratios(state: dict) -> tuple[dict, str]:
    app = _app(state)
    product = PRODUCTS[app["product"]]
    emi = calc.emi(app["loan_amount"], product["base_rate"], app["loan_tenure_months"])
    foir = calc.foir(emi, app.get("existing_monthly_obligations", 0.0), app["monthly_income"])
    ltv = calc.ltv(app["loan_amount"], app.get("collateral_value"))
    numbers = {
        "emi_at_base_rate": round(emi, 2),
        "base_rate": product["base_rate"],
        "foir": round(foir, 4),
        "ltv": round(ltv, 4) if ltv is not None else None,
    }
    note = f"EMI={emi:,.0f} @ {product['base_rate']:.1%}, FOIR={foir:.3f}, LTV={ltv if ltv is not None else 'n/a'}"
    return ({"numbers": numbers}, note)


# ------------------------------------------------------------------- score
def score(state: dict) -> tuple[dict, str]:
    app = _app(state)
    numbers = state["numbers"]
    result = scorecard.score_application(
        cibil=app["cibil_score"],
        foir=numbers["foir"],
        ltv=numbers["ltv"],
        vintage_months=app["employment_vintage_months"],
        worst_dpd_24m=app.get("worst_dpd_24m", 0),
    )
    note = f"synthetic scorecard: {result['score']} ({result['band']} risk)"
    return ({"score": result["score"], "risk_band": result["band"], "score_breakdown": result["breakdown"]}, note)


# ------------------------------------------------------------- policy_check
def policy_check(state: dict) -> tuple[dict, str]:
    app = _app(state)
    product = PRODUCTS[app["product"]]
    numbers = state["numbers"]
    band = state["risk_band"]

    # Final pricing from the risk band (policies/03_pricing.md).
    offered_rate = product["base_rate"] + RISK_ADJUSTMENT[band]
    emi_final = calc.emi(app["loan_amount"], offered_rate, app["loan_tenure_months"])
    foir_final = calc.foir(emi_final, app.get("existing_monthly_obligations", 0.0), app["monthly_income"])
    ltv = numbers["ltv"]

    hard: list[str] = []
    grey: list[str] = []
    notes: list[str] = []

    # CIBIL vs product minimum (02_credit_policy.md, 05_exceptions.md)
    if app["cibil_score"] < product["min_cibil"]:
        hard.append(
            f"CIBIL {app['cibil_score']} below product minimum {product['min_cibil']} "
            f"for {product['label']} (02_credit_policy.md)"
        )

    # FOIR (02_credit_policy.md)
    if foir_final > product["grey_foir"]:
        hard.append(
            f"FOIR {foir_final:.3f} above hard cap {product['grey_foir']:.2f} (02_credit_policy.md)"
        )
    elif foir_final > product["max_foir"]:
        if app["employment_vintage_months"] >= 36 and app.get("worst_dpd_24m", 0) == 0:
            grey.append(
                f"FOIR {foir_final:.3f} in grey zone 0.50-0.55 with vintage "
                f"{app['employment_vintage_months']}m and clean repayment history: "
                f"referral-eligible (05_exceptions.md)"
            )
        else:
            hard.append(
                f"FOIR {foir_final:.3f} in grey zone but not exception-eligible "
                f"(needs vintage >= 36m and no delinquency) (05_exceptions.md)"
            )

    # LTV (02_credit_policy.md)
    if product["max_ltv"] is not None and ltv is not None and ltv > product["max_ltv"]:
        hard.append(
            f"LTV {ltv:.3f} above maximum {product['max_ltv']:.2f} (02_credit_policy.md)"
        )

    # Vintage (01_eligibility.md, 05_exceptions.md)
    vintage = app["employment_vintage_months"]
    if vintage < 6:
        hard.append(f"employment vintage {vintage}m below 6-month floor (05_exceptions.md)")
    elif vintage < product["min_vintage_months"]:
        if app.get("has_coapplicant"):
            grey.append(
                f"vintage {vintage}m below {product['min_vintage_months']}m minimum but "
                f"co-applicant present: referral-eligible (05_exceptions.md)"
            )
        else:
            hard.append(
                f"employment vintage {vintage}m below product minimum "
                f"{product['min_vintage_months']}m (01_eligibility.md)"
            )

    # Delinquency (02_credit_policy.md)
    dpd = app.get("worst_dpd_24m", 0)
    if dpd >= 90:
        hard.append(f"90+ DPD delinquency in last 24 months (02_credit_policy.md)")
    elif dpd >= 60:
        if vintage >= 24:
            grey.append(f"60 DPD delinquency with vintage {vintage}m: referral-eligible (05_exceptions.md)")
        else:
            hard.append(f"60 DPD delinquency with vintage {vintage}m below 24m (05_exceptions.md)")
    elif dpd >= 30:
        notes.append(f"single 30 DPD delinquency noted; acceptable per policy (02_credit_policy.md)")

    # Documentation (04_documentation.md)
    required = REQUIRED_DOCS[app["product"]]
    provided = set(app.get("documents_provided", []))
    missing_docs = [d for d in required if d not in provided]
    critical_missing = [d for d in missing_docs if d in CRITICAL_DOCS]
    if critical_missing:
        hard.append(f"missing critical documents: {', '.join(critical_missing)} (04_documentation.md)")
    elif missing_docs:
        grey.append(f"missing documents: {', '.join(missing_docs)} — collect before disbursal (04_documentation.md)")

    updates = {
        "offered_rate": offered_rate,
        "numbers": {
            **numbers,
            "offered_rate": offered_rate,
            "emi": round(emi_final, 2),
            "foir": round(foir_final, 4),
        },
        "hard_breaches": hard,
        "grey_flags": grey,
        "policy_notes": notes,
        "missing_docs": missing_docs,
    }
    note = f"{len(hard)} hard breach(es), {len(grey)} grey flag(s), {len(missing_docs)} doc(s) missing"
    return (updates, note)


# ------------------------------------------------------------------ decide
def decide(state: dict) -> tuple[dict, str]:
    citations = state.get("citations", [])
    hard = state.get("hard_breaches", [])
    grey = state.get("grey_flags", [])
    notes = state.get("policy_notes", [])
    band = state.get("risk_band", "high")
    missing_docs = state.get("missing_docs", [])

    reasons: list[str] = []
    conditions: list[str] = []
    app = _app(state)

    def cite_hint() -> str:
        docs = sorted({c["doc_id"] for c in citations})
        return f"Policy basis: {', '.join(docs)}." if docs else "No policy citations retrieved."

    # Honesty gate: never approve without policy grounding.
    grounded = len(citations) > 0

    if hard:
        decision = "decline"
        reasons = [f"DECLINED — {b}" for b in hard]
    elif band == "high":
        decision = "decline"
        reasons = [
            f"DECLINED — synthetic scorecard {state['score']} is in the high-risk band "
            f"(below 650); risk too high for automated approval."
        ]
    elif grey or band == "medium" or missing_docs:
        decision = "refer"
        if not grounded:
            reasons.append("REFER — insufficient policy grounding for an automated decision; manual review required.")
        if band == "medium":
            reasons.append(f"REFER — score {state['score']} in medium-risk band (650-749); senior underwriter review.")
        reasons.extend(f"REFER — {g}" for g in grey)
        if missing_docs and not grey:
            reasons.append(f"REFER — collect before disbursal: {', '.join(missing_docs)}.")
        conditions.append("Senior underwriter review required (05_exceptions.md).")
    else:
        if not grounded:
            # Honesty gate: refuse to approve without citations.
            decision = "refer"
            reasons.append("REFER — no policy citations retrieved; cannot approve without grounding. Manual review required.")
            conditions.append("Senior underwriter review required.")
        else:
            decision = "approve"
            rate = state["offered_rate"]
            reasons.append(
                f"APPROVED — all policy checks passed: CIBIL {app['cibil_score']}, "
                f"FOIR {state['numbers']['foir']:.3f} within limit, "
                f"score {state['score']} ({band} risk)."
            )
            conditions.append(
                f"Offered rate {rate:.2%} p.a. (base {state['numbers']['base_rate']:.2%} + "
                f"{RISK_ADJUSTMENT[band]:.1%} {band}-risk adjustment, 03_pricing.md)."
            )
            conditions.append(f"EMI {state['numbers']['emi']:,.0f} INR/month for {app['loan_tenure_months']} months.")
            fee = min(0.01 * app["loan_amount"], 25000)
            conditions.append(f"Processing fee {fee:,.0f} INR (1%, capped at 25,000; 03_pricing.md).")

    reasons.append(cite_hint())
    reasons.extend(notes)
    note = f"decision={decision} ({len(reasons)} reason(s))"
    return (
        {
            "status": "decided",
            "decision": decision,
            "reasons": reasons,
            "conditions": conditions,
        },
        note,
    )


# -------------------------------------------------------------------- memo
def memo(state: dict) -> tuple[dict, str]:
    from src import llm  # local import so tests can run without network deps

    app = _app(state)
    numbers = state.get("numbers", {})
    lines = [
        f"UNDERWRITING MEMO — {app.get('application_id', 'APP-000')}",
        f"Applicant: {app.get('applicant_name') or 'n/a'} | Product: {PRODUCTS[app['product']]['label']}",
        "",
        f"DECISION: {state['decision'].upper()}",
        "",
        "KEY NUMBERS",
        f"- Loan amount: {app['loan_amount']:,.0f} INR, tenure {app['loan_tenure_months']} months",
        f"- Monthly income: {app['monthly_income']:,.0f} INR; existing obligations: {app.get('existing_monthly_obligations', 0):,.0f} INR",
        f"- EMI: {numbers.get('emi', 0):,.0f} INR/month at {numbers.get('offered_rate', 0):.2%} p.a.",
        f"- FOIR: {numbers.get('foir', 0):.3f} | LTV: {numbers.get('ltv') if numbers.get('ltv') is not None else 'n/a (unsecured)'}",
        f"- CIBIL: {app['cibil_score']} | Vintage: {app['employment_vintage_months']} months",
        f"- Synthetic scorecard: {state.get('score')} ({state.get('risk_band')} risk) [DEMO SCORECARD — not a real credit model]",
        "",
        "REASONS",
    ]
    lines += [f"- {r}" for r in state.get("reasons", [])]
    if state.get("conditions"):
        lines.append("")
        lines.append("CONDITIONS")
        lines += [f"- {c}" for c in state["conditions"]]
    if state.get("citations"):
        lines.append("")
        lines.append("POLICY CITATIONS")
        for c in state["citations"]:
            lines.append(f"- [{c['doc_id']} :: {c['heading']}] {c['text'][:160]}...")
    lines.append("")
    lines.append(
        "NOTE: Synthetic demonstration. Policy documents are fictional; the scorecard is a "
        "demo construct, not a real credit model. Not financial advice."
    )
    body = "\n".join(lines)
    polished = llm.polish_memo(body, {"decision": state["decision"], "product": app["product"]})
    return ({"memo": polished}, f"memo rendered ({len(polished)} chars)")


def build_graph() -> "StateGraph":
    from src.graph import StateGraph

    g = StateGraph()
    g.add_node("validate", validate)
    g.add_node("clarify", clarify)
    g.add_node("retrieve_policy", retrieve_policy)
    g.add_node("compute_ratios", compute_ratios)
    g.add_node("score", score)
    g.add_node("policy_check", policy_check)
    g.add_node("decide", decide)
    g.add_node("memo", memo)
    g.set_entry("validate")
    g.add_conditional_edges("validate", route_after_validate, {"clarify": "clarify", "retrieve_policy": "retrieve_policy"})
    g.add_edge("clarify", "__end__")
    g.add_edge("retrieve_policy", "compute_ratios")
    g.add_edge("compute_ratios", "score")
    g.add_edge("score", "policy_check")
    g.add_edge("policy_check", "decide")
    g.add_edge("decide", "memo")
    g.add_edge("memo", "__end__")
    return g

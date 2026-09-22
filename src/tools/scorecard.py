"""SYNTHETIC DEMO SCORECARD — NOT A REAL CREDIT MODEL.

This is a deterministic, hand-written weighted scorecard built purely for a
software portfolio demonstration. It has no statistical basis, was not trained
on any data, and must never be presented or used as a real credit model or to
make real lending decisions.
"""

from __future__ import annotations

BASE_SCORE = 300
MAX_SCORE = 900

LOW_BAND_MIN = 750
MEDIUM_BAND_MIN = 650


def _cibil_points(cibil: int) -> int:
    if cibil >= 750:
        return 220
    if cibil >= 700:
        return 170
    if cibil >= 650:
        return 110
    return 40


def _foir_points(foir: float) -> int:
    if foir <= 0.35:
        return 130
    if foir <= 0.45:
        return 100
    if foir <= 0.50:
        return 70
    if foir <= 0.55:
        return 40
    return 10


def _ltv_points(ltv: float | None) -> int:
    # Unsecured products get a neutral mid value (no collateral risk either way).
    if ltv is None:
        return 90
    if ltv <= 0.50:
        return 110
    if ltv <= 0.70:
        return 90
    if ltv <= 0.80:
        return 70
    if ltv <= 0.90:
        return 40
    return 0


def _vintage_points(vintage_months: int) -> int:
    if vintage_months >= 36:
        return 80
    if vintage_months >= 24:
        return 65
    if vintage_months >= 12:
        return 45
    if vintage_months >= 6:
        return 25
    return 5


def _delinquency_points(worst_dpd_24m: int) -> int:
    if worst_dpd_24m >= 90:
        return 0
    if worst_dpd_24m >= 60:
        return 10
    if worst_dpd_24m >= 30:
        return 30
    return 60


def risk_band(score: int) -> str:
    if score >= LOW_BAND_MIN:
        return "low"
    if score >= MEDIUM_BAND_MIN:
        return "medium"
    return "high"


def score_application(
    cibil: int,
    foir: float,
    ltv: float | None,
    vintage_months: int,
    worst_dpd_24m: int,
) -> dict:
    """Deterministic synthetic score in [300, 900] plus band and breakdown."""
    breakdown = {
        "cibil": _cibil_points(cibil),
        "foir": _foir_points(foir),
        "ltv": _ltv_points(ltv),
        "vintage": _vintage_points(vintage_months),
        "delinquency": _delinquency_points(worst_dpd_24m),
    }
    score = BASE_SCORE + sum(breakdown.values())
    score = max(BASE_SCORE, min(MAX_SCORE, score))
    return {"score": score, "band": risk_band(score), "breakdown": breakdown}

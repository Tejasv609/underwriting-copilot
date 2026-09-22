"""Deterministic financial calculators for the underwriting agent.

All functions are pure and hand-rolled: no external finance libraries.
"""

from __future__ import annotations


def emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Monthly EMI via the standard amortization formula.

    EMI = P * r * (1+r)^n / ((1+r)^n - 1), where r is the monthly rate.
    """
    if principal <= 0:
        raise ValueError("principal must be positive")
    if tenure_months <= 0:
        raise ValueError("tenure_months must be positive")
    if annual_rate < 0:
        raise ValueError("annual_rate must be non-negative")
    monthly_rate = annual_rate / 12.0
    if monthly_rate == 0:
        return principal / tenure_months
    factor = (1 + monthly_rate) ** tenure_months
    return principal * monthly_rate * factor / (factor - 1)


def foir(proposed_emi: float, existing_obligations: float, monthly_income: float) -> float:
    """Fixed Obligation to Income Ratio.

    FOIR = (proposed EMI + existing monthly obligations) / monthly income.
    """
    if monthly_income <= 0:
        raise ValueError("monthly_income must be positive")
    if proposed_emi < 0 or existing_obligations < 0:
        raise ValueError("obligations must be non-negative")
    return (proposed_emi + existing_obligations) / monthly_income


def ltv(loan_amount: float, collateral_value: float | None) -> float | None:
    """Loan to Value ratio. Returns None for unsecured products (no collateral)."""
    if loan_amount <= 0:
        raise ValueError("loan_amount must be positive")
    if collateral_value is None:
        return None
    if collateral_value <= 0:
        raise ValueError("collateral_value must be positive")
    return loan_amount / collateral_value

# Credit Policy

> **SYNTHETIC DEMO DATA** — This document is entirely fictional and was written
> for a software demonstration. It is not a real credit policy, not financial
> advice, and must not be used to make real lending decisions.

## CIBIL score bands

| Band      | CIBIL range | Interpretation        |
|-----------|-------------|-----------------------|
| Excellent | 750+        | Strong credit history |
| Good      | 700–749     | Acceptable            |
| Fair      | 650–699     | Elevated risk         |
| Poor      | Below 650   | High risk             |

Applications below the product minimum CIBIL (see `01_eligibility.md`) are
hard declines and cannot be approved or referred.

## FOIR (Fixed Obligation to Income Ratio)

- FOIR = (proposed EMI + existing monthly obligations) / monthly income.
- FOIR up to 0.50 is acceptable.
- FOIR between 0.50 and 0.55 is a grey zone: eligible for referral only when
  employment vintage is at least 36 months and there is no delinquency history.
- FOIR above 0.55 is a hard decline.

## LTV (Loan to Value)

- For secured products, LTV = loan amount / collateral value.
- Maximum permitted LTV is 0.90. LTV above 0.90 is a hard decline.

## Delinquency history

- Any 90+ days-past-due (DPD) delinquency in the last 24 months is a hard decline.
- A 60 DPD delinquency in the last 24 months routes the application to referral.
- A single 30 DPD delinquency older than 12 months is acceptable with a note.

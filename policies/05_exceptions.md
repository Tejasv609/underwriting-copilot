# Exception and Referral Matrix

> **SYNTHETIC DEMO DATA** — This document is entirely fictional and was written
> for a software demonstration. It is not a real credit policy, not financial
> advice, and must not be used to make real lending decisions.

## Referral-eligible exceptions

An application that breaches a soft threshold may be referred to a senior
underwriter instead of declined, only under these conditions:

| Situation                              | Condition for referral              |
|----------------------------------------|-------------------------------------|
| FOIR in grey zone 0.50–0.55            | Vintage >= 36 months, no delinquency|
| Employment vintage 6–12 months         | Co-applicant with own income added  |
| Single 60 DPD in last 24 months        | Vintage >= 24 months                |
| Missing non-critical document(s)       | Collect before disbursal            |

## Hard declines (no exception permitted)

- CIBIL below the product minimum.
- FOIR above 0.55.
- LTV above 0.90 on secured products.
- Any 90+ DPD delinquency in the last 24 months.
- Employment vintage below 6 months.
- Missing income proof or identity proof after clarification.

## Authority levels

| Decision | Authority              |
|----------|------------------------|
| Approve  | System (within policy) |
| Refer    | Senior underwriter     |
| Decline  | System (hard breach)   |

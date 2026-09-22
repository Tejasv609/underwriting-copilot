# Product Eligibility Criteria

> **SYNTHETIC DEMO DATA** — This document is entirely fictional and was written
> for a software demonstration. It is not a real credit policy, not financial
> advice, and must not be used to make real lending decisions.

## Applicant basics

- Applicant must be an Indian resident aged 21 to 60 years at loan maturity.
- Applicant must have a verifiable monthly income (salaried or self-employed).

## Product-wise eligibility thresholds

| Product        | Min CIBIL | Min employment vintage | Max FOIR | Max LTV | Secured |
|----------------|-----------|------------------------|----------|---------|---------|
| Personal Loan  | 650       | 12 months              | 0.50     | n/a     | No      |
| Home Loan      | 700       | 12 months              | 0.50     | 0.90    | Yes     |
| Auto Loan      | 675       | 12 months              | 0.50     | 0.90    | Yes     |
| Business Loan  | 700       | 24 months              | 0.50     | n/a     | No      |

## Vintage rule

- "Employment vintage" means continuous months in the current job (salaried) or
  continuous months of business operation (self-employed).
- Vintage below the product minimum but at least 6 months may be considered
  under the exception matrix (see `05_exceptions.md`).
- Vintage below 6 months is a hard decline for all products.

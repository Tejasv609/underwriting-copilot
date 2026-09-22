# Underwriting Copilot

An agentic loan-underwriting assistant. A hand-rolled state graph
(no LangChain/LangGraph) takes a loan application through an underwriting
workflow, retrieves the governing policy chunks, computes ratios with
deterministic calculators, scores with a synthetic scorecard, and emits a
cited decision memo — with a visible execution trace for explainability.

> **Synthetic demo.** All policy documents, applications, and the scorecard are
> fictional and built for a software portfolio. This is **not a real credit
> model**, not financial advice, and must not be used for real lending decisions.

## Architecture

```
                         ┌──────────┐
                         │ validate │  required fields present & sane?
                         └────┬─────┘
                    missing   │   complete
                         ┌────▼─────┐      ┌─────────────────┐
                         │ clarify  │─────▶│ END (await info)│  asks questions
                         └──────────┘      └─────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  retrieve_policy   │  BM25 + TF-IDF cosine, RRF fusion
                    └─────────┬──────────┘  over policies/ -> citations
                    ┌─────────▼──────────┐
                    │  compute_ratios    │  EMI (amortization), FOIR, LTV
                    └─────────┬──────────┘
                    ┌─────────▼──────────┐
                    │  score             │  synthetic weighted scorecard 300-900
                    └─────────┬──────────┘  -> low / medium / high band
                    ┌─────────▼──────────┐
                    │  policy_check      │  hard breaches vs grey flags vs docs,
                    └─────────┬──────────┘  final rate from pricing policy
                    ┌─────────▼──────────┐
                    │  decide            │  DECLINE / REFER / APPROVE + honesty
                    └─────────┬──────────┘  gate: no citations -> never approve
                    ┌─────────▼──────────┐
                    │  memo              │  template renderer (LLM polish optional)
                    └────────────────────┘

Every run returns `trace`: the ordered list of node transitions with notes.
```

Decision logic (`src/nodes.py::decide`, deterministic):

- **DECLINE** on hard policy breach: CIBIL below product minimum, FOIR above
  0.55, LTV above 0.90, any 90+ DPD delinquency in 24 months, vintage under
  6 months, missing critical documents — or a high-risk score band.
- **REFER** in the grey zone: FOIR 0.50–0.55 with vintage ≥ 36m and clean
  history, vintage 6–12m with co-applicant, medium score band, or missing
  non-critical documents. Also used when the honesty gate fires (no policy
  citations retrieved → refuse to approve).
- **APPROVE** otherwise, with conditions: offered rate (base + risk adjustment
  from `policies/03_pricing.md`), EMI, processing fee.

## Project layout

```
underwriting-copilot/
├── policies/            5 synthetic policy docs (SYNTHETIC DEMO DATA header)
├── src/
│   ├── graph.py         tiny state graph: nodes + conditional edges + trace
│   ├── nodes.py         validate/clarify/retrieve/compute/score/check/decide/memo
│   ├── runner.py        builds graph once; shared policy index
│   ├── llm.py           optional OpenAI-compatible memo polish (offline default)
│   ├── main.py          FastAPI: /health, /api/underwrite, /api/chat, /api/policies
│   ├── models.py        pydantic schemas
│   ├── policy_tables.py numeric thresholds mirroring policies/
│   └── tools/
│       ├── calculator.py  EMI / FOIR / LTV (pure functions)
│       ├── retriever.py   BM25 + TF-IDF cosine + RRF, markdown section chunks
│       └── scorecard.py   SYNTHETIC DEMO scorecard 300-900 (not a real model)
├── data/sample_applications.json   10 applications with expected decisions
├── scripts/eval.py      runs the 10 apps, writes eval/results.json
├── eval/results.json    measured eval output
├── ui/                  static single-page app: form, memo+citations+trace, chat
└── tests/               34 pytest tests
```

## How to run

```bash
make setup     # create .venv and install (light deps only: no torch/faiss)
make ingest    # build the policy index (also built lazily on first run)
make test      # pytest
make eval      # scripts/eval.py -> eval/results.json
make run       # uvicorn on :8000, serves API + UI at /
```

Optional LLM memo polish (decision logic never touches the LLM):

```bash
cp .env.example .env   # set UNDERWRITE_LLM_BASE_URL / _MODEL
```

Docker: `make docker` (or `docker build -t underwriting-copilot .`).

## API

- `GET /health` → `{"status":"ok"}`
- `POST /api/underwrite` — body `{"application": {...}}`; returns decision,
  memo, citations, numbers, score/band, and the execution `trace`. If required
  fields are missing it returns `status: "awaiting_info"` with `questions`
  instead of a decision.
- `POST /api/chat` — body `{"session_id": ..., "message": "...", "application": {...}}`.
  Conversational flow: send partial details (JSON or `key: value` pairs), the
  agent asks clarifying questions, and continues to a full decision once
  answered. Sessions are kept in memory.
- `GET /api/policies` — lists the 5 indexed policy docs and chunk counts.
- `GET /` — the static UI.

Application fields: `product` (personal_loan | home_loan | auto_loan |
business_loan), `loan_amount`, `loan_tenure_months`, `monthly_income`,
`existing_monthly_obligations`, `employment_vintage_months`, `cibil_score`,
`collateral_value` (secured products), `worst_dpd_24m`, `has_coapplicant`,
`documents_provided`.

## Evaluation

`scripts/eval.py` runs the 10 sample applications through the graph and
compares against the expected decisions designed into
`data/sample_applications.json` (2 approve, 4 refer, 3 decline, 1 clarify).
Measured output (`eval/results.json`):

| Metric | Value |
|---|---|
| Decision agreement vs expected | **1.000** (10/10) |
| Citation rate (decided runs with ≥1 citation) | **1.000** |
| Policy-hit rate (runs citing ≥2 distinct policy docs) | **1.000** |
| Clarify-trigger rate | **0.100** (1/10) |
| Rationale keyword coverage | **1.000** |

Test suite: **34/34 pytest tests pass** (`make test`), covering the
calculators (EMI 8884.88 on the textbook case), scorecard monotonicity,
retriever precision (CIBIL query → `02_credit_policy.md`), graph routing
(missing income → clarify; CIBIL breach → decline; clean app → approve;
honesty gate refuses approval without citations), and the API including a
chat clarify round-trip.

## Limitations

- Every policy document, application, threshold, and rate is **synthetic demo
  data**, invented for this project.
- `src/tools/scorecard.py` is a **hand-written demo scorecard, not a real
  credit model**: it was not trained on data and has no statistical validity.
- The retriever is lexical (BM25 + TF-IDF); it does not understand paraphrase
  the way embedding retrieval would.
- Chat sessions are in-memory and do not persist across restarts.
- This project must not be used to make, or presented as capable of making,
  real credit or lending decisions.

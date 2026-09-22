"""Run all sample applications through the underwriting graph.

Writes eval/results.json and prints the headline metrics:
- decision agreement vs expected
- citation rate (runs with >= 1 policy citation)
- policy-hit rate (non-clarify runs citing >= 2 distinct policy docs)
- clarify-trigger rate
- rationale keyword coverage
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import runner  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data", "sample_applications.json")
OUT = os.path.join(ROOT, "eval", "results.json")


def main() -> None:
    with open(DATA, encoding="utf-8") as f:
        apps = json.load(f)

    per_app = []
    for app in apps:
        expected = app["expected_decision"]
        application = {k: v for k, v in app.items() if not k.startswith("expected_")}
        state = runner.run_underwrite(application)
        actual = state.get("decision") if state.get("status") == "decided" else "clarify"
        citations = state.get("citations", [])
        doc_ids = {c["doc_id"] for c in citations}
        text_blob = " ".join(state.get("reasons", []) + state.get("questions", []) + [state.get("memo", "")])
        keywords_hit = [kw for kw in app["expected_keywords"] if kw.lower() in text_blob.lower()]
        per_app.append(
            {
                "application_id": app["application_id"],
                "expected": expected,
                "actual": actual,
                "agree": actual == expected,
                "citations": len(citations),
                "policy_docs_cited": sorted(doc_ids),
                "keywords_expected": app["expected_keywords"],
                "keywords_hit": keywords_hit,
                "keywords_ok": len(keywords_hit) == len(app["expected_keywords"]),
            }
        )

    n = len(per_app)
    decided = [r for r in per_app if r["actual"] != "clarify"]
    metrics = {
        "n_applications": n,
        "decision_agreement": sum(r["agree"] for r in per_app) / n,
        "citation_rate": sum(1 for r in decided if r["citations"] > 0) / len(decided) if decided else 0.0,
        "policy_hit_rate": sum(1 for r in decided if len(r["policy_docs_cited"]) >= 2) / len(decided) if decided else 0.0,
        "clarify_trigger_rate": sum(1 for r in per_app if r["actual"] == "clarify") / n,
        "keyword_coverage": sum(r["keywords_ok"] for r in per_app) / n,
    }

    os.makedirs(os.path.join(ROOT, "eval"), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"metrics": metrics, "per_application": per_app}, f, indent=2)

    print(f"evaluated {n} applications -> {OUT}")
    for k, v in metrics.items():
        print(f"  {k}: {v:.3f}")
    mismatches = [r for r in per_app if not r["agree"]]
    for r in mismatches:
        print(f"  MISMATCH {r['application_id']}: expected {r['expected']}, got {r['actual']}")


if __name__ == "__main__":
    main()

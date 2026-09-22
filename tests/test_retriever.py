import os

from src.tools.retriever import PolicyIndex

POLICIES = os.path.join(os.path.dirname(__file__), "..", "policies")


def test_cibil_query_hits_credit_policy():
    index = PolicyIndex(POLICIES)
    results = index.search("What is the minimum CIBIL score for a personal loan?", top_k=3)
    assert results, "expected at least one result"
    assert results[0]["doc_id"] == "02_credit_policy.md"


def test_foir_query_hits_credit_policy():
    index = PolicyIndex(POLICIES)
    results = index.search("maximum FOIR debt to income ratio limit", top_k=3)
    assert results[0]["doc_id"] == "02_credit_policy.md"


def test_citation_shape():
    index = PolicyIndex(POLICIES)
    results = index.search("documentation checklist", top_k=2)
    for c in results:
        assert {"doc_id", "chunk_id", "heading", "text"} <= set(c.keys())
        assert c["text"]


def test_multi_search_dedupes():
    index = PolicyIndex(POLICIES)
    results = index.multi_search(["CIBIL score", "minimum CIBIL eligibility"], top_k=5)
    chunk_ids = [c["chunk_id"] for c in results]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_list_documents():
    index = PolicyIndex(POLICIES)
    docs = index.list_documents()
    assert len(docs) == 5
    assert docs[0]["doc_id"] == "01_eligibility.md"

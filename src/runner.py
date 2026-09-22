"""Graph runner: builds the workflow once per process with a shared policy index."""

from __future__ import annotations

import os

from src.nodes import build_graph
from src.tools.retriever import PolicyIndex

_POLICIES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "policies")

_index: PolicyIndex | None = None
_graph = None


def get_index() -> PolicyIndex:
    global _index
    if _index is None:
        _index = PolicyIndex(_POLICIES_DIR)
    return _index


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_underwrite(application: dict) -> dict:
    """Run the full underwriting graph for one application dict."""
    state = {"application": application, "_policy_index": get_index()}
    return get_graph().run(state)

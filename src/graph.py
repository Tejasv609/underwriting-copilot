"""A tiny hand-rolled state graph: nodes + conditional edges, no dependencies.

Each node is a function ``(state: dict) -> tuple[dict, str]`` returning
(state updates, trace note). Conditional edges route on a router function.
The full execution trace (list of node transitions) is recorded for
explainability and returned with every run.
"""

from __future__ import annotations

from typing import Callable

END = "__end__"
NodeFn = Callable[[dict], tuple[dict, str]]


class StateGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, NodeFn] = {}
        self._edges: dict[str, str | tuple[Callable[[dict], str], dict[str, str]]] = {}
        self._entry: str | None = None

    def add_node(self, name: str, fn: NodeFn) -> "StateGraph":
        self._nodes[name] = fn
        return self

    def add_edge(self, src: str, dst: str) -> "StateGraph":
        self._edges[src] = dst
        return self

    def add_conditional_edges(
        self, src: str, router: Callable[[dict], str], mapping: dict[str, str]
    ) -> "StateGraph":
        self._edges[src] = (router, mapping)
        return self

    def set_entry(self, name: str) -> "StateGraph":
        self._entry = name
        return self

    def run(self, initial_state: dict) -> dict:
        if self._entry is None:
            raise ValueError("entry node not set")
        state = dict(initial_state)
        trace: list[dict[str, str]] = []
        current = self._entry
        steps = 0
        while current != END:
            steps += 1
            if steps > 50:
                raise RuntimeError("graph exceeded max steps (possible cycle)")
            node = self._nodes[current]
            updates, note = node(state)
            state.update(updates)
            edge = self._edges.get(current, END)
            if isinstance(edge, tuple):
                router, mapping = edge
                nxt = mapping[router(state)]
            else:
                nxt = edge
            trace.append({"from": current, "to": nxt, "note": note})
            current = nxt
        state["trace"] = trace
        return state

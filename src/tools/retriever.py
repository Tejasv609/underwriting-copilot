"""Hybrid retrieval over policies/: BM25 (rank-bm25) + TF-IDF cosine (numpy),
fused with Reciprocal Rank Fusion. Fully deterministic, no network, no models.

Citations are returned as {"doc_id", "chunk_id", "heading", "text"} dicts.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field

import numpy as np
from rank_bm25 import BM25Okapi

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


@dataclass
class Chunk:
    doc_id: str
    chunk_id: str
    heading: str
    text: str
    tokens: list[str] = field(default_factory=list)


def chunk_markdown(doc_id: str, text: str) -> list[Chunk]:
    """Split a markdown doc into one chunk per ## section (H1 becomes its own chunk)."""
    chunks: list[Chunk] = []
    current_heading = ""
    current_lines: list[str] = []
    index = 0

    def flush():
        nonlocal index
        body = "\n".join(current_lines).strip()
        if body:
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    chunk_id=f"{doc_id}#c{index}",
                    heading=current_heading or doc_id,
                    text=body,
                    tokens=tokenize((current_heading + " " + body)),
                )
            )
            index += 1

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_heading = line[3:].strip()
            current_lines = []
        elif line.startswith("# "):
            flush()
            current_heading = line[2:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    flush()
    return chunks


class PolicyIndex:
    def __init__(self, policies_dir: str):
        self.policies_dir = policies_dir
        self.chunks: list[Chunk] = []
        for fname in sorted(os.listdir(policies_dir)):
            if not fname.endswith(".md"):
                continue
            with open(os.path.join(policies_dir, fname), encoding="utf-8") as f:
                self.chunks.extend(chunk_markdown(fname, f.read()))
        if not self.chunks:
            raise ValueError(f"no markdown policies found in {policies_dir}")

        corpus_tokens = [c.tokens for c in self.chunks]
        self._bm25 = BM25Okapi(corpus_tokens)

        # TF-IDF with numpy
        vocab: dict[str, int] = {}
        for tokens in corpus_tokens:
            for t in set(tokens):
                if t not in vocab:
                    vocab[t] = len(vocab)
        self._vocab = vocab
        n_docs = len(corpus_tokens)
        df = np.zeros(len(vocab))
        tf = np.zeros((n_docs, len(vocab)))
        for i, tokens in enumerate(corpus_tokens):
            counts: dict[str, int] = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1
            for t, c in counts.items():
                j = vocab[t]
                tf[i, j] = c / len(tokens)
                df[j] += 1
        idf = np.log((1 + n_docs) / (1 + df)) + 1.0
        tfidf = tf * idf
        norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._tfidf = tfidf / norms
        self._idf = idf

    # -- internals ---------------------------------------------------------
    def _bm25_ranking(self, query_tokens: list[str]) -> list[int]:
        scores = self._bm25.get_scores(query_tokens)
        return list(np.argsort(-scores, kind="stable"))

    def _tfidf_ranking(self, query_tokens: list[str]) -> list[int]:
        vec = np.zeros(len(self._vocab))
        counts: dict[str, int] = {}
        for t in query_tokens:
            if t in self._vocab:
                counts[t] = counts.get(t, 0) + 1
        if not counts or not query_tokens:
            return list(range(len(self.chunks)))
        for t, c in counts.items():
            vec[self._vocab[t]] = (c / len(query_tokens)) * self._idf[self._vocab[t]]
        norm = np.linalg.norm(vec)
        if norm == 0:
            return list(range(len(self.chunks)))
        vec = vec / norm
        sims = self._tfidf @ vec
        return list(np.argsort(-sims, kind="stable"))

    # -- public ------------------------------------------------------------
    def search(self, query: str, top_k: int = 5, rrf_k: int = 60) -> list[dict]:
        tokens = tokenize(query)
        rankings = [self._bm25_ranking(tokens), self._tfidf_ranking(tokens)]
        fused: dict[int, float] = {}
        for ranking in rankings:
            for rank, doc_idx in enumerate(ranking):
                fused[doc_idx] = fused.get(doc_idx, 0.0) + 1.0 / (rrf_k + rank + 1)
        ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [self._citation(i) for i, _ in ordered]

    def multi_search(self, queries: list[str], top_k: int = 8) -> list[dict]:
        """Run several queries, dedupe chunks, return top_k by best RRF rank."""
        seen: dict[str, dict] = {}
        for q in queries:
            for cit in self.search(q, top_k=top_k):
                if cit["chunk_id"] not in seen:
                    seen[cit["chunk_id"]] = cit
        # stable order: keep first-seen (relevance) order, truncate
        return list(seen.values())[:top_k]

    def _citation(self, idx: int) -> dict:
        c = self.chunks[idx]
        return {
            "doc_id": c.doc_id,
            "chunk_id": c.chunk_id,
            "heading": c.heading,
            "text": c.text[:600],
        }

    def list_documents(self) -> list[dict]:
        docs: dict[str, int] = {}
        for c in self.chunks:
            docs[c.doc_id] = docs.get(c.doc_id, 0) + 1
        return [{"doc_id": d, "chunks": n} for d, n in sorted(docs.items())]

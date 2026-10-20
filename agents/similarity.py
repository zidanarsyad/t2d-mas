"""Duplicate search for the live demo: TF-IDF over character n-grams plus cosine similarity.

The idea report (section 3.1) compares tickets as vectors with cosine similarity
and allows "embedding/TF-IDF sederhana". Character 3-5-grams cope with typos,
slang and Indonesian affixes ("bayar", "pembayaran") without a language model.
The offline research module in triage/ uses MiniLM sentence embeddings + FAISS
for the same task.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Iterable, Sequence

from agents.text import normalize_for_matching

NGRAM_SIZES = (3, 4, 5)


def cosine_dense(a: Sequence[float], b: Sequence[float]) -> float:
    """Plain cosine similarity of two equal-length vectors (the idea's worked example)."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return 0.0 if norm == 0 else dot / norm


def char_ngrams(text: str) -> Counter[str]:
    padded = f" {normalize_for_matching(text)} "
    return Counter(padded[i:i + n] for n in NGRAM_SIZES for i in range(len(padded) - n + 1))


class TfidfCosine:
    """Fit document frequencies once on a background corpus, then compare any two texts.

    Using a fixed background corpus keeps scores stable while new tickets arrive.
    """

    def __init__(self, background: Iterable[str]) -> None:
        documents = [set(char_ngrams(text)) for text in background]
        self.document_count = len(documents)
        self.document_frequency = Counter(gram for grams in documents for gram in grams)

    def _idf(self, gram: str) -> float:
        return math.log((1 + self.document_count) / (1 + self.document_frequency[gram])) + 1.0

    def vector(self, text: str) -> dict[str, float]:
        counts = char_ngrams(text)
        weights = {gram: (1 + math.log(count)) * self._idf(gram) for gram, count in counts.items()}
        norm = math.sqrt(sum(value * value for value in weights.values())) or 1.0
        return {gram: value / norm for gram, value in weights.items()}

    def similarity(self, a: str, b: str) -> float:
        left, right = self.vector(a), self.vector(b)
        if len(left) > len(right):
            left, right = right, left
        return sum(value * right.get(gram, 0.0) for gram, value in left.items())

    def best_matches(self, text: str, candidates: Sequence[tuple[str, str]], top: int = 3) -> list[tuple[str, float]]:
        """Rank (ticket_id, text) candidates by similarity to `text`."""
        query = self.vector(text)
        scored = []
        for ticket_id, candidate in candidates:
            other = self.vector(candidate)
            scored.append((ticket_id, sum(value * other.get(gram, 0.0) for gram, value in query.items())))
        return sorted(scored, key=lambda item: (-item[1], item[0]))[:top]

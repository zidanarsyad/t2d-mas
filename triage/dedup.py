"""Exact cosine-similarity search using FAISS inner product on unit vectors."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

import numpy as np

from .embedder import encode as default_encode


class DedupAction(str, Enum):
    AUTO_LINK = "auto-link"
    HUMAN_REVIEW = "human-review"
    NEW_TICKET = "new-ticket"


@dataclass(frozen=True)
class DedupDecision:
    action: DedupAction
    best_match_id: str | None
    score: float


def decision_for_score(score: float, tau: float = 0.85) -> DedupAction:
    """Apply the three requested score bands, including the 0.70 boundary."""
    if score >= tau:
        return DedupAction.AUTO_LINK
    if score >= 0.70:
        return DedupAction.HUMAN_REVIEW
    return DedupAction.NEW_TICKET


class DuplicateDetector:
    """In-memory exact nearest-neighbor index for a course-sized ticket set."""

    def __init__(self, embed: Callable[[list[str]], np.ndarray] = default_encode) -> None:
        self._embed = embed
        self._index = None
        self._ticket_ids: list[str] = []
        self._dimension: int | None = None

    def _faiss(self):
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("Install triage/requirements.txt to use FAISS") from exc
        return faiss

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim != 2:
            raise ValueError("Embeddings must be a 2D array")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)

    def add(self, ticket_id: str, text: str) -> None:
        """Add one ticket; duplicate IDs are rejected to keep FAISS positions stable."""
        if ticket_id in self._ticket_ids:
            raise ValueError(f"ticket_id already indexed: {ticket_id}")
        vector = self._normalize(self._embed([text]))
        if vector.shape[0] != 1 or vector.shape[1] == 0:
            raise ValueError("Embedder must return one non-empty vector for one text")
        if self._dimension is None:
            self._dimension = int(vector.shape[1])
            self._index = self._faiss().IndexFlatIP(self._dimension)
        elif vector.shape[1] != self._dimension:
            raise ValueError("Embedding dimension changed after the index was created")
        self._index.add(vector)
        self._ticket_ids.append(ticket_id)

    def search(self, text: str, k: int = 10) -> list[tuple[str, float]]:
        """Return best matches as (ticket_id, cosine_score), highest score first."""
        if k < 1:
            raise ValueError("k must be at least 1")
        if not self._ticket_ids:
            return []
        query = self._normalize(self._embed([text]))
        if query.shape[1] != self._dimension:
            raise ValueError("Query embedding dimension does not match the index")
        scores, positions = self._index.search(query, min(k, len(self._ticket_ids)))
        return [
            (self._ticket_ids[int(position)], float(score))
            for position, score in zip(positions[0], scores[0])
            if position >= 0
        ]

    def decision(self, text: str, tau: float = 0.85) -> DedupDecision:
        """Expose all three routing zones without conflating review with auto-link."""
        matches = self.search(text, k=1)
        if not matches:
            return DedupDecision(DedupAction.NEW_TICKET, None, 0.0)
        match_id, score = matches[0]
        return DedupDecision(decision_for_score(score, tau), match_id, score)

    def is_duplicate(self, text: str, tau: float = 0.85) -> tuple[bool, str | None, float]:
        """Return true only for auto-link; review-band matches return false with evidence."""
        result = self.decision(text, tau)
        return result.action is DedupAction.AUTO_LINK, result.best_match_id, result.score

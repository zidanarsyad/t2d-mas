"""Sentence-transformer embeddings with L2 normalization."""
from __future__ import annotations

import os
from dataclasses import dataclass
from threading import Lock

import numpy as np


@dataclass(frozen=True)
class EmbedderConfig:
    """Embedding settings; downloads are opt-in and inference always runs locally."""

    model_name: str = "all-MiniLM-L6-v2"
    batch_size: int = 32
    allow_remote_download: bool = False


class SentenceEmbedder:
    """Lazy wrapper around SentenceTransformer so imports stay lightweight."""

    def __init__(self, config: EmbedderConfig | None = None) -> None:
        self.config = config or EmbedderConfig(
            model_name=os.getenv("TRIAGE_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            allow_remote_download=os.getenv("TRIAGE_ALLOW_MODEL_DOWNLOAD", "false").lower()
            in {"1", "true", "yes"},
        )
        self._model = None
        self._lock = Lock()

    def _load_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                    except ImportError as exc:
                        raise RuntimeError(
                            "Install triage/requirements.txt to use sentence embeddings"
                        ) from exc
                    try:
                        self._model = SentenceTransformer(
                            self.config.model_name,
                            local_files_only=not self.config.allow_remote_download,
                        )
                    except OSError as exc:
                        if not self.config.allow_remote_download:
                            raise RuntimeError(
                                f"Embedding model {self.config.model_name!r} is not cached locally. "
                                "Download the public model once or set TRIAGE_ALLOW_MODEL_DOWNLOAD=true."
                            ) from exc
                        raise
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode texts as float32 vectors with unit L2 norm."""
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        vectors = self._load_model().encode(
            texts,
            batch_size=self.config.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vectors = np.asarray(vectors, dtype=np.float32)
        # Normalize once more to guarantee the API contract across model versions.
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)


_DEFAULT_EMBEDDER = SentenceEmbedder()


def encode(texts: list[str]) -> np.ndarray:
    """Module-level convenience function used by the triage pipeline."""
    return _DEFAULT_EMBEDDER.encode(texts)

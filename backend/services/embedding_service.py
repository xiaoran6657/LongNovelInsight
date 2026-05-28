"""v0.3 Step 10 — Optional semantic rerank skeleton.

Disabled by default (ENABLE_SEMANTIC_RERANK=False). This module provides
the extension point for future embedding-based reranking without adding
vector database dependencies.
"""

import logging

from config import ENABLE_SEMANTIC_RERANK

logger = logging.getLogger(__name__)


def semantic_rerank(
    candidates: list[dict],
    query: str,
    topic_id: str,
) -> tuple[list[dict], str | None]:
    """Re-rank candidates using embedding similarity.

    Returns (reranked_candidates, warning). When disabled, returns the
    original candidates unchanged with a warning message.
    """
    if not ENABLE_SEMANTIC_RERANK:
        return (
            candidates,
            "Semantic rerank is disabled. Enable it via ENABLE_SEMANTIC_RERANK config.",
        )

    # Future: compute query embedding, load/embed candidates, cosine-sort.
    return candidates, None


class EmbeddingProvider:
    """Abstract base for embedding providers (OpenAI-compatible endpoint).

    This is a skeleton — not wired to any real API in v0.3.0.
    """

    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for each input text."""
        raise NotImplementedError("EmbeddingProvider.embed is not implemented")

# Assistant Module - RAG: Reranker (Cross-Encoder Style)
"""
Two-stage reranking using Ollama embeddings for cross-encoder-style scoring.

Pipeline:
  vector search (top 75) → reranker scoring → select top 10

The reranker works by:
1. Batch-embedding query+passage pairs via Ollama's /api/embed endpoint
2. Computing cosine similarity between the query embedding and each cross-embedding
3. Combining the reranker score with the original retrieval score

This provides cross-encoder-like scoring without dedicated cross-encoder
models or heavy dependencies (PyTorch, sentence-transformers).
"""
import logging
import math
import time
from typing import List, Dict, Any, Optional

from modules.assistant.rag.embeddings import get_embedding_service

logger = logging.getLogger(__name__)

MAX_PASSAGE_LENGTH = 600  # chars to truncate passage for embedding


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class Reranker:
    """Cross-encoder-style reranker using Ollama embeddings.

    Reranks candidate chunks by embedding query+passage concatenations
    and computing relevance scores against the standalone query embedding.

    The final score is a weighted combination of:
      - original retrieval score (vector similarity)
      - reranker score (cross-encoded cosine similarity)
    """

    def __init__(self, model: str = None):
        """
        Args:
            model: Embedding model override for reranking.
                   None = use the default embedding model.
        """
        self.model = model

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        final_k: int = 10,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Rerank candidates using cross-encoder scoring.

        Args:
            query: The user's question.
            candidates: List of retrieval results with 'metadata', 'score'.
            final_k: Number of top results to return.
            query_embedding: Pre-computed query embedding (avoids redundant call).

        Returns:
            Reranked list (top final_k) with added 'reranker_score' field.
        """
        if not candidates:
            return []

        if len(candidates) <= final_k:
            for c in candidates:
                c['reranker_score'] = c.get('score', 0)
            return candidates

        t0 = time.monotonic()
        embedding_service = get_embedding_service()

        # Use custom model if specified
        original_model = embedding_service.model
        if self.model:
            embedding_service.set_model(self.model)

        try:
            # Step 1: Get query embedding if not provided
            if query_embedding is None:
                query_embedding = embedding_service.embed_text(query)
                if query_embedding is None:
                    logger.error("[Reranker] Failed to embed query — returning original order")
                    return candidates[:final_k]

            # Step 2: Create cross-encoded texts (query + passage)
            cross_texts = []
            for c in candidates:
                chunk_text = c.get('metadata', {}).get('chunk_text', '')[:MAX_PASSAGE_LENGTH]
                title = c.get('metadata', {}).get('title', '')
                cross_text = f"search_query: {query}\nsearch_document: {title} — {chunk_text}"
                cross_texts.append(cross_text)

            # Step 3: Batch embed all cross-texts (single Ollama call)
            cross_embeddings = embedding_service.embed_batch_native(cross_texts)

            # Step 4: Compute reranker scores (cosine similarity)
            for i, c in enumerate(candidates):
                cross_emb = cross_embeddings[i] if i < len(cross_embeddings) else None
                if cross_emb is not None:
                    reranker_score = _cosine_similarity(query_embedding, cross_emb)
                    c['reranker_score'] = max(0.0, reranker_score)
                else:
                    # Penalty for failed embedding
                    c['reranker_score'] = c.get('score', 0) * 0.5

            # Step 5: Combine scores
            # final_score = 0.4 * original_score + 0.6 * reranker_score
            for c in candidates:
                original = c.get('score', 0)
                reranker = c.get('reranker_score', 0)
                c['pre_rerank_score'] = original
                c['score'] = 0.4 * original + 0.6 * reranker

            # Sort by final combined score
            candidates.sort(key=lambda x: x['score'], reverse=True)

            elapsed = time.monotonic() - t0
            logger.info(
                "[Reranker] Reranked %d → %d candidates in %.2fs (model=%s)",
                len(candidates), min(final_k, len(candidates)), elapsed,
                self.model or 'default',
            )

            return candidates[:final_k]

        except Exception as e:
            logger.error("[Reranker] Reranking failed: %s — returning original order", e)
            return candidates[:final_k]

        finally:
            # Restore original model
            if self.model:
                embedding_service.set_model(original_model)


# Module-level singleton
_reranker: Optional[Reranker] = None


def get_reranker(model: str = None) -> Reranker:
    """Return the module-level Reranker singleton."""
    global _reranker
    if _reranker is None or (model and _reranker.model != model):
        _reranker = Reranker(model=model)
    return _reranker

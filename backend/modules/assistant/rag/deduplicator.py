# Assistant Module - RAG: Semantic Deduplication
"""
Removes near-duplicate chunks from retrieval results to maximise
context window diversity.

Method:
1. After selecting candidate chunks, compute cosine similarity between them
2. Remove chunks that are too similar (above threshold) to a higher-ranked chunk
3. Preserve the highest-ranked chunk from each near-duplicate group

Default threshold: 0.92 cosine similarity.
"""
import logging
import math
import time
from typing import List, Dict, Any, Tuple

from modules.assistant.rag.embeddings import get_embedding_service

logger = logging.getLogger(__name__)

DEFAULT_DEDUP_THRESHOLD = 0.92


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticDeduplicator:
    """Remove near-duplicate chunks from retrieval results."""

    def deduplicate(
        self,
        results: List[Dict[str, Any]],
        threshold: float = DEFAULT_DEDUP_THRESHOLD,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Remove near-duplicate chunks.

        Assumes results are already sorted by score (highest first).
        Uses greedy deduplication: iterates in rank order and removes
        any chunk that is too similar to an already-kept chunk.

        Args:
            results: List of retrieval result dicts (must have 'metadata.chunk_text').
            threshold: Cosine similarity threshold for duplicates (0–1).

        Returns:
            Tuple of (deduplicated_results, removed_count).
        """
        if len(results) <= 1:
            return results, 0

        t0 = time.monotonic()

        # Embed all chunk texts in one batch
        embedding_service = get_embedding_service()
        texts = [
            r.get('metadata', {}).get('chunk_text', '')
            for r in results
        ]
        embeddings = embedding_service.embed_batch_native(texts)

        # Greedy deduplication: iterate in score order, remove near-duplicates
        keep: List[Dict[str, Any]] = []
        keep_embeddings: List[List[float]] = []
        removed = 0

        for i, result in enumerate(results):
            emb = embeddings[i] if i < len(embeddings) else None
            if emb is None:
                # Can't compute similarity — keep by default
                keep.append(result)
                continue

            is_duplicate = False
            for kept_emb in keep_embeddings:
                sim = _cosine_similarity(emb, kept_emb)
                if sim > threshold:
                    is_duplicate = True
                    break

            if is_duplicate:
                removed += 1
                result['_dedup_removed'] = True
            else:
                keep.append(result)
                keep_embeddings.append(emb)

        elapsed = time.monotonic() - t0
        logger.info(
            "[Dedup] %d → %d results (removed %d) in %.2fs (threshold=%.2f)",
            len(results), len(keep), removed, elapsed, threshold,
        )

        return keep, removed

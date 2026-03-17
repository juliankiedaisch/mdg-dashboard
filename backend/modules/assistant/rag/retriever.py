# Assistant Module - RAG: Retriever
"""
Handles retrieval of relevant documents from the vector store.

Full pipeline (when all features are enabled):
  1. Vector search  (top initial_retrieval_k)
  2. BM25 keyword search  (top initial_retrieval_k / 2)
  3. Merge & combined scoring  (vector_weight × v + keyword_weight × k)
  4. Tag-based score weighting
  5. Cross-encoder reranking  → final_context_k
  6. Top_K distribution  (optional percentage caps per source_type)
  7. Semantic deduplication  (remove near-duplicates)
  8. Parent-chunk expansion  (replace children with parent chunks)

All stages are optional and configurable.  When no advanced features are
enabled, the retriever falls back to simple vector top-k.

Retrieval diagnostics are collected at every stage and returned alongside
results for the admin debug view.
"""
import logging
import math
import time
from typing import List, Dict, Any, Optional, Tuple

from modules.assistant.rag.embeddings import get_embedding_service
from modules.assistant.rag.vector_store import get_vector_store
from modules.assistant.rag.bm25_index import get_bm25_index
from modules.assistant.rag.reranker import get_reranker
from modules.assistant.rag.deduplicator import SemanticDeduplicator

logger = logging.getLogger(__name__)


class Retriever:
    """Searches for relevant documents using a multi-stage retrieval pipeline.

    Supports:
    - Hybrid search (vector + BM25 keyword)
    - Cross-encoder reranking
    - Tag-based score weighting
    - Intelligent Top_K distribution across source types
    - Semantic deduplication
    - Parent-chunk expansion
    - Retrieval diagnostics
    """

    def __init__(self, top_k: int = 5, rerank: bool = False):
        self.top_k = top_k
        self.rerank = rerank
        self._deduplicator = SemanticDeduplicator()

    def retrieve(
        self,
        query: str,
        top_k: int = None,
        source_filter: Optional[str] = None,
        permission_tags: Optional[List[str]] = None,
        retrieval_config: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Retrieve the most relevant documents for a query.

        Returns:
            Tuple of (results_list, diagnostics_dict).
        """
        t_total_start = time.monotonic()

        cfg = retrieval_config or {}
        pipeline_cfg = cfg.get('pipeline_config', {})

        # ── Resolve effective settings ──────────────────────────────
        k = cfg.get('top_k') or top_k or self.top_k
        tag_weights = cfg.get('tag_weights') or {}
        top_k_distribution = cfg.get('top_k_distribution') or {}

        # Pipeline feature flags
        reranker_enabled = pipeline_cfg.get('reranker_enabled', False)
        hybrid_enabled = pipeline_cfg.get('hybrid_enabled', False)
        parent_child_enabled = pipeline_cfg.get('parent_child_enabled', False)
        dedup_enabled = pipeline_cfg.get('dedup_enabled', False)

        initial_retrieval_k = pipeline_cfg.get('initial_retrieval_k', 75)
        final_context_k = pipeline_cfg.get('final_context_k', 10)
        vector_weight = pipeline_cfg.get('vector_weight', 0.7)
        keyword_weight = pipeline_cfg.get('keyword_weight', 0.3)
        dedup_threshold = pipeline_cfg.get('dedup_threshold', 0.92)
        reranker_model = pipeline_cfg.get('reranker_model', '') or None

        # If advanced features active, use their k values; otherwise fall back
        any_advanced = reranker_enabled or hybrid_enabled or dedup_enabled
        effective_fetch_k = initial_retrieval_k if any_advanced else (
            k * 3 if (top_k_distribution or tag_weights) else k
        )
        effective_final_k = final_context_k if reranker_enabled else k

        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        logger.info(
            "[Retriever] query=%r top_k=%d fetch_k=%d final_k=%d "
            "hybrid=%s reranker=%s dedup=%s parent_child=%s "
            "permission_tags=%s embed_model=%s",
            query[:80], k, effective_fetch_k, effective_final_k,
            hybrid_enabled, reranker_enabled, dedup_enabled, parent_child_enabled,
            permission_tags, embedding_service.model,
        )

        diagnostics: Dict[str, Any] = {
            'query': query,
            'config': {
                'top_k': k,
                'initial_retrieval_k': effective_fetch_k,
                'final_context_k': effective_final_k,
                'reranker_enabled': reranker_enabled,
                'hybrid_enabled': hybrid_enabled,
                'dedup_enabled': dedup_enabled,
                'parent_child_enabled': parent_child_enabled,
                'vector_weight': vector_weight,
                'keyword_weight': keyword_weight,
                'tag_weights': tag_weights,
                'top_k_distribution': top_k_distribution,
            },
            'stages': {},
        }

        # ── Stage 1: Generate query embedding ──────────────────────
        t0 = time.monotonic()
        query_embedding = embedding_service.embed_text(query)
        if query_embedding is None:
            logger.error("[Retriever] Failed to generate query embedding")
            diagnostics['error'] = 'Embedding generation failed'
            return [], diagnostics
        diagnostics['stages']['embedding'] = {
            'duration_ms': round((time.monotonic() - t0) * 1000, 1),
            'dimension': len(query_embedding),
        }

        # ── Stage 2: Vector search ─────────────────────────────────
        t0 = time.monotonic()
        vector_results = vector_store.search(
            query_vector=query_embedding,
            top_k=effective_fetch_k,
            source_filter=source_filter,
            permission_tags=permission_tags,
        )
        logger.info("[Retriever] Vector search returned %d results", len(vector_results))
        diagnostics['stages']['vector_search'] = {
            'count': len(vector_results),
            'duration_ms': round((time.monotonic() - t0) * 1000, 1),
            'top_results': [
                {
                    'id': r.get('id', ''),
                    'title': r.get('metadata', {}).get('title', '')[:60],
                    'source_type': r.get('metadata', {}).get('source_type', ''),
                    'vector_score': round(r.get('score', 0), 4),
                }
                for r in vector_results[:10]
            ],
        }

        # ── Stage 3: BM25 keyword search (hybrid) ─────────────────
        bm25_results = []
        if hybrid_enabled:
            t0 = time.monotonic()
            bm25_index = get_bm25_index()
            if bm25_index.is_built:
                bm25_results = bm25_index.search(
                    query=query,
                    top_k=effective_fetch_k // 2,
                    permission_tags=permission_tags,
                )
                logger.info("[Retriever] BM25 search returned %d results", len(bm25_results))
            else:
                logger.warning("[Retriever] BM25 index not built — skipping keyword search")

            diagnostics['stages']['keyword_search'] = {
                'count': len(bm25_results),
                'duration_ms': round((time.monotonic() - t0) * 1000, 1),
                'index_built': bm25_index.is_built,
                'index_size': bm25_index.N,
                'top_results': [
                    {
                        'id': r.get('id', ''),
                        'title': r.get('metadata', {}).get('title', '')[:60],
                        'bm25_score': round(r.get('bm25_score', 0), 4),
                    }
                    for r in bm25_results[:10]
                ],
            }

        # ── Stage 4: Merge results (hybrid scoring) ───────────────
        if hybrid_enabled and bm25_results:
            t0 = time.monotonic()
            merged = self._merge_hybrid_results(
                vector_results, bm25_results,
                vector_weight, keyword_weight,
            )
            diagnostics['stages']['hybrid_merge'] = {
                'input_vector': len(vector_results),
                'input_keyword': len(bm25_results),
                'merged_count': len(merged),
                'duration_ms': round((time.monotonic() - t0) * 1000, 1),
            }
        else:
            merged = vector_results

        # ── Stage 5: Tag-based score weighting ─────────────────────
        if tag_weights:
            merged = self._apply_tag_weights(merged, tag_weights)
            diagnostics['stages']['tag_weighting'] = {
                'weights_applied': tag_weights,
                'count': len(merged),
            }

        # ── Stage 6: Cross-encoder reranking ───────────────────────
        if reranker_enabled and len(merged) > effective_final_k:
            t0 = time.monotonic()
            reranker = get_reranker(model=reranker_model)
            merged = reranker.rerank(
                query=query,
                candidates=merged,
                final_k=effective_final_k,
                query_embedding=query_embedding,
            )
            diagnostics['stages']['reranking'] = {
                'model': reranker_model or 'default',
                'output_count': len(merged),
                'duration_ms': round((time.monotonic() - t0) * 1000, 1),
                'top_results': [
                    {
                        'id': r.get('id', ''),
                        'title': r.get('metadata', {}).get('title', '')[:60],
                        'pre_rerank_score': round(r.get('pre_rerank_score', 0), 4),
                        'reranker_score': round(r.get('reranker_score', 0), 4),
                        'final_score': round(r.get('score', 0), 4),
                    }
                    for r in merged[:10]
                ],
            }
        elif not reranker_enabled:
            # No reranking — apply simple truncation
            merged = merged[:effective_final_k if any_advanced else k]

        # ── Stage 7: Top_K distribution ────────────────────────────
        if top_k_distribution:
            target_k = effective_final_k if any_advanced else k
            merged = self._apply_top_k_distribution(merged, target_k, top_k_distribution)
            diagnostics['stages']['top_k_distribution'] = {
                'distribution': top_k_distribution,
                'output_count': len(merged),
            }

        # ── Stage 8: Semantic deduplication ────────────────────────
        if dedup_enabled and len(merged) > 1:
            t0 = time.monotonic()
            merged, removed = self._deduplicator.deduplicate(merged, dedup_threshold)
            diagnostics['stages']['deduplication'] = {
                'threshold': dedup_threshold,
                'removed': removed,
                'output_count': len(merged),
                'duration_ms': round((time.monotonic() - t0) * 1000, 1),
            }

        # ── Stage 9: Parent-chunk expansion ────────────────────────
        if parent_child_enabled:
            t0 = time.monotonic()
            merged, expansion_info = self._expand_to_parents(merged)
            diagnostics['stages']['parent_expansion'] = {
                'duration_ms': round((time.monotonic() - t0) * 1000, 1),
                **expansion_info,
            }

        # ── Finalize diagnostics ───────────────────────────────────
        diagnostics['total_duration_ms'] = round(
            (time.monotonic() - t_total_start) * 1000, 1,
        )
        diagnostics['final_count'] = len(merged)
        diagnostics['final_results'] = [
            {
                'id': r.get('id', ''),
                'title': r.get('metadata', {}).get('title', '')[:80],
                'source': r.get('metadata', {}).get('source', ''),
                'source_type': r.get('metadata', {}).get('source_type', ''),
                'score': round(r.get('score', 0), 4),
                'vector_score': round(r.get('vector_score', r.get('score', 0)), 4),
                'keyword_score': round(r.get('keyword_score', 0), 4),
                'reranker_score': round(r.get('reranker_score', 0), 4),
                'chunk_text_preview': r.get('metadata', {}).get('chunk_text', '')[:150],
            }
            for r in merged
        ]

        logger.info(
            "[Retriever] Pipeline complete: %d results in %.0fms",
            len(merged), diagnostics['total_duration_ms'],
        )

        return merged, diagnostics

    # ── Hybrid merge ────────────────────────────────────────────────

    def _merge_hybrid_results(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        vector_weight: float,
        keyword_weight: float,
    ) -> List[Dict[str, Any]]:
        """Merge vector and BM25 results with weighted scoring.

        BM25 scores are normalised to [0, 1] before merging.
        """
        max_bm25 = max((r.get('bm25_score', 0) for r in bm25_results), default=1) or 1

        bm25_by_id: Dict[str, Dict] = {}
        for r in bm25_results:
            bm25_by_id[r['id']] = r

        seen_ids = set()
        merged: List[Dict[str, Any]] = []

        for r in vector_results:
            rid = r.get('id', '')
            seen_ids.add(rid)
            vector_score = r.get('score', 0)
            r['vector_score'] = vector_score

            bm25_match = bm25_by_id.get(rid)
            if bm25_match:
                kw_score = bm25_match.get('bm25_score', 0) / max_bm25
                r['keyword_score'] = kw_score
                r['score'] = (vector_weight * vector_score) + (keyword_weight * kw_score)
            else:
                r['keyword_score'] = 0.0
                r['score'] = vector_weight * vector_score

            merged.append(r)

        for r in bm25_results:
            if r['id'] not in seen_ids:
                kw_score_norm = r.get('bm25_score', 0) / max_bm25
                merged.append({
                    'id': r['id'],
                    'score': keyword_weight * kw_score_norm,
                    'vector_score': 0.0,
                    'keyword_score': kw_score_norm,
                    'metadata': r.get('metadata', {}),
                    '_bm25_only': True,
                })

        merged.sort(key=lambda x: x.get('score', 0), reverse=True)
        return merged

    # ── Tag weighting ───────────────────────────────────────────────

    def _apply_tag_weights(
        self,
        results: List[Dict[str, Any]],
        tag_weights: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """Multiply each result's score by the weight of its source_type tag."""
        for r in results:
            source_type = r.get('metadata', {}).get('source_type', 'unknown')
            weight = float(tag_weights.get(source_type, 1.0))
            original_score = r.get('score', 0)
            if 'original_score' not in r:
                r['original_score'] = original_score
            r['score'] = original_score * weight
            r['applied_weight'] = weight

        results.sort(key=lambda x: x['score'], reverse=True)
        return results

    # ── Top_K distribution ──────────────────────────────────────────

    def _apply_top_k_distribution(
        self,
        results: List[Dict[str, Any]],
        total_k: int,
        distribution: Dict[str, int],
    ) -> List[Dict[str, Any]]:
        """Select results respecting per-source-type percentage caps."""
        total_pct = sum(distribution.values()) or 100
        targets: Dict[str, int] = {}
        for stype, pct in distribution.items():
            targets[stype] = max(1, math.floor(total_k * (pct / total_pct)))

        buckets: Dict[str, List[Dict]] = {}
        for r in results:
            stype = r.get('metadata', {}).get('source_type', 'unknown')
            buckets.setdefault(stype, []).append(r)

        selected: List[Dict] = []
        remaining_pool: List[Dict] = []

        for stype, target_count in targets.items():
            bucket = buckets.pop(stype, [])
            selected.extend(bucket[:target_count])
            remaining_pool.extend(bucket[target_count:])

        for stype, bucket in buckets.items():
            remaining_pool.extend(bucket)

        remaining_slots = total_k - len(selected)
        if remaining_slots > 0 and remaining_pool:
            remaining_pool.sort(key=lambda x: x.get('score', 0), reverse=True)
            selected.extend(remaining_pool[:remaining_slots])

        selected.sort(key=lambda x: x.get('score', 0), reverse=True)
        return selected[:total_k]

    # ── Parent-chunk expansion ──────────────────────────────────────

    def _expand_to_parents(
        self,
        results: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Replace child chunks with their parent chunks.

        Groups children by ``parent_id``, fetches parent payloads from Qdrant,
        and returns parent chunks (score = max child score).
        Legacy chunks without ``chunk_role`` are passed through unchanged.
        """
        vector_store = get_vector_store()

        children_with_parent: Dict[str, List[Dict]] = {}
        legacy_results: List[Dict] = []

        for r in results:
            meta = r.get('metadata', {})
            role = meta.get('chunk_role', '')
            parent_id = meta.get('parent_id', '')

            if role == 'child' and parent_id:
                children_with_parent.setdefault(parent_id, []).append(r)
            else:
                legacy_results.append(r)

        if not children_with_parent:
            return results, {'children_grouped': 0, 'parents_fetched': 0, 'legacy': len(legacy_results)}

        parent_ids = list(children_with_parent.keys())
        parent_points = vector_store.get_points_by_ids(parent_ids)
        parent_by_id = {p['id']: p for p in parent_points}

        expanded: List[Dict] = []
        for parent_id, children in children_with_parent.items():
            parent_point = parent_by_id.get(parent_id)
            best_child = max(children, key=lambda c: c.get('score', 0))
            if parent_point:
                expanded.append({
                    'id': parent_id,
                    'score': best_child.get('score', 0),
                    'vector_score': best_child.get('vector_score', 0),
                    'keyword_score': best_child.get('keyword_score', 0),
                    'reranker_score': best_child.get('reranker_score', 0),
                    'metadata': parent_point.get('payload', {}),
                    '_expanded_from_children': len(children),
                })
            else:
                expanded.append(best_child)

        all_results = expanded + legacy_results
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)

        info = {
            'children_grouped': sum(len(c) for c in children_with_parent.values()),
            'unique_parents': len(children_with_parent),
            'parents_fetched': len(parent_points),
            'legacy': len(legacy_results),
            'output_count': len(all_results),
        }

        logger.info(
            "[Retriever] Parent expansion: %d children → %d parents + %d legacy",
            info['children_grouped'], info['parents_fetched'], info['legacy'],
        )

        return all_results, info


# Module-level singleton
_retriever: Optional[Retriever] = None


def get_retriever(top_k: int = 5, rerank: bool = False) -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever(top_k=top_k, rerank=rerank)
    return _retriever

# Assistant Module - Ingestion: Pipeline
"""
Document ingestion pipeline:
  Source → Fetch → Clean → Chunk → Embed → Store

Redesigned for high parallelism, GPU efficiency, and network-based services.

Architecture
────────────
• **Parallel fetching** — attachments are downloaded concurrently via a gevent
  pool so network I/O overlaps with extraction.
• **Distributed extraction** — documents are sent to Docling (primary) and
  Tika (fallback) services over HTTP.  The DoclingClient handles retries,
  circuit-breaking, and connection pooling.
• **Docling chunking** — when enabled, Docling's built-in hierarchical chunker
  produces semantically meaningful chunks, avoiding the need for the backend's
  overlap-based splitter.  Falls back to local chunking when Docling chunks
  are unavailable.
• **Batch embedding** — embeddings are generated in configurable batches via
  Ollama's ``/api/embed`` batch endpoint, maximising GPU throughput on the
  RTX 4080.
• **Resilient processing** — every document is processed individually.
  Failures are logged and skipped; they never stop the pipeline.
• **Streaming batches** — documents flow through the pipeline in rolling
  batches (``STREAM_BATCH``), so embedding starts while extraction is still
  in progress.
• **Metrics** — ``PipelineMetrics`` tracks per-document and per-stage
  statistics for performance tuning.

Supports full rebuild, incremental updates, and manual triggering.
"""
import logging
import os
import uuid as uuid_lib
import time
import gevent
from gevent.pool import Pool as GeventPool
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

from modules.assistant.ingestion.chunker import TextChunker, ParentChildChunker
from modules.assistant.ingestion.pipeline_metrics import PipelineMetrics
from modules.assistant.rag.embeddings import get_embedding_service
from modules.assistant.rag.vector_store import get_vector_store
from modules.assistant.rag.bm25_index import get_bm25_index
from modules.assistant.sources.base_source import BaseSource, DocumentChunk
from modules.assistant.sources.bookstack_source import BookStackSource
from modules.assistant.sources.filesystem_source import FilesystemSource
from modules.assistant.tasks.progress import emit_progress

logger = logging.getLogger(__name__)

class PipelineCancelledError(Exception):
    """Raised when the pipeline detects a cancellation request mid-processing.

    Propagated up through ingest_source / rebuild_all to the worker loop,
    which catches it and marks the task as 'cancelled' in the database.
    """

# ── Tunables (override via env) ────────────────────────────────────
# Documents buffered before triggering a chunk→embed→store cycle.
STREAM_BATCH = int(os.getenv('PIPELINE_STREAM_BATCH', '75'))

# Number of greenlets for parallel embedding within a batch.
EMBED_POOL_SIZE = int(os.getenv('PIPELINE_EMBED_POOL_SIZE', '4'))

# Embedding batch size sent to Ollama in a single /api/embed call.
# RTX 4080 with nomic-embed-text: 64–128 is optimal.
EMBED_BATCH_SIZE = int(os.getenv('PIPELINE_EMBED_BATCH_SIZE', '64'))

SOURCE_TYPES = {
    'bookstack': BookStackSource,
    'filesystem': FilesystemSource,
}


def get_source_connector(source_config: Dict[str, Any]) -> Optional[BaseSource]:
    """Factory: create a source connector from a source config dict."""
    source_type = source_config.get('source_type', '')
    cls = SOURCE_TYPES.get(source_type)
    if cls is None:
        logger.error(f"Unknown source type: {source_type}")
        return None
    return cls(source_config)


class IngestionPipeline:
    """Orchestrates the distributed, parallel document ingestion pipeline.

    Key improvements over the previous implementation:

    1. **True batch embedding** — uses Ollama's batch endpoint instead of
       serial one-at-a-time calls.
    2. **Parallel embedding** — multiple embedding batches run concurrently
       in a gevent pool.
    3. **Docling chunking** — when available, uses Docling's semantically
       aware chunks directly, falling back to the local TextChunker.
    4. **Per-document error handling** — failures are recorded in metrics
       and skipped, never crashing the pipeline.
    5. **Detailed metrics** — every stage is timed and counted for
       performance analysis.
    """

    def __init__(self, chunk_size: int = 800, overlap: int = 150):
        self.chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
        self.parent_child_chunker = None  # Created on demand when enabled
        self.embedding_service = get_embedding_service()
        self.vector_store = get_vector_store()

    # ── Embedding sub-pipeline (parallel batch) ────────────────────

    def _embed_texts_batch(
        self,
        texts: List[str],
        cancel_check=None,
    ) -> List[Optional[List[float]]]:
        """Embed a list of texts using true batch processing.

        Splits ``texts`` into sub-batches of ``EMBED_BATCH_SIZE`` and sends
        them to Ollama's ``/api/embed`` endpoint.  Sub-batches run in parallel
        within a gevent pool to fill the GPU.

        ``cancel_check`` — optional zero-argument callable that returns ``True``
        when a cancellation has been requested.  Checked between sub-batch
        dispatches so in-flight HTTP calls are not aborted mid-stream (which
        would leave Ollama in an undefined state) but no further work is
        started.
        """
        if not texts:
            return []

        total = len(texts)
        results: List[Optional[List[float]]] = [None] * total

        # Split into sub-batches
        sub_batches: List[Tuple[int, int]] = []
        for i in range(0, total, EMBED_BATCH_SIZE):
            sub_batches.append((i, min(i + EMBED_BATCH_SIZE, total)))

        def _process_sub_batch(start: int, end: int):
            batch_texts = texts[start:end]
            try:
                embeddings = self.embedding_service.embed_batch_native(batch_texts)
                for j, emb in enumerate(embeddings):
                    results[start + j] = emb
            except Exception as exc:
                logger.error(
                    "[Pipeline] Embedding sub-batch [%d:%d] failed: %s",
                    start, end, exc,
                )
                # Fall back to one-at-a-time for this sub-batch
                for j, txt in enumerate(batch_texts):
                    try:
                        results[start + j] = self.embedding_service.embed_text(txt)
                    except Exception:
                        results[start + j] = None

        if len(sub_batches) == 1:
            start, end = sub_batches[0]
            _process_sub_batch(start, end)
        else:
            pool = GeventPool(size=EMBED_POOL_SIZE)
            for start, end in sub_batches:
                # Check for cancellation before spawning each sub-batch.
                # Any already-spawned greenlets run to completion (we do not
                # kill them mid-HTTP-request to avoid leaving Ollama in an
                # inconsistent state), but we stop dispatching new work.
                if cancel_check and cancel_check():
                    pool.join()  # wait for in-flight requests to finish
                    raise PipelineCancelledError(
                        "Ingestion cancelled during embedding batch dispatch."
                    )
                pool.spawn(_process_sub_batch, start, end)
            pool.join()

        return results

    # ── Core batch processing ──────────────────────────────────────

    def _process_doc_batch(
        self,
        doc_dicts: List[dict],
        source_name: str,
        batch_num: int,
        metrics: Optional[PipelineMetrics] = None,
        cancel_check=None,
        parent_child_enabled: bool = False,
    ) -> tuple:
        """Chunk → embed → store one batch of doc_dicts.

        Uses Docling chunks when available (``doc_dict['docling_chunks']``),
        falling back to the local TextChunker (or ParentChildChunker when
        ``parent_child_enabled`` is True).

        ``cancel_check`` is forwarded to ``_embed_texts_batch`` so that
        cancellation can interrupt between embedding sub-batches.

        Returns:
            ``(chunk_count, stored_count, failed_embedding_count)``
        """
        t_chunk_start = time.monotonic()

        # Lazily create the parent-child chunker when first needed
        if parent_child_enabled and self.parent_child_chunker is None:
            self.parent_child_chunker = ParentChildChunker()
            logger.info("[Pipeline] ParentChildChunker initialised")

        active_chunker = self.parent_child_chunker if parent_child_enabled else self.chunker

        # --- Chunk: prefer Docling chunks, fall back to local ---
        chunked: List[dict] = []
        for doc in doc_dicts:
            docling_chunks = doc.get('docling_chunks')
            if docling_chunks and not parent_child_enabled:
                # Docling chunks are flat — skip them when parent-child is on
                metadata = doc.get('metadata', {})
                for i, dc in enumerate(docling_chunks):
                    chunk_meta = dict(metadata)
                    chunk_text = dc.get('text', '') if isinstance(dc, dict) else str(dc)
                    chunk_meta['chunk_text'] = chunk_text
                    chunk_meta['chunk_position'] = i
                    chunk_meta['total_chunks'] = len(docling_chunks)
                    chunk_meta['chunking_method'] = 'docling'
                    if isinstance(dc, dict):
                        if dc.get('headings'):
                            chunk_meta['chunk_headings'] = dc['headings']
                        if dc.get('page_numbers'):
                            chunk_meta['chunk_pages'] = dc['page_numbers']
                    chunked.append({'text': chunk_text, 'metadata': chunk_meta})
            else:
                local_chunks = active_chunker.chunk_documents([doc])
                method = 'parent_child' if parent_child_enabled else 'local'
                for lc in local_chunks:
                    lc['metadata'].setdefault('chunking_method', method)
                chunked.extend(local_chunks)

        t_chunk_end = time.monotonic()
        chunk_time = t_chunk_end - t_chunk_start
        if metrics:
            metrics.record_stage('chunking', items=len(chunked), duration=chunk_time)

        if not chunked:
            return 0, 0, 0

        # --- Embed (parallel batch) ---
        t_embed_start = time.monotonic()
        texts = [c['text'] for c in chunked]

        # Check cancellation *before* firing off Ollama requests
        if cancel_check and cancel_check():
            raise PipelineCancelledError(
                f"Ingestion cancelled before embedding batch {batch_num}."
            )

        emit_progress(
            'embed',
            f"Batch {batch_num}: {len(texts)} Chunks einbetten "
            f"(Modell: {self.embedding_service.model}, "
            f"Batch-Größe: {EMBED_BATCH_SIZE})...",
            source_name=source_name,
            detail={
                'batch': batch_num, 'chunks': len(texts),
                'model': self.embedding_service.model,
                'embed_batch_size': EMBED_BATCH_SIZE,
            },
        )

        embeddings = self._embed_texts_batch(texts, cancel_check=cancel_check)
        t_embed_end = time.monotonic()
        embed_time = t_embed_end - t_embed_start

        failed = sum(1 for e in embeddings if e is None)
        succeeded = len(embeddings) - failed

        if metrics:
            metrics.record_stage('embedding', items=succeeded,
                                 failed=failed, duration=embed_time)

        if failed == len(embeddings) and len(embeddings) > 0:
            logger.error(
                "[Pipeline] '%s': batch %d — all %d embeddings failed!",
                source_name, batch_num, len(embeddings),
            )
            if metrics:
                metrics.increment(total_embedding_failures=failed)
            return len(chunked), 0, failed

        # --- Build points (sanitise surrogates) ---
        points = []
        for pt_idx, (chunk, embedding) in enumerate(zip(chunked, embeddings)):
            if embedding is None:
                continue
            meta = chunk['metadata']
            for key, val in list(meta.items()):
                if isinstance(val, str):
                    meta[key] = val.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            # Build a deterministic ID from source + subsource + chunk position so
            # re-ingesting the same document overwrites old chunks instead of creating
            # duplicate entries in Qdrant.
            source_id_val = meta.get('source_id', 'unknown')
            subsource_id_val = meta.get('subsource_id', 'unknown')
            chunk_pos = meta.get('chunk_position', 0)
            doc_id = f"source_{source_id_val}_{subsource_id_val}_chunk_{chunk_pos}"
            points.append({
                'id': doc_id,
                'embedding': embedding,
                'metadata': meta,
            })
            if (pt_idx + 1) % 50 == 0:
                gevent.sleep(0)

        # --- Delete old chunks for these documents before upserting ---
        # This ensures that re-processing a document (e.g. after a retry or
        # manual re-sync) removes stale chunks before inserting new ones.
        subsource_ids_in_batch: set = set()
        for chunk in chunked:
            sid = chunk['metadata'].get('subsource_id')
            if sid:
                subsource_ids_in_batch.add(sid)
        if subsource_ids_in_batch:
            try:
                for sid in subsource_ids_in_batch:
                    self.vector_store.delete_by_metadata({'subsource_id': sid})
                logger.info(
                    "[Pipeline] Deleted old chunks for %d subsources before upserting",
                    len(subsource_ids_in_batch),
                )
            except Exception as cleanup_err:
                logger.warning("[Pipeline] Pre-ingestion cleanup failed: %s", cleanup_err)

        # --- Store ---
        t_store_start = time.monotonic()
        gevent.sleep(0)
        stored = self.vector_store.upsert_documents(points)
        t_store_end = time.monotonic()
        store_time = t_store_end - t_store_start

        if metrics:
            metrics.record_stage('storage', items=stored, duration=store_time)
            metrics.increment(
                total_chunks_embedded=succeeded,
                total_chunks_stored=stored,
                total_embedding_failures=failed,
            )

        # --- Incrementally update BM25 index ---
        try:
            bm25_idx = get_bm25_index()
            bm25_docs = [
                {'id': p['id'], 'payload': p['metadata']}
                for p in points
            ]
            bm25_idx.add_documents(bm25_docs)
        except Exception as bm25_err:
            logger.warning("[Pipeline] BM25 incremental update failed: %s", bm25_err)

        logger.info(
            "[Pipeline] '%s': batch %d — %d chunks, %d embedded, %d stored, "
            "%d failed | chunk=%.1fs embed=%.1fs store=%.1fs",
            source_name, batch_num, len(chunked), succeeded, stored, failed,
            chunk_time, embed_time, store_time,
        )

        return len(chunked), stored, failed

    def ingest_source(
        self,
        source_config: Dict[str, Any],
        incremental: bool = True,
        cancel_check=None,
    ) -> Dict[str, Any]:
        """
        Run the ingestion pipeline for a single source.

        Documents are processed in rolling batches of ``STREAM_BATCH`` to
        overlap fetching with chunk/embed/store — pages and chapters start
        being embedded while Docling is still extracting later attachments.

        ``cancel_check`` — optional zero-argument callable (typically
        ``check_cancel_requested`` from ingestion_worker) that returns ``True``
        when a cancel has been requested.  Checked at every batch boundary and
        in the document loop.

        Args:
            source_config: Source configuration dict (from SourceConfig.to_dict()).
            incremental: If True, only process new/updated documents.

        Returns:
            Dict with 'success', 'documents_processed', 'chunks_stored',
            'message', and 'metrics'.
        """
        source_name = source_config.get('name', 'unknown')
        source_id = source_config.get('id', '?')
        logger.info(
            "[Pipeline] ingest_source: '%s' (id=%s, incremental=%s, "
            "embed_model=%s, stream_batch=%d, embed_batch=%d)",
            source_name, source_id, incremental,
            self.embedding_service.model, STREAM_BATCH, EMBED_BATCH_SIZE,
        )

        # Initialise metrics collector
        metrics = PipelineMetrics(source_name=source_name, source_id=source_id)
        metrics.start()

        connector = get_source_connector(source_config)
        if connector is None:
            metrics.finish()
            return {
                'success': False, 'documents_processed': 0, 'chunks_stored': 0,
                'message': f"Unknown source type: {source_config.get('source_type')}",
                'metrics': metrics.summary(),
            }

        try:
            emit_progress('fetch', f"Dokumente abrufen von '{source_name}'...",
                          source_name=source_name)

            # Parse last-sync timestamp for incremental mode
            last_sync = None
            if incremental and source_config.get('last_sync_at'):
                try:
                    last_sync = datetime.fromisoformat(source_config['last_sync_at'])
                except (ValueError, TypeError):
                    last_sync = None

            # Resolve source-level permission tags upfront (independent of docs)
            source_tag_names = source_config.get('tags', [])
            if isinstance(source_tag_names, list) and source_tag_names:
                resolved_tags = [
                    t['name'] if isinstance(t, dict) else t
                    for t in source_tag_names
                ]
            else:
                resolved_tags = ['default_assistant_source']

            logger.info("[Pipeline] '%s': resolved_tags=%s", source_name, resolved_tags)

            # Build the document stream
            if incremental and last_sync:
                raw_list = connector.sync(last_sync)
                if not raw_list:
                    emit_progress('fetch', f"Keine neuen Dokumente für '{source_name}'.",
                                  source_name=source_name, level='warning')
                    metrics.finish()
                    return {
                        'success': True, 'documents_processed': 0,
                        'chunks_stored': 0,
                        'message': 'No documents to process.',
                        'metrics': metrics.summary(),
                    }
                logger.info("[Pipeline] '%s': incremental sync — %d documents",
                            source_name, len(raw_list))
                emit_progress('fetch',
                              f"{len(raw_list)} Dokumente für inkrementelles Update von '{source_name}'.",
                              source_name=source_name,
                              detail={'document_count': len(raw_list)},
                              level='success')
                doc_stream = iter(raw_list)
            else:
                # Full rebuild: wipe existing vectors, then stream docs as produced
                emit_progress('fetch', f"Alte Vektoren für '{source_name}' werden gelöscht...",
                              source_name=source_name)
                self.vector_store.delete_by_source(source_config['id'])
                doc_stream = connector.fetch_documents_stream()

            # ── Rolling batch loop: chunk→embed→store every STREAM_BATCH docs ──
            batch: List[dict] = []
            total_docs = 0
            total_chunks = 0
            total_stored = 0
            total_failed = 0
            batch_num = 0
            # Track subsources already processed in this run to guard against
            # connector bugs that yield the same document more than once.
            seen_subsources: set = set()

            # Check if parent-child chunking is enabled (from admin config)
            parent_child_enabled = False
            try:
                from modules.assistant.models.retrieval_config import get_admin_retrieval_config
                admin_cfg = get_admin_retrieval_config()
                pipeline_cfg = admin_cfg.get('pipeline_config', {})
                parent_child_enabled = pipeline_cfg.get('parent_child_enabled', False)
                if parent_child_enabled:
                    logger.info("[Pipeline] '%s': parent-child chunking ENABLED", source_name)
            except Exception as cfg_err:
                logger.warning("[Pipeline] Could not read pipeline_config: %s", cfg_err)

            def _flush_batch() -> None:
                nonlocal total_chunks, total_stored, total_failed, batch_num
                # Check for cancellation before starting chunk/embed/store work.
                if cancel_check and cancel_check():
                    raise PipelineCancelledError(
                        f"Ingestion cancelled before batch {batch_num + 1} "
                        f"({len(batch)} docs)."
                    )
                batch_num += 1
                logger.info("[Pipeline] '%s': processing batch #%d (%d docs)...",
                            source_name, batch_num, len(batch))
                emit_progress(
                    'embed',
                    f"Batch {batch_num}: {len(batch)} Dokumente werden eingebettet "
                    f"(Modell: {self.embedding_service.model})...",
                    source_name=source_name,
                    detail={'batch': batch_num, 'docs_in_batch': len(batch),
                            'model': self.embedding_service.model},
                )
                c, s, f = self._process_doc_batch(
                    batch, source_name, batch_num, metrics,
                    cancel_check=cancel_check,
                    parent_child_enabled=parent_child_enabled,
                )
                total_chunks += c
                total_stored += s
                total_failed += f
                if f > 0:
                    logger.warning(
                        "[Pipeline] '%s': batch %d — %d/%d embedding failures",
                        source_name, batch_num, f, c,
                    )
                emit_progress(
                    'store',
                    f"Batch {batch_num}: {s} Vektoren gespeichert ({c} Chunks aus {len(batch)} Docs).",
                    source_name=source_name,
                    detail={'batch': batch_num, 'stored': s, 'chunks': c,
                            'failed_embeddings': f},
                    level='success' if f == 0 else 'warning',
                )
                batch.clear()

            for doc in doc_stream:
                # Check for cancellation in the document fetch loop.
                # This exits *before* appending so the current document is not
                # partially processed.
                if cancel_check and cancel_check():
                    raise PipelineCancelledError(
                        "Ingestion cancelled during document stream."
                    )

                metadata = doc.to_metadata()
                # Guard against connector bugs that yield the same document twice.
                subsource_id = metadata.get('subsource_id')
                if subsource_id:
                    if subsource_id in seen_subsources:
                        logger.warning(
                            "[Pipeline] Duplicate subsource '%s' detected — skipping",
                            subsource_id,
                        )
                        continue
                    seen_subsources.add(subsource_id)
                # Use document-level permission tags when present; fall back to
                # the source-level tags configured in the assistant settings.
                if not (metadata.get('permission_tags') or []):
                    metadata['permission_tags'] = resolved_tags

                # Build doc dict — include Docling chunks if available
                doc_dict: dict = {'text': doc.text, 'metadata': metadata}
                if hasattr(doc, 'docling_chunks') and doc.docling_chunks:
                    doc_dict['docling_chunks'] = [
                        dc if isinstance(dc, dict) else
                        {'text': dc.text,
                         'headings': getattr(dc, 'headings', []),
                         'page_numbers': getattr(dc, 'page_numbers', [])}
                        for dc in doc.docling_chunks
                    ]

                batch.append(doc_dict)
                total_docs += 1
                metrics.total_docs_fetched = total_docs

                if len(batch) >= STREAM_BATCH:
                    _flush_batch()
                    gevent.sleep(0)

            # Flush any remaining documents
            if batch:
                _flush_batch()

            # Persist BM25 index to disk after ingestion
            try:
                bm25_idx = get_bm25_index()
                if bm25_idx.is_built:
                    bm25_idx.save()
                    logger.info("[Pipeline] '%s': BM25 index saved (%d docs)", source_name, bm25_idx.N)
            except Exception as bm25_err:
                logger.warning("[Pipeline] BM25 index save failed: %s", bm25_err)

            metrics.finish()
            metrics.log_summary()

            if total_docs == 0:
                emit_progress('fetch', f"Keine neuen Dokumente für '{source_name}'.",
                              source_name=source_name, level='warning')
                return {
                    'success': True, 'documents_processed': 0,
                    'chunks_stored': 0,
                    'message': 'No documents to process.',
                    'metrics': metrics.summary(),
                }

            # Surface a hard error when *every* embedding failed
            if total_failed == total_chunks and total_chunks > 0:
                emit_progress(
                    'embed',
                    f"Embedding-Generierung komplett fehlgeschlagen ({total_chunks} Chunks). "
                    "Ist Ollama erreichbar?",
                    source_name=source_name, level='error',
                )
                return {
                    'success': False,
                    'documents_processed': total_docs,
                    'chunks_stored': 0,
                    'message': (
                        f'Embedding generation failed for all {total_chunks} chunks. '
                        'Is the embedding model running in Ollama?'
                    ),
                    'metrics': metrics.summary(),
                }

            logger.info(
                "[Pipeline] '%s': ingestion complete — %d docs, %d chunks, %d stored, %d failed embeddings",
                source_name, total_docs, total_chunks, total_stored, total_failed,
            )
            emit_progress(
                'store',
                f"Ingestion abgeschlossen: {total_docs} Dokumente, {total_stored} Chunks gespeichert.",
                source_name=source_name,
                detail={
                    'documents': total_docs, 'chunks_stored': total_stored,
                    'failed_embeddings': total_failed,
                    'metrics_summary': metrics.summary(),
                },
                level='success' if total_failed == 0 else 'warning',
            )

            msg = f'Processed {total_docs} documents, stored {total_stored} chunks.'
            if total_failed > 0:
                msg += f' ({total_failed} chunks had embedding failures.)'
            if total_stored == 0 and total_docs > 0:
                msg += ' WARNING: No chunks stored — check embedding model availability.'

            return {
                'success': total_stored > 0 or total_docs == 0,
                'documents_processed': total_docs,
                'chunks_stored': total_stored,
                'message': msg,
                'metrics': metrics.summary(),
            }

        except PipelineCancelledError:
            # Re-raise cancellations — do not treat them as errors.
            # The worker loop has its own handler that marks the DB task
            # as 'cancelled' and emits the appropriate progress event.
            metrics.finish()
            raise

        except Exception as e:
            logger.error(f"Ingestion pipeline error: {e}", exc_info=True)
            metrics.finish()
            metrics.record_error('pipeline', 'ingest_source', str(e))
            emit_progress('error', f"Pipeline-Fehler für '{source_name}': {e}",
                          source_name=source_name, level='error')
            return {
                'success': False, 'documents_processed': 0,
                'chunks_stored': 0,
                'message': f'Pipeline error: {str(e)}',
                'metrics': metrics.summary(),
            }

    def rebuild_all(
        self,
        source_configs: List[Dict[str, Any]],
        cancel_check=None,
    ) -> Dict[str, Any]:
        """Full rebuild of the entire vector store.

        ``cancel_check`` is forwarded to each ``ingest_source`` call so that
        cancellation propagates all the way down to the batch/embedding level.

        Returns a ``source_results`` list in addition to aggregate totals so
        the caller can persist per-source document counts and sync status.
        """
        # Delete the existing collection so stale vectors from the old model are
        # wiped out.  Do NOT call ensure_collection() here — upsert_documents()
        # will create the collection with the correct dimension once we know what
        # the embedding model actually produces.
        emit_progress('worker', 'Vollständiger Rebuild gestartet — lösche bestehende Collection...',
                      level='info')
        self.vector_store.delete_collection()

        total_docs = 0
        total_chunks = 0
        errors = []
        source_results = []  # [{source_id, name, success, documents_processed, message}]
        all_metrics = []

        for idx, config in enumerate(source_configs):
            # Check cancellation at the start of every source so we stop
            # immediately instead of wasting time on the next source.
            if cancel_check and cancel_check():
                raise PipelineCancelledError(
                    "Rebuild cancelled before processing source "
                    f"'{config.get('name')}' (idx={idx})."
                )
            if not config.get('enabled', True):
                logger.info("[Pipeline] rebuild_all: skipping disabled source '%s'", config.get('name'))
                continue
            logger.info("[Pipeline] rebuild_all: ingesting source '%s' (id=%s)...",
                        config.get('name'), config.get('id'))
            emit_progress('worker',
                          f"Rebuild Quelle {idx + 1}/{len(source_configs)}: '{config.get('name')}'",
                          source_name=config.get('name'),
                          progress=(idx / max(len(source_configs), 1)))
            result = self.ingest_source(config, incremental=False,
                                        cancel_check=cancel_check)
            source_results.append({
                'source_id': config.get('id'),
                'name': config.get('name'),
                'success': result['success'],
                'documents_processed': result.get('documents_processed', 0),
                'chunks_stored': result.get('chunks_stored', 0),
                'message': result['message'],
            })
            if result.get('metrics'):
                all_metrics.append(result['metrics'])
            if result['success']:
                total_docs += result['documents_processed']
                total_chunks += result['chunks_stored']
                logger.info("[Pipeline] rebuild_all: '%s' OK — %d docs, %d chunks",
                            config.get('name'), result['documents_processed'], result['chunks_stored'])
            else:
                errors.append(f"{config['name']}: {result['message']}")
                logger.error("[Pipeline] rebuild_all: '%s' FAILED — %s",
                             config.get('name'), result['message'])

        # Rebuild BM25 index from scratch after full rebuild
        try:
            emit_progress('worker', 'BM25-Index wird neu aufgebaut...', level='info')
            bm25_idx = get_bm25_index()
            bm25_count = bm25_idx.build_from_vector_store()
            bm25_idx.save()
            logger.info("[Pipeline] rebuild_all: BM25 index rebuilt (%d docs)", bm25_count)
        except Exception as bm25_err:
            logger.warning("[Pipeline] rebuild_all: BM25 index rebuild failed: %s", bm25_err)

        return {
            'success': len(errors) == 0,
            'documents_processed': total_docs,
            'chunks_stored': total_chunks,
            'errors': errors,
            'source_results': source_results,
            'message': f'Rebuilt index: {total_docs} documents, {total_chunks} chunks.' +
                       (f' Errors: {len(errors)}' if errors else ''),
            'metrics': all_metrics,
        }

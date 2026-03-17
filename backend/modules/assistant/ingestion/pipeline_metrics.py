# Assistant Module - Ingestion: Pipeline Metrics
"""
Structured metrics collection for the ingestion pipeline.

Tracks document-level statistics, timing, errors, and per-stage throughput
so operators can tune batch sizes, pool sizes, and GPU parameters.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DocumentMetric:
    """Per-document processing metrics."""
    filename: str
    doc_type: str = ''                    # page, chapter, book, attachment
    file_size_bytes: int = 0
    extraction_method: str = ''           # docling, tika, plaintext, none
    extraction_time_s: float = 0.0
    chunk_count: int = 0
    embedding_time_s: float = 0.0
    storage_time_s: float = 0.0
    total_time_s: float = 0.0
    success: bool = True
    error: str = ''
    retries: int = 0


@dataclass
class StageMetrics:
    """Aggregate metrics for a pipeline stage."""
    stage_name: str
    started_at: float = 0.0
    completed_at: float = 0.0
    items_processed: int = 0
    items_failed: int = 0
    total_time_s: float = 0.0
    avg_time_per_item_s: float = 0.0


class PipelineMetrics:
    """Thread-safe metrics collector for the ingestion pipeline.

    Usage::

        metrics = PipelineMetrics(source_name='My BookStack')
        metrics.start()

        # Record per-document metrics
        metrics.record_document(DocumentMetric(filename='report.pdf', ...))

        # Record stage-level data
        metrics.record_stage('extraction', items=10, failed=1, duration=45.2)

        metrics.finish()
        summary = metrics.summary()
    """

    def __init__(self, source_name: str = '', source_id: int = 0):
        self.source_name = source_name
        self.source_id = source_id
        self._lock = threading.Lock()

        # Timing
        self._start_time: float = 0.0
        self._end_time: float = 0.0

        # Document-level metrics
        self._documents: List[DocumentMetric] = []

        # Stage-level aggregates
        self._stages: Dict[str, StageMetrics] = {}

        # Counters
        self.total_docs_fetched: int = 0
        self.total_docs_extracted: int = 0
        self.total_docs_failed: int = 0
        self.total_chunks_generated: int = 0
        self.total_chunks_embedded: int = 0
        self.total_chunks_stored: int = 0
        self.total_embedding_failures: int = 0
        self.total_bytes_processed: int = 0

        # Error log
        self._errors: List[Dict[str, str]] = []

    def start(self):
        self._start_time = time.monotonic()

    def finish(self):
        self._end_time = time.monotonic()

    @property
    def elapsed_s(self) -> float:
        end = self._end_time or time.monotonic()
        return end - self._start_time if self._start_time else 0.0

    def record_document(self, doc: DocumentMetric):
        with self._lock:
            self._documents.append(doc)
            if doc.success:
                self.total_docs_extracted += 1
            else:
                self.total_docs_failed += 1
            self.total_bytes_processed += doc.file_size_bytes
            self.total_chunks_generated += doc.chunk_count

    def record_stage(self, stage_name: str, items: int = 0,
                     failed: int = 0, duration: float = 0.0):
        with self._lock:
            if stage_name not in self._stages:
                self._stages[stage_name] = StageMetrics(stage_name=stage_name)
            s = self._stages[stage_name]
            s.items_processed += items
            s.items_failed += failed
            s.total_time_s += duration
            s.avg_time_per_item_s = (
                s.total_time_s / max(s.items_processed, 1)
            )

    def record_error(self, filename: str, stage: str, error: str):
        with self._lock:
            self._errors.append({
                'filename': filename,
                'stage': stage,
                'error': error,
                'timestamp': time.time(),
            })

    def increment(self, **counters):
        """Increment named counters atomically.

        Example: ``metrics.increment(total_chunks_stored=50, total_embedding_failures=2)``
        """
        with self._lock:
            for key, val in counters.items():
                current = getattr(self, key, None)
                if current is not None and isinstance(current, int):
                    setattr(self, key, current + val)

    def summary(self) -> Dict[str, Any]:
        """Return a comprehensive metrics summary dict."""
        elapsed = self.elapsed_s
        docs_per_sec = self.total_docs_extracted / max(elapsed, 0.001)
        chunks_per_sec = self.total_chunks_stored / max(elapsed, 0.001)

        # Per-extraction-method breakdown
        method_counts: Dict[str, int] = {}
        method_times: Dict[str, float] = {}
        for d in self._documents:
            m = d.extraction_method or 'unknown'
            method_counts[m] = method_counts.get(m, 0) + 1
            method_times[m] = method_times.get(m, 0.0) + d.extraction_time_s

        return {
            'source_name': self.source_name,
            'source_id': self.source_id,
            'total_time_s': round(elapsed, 2),
            'total_docs_fetched': self.total_docs_fetched,
            'total_docs_extracted': self.total_docs_extracted,
            'total_docs_failed': self.total_docs_failed,
            'total_chunks_generated': self.total_chunks_generated,
            'total_chunks_embedded': self.total_chunks_embedded,
            'total_chunks_stored': self.total_chunks_stored,
            'total_embedding_failures': self.total_embedding_failures,
            'total_bytes_processed': self.total_bytes_processed,
            'throughput_docs_per_sec': round(docs_per_sec, 2),
            'throughput_chunks_per_sec': round(chunks_per_sec, 2),
            'extraction_methods': method_counts,
            'extraction_times_by_method': {
                k: round(v, 2) for k, v in method_times.items()
            },
            'stages': {
                name: {
                    'items_processed': s.items_processed,
                    'items_failed': s.items_failed,
                    'total_time_s': round(s.total_time_s, 2),
                    'avg_time_per_item_s': round(s.avg_time_per_item_s, 3),
                }
                for name, s in self._stages.items()
            },
            'errors': self._errors[-50:],  # last 50 errors
            'error_count': len(self._errors),
        }

    def log_summary(self):
        """Write the metrics summary to the logger."""
        s = self.summary()
        logger.info(
            "[PipelineMetrics] '%s' complete: %.1fs elapsed | "
            "%d docs extracted (%d failed) | %d chunks stored (%d embed failures) | "
            "%.1f docs/s | %.1f chunks/s | %s bytes processed",
            s['source_name'], s['total_time_s'],
            s['total_docs_extracted'], s['total_docs_failed'],
            s['total_chunks_stored'], s['total_embedding_failures'],
            s['throughput_docs_per_sec'], s['throughput_chunks_per_sec'],
            _format_bytes(s['total_bytes_processed']),
        )
        for method, count in s.get('extraction_methods', {}).items():
            avg = s['extraction_times_by_method'].get(method, 0) / max(count, 1)
            logger.info(
                "[PipelineMetrics]   %s: %d docs, avg %.2fs/doc",
                method, count, avg,
            )
        if s['error_count'] > 0:
            logger.warning(
                "[PipelineMetrics]   %d errors recorded (last: %s)",
                s['error_count'],
                s['errors'][-1] if s['errors'] else 'n/a',
            )


def _format_bytes(n: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if abs(n) < 1024.0:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"

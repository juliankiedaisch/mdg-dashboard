# Assistant Module – External Document Extraction Service
"""
Delegates text extraction to external Docker services (Docling & Apache Tika)
instead of running PDF/DOCX libraries in-process.

Architecture (redesigned)
─────────────────────────
• **Docling** (primary) — handles PDF, DOCX, DOC, PPTX, PPT, XLSX, CSV,
  HTML, Markdown, AsciiDoc, and image OCR.  Uses the new ``DoclingClient``
  with connection pooling, retry, circuit-breaker, and GPU optimisation.
• **Apache Tika** (secondary / fallback) — handles ODT, ODS, RTF, and any
  format that Docling fails on.
• **Plain text** — read directly without any service (TXT, JSON, XML, LOG, RST).
• **Batch extraction** — ``extract_batch()`` processes multiple files
  concurrently via a gevent pool, maximising throughput.
• **Docling chunking** — ``extract_with_chunks()`` returns both full text
  and Docling-generated semantic chunks for direct use in the RAG pipeline.

All service calls use hard timeouts so a stuck extraction never blocks the
pipeline.  Each individual file failure is logged and skipped — it never
aborts the whole job.
"""

import logging
import os
import time
import requests
import gevent
from gevent.pool import Pool as GeventPool
from typing import Tuple, Optional, List, Dict, Any
from dataclasses import dataclass, field
from src.globals import DOCLING_URL, TIKA_URL, DOCLING_POOL_SIZE, TIKA_TIMEOUT

from modules.assistant.services.docling_client import (
    get_docling_client, SUPPORTED_EXTENSIONS as DOCLING_SUPPORTED,
)

logger = logging.getLogger(__name__)


# ── Extension routing ──────────────────────────────────────────────
TEXT_EXTENSIONS = {
    '.txt', '.json', '.xml', '.log',
}

DOCLING_EXTENSIONS = {
    '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.csv',
    '.html', '.htm', '.md', '.rst', '.asciidoc', '.adoc',
}

TIKA_EXTENSIONS = {
    '.odt', '.ods', '.odp', '.rtf', '.epub', '.xls',
}

IMAGE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.webp',
}

ALL_SUPPORTED_EXTENSIONS = (
    TEXT_EXTENSIONS | DOCLING_EXTENSIONS | TIKA_EXTENSIONS | IMAGE_EXTENSIONS
)

# ── Result data class ─────────────────────────────────────────────

@dataclass
class ExtractionResult:
    """Result from extracting text from a single file."""
    text: str = ''
    method: str = 'none'               # docling, tika, plaintext, none
    success: bool = False
    processing_time_s: float = 0.0
    chunks: List[Dict[str, Any]] = field(default_factory=list)  # Docling chunks
    error: str = ''
    page_count: int = 0
    table_count: int = 0


# ── Helpers ────────────────────────────────────────────────────────

def _get_extension(filename: str) -> str:
    """Return the lowercase extension including the leading dot."""
    if '.' in filename:
        return '.' + filename.rsplit('.', 1)[1].lower()
    return ''


def _sanitize_text(text: str) -> str:
    """Remove Unicode surrogates and other non-UTF-8 characters."""
    if not text:
        return text
    return text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')


# ── Tika client (kept for fallback) ───────────────────────────────

def _extract_with_tika(file_data: bytes, filename: str,
                       timeout: int = TIKA_TIMEOUT) -> Optional[str]:
    """Send a file to the Apache Tika service and return plain text.

    Returns ``None`` on any failure.
    """
    url = f"{TIKA_URL}/tika"
    try:
        resp = requests.put(
            url,
            data=file_data,
            headers={
                'Accept': 'text/plain',
                'Content-Disposition': f'attachment; filename="{filename}"',
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.warning(
                "[Extraction] Tika returned %d for '%s': %s",
                resp.status_code, filename, resp.text[:300],
            )
            return None

        text = resp.text.strip()
        if text:
            return _sanitize_text(text)

        logger.info("[Extraction] Tika returned empty text for '%s'", filename)
        return None

    except requests.exceptions.Timeout:
        logger.error(
            "[Extraction] Tika timed out after %ds for '%s'",
            timeout, filename,
        )
        return None
    except requests.exceptions.ConnectionError:
        logger.error(
            "[Extraction] Cannot reach Tika at %s — is the service running?",
            TIKA_URL,
        )
        return None
    except Exception as exc:
        logger.error(
            "[Extraction] Tika request failed for '%s': %s",
            filename, exc,
        )
        return None


# ── Main dispatcher ────────────────────────────────────────────────

def extract_text(file_data: bytes, filename: str) -> Tuple[str, str]:
    """Extract text from a file using the best available external service.

    Returns ``(text, method)`` where *method* is one of:
    ``'plaintext'``, ``'docling'``, ``'tika'``, ``'none'``.
    An empty *text* string means extraction yielded nothing.

    Routing logic:
    1. Plain-text extensions → decode directly.
    2. Docling-supported + image extensions → try Docling first.
    3. Tika-supported extensions → try Tika first.
    4. If the primary service fails, try the other as fallback.
    5. If both fail, return empty text with method ``'none'``.
    """
    ext = _get_extension(filename)
    t0 = time.monotonic()

    # ── 1. Plain text — read directly ─────────────────────────────
    if ext in TEXT_EXTENSIONS:
        text = _sanitize_text(file_data.decode('utf-8', errors='replace'))
        elapsed = time.monotonic() - t0
        logger.debug("[Extraction] '%s' read as plain text in %.2fs", filename, elapsed)
        return text, 'plaintext'

    # ── 2. Docling-primary formats (+ images for OCR) ─────────────
    if ext in DOCLING_EXTENSIONS or ext in IMAGE_EXTENSIONS:
        client = get_docling_client()
        result = client.convert_file(file_data, filename, use_chunking=False)
        if result.success and result.text.strip():
            elapsed = time.monotonic() - t0
            logger.info(
                "[Extraction] '%s' extracted via Docling in %.2fs (%d chars)",
                filename, elapsed, len(result.text),
            )
            return result.text, 'docling'
        # Docling failed — fall back to Tika
        logger.info("[Extraction] Docling failed for '%s', trying Tika fallback...", filename)
        text = _extract_with_tika(file_data, filename)
        if text:
            elapsed = time.monotonic() - t0
            logger.info(
                "[Extraction] '%s' extracted via Tika (fallback) in %.2fs (%d chars)",
                filename, elapsed, len(text),
            )
            return text, 'tika'

    # ── 3. Tika-primary formats ───────────────────────────────────
    elif ext in TIKA_EXTENSIONS:
        text = _extract_with_tika(file_data, filename)
        if text:
            elapsed = time.monotonic() - t0
            logger.info(
                "[Extraction] '%s' extracted via Tika in %.2fs (%d chars)",
                filename, elapsed, len(text),
            )
            return text, 'tika'
        # Tika failed — try Docling as fallback
        logger.info("[Extraction] Tika failed for '%s', trying Docling fallback...", filename)
        client = get_docling_client()
        result = client.convert_file(file_data, filename, use_chunking=False)
        if result.success and result.text.strip():
            elapsed = time.monotonic() - t0
            logger.info(
                "[Extraction] '%s' extracted via Docling (fallback) in %.2fs (%d chars)",
                filename, elapsed, len(result.text),
            )
            return result.text, 'docling'

    # ── 4. Unknown extension — try both services ──────────────────
    else:
        client = get_docling_client()
        result = client.convert_file(file_data, filename, use_chunking=False)
        if result.success and result.text.strip():
            elapsed = time.monotonic() - t0
            logger.info(
                "[Extraction] '%s' extracted via Docling in %.2fs (%d chars)",
                filename, elapsed, len(result.text),
            )
            return result.text, 'docling'
        text = _extract_with_tika(file_data, filename)
        if text:
            elapsed = time.monotonic() - t0
            logger.info(
                "[Extraction] '%s' extracted via Tika in %.2fs (%d chars)",
                filename, elapsed, len(text),
            )
            return text, 'tika'

    # ── 5. Nothing worked ─────────────────────────────────────────
    elapsed = time.monotonic() - t0
    logger.warning(
        "[Extraction] No text extracted for '%s' after %.2fs — all services failed",
        filename, elapsed,
    )
    return '', 'none'


# ── Extraction with Docling chunks ─────────────────────────────────

def extract_with_chunks(
        file_data: bytes,
        filename: str,
) -> ExtractionResult:
    """Extract text AND Docling semantic chunks from a file.

    Uses the DoclingClient with chunking enabled so the result includes
    both full text and pre-generated semantic chunks that respect document
    structure (headings, tables, lists).

    If Docling fails, falls back to Tika (without chunks).
    """
    ext = _get_extension(filename)
    t0 = time.monotonic()

    # Plain text
    if ext in TEXT_EXTENSIONS:
        text = _sanitize_text(file_data.decode('utf-8', errors='replace'))
        return ExtractionResult(
            text=text, method='plaintext', success=bool(text.strip()),
            processing_time_s=time.monotonic() - t0,
        )

    # Docling formats + images
    if ext in DOCLING_EXTENSIONS or ext in IMAGE_EXTENSIONS:
        client = get_docling_client()
        result = client.convert_file(file_data, filename, use_chunking=True)
        if result.success:
            chunks = [
                {'text': c.text, 'headings': c.headings,
                 'page_numbers': c.page_numbers, 'metadata': c.metadata}
                for c in result.chunks
            ] if result.chunks else []
            return ExtractionResult(
                text=result.text, method='docling', success=True,
                processing_time_s=result.processing_time_s,
                chunks=chunks,
                page_count=result.page_count,
                table_count=result.table_count,
            )
        # Docling failed — Tika fallback (no chunks)
        text = _extract_with_tika(file_data, filename)
        if text:
            return ExtractionResult(
                text=text, method='tika', success=True,
                processing_time_s=time.monotonic() - t0,
            )

    # Tika formats
    elif ext in TIKA_EXTENSIONS:
        text = _extract_with_tika(file_data, filename)
        if text:
            return ExtractionResult(
                text=text, method='tika', success=True,
                processing_time_s=time.monotonic() - t0,
            )
        # Tika failed — Docling fallback
        client = get_docling_client()
        result = client.convert_file(file_data, filename, use_chunking=True)
        if result.success:
            chunks = [
                {'text': c.text, 'headings': c.headings,
                 'page_numbers': c.page_numbers, 'metadata': c.metadata}
                for c in result.chunks
            ] if result.chunks else []
            return ExtractionResult(
                text=result.text, method='docling', success=True,
                processing_time_s=result.processing_time_s,
                chunks=chunks,
                page_count=result.page_count,
                table_count=result.table_count,
            )

    return ExtractionResult(
        processing_time_s=time.monotonic() - t0,
        error=f'No extraction service could process {filename}',
    )


# ── Batch extraction (parallel) ───────────────────────────────────

def extract_batch(
    files: List[Tuple[bytes, str]],
    pool_size: int = None,
    use_chunks: bool = True,
) -> List[ExtractionResult]:
    """Extract text from multiple files concurrently.

    Uses a gevent pool to parallelise extraction across the Docling and
    Tika services.  Each file is processed independently — failures do
    not affect other files.

    Parameters
    ----------
    files : list of (file_data, filename) tuples
    pool_size : int, optional
        Max concurrent extractions (default: ``EXTRACTION_POOL_SIZE``).
    use_chunks : bool
        If True, requests Docling chunks alongside text.

    Returns
    -------
    list of ExtractionResult, one per input file.
    """
    effective_pool = pool_size or DOCLING_POOL_SIZE
    results: List[Optional[ExtractionResult]] = [None] * len(files)

    logger.info(
        "[Extraction] Starting batch extraction: %d files, pool=%d, chunks=%s",
        len(files), effective_pool, use_chunks,
    )

    def _worker(idx: int, file_data: bytes, filename: str):
        try:
            if use_chunks:
                results[idx] = extract_with_chunks(file_data, filename)
            else:
                text, method = extract_text(file_data, filename)
                results[idx] = ExtractionResult(
                    text=text, method=method, success=bool(text.strip()),
                )
        except Exception as exc:
            logger.error(
                "[Extraction] Batch worker error for '%s': %s",
                filename, exc, exc_info=True,
            )
            results[idx] = ExtractionResult(error=str(exc))

    pool = GeventPool(size=effective_pool)
    for idx, (file_data, filename) in enumerate(files):
        pool.spawn(_worker, idx, file_data, filename)
    pool.join()

    # Fill any None entries
    for idx in range(len(results)):
        if results[idx] is None:
            results[idx] = ExtractionResult(
                error='Worker did not produce a result',
            )

    succeeded = sum(1 for r in results if r.success)
    logger.info(
        "[Extraction] Batch complete: %d/%d succeeded",
        succeeded, len(results),
    )
    return results


# ── Health checks ──────────────────────────────────────────────────

def check_service_health() -> dict:
    """Return health status of all extraction services.

    Useful for the admin dashboard to show whether services are reachable.
    """
    status = {}

    # Check Docling via the client
    try:
        client = get_docling_client()
        status['docling'] = client.health_check()
    except Exception as exc:
        status['docling'] = {
            'url': DOCLING_URL,
            'healthy': False,
            'error': str(exc),
        }

    # Check Tika
    try:
        resp = requests.get(f"{TIKA_URL}/version", timeout=5)
        status['tika'] = {
            'url': TIKA_URL,
            'healthy': resp.status_code == 200,
            'status_code': resp.status_code,
            'version': resp.text.strip() if resp.status_code == 200 else None,
        }
    except Exception as exc:
        status['tika'] = {
            'url': TIKA_URL,
            'healthy': False,
            'error': str(exc),
        }

    return status

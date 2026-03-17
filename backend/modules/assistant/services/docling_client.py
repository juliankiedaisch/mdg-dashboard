# Assistant Module – Services: Docling Client
"""
High-performance, resilient client for the Docling document parsing service.

Features
────────
• Connection pooling via ``requests.Session``
• Retry with exponential back-off (configurable)
• Per-request timeouts
• Circuit breaker: after N consecutive failures the client stops hitting the
  service for a cool-down period, preventing request pile-ups when Docling is
  down.
• GPU-optimised default parameters for RTX 4080 (16 GB VRAM)
• Support for Docling's built-in chunking (``/v1/convert/file`` with
  ``chunker`` parameter) so the backend can skip its own chunking step.
• Batch processing: submit multiple files concurrently via ``gevent.pool.Pool``
  and return results as they complete.

All methods are safe to call from gevent greenlets.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import gevent
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.globals import DOCLING_URL, DOCLING_TIMEOUT, DOCLING_MAX_RETRIES, DOCLING_RETRY_BACKOFF, DOCLING_POOL_SIZE, DOCLING_USE_CHUNKING, CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_COOLDOWN
logger = logging.getLogger(__name__)


# ── GPU-optimised conversion parameters for RTX 4080 ──────────────
# These are sent as form-data alongside each file upload to Docling.
# See https://github.com/docling-project/docling-serve/blob/main/docs/usage.md
GPU_OPTIMISED_PARAMS: Dict[str, Any] = {
    'to_formats':              'md',
    'pdf_backend':             'dlparse_v2',       # GPU-accelerated PDF parser
    'table_mode':              'accurate',          # better table extraction with GPU
    'do_ocr':                  'true',
    'ocr_engine':              'easyocr',           # CUDA-accelerated OCR
    'ocr_lang':                ['de', 'en'],
    'force_ocr':               'false',
    'do_table_structure':      'true',
    'include_images':          'false',             # skip base64 image payloads
    'do_code_enrichment':      'false',
    'do_formula_enrichment':   'false',
    'abort_on_error':          'false',
    'image_resolution_scale':  '2',                 # higher res for OCR accuracy
}

# Chunking parameters sent when DOCLING_USE_CHUNKING is enabled.
# Docling's HierarchicalChunker produces semantically meaningful chunks
# respecting document structure (headings, tables, lists).
CHUNKING_PARAMS: Dict[str, Any] = {
    'chunker':            'hybrid',                 # hierarchical + token-based
    'max_tokens':         512,                      # tokens per chunk
    'merge_peers':        'true',                   # merge small sibling sections
    'include_metadata':   'true',                   # attach heading hierarchy etc.
}


# ── Extension → Docling format mapping ─────────────────────────────
EXT_TO_DOCLING_FORMAT = {
    '.pdf': 'pdf',
    '.docx': 'docx', '.doc': 'docx',
    '.pptx': 'pptx', '.ppt': 'pptx',
    '.xlsx': 'xlsx', '.csv': 'csv',
    '.html': 'html', '.htm': 'html',
    '.md': 'md',
    '.rst': 'asciidoc', '.asciidoc': 'asciidoc', '.adoc': 'asciidoc',
    # Images → OCR
    '.png': 'image', '.jpg': 'image', '.jpeg': 'image', '.gif': 'image',
    '.bmp': 'image', '.tiff': 'image', '.tif': 'image', '.webp': 'image',
}

SUPPORTED_EXTENSIONS = set(EXT_TO_DOCLING_FORMAT.keys())


# ── Data classes ───────────────────────────────────────────────────

@dataclass
class DoclingChunk:
    """A single chunk produced by Docling's built-in chunker."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    headings: List[str] = field(default_factory=list)
    page_numbers: List[int] = field(default_factory=list)


@dataclass
class DoclingResult:
    """Result from processing a single document through Docling."""
    filename: str
    success: bool
    text: str = ''
    chunks: List[DoclingChunk] = field(default_factory=list)
    extraction_method: str = 'docling'
    processing_time_s: float = 0.0
    error: str = ''
    # Raw metadata from Docling response
    page_count: int = 0
    table_count: int = 0
    image_count: int = 0


# ── Client class ───────────────────────────────────────────────────

class DoclingClient:
    """Resilient, GPU-optimised client for Docling document parsing service.

    Designed for high parallelism — safe to use from multiple gevent greenlets
    simultaneously.  The underlying ``requests.Session`` uses connection pooling
    to avoid TCP re-establishment overhead.
    """

    def __init__(
        self,
        base_url: str = None,
        timeout: int = None,
        max_retries: int = None,
        retry_backoff: float = None,
        pool_size: int = None,
        use_chunking: bool = None,
    ):
        self.base_url = (base_url or DOCLING_URL).rstrip('/')
        self.timeout = timeout or DOCLING_TIMEOUT
        self.max_retries = max_retries if max_retries is not None else DOCLING_MAX_RETRIES
        self.retry_backoff = retry_backoff or DOCLING_RETRY_BACKOFF
        self.pool_size = pool_size or DOCLING_POOL_SIZE
        self.use_chunking = use_chunking if use_chunking is not None else DOCLING_USE_CHUNKING

        # Circuit breaker state
        self._consecutive_failures = 0
        self._circuit_open_until: float = 0.0

        # Build a session with connection pooling and automatic retries on
        # transport-level errors (connection reset, etc.)
        self._session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=self.pool_size,
            pool_maxsize=self.pool_size * 2,
            max_retries=Retry(
                total=0,  # We handle retries ourselves for better control
                backoff_factor=0,
            ),
        )
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)

        logger.info(
            "[DoclingClient] Initialised: url=%s timeout=%ds retries=%d "
            "pool=%d chunking=%s",
            self.base_url, self.timeout, self.max_retries,
            self.pool_size, self.use_chunking,
        )

    # ── Circuit breaker ────────────────────────────────────────────

    def _check_circuit(self) -> bool:
        """Return True if the circuit is closed (requests allowed)."""
        if self._consecutive_failures < CIRCUIT_BREAKER_THRESHOLD:
            return True
        if time.monotonic() >= self._circuit_open_until:
            # Cool-down expired — allow one probe request
            logger.info("[DoclingClient] Circuit breaker: cool-down expired, "
                        "allowing probe request")
            self._consecutive_failures = CIRCUIT_BREAKER_THRESHOLD - 1
            return True
        return False

    def _record_success(self):
        self._consecutive_failures = 0

    def _record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open_until = time.monotonic() + CIRCUIT_BREAKER_COOLDOWN
            logger.error(
                "[DoclingClient] Circuit breaker OPEN — %d consecutive failures. "
                "Pausing requests for %ds.",
                self._consecutive_failures, CIRCUIT_BREAKER_COOLDOWN,
            )

    # ── Health check ───────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """Check if Docling service is healthy."""
        try:
            resp = self._session.get(
                f"{self.base_url}/health",
                timeout=10,
            )
            return {
                'healthy': resp.status_code == 200,
                'url': self.base_url,
                'status_code': resp.status_code,
                'circuit_breaker': 'closed' if self._check_circuit() else 'open',
            }
        except Exception as exc:
            return {
                'healthy': False,
                'url': self.base_url,
                'error': str(exc),
                'circuit_breaker': 'closed' if self._check_circuit() else 'open',
            }

    # ── Single file conversion ─────────────────────────────────────

    def convert_file(
        self,
        file_data: bytes,
        filename: str,
        use_chunking: bool = None,
        extra_params: Dict[str, Any] = None,
    ) -> DoclingResult:
        """Convert a single document via Docling with retry and circuit breaker.

        Parameters
        ----------
        file_data : bytes
            Raw file content.
        filename : str
            Original filename (used for extension detection and Docling hints).
        use_chunking : bool, optional
            Override instance-level chunking setting.
        extra_params : dict, optional
            Additional form-data parameters to send to Docling.

        Returns
        -------
        DoclingResult
            Always returns a result — check ``result.success`` for errors.
        """
        t0 = time.monotonic()
        ext = _get_extension(filename)

        if not self._check_circuit():
            return DoclingResult(
                filename=filename, success=False,
                error='Circuit breaker is open — service temporarily unavailable',
                processing_time_s=time.monotonic() - t0,
            )

        # Build form data
        form_data = dict(GPU_OPTIMISED_PARAMS)
        from_fmt = EXT_TO_DOCLING_FORMAT.get(ext)
        if from_fmt:
            form_data['from_formats'] = from_fmt

        # Add chunking params if requested
        should_chunk = use_chunking if use_chunking is not None else self.use_chunking
        if should_chunk:
            form_data.update(CHUNKING_PARAMS)
            form_data['to_formats'] = 'md'  # ensure markdown output alongside chunks

        if extra_params:
            form_data.update(extra_params)

        # Retry loop
        last_error = ''
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.post(
                    f"{self.base_url}/v1/convert/file",
                    files={'files': (filename, file_data)},
                    data=form_data,
                    timeout=self.timeout,
                )

                if resp.status_code == 429:
                    # Rate limited — wait and retry
                    retry_after = float(resp.headers.get('Retry-After', 2 ** attempt))
                    logger.warning(
                        "[DoclingClient] Rate limited for '%s' (attempt %d/%d), "
                        "waiting %.1fs",
                        filename, attempt, self.max_retries, retry_after,
                    )
                    gevent.sleep(retry_after)
                    continue

                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                    logger.warning(
                        "[DoclingClient] '%s' attempt %d/%d failed: %s",
                        filename, attempt, self.max_retries, last_error,
                    )
                    if attempt < self.max_retries:
                        gevent.sleep(self.retry_backoff * (2 ** (attempt - 1)))
                    continue

                # Parse response
                result = self._parse_response(resp.json(), filename, should_chunk, t0)
                self._record_success()
                return result

            except requests.exceptions.Timeout:
                last_error = f"Timeout after {self.timeout}s"
                logger.error(
                    "[DoclingClient] '%s' attempt %d/%d: %s",
                    filename, attempt, self.max_retries, last_error,
                )
            except requests.exceptions.ConnectionError as exc:
                last_error = f"Connection error: {exc}"
                logger.error(
                    "[DoclingClient] '%s' attempt %d/%d: %s",
                    filename, attempt, self.max_retries, last_error,
                )
            except Exception as exc:
                last_error = f"Unexpected error: {exc}"
                logger.error(
                    "[DoclingClient] '%s' attempt %d/%d: %s",
                    filename, attempt, self.max_retries, last_error,
                    exc_info=True,
                )

            if attempt < self.max_retries:
                wait = self.retry_backoff * (2 ** (attempt - 1))
                logger.info("[DoclingClient] Retrying '%s' in %.1fs...", filename, wait)
                gevent.sleep(wait)

        # All retries exhausted
        self._record_failure()
        elapsed = time.monotonic() - t0
        logger.error(
            "[DoclingClient] '%s' FAILED after %d attempts in %.2fs: %s",
            filename, self.max_retries, elapsed, last_error,
        )
        return DoclingResult(
            filename=filename, success=False,
            error=last_error, processing_time_s=elapsed,
        )

    # ── Batch conversion ───────────────────────────────────────────

    def convert_batch(
        self,
        files: List[Tuple[bytes, str]],
        pool_size: int = None,
        use_chunking: bool = None,
        on_result: callable = None,
    ) -> List[DoclingResult]:
        """Convert multiple files concurrently using a gevent pool.

        Parameters
        ----------
        files : list of (file_data, filename) tuples
        pool_size : int, optional
            Max concurrent conversions (default: self.pool_size).
        use_chunking : bool, optional
            Override instance-level chunking setting.
        on_result : callable, optional
            Called with ``(index, DoclingResult)`` as each file completes.
            Useful for streaming results into the pipeline.

        Returns
        -------
        list of DoclingResult
            One result per input file, in the same order.
        """
        from gevent.pool import Pool

        effective_pool = pool_size or self.pool_size
        pool = Pool(size=effective_pool)
        results: List[Optional[DoclingResult]] = [None] * len(files)

        logger.info(
            "[DoclingClient] Starting batch conversion: %d files, pool=%d",
            len(files), effective_pool,
        )

        def _worker(idx: int, file_data: bytes, filename: str):
            result = self.convert_file(file_data, filename, use_chunking=use_chunking)
            results[idx] = result
            if on_result:
                try:
                    on_result(idx, result)
                except Exception as exc:
                    logger.error("[DoclingClient] on_result callback error: %s", exc)

        jobs = []
        for idx, (file_data, filename) in enumerate(files):
            job = pool.spawn(_worker, idx, file_data, filename)
            jobs.append(job)

        gevent.joinall(jobs)

        # Replace any None entries (should not happen, but be safe)
        for idx in range(len(results)):
            if results[idx] is None:
                results[idx] = DoclingResult(
                    filename=files[idx][1], success=False,
                    error='Worker did not produce a result',
                )

        succeeded = sum(1 for r in results if r.success)
        logger.info(
            "[DoclingClient] Batch complete: %d/%d succeeded",
            succeeded, len(results),
        )
        return results

    # ── Response parsing ───────────────────────────────────────────

    def _parse_response(
        self,
        payload: Dict[str, Any],
        filename: str,
        chunked: bool,
        t0: float,
    ) -> DoclingResult:
        """Parse a Docling JSON response into a ``DoclingResult``."""
        elapsed = time.monotonic() - t0

        # Handle the response structure from docling-serve
        # It may be: {"document": {...}, "chunks": [...], "status": "success"}
        # Or for newer versions: {"document": {...}}
        doc = payload.get('document', {})
        status = payload.get('status', 'unknown')

        # Extract text content
        text = (
            doc.get('md_content')
            or doc.get('text_content')
            or doc.get('html_content')
            or ''
        )
        if isinstance(text, str):
            text = _sanitize_text(text.strip())

        # Extract metadata
        page_count = doc.get('num_pages', 0) or doc.get('page_count', 0) or 0
        table_count = len(doc.get('tables', [])) if isinstance(doc.get('tables'), list) else 0
        image_count = len(doc.get('pictures', [])) if isinstance(doc.get('pictures'), list) else 0

        # Parse chunks if chunking was requested
        chunks: List[DoclingChunk] = []
        if chunked:
            raw_chunks = payload.get('chunks', [])
            if not raw_chunks:
                # Some docling-serve versions nest chunks inside the document
                raw_chunks = doc.get('chunks', [])
            for rc in raw_chunks:
                chunk_text = rc.get('text', '') or rc.get('content', '')
                if not chunk_text.strip():
                    continue
                meta = rc.get('meta', {}) or rc.get('metadata', {})
                headings = meta.get('headings', []) or rc.get('headings', [])
                pages = meta.get('page_numbers', []) or rc.get('page_numbers', [])
                chunks.append(DoclingChunk(
                    text=_sanitize_text(chunk_text.strip()),
                    metadata=meta,
                    headings=headings if isinstance(headings, list) else [],
                    page_numbers=pages if isinstance(pages, list) else [],
                ))

        success = bool(text.strip()) or bool(chunks)

        if success:
            logger.info(
                "[DoclingClient] '%s' OK: %d chars, %d chunks, %d pages, "
                "%d tables in %.2fs",
                filename, len(text), len(chunks), page_count, table_count, elapsed,
            )
        else:
            logger.warning(
                "[DoclingClient] '%s': Docling returned empty result "
                "(status=%s) in %.2fs",
                filename, status, elapsed,
            )

        return DoclingResult(
            filename=filename,
            success=success,
            text=text,
            chunks=chunks,
            extraction_method='docling',
            processing_time_s=elapsed,
            page_count=page_count,
            table_count=table_count,
            image_count=image_count,
        )


# ── Module-level singleton ─────────────────────────────────────────

_client: Optional[DoclingClient] = None


def get_docling_client(**kwargs) -> DoclingClient:
    """Return the module-level DoclingClient singleton."""
    global _client
    if _client is None:
        _client = DoclingClient(**kwargs)
    return _client


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

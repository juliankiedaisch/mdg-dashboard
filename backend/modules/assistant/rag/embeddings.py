# Assistant Module - RAG: Embeddings Service
"""
Handles embedding generation using Ollama's embedding API.

Redesigned for GPU efficiency:
• **True batch embedding** via Ollama's ``/api/embed`` endpoint (sends
  multiple texts in a single request, letting the model batch on GPU).
• **Parallel batch processing** — multiple sub-batches can run concurrently
  in separate greenlets.
• **Configurable batch sizes** optimised for RTX 4080 (16 GB VRAM).
• **Connection pooling** via ``requests.Session``.
• **Retry with back-off** on transient failures.
"""
import logging
import os
import time
import requests
from requests.adapters import HTTPAdapter
from typing import List, Optional
from src.globals import EMBEDDING_MODEL, OLLAMA_API_URL, EMBED_BATCH_SIZE, EMBED_MAX_RETRIES, EMBED_RETRY_BACKOFF, EMBED_TIMEOUT

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings via Ollama embedding API with true batch support.

    Two embedding modes:
    1. ``embed_text()`` — single text, returns one embedding vector.
    2. ``embed_batch_native()`` — sends N texts in one ``/api/embed`` call,
       GPU processes them in a single forward pass.
    3. ``embed_batch()`` — compatibility wrapper that calls ``embed_batch_native``
       under the hood but matches the old one-at-a-time signature.
    """

    def __init__(self, ollama_url: str = None, model: str = None):
        self.ollama_url = ollama_url or OLLAMA_API_URL
        self.model = model or EMBEDDING_MODEL

        # Connection-pooled session for all Ollama requests
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=4, pool_maxsize=8)
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)

    def set_model(self, model: str):
        self.model = model

    # ── Single-text embedding ──────────────────────────────────────

    def embed_text(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text string."""
        try:
            logger.debug("[Embedding] embed_text: model=%s len=%d", self.model, len(text))
            response = self._session.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=EMBED_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding")
            if embedding:
                logger.debug("[Embedding] embed_text: OK dim=%d", len(embedding))
            else:
                logger.warning("[Embedding] embed_text: response contained no 'embedding' key")
            return embedding
        except requests.RequestException as e:
            logger.error("[Embedding] embed_text FAILED (model=%s): %s", self.model, e)
            return None

    # ── Native batch embedding (GPU-optimised) ─────────────────────

    def embed_batch_native(
        self,
        texts: List[str],
        max_retries: int = None,
    ) -> List[Optional[List[float]]]:
        """Send multiple texts in a single ``/api/embed`` call.

        Ollama's ``/api/embed`` endpoint accepts an ``input`` list and returns
        an ``embeddings`` list, enabling the model to batch-process on GPU
        in a single forward pass — vastly more efficient than serial calls.

        Falls back to one-at-a-time if the batch endpoint fails.
        """
        if not texts:
            return []

        retries = max_retries if max_retries is not None else EMBED_MAX_RETRIES
        t0 = time.monotonic()

        for attempt in range(1, retries + 1):
            try:
                response = self._session.post(
                    f"{self.ollama_url}/api/embed",
                    json={"model": self.model, "input": texts},
                    timeout=EMBED_TIMEOUT,
                )
                response.raise_for_status()
                data = response.json()

                embeddings = data.get("embeddings", [])
                if len(embeddings) == len(texts):
                    elapsed = time.monotonic() - t0
                    logger.info(
                        "[Embedding] embed_batch_native: %d texts in %.2fs "
                        "(%.1f texts/s, model=%s)",
                        len(texts), elapsed,
                        len(texts) / max(elapsed, 0.001),
                        self.model,
                    )
                    return embeddings

                # Mismatch — some failed silently
                logger.warning(
                    "[Embedding] embed_batch_native: expected %d embeddings, "
                    "got %d — padding with None",
                    len(texts), len(embeddings),
                )
                result: List[Optional[List[float]]] = list(embeddings)
                while len(result) < len(texts):
                    result.append(None)
                return result

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    # /api/embed not available (older Ollama) — fall back
                    logger.info(
                        "[Embedding] /api/embed not available (404), "
                        "falling back to serial embed"
                    )
                    return self._embed_serial(texts)
                logger.warning(
                    "[Embedding] embed_batch_native attempt %d/%d: HTTP %s",
                    attempt, retries, e,
                )
            except requests.RequestException as e:
                logger.warning(
                    "[Embedding] embed_batch_native attempt %d/%d: %s",
                    attempt, retries, e,
                )

            if attempt < retries:
                wait = EMBED_RETRY_BACKOFF * (2 ** (attempt - 1))
                logger.info("[Embedding] Retrying in %.1fs...", wait)
                import gevent
                gevent.sleep(wait)

        # All retries failed — fall back to serial
        logger.error(
            "[Embedding] embed_batch_native FAILED after %d attempts, "
            "falling back to serial",
            retries,
        )
        return self._embed_serial(texts)

    def _embed_serial(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Serial fallback: embed texts one at a time."""
        import gevent
        results = []
        for i, text in enumerate(texts):
            results.append(self.embed_text(text))
            if (i + 1) % 4 == 0:
                gevent.sleep(0)
        return results

    # ── Compatibility wrapper ──────────────────────────────────────

    def embed_batch(self, texts: List[str], batch_size: int = None) -> List[Optional[List[float]]]:
        """Generate embeddings for a batch of texts.

        This is the compatibility wrapper used by the pipeline. It now
        delegates to ``embed_batch_native()`` for GPU-optimised batching,
        splitting into sub-batches of ``batch_size`` and yielding between
        them so other greenlets are not starved.
        """
        import gevent
        from modules.assistant.tasks.progress import emit_progress

        effective_batch = batch_size or EMBED_BATCH_SIZE
        total = len(texts)
        if total == 0:
            return []

        results: List[Optional[List[float]]] = []

        for i in range(0, total, effective_batch):
            chunk = texts[i:i + effective_batch]
            batch_results = self.embed_batch_native(chunk)
            results.extend(batch_results)

            # Yield and emit progress
            gevent.sleep(0)
            done = min(i + effective_batch, total)
            if done % 50 == 0 or done == total:
                emit_progress(
                    'embed',
                    f"Embedding {done}/{total}...",
                    progress=(done / max(total, 1)),
                    detail={'current': done, 'total': total, 'model': self.model},
                )

        return results

    def get_embedding_dimension(self) -> Optional[int]:
        """Get the dimension of embeddings produced by the current model."""
        test_embedding = self.embed_text("test")
        if test_embedding:
            return len(test_embedding)
        return None

    def is_available(self) -> bool:
        """Check if the embedding service is reachable (short timeout)."""
        t0 = time.monotonic()
        try:
            response = self._session.get(
                f"{self.ollama_url}/api/tags",
                timeout=(2, 3),
            )
            ok = response.status_code == 200
            logger.info("[Embedding] is_available: %s (%.3fs)", ok, time.monotonic() - t0)
            return ok
        except requests.RequestException as e:
            logger.warning("[Embedding] is_available: False (%.3fs) — %s",
                           time.monotonic() - t0, e)
            return False


# Module-level singleton
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(ollama_url: str = None, model: str = None) -> EmbeddingService:
    """Return the module-level EmbeddingService singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(ollama_url=ollama_url, model=model)
    return _embedding_service

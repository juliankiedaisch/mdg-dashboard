# Assistant Module - RAG: Vector Store (Qdrant)
"""
Interface to Qdrant vector database for storing and searching document embeddings.
"""
import logging
import threading
import time
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FilterSelector,
    FieldCondition,
    MatchValue,
    MatchAny,
    MatchText,
    TextIndexParams,
    TokenizerType,
    PayloadSchemaType,
)
import uuid as uuid_lib
from src.globals import VECTOR_DB_URL

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "assistant_documents"
DEFAULT_VECTOR_SIZE = 1024

# Separate timeouts: short for health/status checks, longer for data ops
HEALTH_TIMEOUT = 5
DATA_TIMEOUT = 30


class VectorStore:
    """Manages Qdrant vector database operations."""

    def __init__(self, qdrant_url: str = None, collection_name: str = None, vector_size: int = None):
        self.qdrant_url = qdrant_url or VECTOR_DB_URL
        self.collection_name = collection_name or DEFAULT_COLLECTION
        self.vector_size = vector_size or DEFAULT_VECTOR_SIZE
        # Under gevent monkey-patching, ``threading.local()`` becomes
        # *greenlet-local* storage.  Each greenlet (Flask request handler,
        # ingestion worker, scheduler) gets its own QdrantClient instance,
        # preventing connection pool sharing and stale-connection issues
        # between concurrent greenlets.
        self._thread_local = threading.local()
        # Set to True once ensure_collection() has succeeded in this process so
        # we skip the GET /collections round-trip on every search/upsert.
        self._collection_ensured: bool = False

    def _make_client(self, timeout: int = DATA_TIMEOUT) -> QdrantClient:
        """Create a new QdrantClient instance."""
        logger.debug("[Qdrant] Creating client url=%s timeout=%s thread=%s",
                     self.qdrant_url, timeout, threading.current_thread().name)
        return QdrantClient(url=self.qdrant_url, timeout=timeout)

    @property
    def client(self) -> QdrantClient:
        """Return a QdrantClient that is private to the current OS thread."""
        if not hasattr(self._thread_local, 'client') or self._thread_local.client is None:
            self._thread_local.client = self._make_client(DATA_TIMEOUT)
        return self._thread_local.client

    def _health_client(self) -> QdrantClient:
        """Return a short-timeout client for health / status checks."""
        if not hasattr(self._thread_local, '_health_client') or self._thread_local._health_client is None:
            self._thread_local._health_client = self._make_client(HEALTH_TIMEOUT)
        return self._thread_local._health_client

    def ensure_collection(self):
        """Create collection if it doesn't exist using the current self.vector_size.
        Safe to call from search paths — will NOT recreate an existing collection
        even if the dimension differs. Use ensure_collection_with_size() from the
        ingestion path where the actual embedding dimension is known.
        """
        if self._collection_ensured:
            return True
        t0 = time.monotonic()
        try:
            collections = self.client.get_collections().collections
            names = [c.name for c in collections]
            if self.collection_name in names:
                # Collection exists — read its actual dimension and remember it
                try:
                    info = self.client.get_collection(self.collection_name)
                    vparams = info.config.params.vectors
                    if hasattr(vparams, 'size'):
                        self.vector_size = vparams.size
                except Exception:
                    pass
                self._collection_ensured = True
                self._ensure_text_indexes()
                logger.info("[Qdrant] ensure_collection: '%s' already exists (dim=%d), reusing",
                            self.collection_name, self.vector_size)
                return True
            # Doesn't exist yet — create with our current size
            logger.info("[Qdrant] ensure_collection: creating '%s' (dim=%d)...",
                        self.collection_name, self.vector_size)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
            self._collection_ensured = True
            self._ensure_text_indexes()
            logger.info("[Qdrant] ensure_collection: '%s' created (dim=%d) in %.3fs",
                        self.collection_name, self.vector_size, time.monotonic() - t0)
            return True
        except UnexpectedResponse as e:
            if e.status_code == 409:
                # Another greenlet/process created the collection between our
                # existence check and our create call — perfectly fine.
                logger.info("[Qdrant] ensure_collection: '%s' already exists "
                            "(409 conflict, concurrent creation) — reusing",
                            self.collection_name)
                self._collection_ensured = True
                return True
            logger.error("[Qdrant] ensure_collection FAILED after %.3fs: %s",
                         time.monotonic() - t0, e)
            return False
        except Exception as e:
            logger.error("[Qdrant] ensure_collection FAILED after %.3fs: %s",
                         time.monotonic() - t0, e)
            return False

    def ensure_collection_with_size(self, size: int) -> bool:
        """
        Create or recreate the collection with the given vector size.

        If the collection already exists with a different dimension it is deleted
        and recreated automatically, so switching embedding models works without
        manual intervention.  Updates self.vector_size to the value actually used.
        """
        t0 = time.monotonic()
        try:
            collections = self.client.get_collections().collections
            names = [c.name for c in collections]

            if self.collection_name in names:
                # Read the dimension that Qdrant actually stored
                info = self.client.get_collection(self.collection_name)
                try:
                    vparams = info.config.params.vectors
                    existing_size = vparams.size if hasattr(vparams, 'size') else size
                except Exception:
                    existing_size = size  # can't read; assume OK

                if existing_size == size:
                    self.vector_size = size
                    self._collection_ensured = True
                    logger.info("[Qdrant] ensure_collection_with_size: '%s' exists "
                                "with correct dim=%d, reusing",
                                self.collection_name, size)
                    return True

                # Dimension mismatch — delete and recreate
                logger.warning(
                    "[Qdrant] Dimension mismatch: collection has dim=%d, "
                    "new embedding model gives dim=%d. "
                    "Deleting collection and recreating with correct dimension.",
                    existing_size, size,
                )
                self.client.delete_collection(self.collection_name)
                self._collection_ensured = False

            logger.info("[Qdrant] Creating collection '%s' (dim=%d)...",
                        self.collection_name, size)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=size,
                    distance=Distance.COSINE,
                ),
            )
            self.vector_size = size
            self._collection_ensured = True
            self._ensure_text_indexes()
            logger.info("[Qdrant] Collection '%s' created (dim=%d) in %.3fs",
                        self.collection_name, size, time.monotonic() - t0)
            return True
        except UnexpectedResponse as e:
            if e.status_code == 409:
                # Concurrent creation — the collection now exists with the
                # correct dimension; treat as success.
                logger.info("[Qdrant] ensure_collection_with_size: '%s' already exists "
                            "(409 conflict, concurrent creation) — reusing",
                            self.collection_name)
                self.vector_size = size
                self._collection_ensured = True
                return True
            logger.error("[Qdrant] ensure_collection_with_size FAILED after %.3fs: %s",
                         time.monotonic() - t0, e)
            return False
        except Exception as e:
            logger.error("[Qdrant] ensure_collection_with_size FAILED after %.3fs: %s",
                         time.monotonic() - t0, e)
            return False

    def _ensure_text_indexes(self):
        """Create full-text payload indexes on ``title`` and ``chunk_text``.

        Qdrant text indexes allow fast substring / token matching via
        ``MatchText`` filters, enabling scalable server-side search even
        with 500k+ documents.  The call is idempotent — Qdrant silently
        ignores the request if the index already exists.
        """
        for field_name in ('title', 'chunk_text'):
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=TextIndexParams(
                        type='text',
                        tokenizer=TokenizerType.WORD,
                        min_token_len=2,
                        max_token_len=20,
                        lowercase=True,
                    ),
                )
                logger.debug("[Qdrant] Text index on '%s' ensured", field_name)
            except Exception:
                # Index already exists or other non-critical issue
                pass

    def upsert_documents(self, documents: List[Dict[str, Any]]) -> int:
        """
        Upsert documents into the vector store.
        
        Each document dict must have:
            - 'id': str (unique identifier)
            - 'embedding': List[float]
            - 'metadata': dict (source, title, chunk_text, chunk_position, document_url, permission_tags, etc.)
        """
        # Detect actual embedding dimension from the first document so the
        # collection is created (or recreated) with the right size automatically.
        first_embedding = next(
            (doc['embedding'] for doc in documents if doc.get('embedding')), None
        )
        if first_embedding is not None:
            self.ensure_collection_with_size(len(first_embedding))
        else:
            self.ensure_collection()
        points = []
        for doc in documents:
            point_id = doc.get('id', str(uuid_lib.uuid4()))
            points.append(
                PointStruct(
                    id=point_id,
                    vector=doc['embedding'],
                    payload=doc.get('metadata', {}),
                )
            )
        if not points:
            return 0

        batch_size = 100
        total = 0
        total_batches = (len(points) + batch_size - 1) // batch_size
        from modules.assistant.tasks.progress import emit_progress
        for batch_idx, i in enumerate(range(0, len(points), batch_size)):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
            total += len(batch)
            # Yield control so Flask request greenlets are not blocked
            # during large upserts.
            import gevent
            gevent.sleep(0)
            emit_progress('store',
                          f"Qdrant Batch {batch_idx + 1}/{total_batches} ({total}/{len(points)} Punkte)...",
                          progress=(total / max(len(points), 1)),
                          detail={'batch': batch_idx + 1, 'total_batches': total_batches,
                                  'points_stored': total, 'total_points': len(points)})
        logger.info(f"Upserted {total} points into '{self.collection_name}'") 
        return total

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        source_filter: Optional[str] = None,
        permission_tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.
        
        Args:
            query_vector: The query embedding
            top_k: Number of results to return
            source_filter: Filter by source type (e.g., 'bookstack')
            permission_tags: Filter by permission tags the user has access to
            
        Returns:
            List of dicts with 'id', 'score', and 'metadata' keys.
        """
        self.ensure_collection()
        must_conditions = []

        if source_filter:
            must_conditions.append(
                FieldCondition(key="source", match=MatchValue(value=source_filter))
            )

        if permission_tags is not None:
            # Only return docs the user has access to (empty list = public)
            must_conditions.append(
                FieldCondition(
                    key="permission_tags",
                    match=MatchAny(any=permission_tags + ["public"]),
                )
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None

        try:
            logger.info("[Qdrant] search: top_k=%d filter=%s permission_tags=%s dim=%d collection=%s",
                        top_k, source_filter, permission_tags,
                        len(query_vector), self.collection_name)

            # Verify the collection exists and check point count for diagnostics
            if not self._collection_ensured:
                logger.warning("[Qdrant] search: collection not yet ensured — calling ensure_collection()")

            # client.search() was removed in qdrant-client >= 1.7; use query_points()
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            )
            hits = response.points
            logger.info("[Qdrant] search: returned %d results (collection=%s)",
                        len(hits), self.collection_name)
            if len(hits) == 0:
                # Diagnostic: how many total points exist?
                try:
                    total = self.count_points()
                    logger.warning(
                        "[Qdrant] search returned 0 results but collection "
                        "has %d total points. filter=%s permission_tags=%s "
                        "query_dim=%d collection_dim=%d",
                        total, query_filter, permission_tags,
                        len(query_vector), self.vector_size,
                    )
                except Exception:
                    pass
            return [
                {
                    'id': str(hit.id),
                    'score': hit.score,
                    'metadata': hit.payload,
                }
                for hit in hits
            ]
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def delete_by_source(self, source_id: int) -> bool:
        """Delete all points belonging to a specific source."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[FieldCondition(key="source_id", match=MatchValue(value=source_id))]
                    )
                ),
            )
            logger.info(f"Deleted points for source_id={source_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete by source: {e}")
            return False

    def get_points_by_ids(self, point_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch specific points by their Qdrant IDs (payload only, no vectors).

        Used by the parent-child retrieval pipeline to look up parent chunks
        after finding relevant children.

        Returns:
            List of dicts with 'id' and 'payload'.
        """
        if not point_ids:
            return []
        try:
            self.ensure_collection()
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=point_ids,
                with_payload=True,
                with_vectors=False,
            )
            return [
                {
                    'id': str(p.id),
                    'payload': p.payload,
                }
                for p in points
            ]
        except Exception as e:
            logger.error("[Qdrant] get_points_by_ids FAILED (%d ids): %s",
                         len(point_ids), e)
            return []

    def delete_by_metadata(self, conditions: Dict[str, Any]) -> bool:
        """Delete points matching arbitrary metadata field conditions.

        Args:
            conditions: Dict of ``{field_name: value}`` pairs.  All
                conditions are combined with AND logic.

        Returns:
            True on success, False on error.
        """
        if not conditions:
            logger.warning("[Qdrant] delete_by_metadata called with empty conditions — skipping")
            return False
        try:
            must = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in conditions.items()
            ]
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=FilterSelector(
                    filter=Filter(must=must)
                ),
            )
            logger.info("[Qdrant] Deleted points matching %s", conditions)
            return True
        except Exception as e:
            logger.error("[Qdrant] delete_by_metadata failed (%s): %s", conditions, e)
            return False

    def delete_collection(self) -> bool:
        """Delete the entire collection (for rebuild)."""
        try:
            self.client.delete_collection(self.collection_name)
            # Reset the cache so the next upsert/search recreates the collection.
            self._collection_ensured = False
            logger.info(f"Deleted collection '{self.collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False

    def get_collection_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the collection.

        Ensures the collection exists first so a brand-new Qdrant instance
        doesn't report itself as unavailable.  Uses a short-timeout client
        so a status-page load never blocks the server.
        """
        t0 = time.monotonic()
        try:
            self.ensure_collection()
            logger.debug("[Qdrant] get_collection_info: fetching '%s'...", self.collection_name)
            info = self._health_client().get_collection(self.collection_name)
            # 'vectors_count' was removed in qdrant-client >= 1.7; fall back to 'points_count'
            vectors_count = (
                getattr(info, 'vectors_count', None)
                or getattr(info, 'points_count', None)
                or 0
            )
            points_count = getattr(info, 'points_count', None) or 0
            status = getattr(info, 'status', None)
            # Read the actual stored vector dimension
            try:
                vparams = info.config.params.vectors
                actual_dim = vparams.size if hasattr(vparams, 'size') else self.vector_size
            except Exception:
                actual_dim = self.vector_size
            logger.info("[Qdrant] get_collection_info: OK (points=%s, dim=%s, status=%s) in %.3fs",
                        points_count, actual_dim, status, time.monotonic() - t0)
            return {
                'name': self.collection_name,
                'vectors_count': vectors_count,
                'points_count': points_count,
                'vector_size': actual_dim,
                'status': status.value if status else 'unknown',
            }
        except Exception as e:
            logger.error("[Qdrant] get_collection_info FAILED after %.3fs: %s",
                         time.monotonic() - t0, e)
            return None

    def scroll_sample(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return a sample of stored points (metadata only, no vectors)."""
        try:
            self.ensure_collection()
            records, _next = self.client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            return [
                {
                    'id': str(r.id),
                    'payload': r.payload,
                }
                for r in records
            ]
        except Exception as e:
            logger.error("[Qdrant] scroll_sample FAILED: %s", e)
            return []

    def scroll_documents(
        self,
        limit: int = 50,
        offset: Optional[str] = None,
        source_id: Optional[int] = None,
        source: Optional[str] = None,
        tag: Optional[str] = None,
        title_search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Paginated scroll through stored points with optional filtering.

        ``title_search`` uses Qdrant's full-text MatchText filter on indexed
        ``title`` and ``chunk_text`` fields, enabling scalable search across
        500k+ documents without client-side filtering.

        Returns ``{'records': [...], 'next_offset': str|None, 'total': int}``.
        Each record contains ``id`` and ``payload`` (no vectors).
        """
        try:
            self.ensure_collection()

            # Build optional filter
            must_conditions = []
            if source_id is not None:
                must_conditions.append(
                    FieldCondition(key="source_id", match=MatchValue(value=source_id))
                )
            if source:
                must_conditions.append(
                    FieldCondition(key="source", match=MatchValue(value=source))
                )
            if tag:
                must_conditions.append(
                    FieldCondition(key="permission_tags", match=MatchValue(value=tag))
                )

            # Server-side full-text search via Qdrant text indexes.
            # Uses ``should`` (OR) to match in either title or chunk_text.
            should_text_conditions = []
            if title_search:
                search_term = title_search.strip()
                should_text_conditions.append(
                    FieldCondition(key="title", match=MatchText(text=search_term))
                )
                should_text_conditions.append(
                    FieldCondition(key="chunk_text", match=MatchText(text=search_term))
                )

            if should_text_conditions:
                # Wrap the text conditions in a nested Filter with should (OR)
                text_filter = Filter(should=should_text_conditions)
                must_conditions.append(text_filter)

            scroll_filter = Filter(must=must_conditions) if must_conditions else None

            # Qdrant scroll offset must be a point ID (string UUID) or None
            scroll_offset = offset if offset else None

            records, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                offset=scroll_offset,
                scroll_filter=scroll_filter,
                with_payload=True,
                with_vectors=False,
            )

            results = []
            for r in records:
                payload = r.payload or {}
                results.append({
                    'id': str(r.id),
                    'payload': payload,
                })

            # Total count (with filter if applicable)
            total = self._count_with_filter(scroll_filter)

            return {
                'records': results,
                'next_offset': str(next_offset) if next_offset else None,
                'total': total,
            }
        except Exception as e:
            logger.error("[Qdrant] scroll_documents FAILED: %s", e)
            return {'records': [], 'next_offset': None, 'total': 0}

    def _count_with_filter(self, scroll_filter: Optional[Filter] = None) -> int:
        """Count points matching a filter, or total points if no filter."""
        try:
            if scroll_filter is not None:
                self.ensure_collection()
                result = self.client.count(
                    collection_name=self.collection_name,
                    count_filter=scroll_filter,
                    exact=False,
                )
                return result.count
            return self.count_points()
        except Exception:
            return self.count_points()

    def count_points(self) -> int:
        """Return the total number of points in the collection."""
        try:
            self.ensure_collection()
            info = self._health_client().get_collection(self.collection_name)
            return getattr(info, 'points_count', 0) or 0
        except Exception:
            return 0

    def count_points_by_source(self) -> Dict[int, int]:
        """Count points in Qdrant grouped by source_id.

        Scrolls through all points (payload only) and tallies the
        ``source_id`` field.  This is intentionally a full scan so
        that DB counts can be reconciled with actual Qdrant state.
        """
        counts: Dict[int, int] = {}
        try:
            self.ensure_collection()
            offset = None
            while True:
                records, next_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=250,
                    offset=offset,
                    with_payload=['source_id'],
                    with_vectors=False,
                )
                for r in records:
                    sid = r.payload.get('source_id')
                    if sid is not None:
                        counts[sid] = counts.get(sid, 0) + 1
                if next_offset is None:
                    break
                offset = next_offset
        except Exception as e:
            logger.error("[Qdrant] count_points_by_source FAILED: %s", e)
        return counts

    def is_available(self) -> bool:
        """Check if Qdrant is reachable (short timeout)."""
        t0 = time.monotonic()
        try:
            self._health_client().get_collections()
            logger.debug("[Qdrant] is_available: True (%.3fs)", time.monotonic() - t0)
            return True
        except Exception as e:
            logger.warning("[Qdrant] is_available: False (%.3fs) — %s",
                           time.monotonic() - t0, e)
            return False


# Module-level singleton
_vector_store: Optional[VectorStore] = None


def get_vector_store(qdrant_url: str = None, collection_name: str = None, vector_size: int = None) -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(qdrant_url=qdrant_url, collection_name=collection_name, vector_size=vector_size)
    return _vector_store

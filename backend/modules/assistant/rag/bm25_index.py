# Assistant Module - RAG: BM25 Keyword Search Index
"""
Lightweight BM25 (Okapi BM25) index for hybrid retrieval.

Maintained as an in-memory index built from the Qdrant vector store
and serialised to disk for persistence across restarts.

Designed for 30k+ document collections.
"""
import logging
import math
import os
import pickle
import re
import time
import threading
from collections import Counter
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Persistence path
BM25_INDEX_PATH = os.getenv('BM25_INDEX_PATH', '/tmp/assistant_bm25_index.pkl')

# German + English stopwords (compact set)
STOP_WORDS = frozenset({
    # German
    'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einen', 'einem', 'einer',
    'und', 'oder', 'aber', 'wenn', 'als', 'wie', 'dass', 'weil', 'da', 'so',
    'ist', 'sind', 'war', 'wird', 'hat', 'haben', 'sein', 'werden',
    'ich', 'du', 'er', 'sie', 'es', 'wir', 'ihr', 'mein', 'dein',
    'in', 'an', 'auf', 'für', 'mit', 'von', 'zu', 'bei', 'nach', 'über', 'unter',
    'nicht', 'auch', 'nur', 'schon', 'noch', 'mehr', 'sehr', 'hier', 'dort',
    # English
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
    'of', 'to', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
    'and', 'or', 'but', 'if', 'not', 'this', 'that', 'it', 'its',
})


def tokenize(text: str) -> List[str]:
    """Simple word tokenizer with lowercasing and stopword removal."""
    tokens = re.findall(r'\b\w+\b', text.lower())
    return [t for t in tokens if t not in STOP_WORDS and len(t) >= 2]


class BM25Index:
    """Okapi BM25 index for keyword search.

    Thread-safe (uses a lock for build/update operations).
    Optimised for collections of 30k+ documents.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._lock = threading.Lock()

        # Index data
        self.doc_ids: List[str] = []            # Qdrant point IDs
        self.doc_metadata: List[Dict] = []      # Minimal metadata for filtering
        self.corpus: List[List[str]] = []       # Tokenised documents
        self.doc_len: List[int] = []
        self.avgdl: float = 0
        self.idf: Dict[str, float] = {}
        self.N: int = 0
        self._built: bool = False

    @property
    def is_built(self) -> bool:
        return self._built

    def build_from_documents(self, documents: List[Dict[str, Any]]) -> int:
        """Build the BM25 index from a list of document dicts.

        Each dict should have:
          - 'id': Qdrant point ID (str)
          - 'payload': dict with 'chunk_text', 'permission_tags', etc.

        Returns the number of indexed documents.
        """
        t0 = time.monotonic()
        with self._lock:
            self.doc_ids = []
            self.doc_metadata = []
            self.corpus = []

            for doc in documents:
                doc_id = doc.get('id', '')
                payload = doc.get('payload', {})
                chunk_text = payload.get('chunk_text', '')

                if not chunk_text:
                    continue

                tokens = tokenize(chunk_text)
                if not tokens:
                    continue

                self.doc_ids.append(doc_id)
                self.doc_metadata.append({
                    'permission_tags': payload.get('permission_tags', []),
                    'source_type': payload.get('source_type', 'unknown'),
                    'title': payload.get('title', ''),
                    'source': payload.get('source', ''),
                    'chunk_role': payload.get('chunk_role', ''),
                })
                self.corpus.append(tokens)

            self._compute_statistics()
            self._built = True

        elapsed = time.monotonic() - t0
        logger.info("[BM25] Index built: %d documents in %.2fs", self.N, elapsed)
        return self.N

    def _compute_statistics(self):
        """Compute IDF and average document length."""
        self.N = len(self.corpus)
        self.doc_len = [len(doc) for doc in self.corpus]
        self.avgdl = sum(self.doc_len) / max(self.N, 1)

        # Document frequency
        df: Counter = Counter()
        for doc in self.corpus:
            seen = set(doc)
            for word in seen:
                df[word] += 1

        # IDF with smoothing
        self.idf = {}
        for word, freq in df.items():
            self.idf[word] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1)

    def search(
        self,
        query: str,
        top_k: int = 50,
        permission_tags: Optional[List[str]] = None,
        chunk_role_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search the BM25 index.

        Returns list of dicts: [{'id': str, 'bm25_score': float, 'metadata': dict}, ...]
        """
        if not self._built or self.N == 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        t0 = time.monotonic()
        scores = []

        allowed_tags = None
        if permission_tags is not None:
            allowed_tags = set(permission_tags)
            allowed_tags.add('public')

        for idx in range(self.N):
            # Permission filtering
            if allowed_tags is not None:
                doc_tags = set(self.doc_metadata[idx].get('permission_tags', []))
                if not doc_tags.intersection(allowed_tags):
                    continue

            # Chunk role filtering
            if chunk_role_filter:
                role = self.doc_metadata[idx].get('chunk_role', '')
                if role and role != chunk_role_filter:
                    continue

            score = self._score_document(query_tokens, idx)
            if score > 0:
                scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        scores = scores[:top_k]

        elapsed = time.monotonic() - t0
        logger.debug("[BM25] Search '%s' → %d results in %.3fs",
                     query[:50], len(scores), elapsed)

        return [
            {
                'id': self.doc_ids[idx],
                'bm25_score': score,
                'metadata': self.doc_metadata[idx],
            }
            for idx, score in scores
        ]

    def _score_document(self, query_tokens: List[str], doc_idx: int) -> float:
        """Compute BM25 score for a single document."""
        doc = self.corpus[doc_idx]
        dl = self.doc_len[doc_idx]
        tf = Counter(doc)

        score = 0.0
        for q in query_tokens:
            idf = self.idf.get(q, 0)
            if idf == 0:
                continue
            f = tf.get(q, 0)
            if f == 0:
                continue
            numerator = f * (self.k1 + 1)
            denominator = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            score += idf * (numerator / denominator)

        return score

    def save(self, path: str = None):
        """Persist the index to disk."""
        path = path or BM25_INDEX_PATH
        try:
            data = {
                'doc_ids': self.doc_ids,
                'doc_metadata': self.doc_metadata,
                'corpus': self.corpus,
                'doc_len': self.doc_len,
                'avgdl': self.avgdl,
                'idf': self.idf,
                'N': self.N,
                'k1': self.k1,
                'b': self.b,
            }
            with open(path, 'wb') as f:
                pickle.dump(data, f)
            logger.info("[BM25] Index saved to %s (%d docs)", path, self.N)
        except Exception as e:
            logger.error("[BM25] Failed to save index: %s", e)

    def load(self, path: str = None) -> bool:
        """Load the index from disk."""
        path = path or BM25_INDEX_PATH
        try:
            if not os.path.exists(path):
                return False
            with open(path, 'rb') as f:
                data = pickle.load(f)
            self.doc_ids = data['doc_ids']
            self.doc_metadata = data['doc_metadata']
            self.corpus = data['corpus']
            self.doc_len = data['doc_len']
            self.avgdl = data['avgdl']
            self.idf = data['idf']
            self.N = data['N']
            self.k1 = data.get('k1', 1.5)
            self.b = data.get('b', 0.75)
            self._built = True
            logger.info("[BM25] Index loaded from %s (%d docs)", path, self.N)
            return True
        except Exception as e:
            logger.error("[BM25] Failed to load index: %s", e)
            return False

    def add_documents(self, documents: List[Dict[str, Any]]):
        """Incrementally add documents to the index.

        NOTE: IDF values won't be perfectly accurate until a full rebuild.
        Suitable for incremental ingestion between full rebuilds.
        """
        with self._lock:
            for doc in documents:
                doc_id = doc.get('id', '')
                payload = doc.get('payload', doc.get('metadata', {}))
                chunk_text = payload.get('chunk_text', '')

                if not chunk_text:
                    continue

                tokens = tokenize(chunk_text)
                if not tokens:
                    continue

                self.doc_ids.append(doc_id)
                self.doc_metadata.append({
                    'permission_tags': payload.get('permission_tags', []),
                    'source_type': payload.get('source_type', 'unknown'),
                    'title': payload.get('title', ''),
                    'source': payload.get('source', ''),
                    'chunk_role': payload.get('chunk_role', ''),
                })
                self.corpus.append(tokens)

            self._compute_statistics()
            if not self._built and self.N > 0:
                self._built = True

    def build_from_vector_store(self) -> int:
        """Build the BM25 index by scrolling the entire Qdrant collection.

        Convenience method that fetches all documents from the vector store
        and builds the index in one call.  Returns document count.
        """
        from modules.assistant.rag.vector_store import get_vector_store

        vs = get_vector_store()
        all_docs = []
        offset = None

        logger.info("[BM25] Building index from vector store...")
        while True:
            try:
                vs.ensure_collection()
                records, next_offset = vs.client.scroll(
                    collection_name=vs.collection_name,
                    limit=250,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                for r in records:
                    all_docs.append({
                        'id': str(r.id),
                        'payload': r.payload or {},
                    })
                if next_offset is None:
                    break
                offset = next_offset
            except Exception as e:
                logger.error("[BM25] Failed to scroll vector store: %s", e)
                break

        count = self.build_from_documents(all_docs)
        self.save()
        return count


# Module-level singleton
_bm25_index: Optional[BM25Index] = None


def get_bm25_index() -> BM25Index:
    """Return the module-level BM25 index singleton."""
    global _bm25_index
    if _bm25_index is None:
        _bm25_index = BM25Index()
        # Try to load from disk
        _bm25_index.load()
    return _bm25_index

# Assistant Module - Ingestion: Chunker
"""
Splits documents into overlapping chunks suitable for embedding.

Supports two modes:
1. **Flat chunking** (default) — single-level overlapping chunks.
2. **Parent-child chunking** — two-level architecture where large parent
   chunks provide LLM context and small child chunks are used for
   embedding/search.
"""
import re
import uuid as uuid_lib
import gevent
from typing import List, Dict, Any


class TextChunker:
    """Split text into overlapping chunks."""

    def __init__(self, chunk_size: int = 800, overlap: int = 150):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks with overlap.
        Tries to split on paragraph/sentence boundaries.
        """
        if not text or not text.strip():
            return []

        # Normalize whitespace
        text = re.sub(r'\r\n', '\n', text)
        text = text.strip()

        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            if end >= len(text):
                chunks.append(text[start:].strip())
                break

            # Try to find a good break point
            break_point = self._find_break_point(text, start, end)
            chunk = text[start:break_point].strip()

            if chunk:
                chunks.append(chunk)

            # Move forward by chunk_size - overlap
            start = break_point - self.overlap
            if start < 0:
                start = 0
            # Prevent infinite loop
            if start >= break_point:
                start = break_point

        return chunks

    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """Find the best break point near the end of a chunk."""
        # Look for paragraph break
        para_break = text.rfind('\n\n', start + self.chunk_size // 2, end)
        if para_break > start:
            return para_break + 2

        # Look for sentence end
        for pattern in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
            sent_break = text.rfind(pattern, start + self.chunk_size // 2, end)
            if sent_break > start:
                return sent_break + len(pattern)

        # Look for line break
        line_break = text.rfind('\n', start + self.chunk_size // 2, end)
        if line_break > start:
            return line_break + 1

        # Look for word boundary
        word_break = text.rfind(' ', start + self.chunk_size // 2, end)
        if word_break > start:
            return word_break + 1

        # Fall back to hard cut
        return end

    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunk a list of document dicts.
        
        Each input dict should have 'text' and 'metadata' keys.
        Returns a list of dicts with the same structure, but with chunked text
        and chunk_position added to metadata.
        """
        result = []

        for doc_idx, doc in enumerate(documents):
            text = doc.get('text', '')
            metadata = doc.get('metadata', {})
            chunks = self.chunk_text(text)

            for i, chunk in enumerate(chunks):
                chunk_metadata = dict(metadata)
                chunk_metadata['chunk_text'] = chunk
                chunk_metadata['chunk_position'] = i
                chunk_metadata['total_chunks'] = len(chunks)
                result.append({
                    'text': chunk,
                    'metadata': chunk_metadata,
                })

            # Yield control every 10 documents so Flask requests are not starved
            if (doc_idx + 1) % 10 == 0:
                gevent.sleep(0)

        return result


class ParentChildChunker:
    """Two-level chunking: parent chunks for LLM context, child chunks for search.

    Parent chunks: ~800–1500 tokens (≈ 3200–6000 chars)
    Child chunks:  ~200–400 tokens  (≈ 800–1600 chars)

    Each child stores a ``parent_id`` reference.  During retrieval the
    system searches on child chunks, then expands to parent chunks for
    the LLM context, ensuring richer surrounding information.
    """

    def __init__(
        self,
        parent_chunk_size: int = 3200,
        parent_overlap: int = 400,
        child_chunk_size: int = 800,
        child_overlap: int = 150,
    ):
        self.parent_chunker = TextChunker(
            chunk_size=parent_chunk_size, overlap=parent_overlap,
        )
        self.child_chunker = TextChunker(
            chunk_size=child_chunk_size, overlap=child_overlap,
        )

    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Produce parent and child chunks from documents.

        Returns a flat list of chunk dicts.  Each dict has:
          - ``text``: chunk text (used for embedding)
          - ``metadata``: includes ``chunk_role`` (``'parent'`` | ``'child'``),
            ``parent_id``, and the usual fields.
        """
        result: List[Dict[str, Any]] = []

        for doc_idx, doc in enumerate(documents):
            text = doc.get('text', '')
            metadata = doc.get('metadata', {})

            # --- Create parent chunks ---
            parent_texts = self.parent_chunker.chunk_text(text)

            for p_idx, parent_text in enumerate(parent_texts):
                parent_id = str(uuid_lib.uuid4())

                # Parent chunk
                parent_meta = dict(metadata)
                parent_meta['chunk_text'] = parent_text
                parent_meta['chunk_position'] = p_idx
                parent_meta['total_chunks'] = len(parent_texts)
                parent_meta['chunk_role'] = 'parent'
                parent_meta['parent_id'] = parent_id
                parent_meta['chunking_method'] = 'parent_child'
                result.append({
                    'text': parent_text,
                    'metadata': parent_meta,
                })

                # --- Create child chunks from this parent ---
                child_texts = self.child_chunker.chunk_text(parent_text)

                for c_idx, child_text in enumerate(child_texts):
                    child_meta = dict(metadata)
                    child_meta['chunk_text'] = child_text
                    child_meta['chunk_position'] = c_idx
                    child_meta['total_chunks'] = len(child_texts)
                    child_meta['chunk_role'] = 'child'
                    child_meta['parent_id'] = parent_id
                    child_meta['parent_position'] = p_idx
                    child_meta['chunking_method'] = 'parent_child'
                    result.append({
                        'text': child_text,
                        'metadata': child_meta,
                    })

            # Yield control periodically
            if (doc_idx + 1) % 10 == 0:
                gevent.sleep(0)

        return result

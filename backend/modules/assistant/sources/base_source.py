# Assistant Module - Sources: Base Source Interface
"""
Abstract base class for all knowledge source connectors.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Iterator
from datetime import datetime


class DocumentChunk:
    """Represents a single document chunk from a source."""

    def __init__(
        self,
        text: str,
        title: str,
        source: str,
        source_id: int,
        document_url: str = '',
        chunk_position: int = 0,
        permission_tags: Optional[List[str]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
        docling_chunks: Optional[List] = None,
        source_type: str = 'unknown',
    ):
        self.text = text
        self.title = title
        self.source = source
        self.source_id = source_id
        self.document_url = document_url
        self.chunk_position = chunk_position
        self.permission_tags = permission_tags or ['public']
        self.extra_metadata = extra_metadata or {}
        # Pre-computed semantic chunks from Docling (if available).
        # When set, the pipeline will use these instead of running the
        # local TextChunker — preserving document-structure-aware splits.
        self.docling_chunks = docling_chunks
        # Technical metadata tag for retrieval weighting (not a permission tag).
        # Values: 'page', 'attachment', 'external_document', 'unknown'
        self.source_type = source_type

    def to_metadata(self) -> Dict[str, Any]:
        metadata = {
            'title': self.title,
            'source': self.source,
            'source_id': self.source_id,
            'document_url': self.document_url,
            'chunk_text': self.text,
            'chunk_position': self.chunk_position,
            'permission_tags': self.permission_tags,
            'source_type': self.source_type,
        }
        metadata.update(self.extra_metadata)
        return metadata


class BaseSource(ABC):
    """Abstract base class for knowledge source connectors."""

    def __init__(self, source_config: Dict[str, Any]):
        """
        Initialize the source connector.
        
        Args:
            source_config: Configuration dict from SourceConfig model.
        """
        self.source_config = source_config
        self.source_id = source_config.get('id', 0)
        self.source_name = source_config.get('name', 'unknown')

    @abstractmethod
    def fetch_documents(self) -> List[DocumentChunk]:
        """
        Fetch all documents from this source.

        Returns:
            List of DocumentChunk objects.
        """
        pass

    def fetch_documents_stream(self) -> Iterator[DocumentChunk]:
        """Streaming variant: yields DocumentChunks as they become available.

        The default implementation simply yields from :meth:`fetch_documents`,
        so every source automatically supports streaming.  Override this method
        in subclasses where documents can be yielded incrementally (e.g. yield
        pages/chapters before slow attachment extraction is complete).
        """
        yield from self.fetch_documents()

    @abstractmethod
    def sync(self, last_sync: Optional[datetime] = None) -> List[DocumentChunk]:
        """
        Incremental sync: fetch only new/updated documents since last sync.
        
        Args:
            last_sync: Timestamp of the last successful sync.
            
        Returns:
            List of new/updated DocumentChunk objects.
        """
        pass

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection to this source.
        
        Returns:
            Dict with 'success' (bool) and 'message' (str).
        """
        pass

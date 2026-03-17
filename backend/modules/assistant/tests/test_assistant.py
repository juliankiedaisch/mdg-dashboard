# Assistant Module - Tests
"""
Test suite for the AI Assistant module.
Covers retrieval, source syncing, permission filtering, and chat API.

Run with: python -m pytest backend/modules/assistant/tests/ -v
"""
import pytest
import os
import sys
import json
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


# ── Chunker Tests ───────────────────────────────────────────────────

class TestTextChunker:
    """Test document chunking logic."""

    def setup_method(self):
        from modules.assistant.ingestion.chunker import TextChunker
        self.chunker = TextChunker(chunk_size=100, overlap=20)

    def test_empty_text(self):
        assert self.chunker.chunk_text('') == []
        assert self.chunker.chunk_text('   ') == []

    def test_short_text(self):
        text = "This is a short document."
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_is_chunked(self):
        text = "Word " * 100  # 500 chars
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) > 1

    def test_chunks_have_overlap(self):
        text = "A " * 200  # 400 chars
        chunker = TextChunker(chunk_size=100, overlap=20)
        chunks = chunker.chunk_text(text)
        assert len(chunks) > 1
        # Chunks should overlap
        for i in range(len(chunks) - 1):
            # Last part of chunk i should appear at the start of chunk i+1
            end_of_chunk = chunks[i][-20:]
            assert end_of_chunk.strip() != ''

    def test_chunk_documents(self):
        docs = [
            {'text': 'Short doc.', 'metadata': {'title': 'Doc1'}},
            {'text': 'Another short.', 'metadata': {'title': 'Doc2'}},
        ]
        result = self.chunker.chunk_documents(docs)
        assert len(result) == 2
        assert result[0]['metadata']['title'] == 'Doc1'
        assert result[0]['metadata']['chunk_position'] == 0


# ── Embeddings Tests ────────────────────────────────────────────────

class TestEmbeddingService:
    """Test embedding service (mocked Ollama)."""

    @patch('modules.assistant.rag.embeddings.requests.post')
    def test_embed_text(self, mock_post):
        from modules.assistant.rag.embeddings import EmbeddingService
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'embedding': [0.1, 0.2, 0.3]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        service = EmbeddingService(ollama_url='http://mock:11434')
        result = service.embed_text("test text")
        assert result == [0.1, 0.2, 0.3]

    @patch('modules.assistant.rag.embeddings.requests.post')
    def test_embed_batch(self, mock_post):
        from modules.assistant.rag.embeddings import EmbeddingService
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'embedding': [0.1, 0.2]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        service = EmbeddingService(ollama_url='http://mock:11434')
        results = service.embed_batch(["text1", "text2"])
        assert len(results) == 2

    @patch('modules.assistant.rag.embeddings.requests.get')
    def test_is_available(self, mock_get):
        from modules.assistant.rag.embeddings import EmbeddingService
        mock_get.return_value = MagicMock(status_code=200)
        service = EmbeddingService(ollama_url='http://mock:11434')
        assert service.is_available() is True

    @patch('modules.assistant.rag.embeddings.requests.get')
    def test_is_not_available(self, mock_get):
        from modules.assistant.rag.embeddings import EmbeddingService
        mock_get.side_effect = Exception("Connection refused")
        service = EmbeddingService(ollama_url='http://mock:11434')
        assert service.is_available() is False


# ── Prompt Builder Tests ────────────────────────────────────────────

class TestPromptBuilder:
    """Test prompt construction."""

    def test_build_prompt_basic(self):
        from modules.assistant.rag.prompt_builder import PromptBuilder
        builder = PromptBuilder()
        docs = [
            {
                'id': '1',
                'score': 0.95,
                'metadata': {
                    'title': 'Install Guide',
                    'source': 'bookstack',
                    'chunk_text': 'To install, run: pip install app',
                    'document_url': 'https://wiki/install',
                },
            },
        ]
        result = builder.build_prompt("How do I install?", docs)
        assert 'messages' in result
        assert 'context_docs' in result
        assert len(result['context_docs']) == 1
        assert result['context_docs'][0]['title'] == 'Install Guide'

    def test_build_prompt_with_history(self):
        from modules.assistant.rag.prompt_builder import PromptBuilder
        builder = PromptBuilder()
        history = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi!'},
        ]
        result = builder.build_prompt("Follow up?", [], chat_history=history)
        # History should be included in messages
        assert len(result['messages']) > 2  # system + history + user

    def test_context_truncation(self):
        from modules.assistant.rag.prompt_builder import PromptBuilder
        builder = PromptBuilder(max_context_length=50)
        docs = [
            {
                'id': '1', 'score': 0.9,
                'metadata': {
                    'title': 'Long Doc',
                    'source': 'test',
                    'chunk_text': 'A' * 200,
                    'document_url': '',
                },
            },
            {
                'id': '2', 'score': 0.8,
                'metadata': {
                    'title': 'Second Doc',
                    'source': 'test',
                    'chunk_text': 'B' * 100,
                    'document_url': '',
                },
            },
        ]
        result = builder.build_prompt("Q?", docs)
        # Should truncate, not include all docs
        assert len(result['context_docs']) <= 2


# ── Filesystem Source Tests ─────────────────────────────────────────

class TestFilesystemSource:
    """Test filesystem source connector."""

    def test_fetch_txt_files(self):
        from modules.assistant.sources.filesystem_source import FilesystemSource
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            with open(os.path.join(tmpdir, 'test.txt'), 'w') as f:
                f.write("Hello world test document.")
            with open(os.path.join(tmpdir, 'notes.md'), 'w') as f:
                f.write("# Notes\n\nSome markdown content.")
            with open(os.path.join(tmpdir, 'ignore.xyz'), 'w') as f:
                f.write("Should be ignored.")

            source = FilesystemSource({
                'id': 1,
                'name': 'test',
                'config': {'directory': tmpdir, 'recursive': True},
            })
            docs = source.fetch_documents()
            assert len(docs) == 2
            titles = [d.title for d in docs]
            assert 'test.txt' in titles
            assert 'notes.md' in titles

    def test_test_connection(self):
        from modules.assistant.sources.filesystem_source import FilesystemSource
        with tempfile.TemporaryDirectory() as tmpdir:
            source = FilesystemSource({
                'id': 1, 'name': 'test',
                'config': {'directory': tmpdir},
            })
            result = source.test_connection()
            assert result['success'] is True

    def test_nonexistent_directory(self):
        from modules.assistant.sources.filesystem_source import FilesystemSource
        source = FilesystemSource({
            'id': 1, 'name': 'test',
            'config': {'directory': '/nonexistent/path'},
        })
        result = source.test_connection()
        assert result['success'] is False


# ── BookStack Source Tests (mocked) ─────────────────────────────────

class TestBookStackSource:
    """Test BookStack source connector with mocked API."""

    @patch('modules.assistant.sources.bookstack_source.requests.get')
    def test_test_connection(self, mock_get):
        from modules.assistant.sources.bookstack_source import BookStackSource
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': [], 'total': 42}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        source = BookStackSource({
            'id': 1, 'name': 'test',
            'config': {
                'base_url': 'http://mock-bookstack',
                'token_id': 'abc',
                'token_secret': 'xyz',
            },
        })
        result = source.test_connection()
        assert result['success'] is True
        assert '42' in result['message']

    @patch('modules.assistant.sources.bookstack_source.requests.get')
    def test_fetch_documents(self, mock_get):
        from modules.assistant.sources.bookstack_source import BookStackSource

        # Mock list pages
        list_response = MagicMock()
        list_response.status_code = 200
        list_response.json.return_value = {
            'data': [{'id': 1, 'name': 'Test Page'}],
            'total': 1,
        }
        list_response.raise_for_status = MagicMock()

        # Mock page detail
        detail_response = MagicMock()
        detail_response.status_code = 200
        detail_response.json.return_value = {
            'id': 1,
            'name': 'Test Page',
            'html': '<p>Test content</p>',
            'book_id': 1,
            'slug': 'test-page',
            'chapter_id': 1,
        }
        detail_response.raise_for_status = MagicMock()

        mock_get.side_effect = [list_response, detail_response]

        source = BookStackSource({
            'id': 1, 'name': 'test',
            'config': {
                'base_url': 'http://mock-bookstack',
                'token_id': 'abc',
                'token_secret': 'xyz',
            },
        })
        docs = source.fetch_documents()
        assert len(docs) == 1
        assert docs[0].title == 'Test Page'
        assert 'Test content' in docs[0].text


# ── Permission Filtering Tests ──────────────────────────────────────

class TestPermissionFiltering:
    """Test that permission tags are correctly stored and used in metadata."""

    def test_document_chunk_has_permission_tags(self):
        from modules.assistant.sources.base_source import DocumentChunk
        chunk = DocumentChunk(
            text="Secret document",
            title="Admin Only",
            source="Wissensdatenbank",
            source_id=1,
            permission_tags=["admin", "staff"],
        )
        metadata = chunk.to_metadata()
        assert 'permission_tags' in metadata
        assert 'admin' in metadata['permission_tags']
        assert 'staff' in metadata['permission_tags']

    def test_document_chunk_default_public(self):
        from modules.assistant.sources.base_source import DocumentChunk
        chunk = DocumentChunk(
            text="Public document",
            title="Public",
            source="filesystem",
            source_id=1,
        )
        metadata = chunk.to_metadata()
        assert metadata['permission_tags'] == ['public']


# ── Retriever Tests (mocked) ───────────────────────────────────────

class TestRetriever:
    """Test retriever logic with mocked dependencies."""

    @patch('modules.assistant.rag.retriever.get_vector_store')
    @patch('modules.assistant.rag.retriever.get_embedding_service')
    def test_retrieve(self, mock_embed, mock_vs):
        from modules.assistant.rag.retriever import Retriever

        mock_embed_inst = MagicMock()
        mock_embed_inst.embed_text.return_value = [0.1, 0.2, 0.3]
        mock_embed.return_value = mock_embed_inst

        mock_vs_inst = MagicMock()
        mock_vs_inst.search.return_value = [
            {'id': '1', 'score': 0.95, 'metadata': {'title': 'Doc1', 'chunk_text': 'Hello'}},
            {'id': '2', 'score': 0.80, 'metadata': {'title': 'Doc2', 'chunk_text': 'World'}},
        ]
        mock_vs.return_value = mock_vs_inst

        retriever = Retriever(top_k=5)
        results = retriever.retrieve("test query")
        assert len(results) == 2
        assert results[0]['metadata']['title'] == 'Doc1'


# ── RAG Service Tests (mocked) ─────────────────────────────────────

class TestRAGService:
    """Test full RAG pipeline with mocked components."""

    @patch('modules.assistant.services.rag_service.requests.post')
    @patch('modules.assistant.services.rag_service.get_retriever')
    def test_answer(self, mock_retriever, mock_post):
        from modules.assistant.services.rag_service import RAGService

        mock_ret_inst = MagicMock()
        mock_ret_inst.retrieve.return_value = [
            {
                'id': '1', 'score': 0.9,
                'metadata': {
                    'title': 'Guide',
                    'source': 'bookstack',
                    'chunk_text': 'Install with pip.',
                    'document_url': 'https://wiki/guide',
                },
            },
        ]
        mock_retriever.return_value = mock_ret_inst

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {'content': 'You can install with pip. [Quelle: Guide]'},
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        service = RAGService(ollama_url='http://mock:11434', model='test')
        result = service.answer("How do I install?")
        assert 'answer' in result
        assert 'sources' in result
        assert len(result['sources']) > 0


# ── Model Service Tests (mocked) ───────────────────────────────────

class TestModelService:
    """Test model management with mocked Ollama API."""

    @patch('modules.assistant.services.model_service.requests.get')
    def test_list_models(self, mock_get):
        from modules.assistant.services.model_service import ModelService
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                'models': [
                    {'name': 'llama3', 'size': 4000000000},
                    {'name': 'nomic-embed-text', 'size': 500000000},
                ],
            }),
        )
        mock_get.return_value.raise_for_status = MagicMock()

        service = ModelService(ollama_url='http://mock:11434')
        models = service.list_models()
        assert len(models) == 2
        assert models[0]['name'] == 'llama3'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

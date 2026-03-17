# Assistant Module - Services: RAG Service
"""
Orchestrates the RAG pipeline: retrieval → (optional summarisation) → prompt assembly → LLM call.

Supports:
- Tag-based score weighting and intelligent Top_K distribution via retrieval_config.
- Optional pre-answer summarisation step that condenses retrieved chunks before
  passing them to the final answering model.
"""
import requests
import logging
import json
from typing import Dict, Any, List, Optional, Generator
from src.globals import OLLAMA_API_URL, ASSISTANT_MODEL

from modules.assistant.rag.retriever import get_retriever
from modules.assistant.rag.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

# ── Summarisation prompt ────────────────────────────────────────────
SUMMARISATION_SYSTEM_PROMPT = (
    "Du bist ein Assistent, der Quelltext-Auszüge zusammenfasst. "
    "Fasse die folgenden Quellen prägnant zusammen und behalte alle relevanten Fakten bei. "
    "Antworte auf Deutsch, sofern die Quellen deutsch sind."
)


class RAGService:
    """Orchestrates the complete RAG pipeline."""

    def __init__(self, ollama_url: str = None, model: str = None):
        self.ollama_url = ollama_url or OLLAMA_API_URL
        self.model = model or ASSISTANT_MODEL
        self.retriever = get_retriever()
        self.prompt_builder = PromptBuilder()

    def set_model(self, model: str):
        self.model = model

    # ── Summarisation helper ────────────────────────────────────────

    def _summarise_sources(
        self,
        sources: List[Dict[str, Any]],
        model: str,
        question: str,
    ) -> str:
        """Summarise retrieved sources using a (potentially smaller) model.

        Returns a single summary string that replaces the raw chunk texts
        in the final prompt context.
        """
        if not sources:
            return ''

        # Build a compact text block from all source chunks
        parts = []
        for i, src in enumerate(sources):
            title = src.get('title', src.get('metadata', {}).get('title', ''))
            chunk = src.get('chunk_text', src.get('metadata', {}).get('chunk_text', ''))
            if chunk:
                parts.append(f"[Quelle {i+1}: {title}]\n{chunk}")
        all_text = '\n\n'.join(parts)

        if not all_text.strip():
            return ''

        logger.info("[RAG] Summarising %d sources (%d chars) with model=%s",
                    len(sources), len(all_text), model)

        messages = [
            {"role": "system", "content": SUMMARISATION_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Frage des Nutzers: {question}\n\n"
                f"Quellen:\n{all_text}\n\n"
                "Erstelle eine prägnante Zusammenfassung der obigen Quellen, "
                "die alle für die Frage relevanten Informationen enthält."
            )},
        ]

        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            summary = data.get('message', {}).get('content', '')
            logger.info("[RAG] Summarisation complete: %d chars → %d chars",
                        len(all_text), len(summary))
            return summary
        except Exception as exc:
            logger.error("[RAG] Summarisation failed: %s — falling back to raw sources", exc)
            return ''

    # ── Main answer methods ─────────────────────────────────────────

    def answer(
        self,
        question: str,
        chat_history: Optional[List[Dict]] = None,
        permission_tags: Optional[List[str]] = None,
        source_filter: Optional[str] = None,
        top_k: int = 5,
        retrieval_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Full RAG pipeline: retrieve context → (summarise) → build prompt → call LLM.

        Returns:
            Dict with 'answer', 'sources', 'model'.
        """
        cfg = retrieval_config or {}
        effective_top_k = cfg.get('top_k', top_k)

        logger.info("[RAG] answer: query=%r model=%s top_k=%d permission_tags=%s retrieval_cfg=%s",
                    question[:80], self.model, effective_top_k, permission_tags, bool(cfg))

        # Step 1: Retrieve relevant documents (with tag weighting & distribution)
        results, diagnostics = self.retriever.retrieve(
            query=question,
            top_k=effective_top_k,
            source_filter=source_filter,
            permission_tags=permission_tags,
            retrieval_config=cfg,
        )
        logger.info("[RAG] Retrieval returned %d results", len(results))
        if not results:
            logger.warning("[RAG] ⚠ NO DOCUMENTS RETRIEVED — context will be empty!")

        # Step 1b: Optional summarisation
        summarisation_enabled = cfg.get('summarization_enabled', False)
        summarisation_model = cfg.get('summarization_model', '') or self.model

        summarised_context = None
        if summarisation_enabled and results:
            summarised_context = self._summarise_sources(results, summarisation_model, question)

        # Step 2: Build prompt
        prompt_data = self.prompt_builder.build_prompt(
            question=question,
            retrieved_docs=results,
            chat_history=chat_history,
            summarised_context=summarised_context,
        )

        context_len = len(prompt_data.get('prompt', ''))
        context_docs = prompt_data['context_docs']
        logger.info("[RAG] Context length: %d chars, sources included: %d%s",
                    context_len, len(context_docs),
                    ' (summarised)' if summarised_context else '')
        for i, cd in enumerate(context_docs):
            logger.info("[RAG]   Source #%d: %s / %s (score=%.4f)",
                        i + 1, cd.get('source', '?'), cd.get('title', '?'), cd.get('score', 0))
        if context_len == 0:
            logger.warning("[RAG] ⚠ CONTEXT IS EMPTY — the LLM will have no documents!")

        # Step 3: Call Ollama
        logger.info("[RAG] Calling Ollama model=%s (non-streaming)", self.model)
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": prompt_data['messages'],
                    "stream": False,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            answer_text = data.get('message', {}).get('content', '')
            logger.info("[RAG] LLM responded: %d chars", len(answer_text))
        except requests.RequestException as e:
            logger.error("[RAG] Ollama API error: %s", e)
            answer_text = f"Fehler bei der Kommunikation mit dem KI-Modell: {str(e)}"

        return {
            'answer': answer_text,
            'sources': context_docs,
            'model': self.model,
            'diagnostics': diagnostics,
        }

    def answer_stream(
        self,
        question: str,
        chat_history: Optional[List[Dict]] = None,
        permission_tags: Optional[List[str]] = None,
        source_filter: Optional[str] = None,
        top_k: int = 5,
        retrieval_config: Optional[Dict[str, Any]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streaming RAG pipeline: yields chunks as they come from the LLM.

        Yields:
            Dicts with 'type' ('chunk', 'sources', 'done', 'error') and content.
        """
        cfg = retrieval_config or {}
        effective_top_k = cfg.get('top_k', top_k)

        logger.info("[RAG] answer_stream: query=%r model=%s top_k=%d permission_tags=%s retrieval_cfg=%s",
                    question[:80], self.model, effective_top_k, permission_tags, bool(cfg))

        # Step 1: Retrieve (with tag weighting & distribution)
        results, diagnostics = self.retriever.retrieve(
            query=question,
            top_k=effective_top_k,
            source_filter=source_filter,
            permission_tags=permission_tags,
            retrieval_config=cfg,
        )
        logger.info("[RAG] Retrieval returned %d results", len(results))
        if not results:
            logger.warning("[RAG] ⚠ NO DOCUMENTS RETRIEVED — context will be empty!")

        # Step 1b: Optional summarisation
        summarisation_enabled = cfg.get('summarization_enabled', False)
        summarisation_model = cfg.get('summarization_model', '') or self.model

        summarised_context = None
        if summarisation_enabled and results:
            summarised_context = self._summarise_sources(results, summarisation_model, question)

        # Step 2: Build prompt
        prompt_data = self.prompt_builder.build_prompt(
            question=question,
            retrieved_docs=results,
            chat_history=chat_history,
            summarised_context=summarised_context,
        )

        context_len = len(prompt_data.get('prompt', ''))
        context_docs = prompt_data['context_docs']
        logger.info("[RAG] Context length: %d chars, sources included: %d%s",
                    context_len, len(context_docs),
                    ' (summarised)' if summarised_context else '')
        for i, cd in enumerate(context_docs):
            logger.info("[RAG]   Source #%d: %s / %s (score=%.4f)",
                        i + 1, cd.get('source', '?'), cd.get('title', '?'), cd.get('score', 0))
        if context_len == 0:
            logger.warning("[RAG] ⚠ CONTEXT IS EMPTY — the LLM will have no documents!")

        # Yield sources first
        yield {'type': 'sources', 'data': context_docs}

        # Yield diagnostics for the debug panel
        yield {'type': 'diagnostics', 'data': diagnostics}

        # Step 3: Stream from Ollama
        logger.info("[RAG] Calling Ollama model=%s (streaming)", self.model)
        # timeout=(connect_seconds, read_seconds_per_chunk) — the read timeout
        # caps how long iter_lines() blocks waiting for the next token, preventing
        # the worker thread from hanging indefinitely if Ollama stalls.
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": prompt_data['messages'],
                    "stream": True,
                },
                stream=True,
                timeout=(15, 90),
            )
            response.raise_for_status()

            done_received = False
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    if chunk.get('done'):
                        done_received = True
                        yield {'type': 'done', 'data': None}
                        break
                    content = chunk.get('message', {}).get('content', '')
                    if content:
                        yield {'type': 'chunk', 'data': content}
                except json.JSONDecodeError:
                    continue

            if not done_received:
                # Stream ended without a done marker — send done anyway
                yield {'type': 'done', 'data': None}

        except requests.Timeout as e:
            logger.error(f"Ollama streaming timed out: {e}")
            yield {'type': 'error', 'data': 'Das KI-Modell hat zu lange nicht geantwortet (Timeout).'}
        except requests.RequestException as e:
            logger.error(f"Ollama streaming error: {e}")
            yield {'type': 'error', 'data': str(e)}

    def is_available(self) -> bool:
        """Check if the LLM service is reachable."""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False


# Module-level singleton
_rag_service: Optional[RAGService] = None


def get_rag_service(ollama_url: str = None, model: str = None) -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService(ollama_url=ollama_url, model=model)
    return _rag_service

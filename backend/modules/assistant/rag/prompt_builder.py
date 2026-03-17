# Assistant Module - RAG: Prompt Builder
"""
Builds prompts for the LLM using retrieved context and the user's question.
"""
from typing import List, Dict, Any

DEFAULT_SYSTEM_PROMPT = """Du bist ein hilfreicher KI-Assistent. Beantworte Fragen ausschließlich auf Basis der bereitgestellten Dokumente.

Regeln:
1. Verwende NUR die bereitgestellten Dokumente als Informationsquelle.
2. Zitiere IMMER die Quellen mit: [Quelle: Titel]
3. Wenn die Dokumente keine relevanten Informationen enthalten, sage dies ehrlich.
4. Antworte in der Sprache, in der die Frage gestellt wurde.
5. Fasse die relevanten Informationen zusammen und strukturiere deine Antwort klar.
"""

CONTEXT_TEMPLATE = """--- Dokument: {title} ---
Quelle: {source}
{chunk_text}
---"""

QUERY_TEMPLATE = """Dokumente:
{context}

Frage:
{question}"""


class PromptBuilder:
    """Assembles prompts for the LLM from retrieved context."""

    def __init__(self, system_prompt: str = None, max_context_length: int = 4000):
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_context_length = max_context_length

    def build_prompt(
        self,
        question: str,
        retrieved_docs: List[Dict[str, Any]],
        chat_history: List[Dict[str, str]] = None,
        summarised_context: str = None,
    ) -> Dict[str, Any]:
        """
        Build the prompt payload for the Ollama API.

        Args:
            question: User's question.
            retrieved_docs: List of retrieved document dicts (from retriever).
            chat_history: Optional list of previous messages [{'role': ..., 'content': ...}].
            summarised_context: Optional pre-summarised context string.
                When provided, this replaces the raw chunked context in the prompt,
                but the original context_docs are still returned for source display.

        Returns:
            Dict with 'system', 'prompt', 'messages', and 'context_docs' keys.
        """
        context_parts = []
        context_docs = []
        total_length = 0

        for doc in retrieved_docs:
            metadata = doc.get('metadata', {})
            title = metadata.get('title', 'Unknown')
            source = metadata.get('source', 'Unknown')
            chunk_text = metadata.get('chunk_text', '')
            document_url = metadata.get('document_url', '')

            formatted = CONTEXT_TEMPLATE.format(
                title=title,
                source=source,
                chunk_text=chunk_text,
            )

            if total_length + len(formatted) > self.max_context_length:
                break

            context_parts.append(formatted)
            context_docs.append({
                'title': title,
                'source': source,
                'url': document_url,
                'chunk_position': metadata.get('chunk_position', 0),
                'score': doc.get('score', 0),
                'book_name': metadata.get('book_name', ''),
                'chapter_name': metadata.get('chapter_name', ''),
                'bookstack_type': metadata.get('bookstack_type', ''),
                'source_type': metadata.get('source_type', ''),
            })
            total_length += len(formatted)

        # Use summarised context if available, otherwise raw chunks
        if summarised_context:
            context = f"[Zusammenfassung der Quellen]\n{summarised_context}"
        else:
            context = "\n\n".join(context_parts)

        prompt = QUERY_TEMPLATE.format(context=context, question=question)

        # Build messages for chat API
        messages = [{"role": "system", "content": self.system_prompt}]

        if chat_history:
            for msg in chat_history[-6:]:  # Keep last 6 messages for context
                messages.append({
                    "role": msg.get('role', 'user'),
                    "content": msg.get('content', msg.get('message', '')),
                })

        messages.append({"role": "user", "content": prompt})

        return {
            'messages': messages,
            'prompt': prompt,
            'system': self.system_prompt,
            'context_docs': context_docs,
        }

# Assistant Module - Dashboard: Metrics Service
"""
Provides status and metrics for the admin dashboard.
"""
import logging
import time
import gevent
from typing import Dict, Any
from datetime import datetime, timezone, timedelta

from src.db import db
from modules.assistant.models.chat_session import ChatSession
from modules.assistant.models.chat_message import ChatMessage
from modules.assistant.models.source_config import SourceConfig
from modules.assistant.models.assistant_model import AssistantLog
from modules.assistant.rag.vector_store import get_vector_store
from modules.assistant.rag.embeddings import get_embedding_service
from modules.assistant.services.model_service import get_model_service, get_config_value
from src.utils import utc_isoformat

logger = logging.getLogger(__name__)

# Maximum time the whole status endpoint may spend on external probes.
_STATUS_PROBE_TIMEOUT = 8  # seconds


def _probe_ollama():
    """Check Ollama availability (run in a worker thread)."""
    return get_model_service().get_status()


def _probe_qdrant():
    """Check Qdrant / collection info (run in a worker thread)."""
    return get_vector_store().get_collection_info()


def _probe_embedding():
    """Check embedding service (run in a worker thread)."""
    return get_embedding_service().is_available()


def get_assistant_status() -> Dict[str, Any]:
    """Get comprehensive status of the assistant system.

    External service probes (Ollama, Qdrant, embedding) are executed in
    parallel threads so a single unreachable service can never freeze the
    entire backend.
    """
    t0 = time.monotonic()
    logger.info("[Status] get_assistant_status: starting...")

    # ── External probes in parallel (gevent greenlets) ────────────────
    # Each probe runs as a separate greenlet so a slow/unreachable service
    # never blocks the others or the Flask request handling.
    ollama_status = {'available': False, 'model_count': 0, 'url': ''}
    vector_info = None
    embedding_available = False

    try:
        g_ollama = gevent.spawn(_probe_ollama)
        g_qdrant = gevent.spawn(_probe_qdrant)
        g_embed = gevent.spawn(_probe_embedding)

        # Wait for all probes with a combined timeout.
        gevent.joinall([g_ollama, g_qdrant, g_embed],
                       timeout=_STATUS_PROBE_TIMEOUT)

        # Harvest results — only from greenlets that completed.
        if g_ollama.ready() and g_ollama.successful():
            ollama_status = g_ollama.value
        elif g_ollama.ready():
            logger.warning("[Status] Ollama probe failed: %s", g_ollama.exception)

        if g_qdrant.ready() and g_qdrant.successful():
            vector_info = g_qdrant.value
        elif g_qdrant.ready():
            logger.warning("[Status] Qdrant probe failed: %s", g_qdrant.exception)

        if g_embed.ready() and g_embed.successful():
            embedding_available = g_embed.value
        elif g_embed.ready():
            logger.warning("[Status] Embedding probe failed: %s", g_embed.exception)

        # Kill any probes that haven't finished within the timeout.
        for g in (g_ollama, g_qdrant, g_embed):
            if not g.ready():
                logger.warning("[Status] Probe timed out: %s", g)
                g.kill()

    except Exception as exc:
        logger.warning("[Status] Probe orchestration error: %s", exc)

    vector_available = vector_info is not None
    logger.info("[Status] Probes done in %.3fs — ollama=%s qdrant=%s embedding=%s",
                time.monotonic() - t0,
                ollama_status.get('available'),
                vector_available,
                embedding_available)

    # ── DB queries (fast, local) ────────────────────────────────────
    try:
        sources = SourceConfig.query.all()
        active_sources = sum(1 for s in sources if s.enabled)
        total_docs = sum(s.document_count for s in sources)
    except Exception as e:
        logger.error("[Status] Failed to query sources: %s", e)
        sources, active_sources, total_docs = [], 0, 0

    try:
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_queries = (ChatMessage.query
                          .filter(ChatMessage.role == 'user')
                          .filter(ChatMessage.created_at >= one_hour_ago)
                          .count())
    except Exception as e:
        logger.error("[Status] Failed to count recent queries: %s", e)
        recent_queries = 0

    try:
        total_sessions = ChatSession.query.count()
        total_messages = ChatMessage.query.count()
    except Exception as e:
        logger.error("[Status] Failed to count sessions/messages: %s", e)
        total_sessions = total_messages = 0

    # Active model config
    llm_model = get_config_value('llm_model', 'llama3')
    embedding_model = get_config_value('embedding_model', 'nomic-embed-text')

    elapsed = time.monotonic() - t0
    logger.info("[Status] get_assistant_status complete in %.3fs", elapsed)

    return {
        'ollama': ollama_status,
        'vector_db': {
            'available': vector_available,
            'info': vector_info,
        },
        'embedding': {
            'available': embedding_available,
            'model': embedding_model,
        },
        'sources': {
            'total': len(sources),
            'active': active_sources,
            'total_documents': total_docs,
        },
        'models': {
            'llm_model': llm_model,
            'embedding_model': embedding_model,
        },
        'metrics': {
            'queries_last_hour': recent_queries,
            'total_sessions': total_sessions,
            'total_messages': total_messages,
        },
    }


def get_source_sync_status() -> list:
    """Get sync status for all sources."""
    sources = SourceConfig.query.order_by(SourceConfig.name).all()
    return [
        {
            'id': s.id,
            'name': s.name,
            'source_type': s.source_type,
            'enabled': s.enabled,
            'last_sync_at': utc_isoformat(s.last_sync_at),
            'last_sync_status': s.last_sync_status,
            'last_sync_message': s.last_sync_message,
            'document_count': s.document_count,
        }
        for s in sources
    ]


def get_recent_logs(limit: int = 50, event_type: str = None,
                    page: int = 1, level: str = None,
                    source: str = None) -> Dict[str, Any]:
    """Get paginated assistant logs with optional filters.

    Returns::

        {
            "logs": [...],
            "total": <int>,
            "page": <int>,
            "per_page": <int>,
            "has_next": <bool>,
            "has_prev": <bool>,
            "total_pages": <int>,
        }
    """
    query = AssistantLog.query

    # ── Filters ─────────────────────────────────────────────────────
    if event_type:
        query = query.filter_by(event_type=event_type)
    if level:
        query = query.filter(AssistantLog.event_type == level)
    if source:
        query = query.filter(AssistantLog.message.ilike(f'%{source}%'))

    # ── Total count (before pagination) ─────────────────────────────
    total = query.count()

    # ── Pagination ──────────────────────────────────────────────────
    per_page = max(1, min(limit, 200))  # clamp between 1 and 200
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    logs = (query
            .order_by(AssistantLog.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all())

    return {
        'logs': [log.to_dict() for log in logs],
        'total': total,
        'page': page,
        'per_page': per_page,
        'has_next': page < total_pages,
        'has_prev': page > 1,
        'total_pages': total_pages,
    }


def get_log_event_types() -> list:
    """Return distinct event_type values for filter dropdowns."""
    rows = (db.session.query(AssistantLog.event_type)
            .distinct()
            .order_by(AssistantLog.event_type)
            .all())
    return [r[0] for r in rows if r[0]]


def add_log(event_type: str, message: str, details: Dict = None, user_id: str = None):
    """Add an assistant log entry.

    After inserting, prunes the table to keep at most 1 000 rows.
    """
    import json
    log = AssistantLog(
        event_type=event_type,
        message=message,
        details_json=json.dumps(details) if details else None,
        user_id=user_id,
    )
    db.session.add(log)
    db.session.commit()

    # Prune: keep only the latest 1 000 entries
    try:
        cutoff = (
            db.session.query(AssistantLog.id)
            .order_by(AssistantLog.id.desc())
            .offset(999)
            .limit(1)
            .scalar()
        )
        if cutoff is not None:
            db.session.query(AssistantLog).filter(
                AssistantLog.id < cutoff
            ).delete(synchronize_session=False)
            db.session.commit()
    except Exception:
        db.session.rollback()

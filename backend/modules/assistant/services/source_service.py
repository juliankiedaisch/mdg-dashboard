# Assistant Module - Services: Source Service
"""
CRUD operations for source configurations.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from src.db import db
from modules.assistant.models.source_config import SourceConfig
from modules.assistant.ingestion.pipeline import get_source_connector

logger = logging.getLogger(__name__)


def get_all_sources() -> List[Dict]:
    """Get all source configurations."""
    sources = SourceConfig.query.order_by(SourceConfig.created_at).all()
    return [s.to_dict() for s in sources]


def get_source(source_id: int) -> Optional[Dict]:
    """Get a single source configuration."""
    source = SourceConfig.query.get(source_id)
    if not source:
        return None
    return source.to_dict()


def create_source(name: str, source_type: str, config: Dict = None, enabled: bool = True) -> tuple:
    """
    Create a new source configuration.
    Returns (source_dict, error_message).
    """
    if not name or not source_type:
        return None, "Name and source_type are required."

    if source_type not in ('bookstack', 'filesystem'):
        return None, f"Unsupported source type: {source_type}"

    source = SourceConfig(
        name=name,
        source_type=source_type,
        enabled=enabled,
    )
    if config:
        source.config = config

    db.session.add(source)
    db.session.commit()
    logger.info(f"Created source '{name}' (type={source_type}, id={source.id})")
    return source.to_dict(), None


def update_source(source_id: int, **kwargs) -> tuple:
    """
    Update a source configuration.
    Returns (source_dict, error_message).
    """
    source = SourceConfig.query.get(source_id)
    if not source:
        return None, "Source not found."

    if 'name' in kwargs and kwargs['name']:
        source.name = kwargs['name']
    if 'enabled' in kwargs:
        source.enabled = kwargs['enabled']
    if 'config' in kwargs:
        source.config = kwargs['config']

    db.session.commit()
    return source.to_dict(), None


def delete_source(source_id: int) -> tuple:
    """
    Delete a source configuration.
    Returns (success_dict, error_message).
    """
    source = SourceConfig.query.get(source_id)
    if not source:
        return None, "Source not found."

    db.session.delete(source)
    db.session.commit()
    logger.info(f"Deleted source id={source_id}")
    return {'status': True, 'message': f'Source {source_id} deleted.'}, None


def test_source_connection(source_id: int) -> Dict[str, Any]:
    """Test connectivity for a source."""
    source = SourceConfig.query.get(source_id)
    if not source:
        return {'success': False, 'message': 'Source not found.'}

    connector = get_source_connector(source.to_dict())
    if not connector:
        return {'success': False, 'message': 'Unknown source type.'}

    return connector.test_connection()


def update_sync_status(source_id: int, status: str, message: str = '',
                       document_count: int = None):
    """Update the sync status of a source."""
    source = SourceConfig.query.get(source_id)
    if not source:
        return
    source.last_sync_at = datetime.now(timezone.utc)
    source.last_sync_status = status
    source.last_sync_message = message
    if document_count is not None:
        source.document_count = document_count
    db.session.commit()


def reconcile_document_counts() -> Dict[str, Any]:
    """Reconcile DB document_count with actual Qdrant point counts.

    Scrolls all points in Qdrant, groups by source_id, and updates
    each SourceConfig row.  Returns a summary of changes made.
    """
    from modules.assistant.rag.vector_store import get_vector_store

    vs = get_vector_store()
    qdrant_counts = vs.count_points_by_source()

    sources = SourceConfig.query.all()
    changes = []
    for src in sources:
        actual = qdrant_counts.get(src.id, 0)
        if src.document_count != actual:
            changes.append({
                'source_id': src.id,
                'name': src.name,
                'old_count': src.document_count,
                'new_count': actual,
            })
            src.document_count = actual

    if changes:
        db.session.commit()
        logger.info("[SourceService] Reconciled document counts: %d source(s) updated",
                    len(changes))
    else:
        logger.info("[SourceService] Reconcile: all counts already match Qdrant")

    return {
        'changes': changes,
        'total_sources': len(sources),
        'total_qdrant_points': sum(qdrant_counts.values()),
    }

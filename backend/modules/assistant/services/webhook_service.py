# Assistant Module - Services: BookStack Webhook Service
"""
Handles incoming BookStack webhook events and triggers incremental
re-indexing of affected content.

Supported event prefixes:
    page_*        → single page operations
    chapter_*     → chapter-level changes (re-indexes all pages in chapter)
    book_*        → book-level changes (re-indexes all pages in book)
    bookshelf_*   → shelf changes (re-indexes books on the shelf)
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from modules.assistant.dashboard.metrics_service import add_log

logger = logging.getLogger(__name__)


# ── Webhook payload parsing ─────────────────────────────────────────

def parse_webhook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant fields from a BookStack webhook payload.

    Returns a normalised dict with:
        event, triggered_at, triggered_by, webhook_id, webhook_name,
        url, related_item (id, book_id, chapter_id, name, slug, type).
    """
    event = payload.get('event', '')
    related = payload.get('related_item') or {}

    # Determine the entity type from the event prefix
    entity_type = event.split('_')[0] if '_' in event else 'unknown'

    return {
        'event': event,
        'entity_type': entity_type,
        'triggered_at': payload.get('triggered_at', ''),
        'triggered_by': payload.get('triggered_by', {}),
        'webhook_id': payload.get('webhook_id'),
        'webhook_name': payload.get('webhook_name', ''),
        'url': payload.get('url', ''),
        'related_item': {
            'id': related.get('id'),
            'book_id': related.get('book_id'),
            'chapter_id': related.get('chapter_id'),
            'name': related.get('name', ''),
            'slug': related.get('slug', ''),
        },
    }


# ── Source lookup ───────────────────────────────────────────────────

def _find_bookstack_sources() -> list:
    """Return all enabled BookStack source configs."""
    from modules.assistant.models.source_config import SourceConfig
    sources = SourceConfig.query.filter_by(
        source_type='bookstack', enabled=True
    ).all()
    return [s for s in sources if s.config.get('webhook_enabled', False)]


def _source_matches_url(source_config: Dict, url: str) -> bool:
    """Check if a webhook URL belongs to this source's BookStack instance."""
    base_url = (source_config.get('config', {}).get('base_url') or '').rstrip('/')
    if not base_url:
        return False
    return url.startswith(base_url)


# ── Incremental re-indexing ────────────────────────────────────────

def _reindex_page(source, page_id: int, source_config_dict: Dict) -> Dict[str, Any]:
    """Fetch and re-index a single page by ID.

    Deletes old vectors for this page, then fetches fresh content from
    BookStack and runs it through the ingestion pipeline.
    """
    from modules.assistant.rag.vector_store import get_vector_store
    from modules.assistant.ingestion.pipeline import IngestionPipeline
    from modules.assistant.sources.bookstack_source import BookStackSource

    vs = get_vector_store()

    # Delete existing vectors for this specific page
    vs.delete_by_metadata({
        'source_id': source_config_dict['id'],
        'page_id': page_id,
    })

    # Also delete any attachment vectors linked to this page
    vs.delete_by_metadata({
        'source_id': source_config_dict['id'],
        'uploaded_to_page_id': page_id,
    })

    # Fetch the single page via BookStack API
    connector = BookStackSource(source_config_dict)
    connector._fetch_books()
    connector._fetch_chapters()
    if connector.map_permissions:
        connector._fetch_roles()

    detail = connector._api_get(f'pages/{page_id}')
    if not detail:
        logger.warning("[Webhook] Page %d not found in BookStack — may have been deleted", page_id)
        return {'action': 'page_not_found', 'page_id': page_id, 'chunks_stored': 0}

    from modules.assistant.sources.bookstack_source import html_to_text, DocumentChunk

    text = html_to_text(detail.get('html', ''))
    if not text.strip():
        return {'action': 'page_empty', 'page_id': page_id, 'chunks_stored': 0}

    book_id = detail.get('book_id', 0)
    chapter_id = detail.get('chapter_id') or 0
    page_slug = detail.get('slug', '')
    page_url = connector._page_url(book_id, page_slug)
    title = detail.get('name', 'Untitled')
    perm_tags = connector._resolve_book_tags(book_id)

    doc = DocumentChunk(
        text=text,
        title=title,
        source='Wissensdatenbank',
        source_id=source_config_dict['id'],
        document_url=page_url,
        permission_tags=perm_tags if perm_tags else [],
        extra_metadata={
            'bookstack_type': 'page',
            'subsource_type': 'page',
            'subsource_id': f'page_{detail["id"]}',
            'automatic_tags': bool(perm_tags),
            'book_id': book_id,
            'book_name': connector._book_map.get(book_id, {}).get('name', ''),
            'chapter_id': chapter_id,
            'chapter_name': connector._chapter_map.get(chapter_id, {}).get('name', ''),
            'page_id': detail['id'],
            'page_slug': page_slug,
        },
    )

    # Auto-create tags
    if perm_tags:
        connector._auto_create_tags(perm_tags)

    # Run through pipeline (chunk → embed → store)
    pipeline = IngestionPipeline()

    # Resolve source-level tags
    source_tag_names = source_config_dict.get('tags', [])
    resolved_tags = [
        t['name'] if isinstance(t, dict) else t
        for t in source_tag_names
    ] if source_tag_names else ['default_assistant_source']

    metadata = doc.to_metadata()
    if not (metadata.get('permission_tags') or []):
        metadata['permission_tags'] = resolved_tags

    doc_dict = {'text': doc.text, 'metadata': metadata}
    chunks, stored, failed = pipeline._process_doc_batch(
        [doc_dict], source_config_dict.get('name', 'bookstack'), 1
    )

    return {
        'action': 'reindexed',
        'page_id': page_id,
        'title': title,
        'chunks_stored': stored,
        'chunks_failed': failed,
    }


def _delete_page_vectors(source_config_dict: Dict, page_id: int) -> Dict[str, Any]:
    """Remove all vectors associated with a specific page."""
    from modules.assistant.rag.vector_store import get_vector_store
    vs = get_vector_store()

    vs.delete_by_metadata({
        'source_id': source_config_dict['id'],
        'page_id': page_id,
    })
    vs.delete_by_metadata({
        'source_id': source_config_dict['id'],
        'uploaded_to_page_id': page_id,
    })

    return {'action': 'deleted', 'page_id': page_id}


def _get_chapter_page_ids(connector, chapter_id: int) -> List[int]:
    """Fetch all page IDs belonging to a chapter."""
    detail = connector._api_get(f'chapters/{chapter_id}')
    if not detail:
        return []
    pages = detail.get('pages', [])
    return [p['id'] for p in pages if 'id' in p]


def _get_book_page_ids(connector, book_id: int) -> List[int]:
    """Fetch all page IDs belonging to a book."""
    detail = connector._api_get(f'books/{book_id}')
    if not detail:
        return []
    # Book detail includes 'contents' which has pages and chapters
    contents = detail.get('contents', [])
    page_ids = []
    for item in contents:
        if item.get('type') == 'page':
            page_ids.append(item['id'])
        elif item.get('type') == 'chapter':
            # Fetch pages within each chapter
            chapter_pages = item.get('pages', [])
            page_ids.extend(p['id'] for p in chapter_pages if 'id' in p)
    return page_ids


def _get_shelf_book_ids(connector, shelf_id: int) -> List[int]:
    """Fetch all book IDs belonging to a shelf."""
    detail = connector._api_get(f'shelves/{shelf_id}')
    if not detail:
        return []
    books = detail.get('books', [])
    return [b['id'] for b in books if 'id' in b]


# ── Main webhook processor ─────────────────────────────────────────

def process_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process a BookStack webhook event.

    Determines which pages are affected by the event and triggers
    incremental re-indexing for each.

    Returns a result dict for logging/response.
    """
    parsed = parse_webhook_payload(payload)
    event = parsed['event']
    entity_type = parsed['entity_type']
    related = parsed['related_item']
    item_id = related.get('id')
    url = parsed['url']

    logger.info("[Webhook] Processing event '%s' for %s id=%s url=%s",
                event, entity_type, item_id, url)

    # Find matching BookStack sources
    sources = _find_bookstack_sources()
    if not sources:
        msg = "No enabled BookStack sources with webhook_enabled found"
        logger.warning("[Webhook] %s", msg)
        _log_webhook_event(parsed, 'skipped', msg)
        return {'status': 'skipped', 'message': msg}

    results = []
    for source in sources:
        source_dict = source.to_dict()

        # Optionally match by base_url if multiple BookStack instances
        if url and not _source_matches_url(source_dict, url):
            continue

        try:
            result = _process_event_for_source(event, entity_type, related, source_dict)
            results.append({
                'source_id': source_dict['id'],
                'source_name': source_dict['name'],
                **result,
            })
        except Exception as exc:
            logger.error("[Webhook] Error processing event '%s' for source %s: %s",
                         event, source_dict['name'], exc, exc_info=True)
            results.append({
                'source_id': source_dict['id'],
                'source_name': source_dict['name'],
                'status': 'error',
                'message': str(exc),
            })

    overall_status = 'success' if all(r.get('status') != 'error' for r in results) else 'partial_error'
    _log_webhook_event(parsed, overall_status, results=results)

    return {
        'status': overall_status,
        'event': event,
        'results': results,
    }


def _process_event_for_source(
    event: str, entity_type: str, related: Dict,
    source_dict: Dict,
) -> Dict[str, Any]:
    """Process a single event for a single source."""
    from modules.assistant.sources.bookstack_source import BookStackSource

    item_id = related.get('id')
    action = event.split('_', 1)[1] if '_' in event else event

    if entity_type == 'page':
        if action == 'delete':
            result = _delete_page_vectors(source_dict, item_id)
        else:
            # create, update, restore, move → re-index the page
            result = _reindex_page(None, item_id, source_dict)
        return {'status': 'success', 'pages_affected': 1, **result}

    elif entity_type == 'chapter':
        connector = BookStackSource(source_dict)
        page_ids = _get_chapter_page_ids(connector, item_id)
        page_results = []
        for pid in page_ids:
            if action == 'delete':
                page_results.append(_delete_page_vectors(source_dict, pid))
            else:
                page_results.append(_reindex_page(None, pid, source_dict))
        return {
            'status': 'success',
            'pages_affected': len(page_ids),
            'page_results': page_results,
        }

    elif entity_type == 'book':
        connector = BookStackSource(source_dict)
        page_ids = _get_book_page_ids(connector, item_id)
        page_results = []
        for pid in page_ids:
            if action == 'delete':
                page_results.append(_delete_page_vectors(source_dict, pid))
            else:
                page_results.append(_reindex_page(None, pid, source_dict))
        return {
            'status': 'success',
            'pages_affected': len(page_ids),
            'page_results': page_results,
        }

    elif entity_type == 'bookshelf':
        connector = BookStackSource(source_dict)
        book_ids = _get_shelf_book_ids(connector, item_id)
        total_pages = 0
        page_results = []
        for bid in book_ids:
            page_ids = _get_book_page_ids(connector, bid)
            total_pages += len(page_ids)
            for pid in page_ids:
                if action == 'delete':
                    page_results.append(_delete_page_vectors(source_dict, pid))
                else:
                    page_results.append(_reindex_page(None, pid, source_dict))
        return {
            'status': 'success',
            'books_affected': len(book_ids),
            'pages_affected': total_pages,
            'page_results': page_results,
        }

    else:
        logger.info("[Webhook] Unhandled entity type '%s' for event '%s'", entity_type, event)
        return {'status': 'ignored', 'message': f'Unhandled entity type: {entity_type}'}


# ── Logging ─────────────────────────────────────────────────────────

def _log_webhook_event(
    parsed: Dict[str, Any],
    status: str,
    message: str = '',
    results: list = None,
):
    """Log a webhook event for auditing and debugging."""
    triggered_by = parsed.get('triggered_by', {})
    details = {
        'event': parsed['event'],
        'entity_type': parsed['entity_type'],
        'related_item_id': parsed['related_item'].get('id'),
        'related_item_name': parsed['related_item'].get('name', ''),
        'url': parsed['url'],
        'triggered_by_id': triggered_by.get('id'),
        'triggered_by_name': triggered_by.get('name', ''),
        'webhook_id': parsed.get('webhook_id'),
        'webhook_name': parsed.get('webhook_name', ''),
        'triggered_at': parsed.get('triggered_at', ''),
        'processing_status': status,
    }
    if results:
        details['results'] = results
    if message:
        details['message'] = message

    log_message = (
        f"Webhook '{parsed['event']}': "
        f"{parsed['related_item'].get('name', 'unknown')} "
        f"(id={parsed['related_item'].get('id')}) "
        f"by {triggered_by.get('name', 'unknown')} — {status}"
    )

    add_log(
        event_type='bookstack_webhook',
        message=log_message,
        details=details,
    )

# Assistant Module - Sources: BookStack Connector
"""
Connector for BookStack wiki system.

Indexes ALL content (books, chapters, pages) with correct URLs and metadata.
Indexes file attachments (PDF, DOCX, TXT, etc.) with text extraction via
external services (Docling + Apache Tika).
Maps BookStack content-level read permissions → assistant tags.
Auto-creates tags and attaches them to indexed documents in Qdrant.

Redesigned for high parallelism:
• Parallel attachment download via gevent pool
• Parallel extraction via batch processing
• Docling chunking integration for semantic chunks
• Per-attachment resilience (failures logged, not fatal)
"""
import base64
import logging
import os
import re
import requests
import time
import gevent
from gevent.pool import Pool as GeventPool
from typing import List, Dict, Any, Optional
from datetime import datetime
from html import unescape

from flask import current_app
from modules.assistant.sources.base_source import BaseSource, DocumentChunk
from modules.assistant.tasks.progress import emit_progress
from modules.assistant.services.extraction_service import (
    extract_text as _service_extract_text,
    extract_with_chunks as _service_extract_with_chunks,
    ALL_SUPPORTED_EXTENSIONS,
)

logger = logging.getLogger(__name__)

# Number of concurrent attachment downloads + extractions
ATTACHMENT_POOL_SIZE = int(os.getenv('BOOKSTACK_ATTACHMENT_POOL_SIZE', '6'))

# Batch size for collecting attachments before yielding to pipeline
ATTACHMENT_BATCH_SIZE = int(os.getenv('BOOKSTACK_ATTACHMENT_BATCH_SIZE', '10'))

logger = logging.getLogger(__name__)


def sanitize_text(text: str) -> str:
    """Remove Unicode surrogates and other non-UTF-8 characters from text.

    Prevents ``PydanticSerializationError`` when Qdrant tries to serialise
    the payload to JSON (surrogates like ``\\udca1`` are invalid in UTF-8).
    """
    if not text:
        return text
    # Encode to UTF-8 replacing surrogates, then decode back
    return text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')


def html_to_text(html: str) -> str:
    """Simple HTML to plain text conversion."""
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>|</p>|</div>|</li>|</tr>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return sanitize_text(text.strip())


class BookStackSource(BaseSource):
    """Connector for BookStack knowledge base.

    Indexes all books, chapters, pages, and file attachments.
    Maps BookStack role ``external_auth_id`` to backend group UUIDs to
    derive automatic permission tags.  Each subsource (page, chapter,
    book, attachment) is tagged individually.
    """

    def __init__(self, source_config: Dict[str, Any]):
        super().__init__(source_config)
        config = source_config.get('config', {})
        self.base_url = config.get('base_url', '').rstrip('/')
        self.token_id = config.get('token_id', '')
        self.token_secret = config.get('token_secret', '')
        self.index_attachments = config.get('index_attachments', True)
        # 0 = no limit; any positive value is the max file size in MB
        self.max_attachment_size_mb = float(config.get('max_attachment_size_mb', 0) or 0)
        self.map_permissions = config.get('map_permissions', True)

        # Caches populated during fetch
        self._book_map: Dict[int, Dict] = {}       # book_id → {slug, name, description}
        self._chapter_map: Dict[int, Dict] = {}     # chapter_id → {slug, name, description, book_id}
        self._page_book_map: Dict[int, int] = {}    # page_id → book_id  (for attachment resolution)
        self._role_map: Dict[int, Dict] = {}         # role_id → {display_name, external_auth_id, tag_name}
        self._group_uuid_set: set = set()            # known group UUIDs from backend DB
        self._role_to_group_uuid: Dict[int, str] = {}  # role_id → group UUID (matched)
        self._role_tag_names: Dict[int, str] = {}    # role_id → bookstack-{name} tag name
        self._book_tags: Dict[int, List[str]] = {}   # book_id → [bookstack-xxx, ...]
        self._page_tags: Dict[int, List[str]] = {}   # page_id → [bookstack-xxx, ...]
        self._chapter_tags: Dict[int, List[str]] = {}  # chapter_id → [bookstack-xxx, ...]
        self._auto_created_tags: set = set()

    def _headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Token {self.token_id}:{self.token_secret}',
            'Content-Type': 'application/json',
        }

    # Delay between individual detail requests to avoid rate-limiting
    _REQUEST_DELAY = 0.1  # seconds

    def _api_get(self, endpoint: str, params: Optional[Dict] = None,
                 _retries: int = 5) -> Optional[Any]:
        """GET request to BookStack API with retry/backoff on 429."""
        url = f"{self.base_url}/api/{endpoint}"
        for attempt in range(_retries):
            try:
                resp = requests.get(url, headers=self._headers(),
                                    params=params, timeout=30)
                if resp.status_code == 429:
                    retry_after = resp.headers.get('Retry-After')
                    wait = float(retry_after) if retry_after else 2 ** attempt
                    logger.warning(
                        "[BookStack] Rate limited (%s), retry in %.1fs "
                        "(attempt %d/%d)", endpoint, wait, attempt + 1, _retries)
                    time.sleep(wait)
                    continue
                if resp.status_code == 403:
                    logger.warning("[BookStack] 403 Forbidden: %s "
                                   "(missing API permission?)", endpoint)
                    return None
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                logger.error("[BookStack] API error (%s): %s", endpoint, e)
                return None
        logger.error("[BookStack] Gave up after %d retries for %s",
                     _retries, endpoint)
        return None

    def _api_get_all(self, endpoint: str,
                     params: Optional[Dict] = None) -> List[Dict]:
        """Paginate through a BookStack list endpoint, return all items."""
        all_items: List[Dict] = []
        offset = 0
        count = 500  # BookStack max per request
        base_params = dict(params or {})
        while True:
            base_params.update({'offset': offset, 'count': count})
            data = self._api_get(endpoint, params=base_params)
            if not data or 'data' not in data:
                break
            items = data['data']
            if not items:
                break
            all_items.extend(items)
            offset += count
            # Yield to other greenlets between pagination requests
            gevent.sleep(0)
            if len(items) < count:
                break
        return all_items

    # ── Structure fetching ──────────────────────────────────────────

    def _fetch_books(self):
        """Fetch all books → populate ``_book_map``."""
        logger.info("[BookStack] Fetching books...")
        books = self._api_get_all('books')
        for b in books:
            self._book_map[b['id']] = {
                'slug': b.get('slug', ''),
                'name': b.get('name', ''),
                'description': b.get('description', ''),
            }
        logger.info("[BookStack] Fetched %d books", len(self._book_map))

    def _fetch_chapters(self):
        """Fetch all chapters → populate ``_chapter_map``."""
        logger.info("[BookStack] Fetching chapters...")
        chapters = self._api_get_all('chapters')
        for c in chapters:
            self._chapter_map[c['id']] = {
                'slug': c.get('slug', ''),
                'name': c.get('name', ''),
                'description': c.get('description', ''),
                'book_id': c.get('book_id', 0),
            }
        logger.info("[BookStack] Fetched %d chapters", len(self._chapter_map))

    # ── Permission / tag mapping ────────────────────────────────────

    def _load_group_uuids(self):
        """Load all group UUIDs from the backend database."""
        try:
            from src.db_models import Group
            groups = Group.query.all()
            self._group_uuid_set = {g.uuid for g in groups if g.uuid}
            logger.info("[BookStack] Loaded %d group UUIDs from database",
                        len(self._group_uuid_set))
        except Exception as e:
            logger.warning("[BookStack] Could not load group UUIDs: %s", e)
            self._group_uuid_set = set()

    def _fetch_roles(self):
        """Fetch BookStack roles and create ``bookstack-{name}`` tags for ALL.

        Every role gets a tag named ``bookstack-{sanitised_display_name}``.
        Additionally, roles whose ``external_auth_id`` matches a backend
        group UUID are stored in ``_role_to_group_uuid`` so that users of
        that group gain automatic access.
        """
        logger.info("[BookStack] Fetching roles for permission mapping...")
        roles_data = self._api_get('roles', params={'count': 500})
        if not roles_data or 'data' not in roles_data:
            logger.warning("[BookStack] Could not fetch roles — "
                           "permission mapping will be skipped "
                           "(API user may lack 'Manage Roles' permission)")
            return

        # Load group UUIDs from backend DB for matching
        self._load_group_uuids()

        from modules.assistant.dashboard.metrics_service import add_log

        for r in roles_data['data']:
            role_id = r['id']
            display_name = r.get('display_name', r.get('name', f'role_{role_id}'))

            # Build a safe tag name: bookstack-{lowered_name_with_underscores}
            safe_name = re.sub(r'[^a-z0-9_-]', '_', display_name.lower()).strip('_')
            tag_name = f"bookstack-{safe_name}"

            # Fetch role detail to get external_auth_id (not in list response)
            detail = self._api_get(f'roles/{role_id}')
            time.sleep(self._REQUEST_DELAY)
            external_auth_id = ''
            if detail:
                external_auth_id = (detail.get('external_auth_id') or '').strip()

            self._role_map[role_id] = {
                'display_name': display_name,
                'external_auth_id': external_auth_id,
                'tag_name': tag_name,
            }
            self._role_tag_names[role_id] = tag_name

            # Yield between role detail fetches
            gevent.sleep(0)

            # Check if external_auth_id matches a group UUID
            if external_auth_id and external_auth_id in self._group_uuid_set:
                self._role_to_group_uuid[role_id] = external_auth_id
                logger.info(
                    "[BookStack] bookstack_role_mapped_to_group_uuid: "
                    "role '%s' (id=%d, external_auth_id=%s) → group UUID %s "
                    "→ tag '%s'",
                    display_name, role_id, external_auth_id,
                    external_auth_id, tag_name)

                # Register the bookstack tag → group UUID mapping in tag_service
                # so get_user_allowed_tags() can resolve access at query time.
                try:
                    from modules.assistant.services.tag_service import set_bookstack_tag_group_uuid
                    set_bookstack_tag_group_uuid(tag_name, external_auth_id)
                except Exception as exc:
                    logger.warning("[BookStack] Could not register tag→group "
                                   "mapping for '%s': %s", tag_name, exc)

                add_log('bookstack_role_mapped_to_group_uuid',
                        f"Role '{display_name}' mapped to group UUID {external_auth_id}",
                        {'role_id': role_id, 'role_name': display_name,
                         'external_auth_id': external_auth_id,
                         'group_uuid': external_auth_id,
                         'tag_name': tag_name})
            else:
                logger.info(
                    "[BookStack] Role '%s' (id=%d) → tag '%s' "
                    "(no group UUID match)", display_name, role_id, tag_name)

        logger.info("[BookStack] Fetched %d roles, %d mapped to group UUIDs, "
                    "%d total tags to create",
                    len(self._role_map), len(self._role_to_group_uuid),
                    len(self._role_tag_names))

    def _resolve_book_tags(self, book_id: int) -> List[str]:
        """Determine permission tags for a book via content-permissions API.

        Returns a list of ``bookstack-{name}`` tag names derived from ALL
        BookStack roles that have *view* access to this book.

        If the book has no custom permissions (inherits defaults) an empty
        list is returned so the pipeline falls back to source-level tags.
        """
        if book_id in self._book_tags:
            return self._book_tags[book_id]

        tags: List[str] = []

        if not self.map_permissions or not self._role_tag_names:
            self._book_tags[book_id] = tags
            return tags

        perms = self._api_get(f'content-permissions/book/{book_id}')
        time.sleep(self._REQUEST_DELAY)

        if not perms:
            self._book_tags[book_id] = tags
            return tags

        role_permissions = perms.get('role_permissions', [])
        if not role_permissions:
            self._book_tags[book_id] = tags
            return tags

        for rp in role_permissions:
            role_id = rp.get('role_id')
            can_view = rp.get('view', False)
            if can_view and role_id in self._role_tag_names:
                tag_name = self._role_tag_names[role_id]
                if tag_name not in tags:
                    tags.append(tag_name)

        self._book_tags[book_id] = tags
        if tags:
            logger.info("[BookStack] Book %d (%s) → tags: %s",
                        book_id,
                        self._book_map.get(book_id, {}).get('name', '?'),
                        tags)
        return tags

    def _resolve_content_tags(self, content_type: str, content_id: int,
                              fallback_book_id: int = 0) -> List[str]:
        """Resolve permission tags for any content type (page/chapter/book).

        Queries ``content-permissions/{content_type}/{content_id}`` to get
        item-specific role permissions.  If the item has **no** custom
        permissions (role_permissions list is empty), falls back to the
        parent book's permissions.

        Returns a list of ``bookstack-{name}`` tag names.
        """
        tags: List[str] = []

        if not self.map_permissions or not self._role_tag_names:
            return tags

        perms = self._api_get(f'content-permissions/{content_type}/{content_id}')
        time.sleep(self._REQUEST_DELAY)

        if not perms:
            # API call failed — fall back to book-level permissions
            if fallback_book_id:
                return self._resolve_book_tags(fallback_book_id)
            return tags

        role_permissions = perms.get('role_permissions', [])
        if not role_permissions:
            # No item-specific overrides — inherit from parent book
            if fallback_book_id:
                return self._resolve_book_tags(fallback_book_id)
            return tags

        for rp in role_permissions:
            role_id = rp.get('role_id')
            can_view = rp.get('view', False)
            if can_view and role_id in self._role_tag_names:
                tag_name = self._role_tag_names[role_id]
                if tag_name not in tags:
                    tags.append(tag_name)

        return tags

    def _resolve_page_tags(self, page_id: int, book_id: int = 0) -> List[str]:
        """Determine permission tags for a page via content-permissions API.

        Checks page-specific permissions first.  If the page has no custom
        permissions (inherits from parent), falls back to book-level tags.

        Results are cached in ``_page_tags``.
        """
        if page_id in self._page_tags:
            return self._page_tags[page_id]

        # If the tag cache has been frozen (i.e. we are in the attachment phase)
        # do NOT make new API calls for pages we haven't seen yet.  Fall back to
        # book-level tags so all attachment chunks remain consistent.
        if getattr(self, '_permission_tags_frozen', False):
            logger.debug(
                "[BookStack] Tags frozen — page %d not in cache, using book %d tags",
                page_id, book_id,
            )
            return self._resolve_book_tags(book_id)

        if not self.map_permissions or not self._role_tag_names:
            tags = self._resolve_book_tags(book_id)
            self._page_tags[page_id] = tags
            return tags

        tags = self._resolve_content_tags('page', page_id, fallback_book_id=book_id)
        self._page_tags[page_id] = tags

        if tags:
            book_tags = self._resolve_book_tags(book_id)
            if tags != book_tags:
                logger.info(
                    "[BookStack] Page %d has custom permissions → tags: %s "
                    "(book %d tags: %s)",
                    page_id, tags, book_id, book_tags)

        return tags

    def _resolve_chapter_tags(self, chapter_id: int, book_id: int = 0) -> List[str]:
        """Determine permission tags for a chapter via content-permissions API.

        Checks chapter-specific permissions first.  If the chapter has no custom
        permissions (inherits from parent), falls back to book-level tags.

        Results are cached in ``_chapter_tags``.
        """
        if chapter_id in self._chapter_tags:
            return self._chapter_tags[chapter_id]

        # If the tag cache has been frozen, fall back to book-level tags without
        # making new API calls (same rationale as _resolve_page_tags).
        if getattr(self, '_permission_tags_frozen', False):
            logger.debug(
                "[BookStack] Tags frozen — chapter %d not in cache, using book %d tags",
                chapter_id, book_id,
            )
            return self._resolve_book_tags(book_id)

        if not self.map_permissions or not self._role_tag_names:
            tags = self._resolve_book_tags(book_id)
            self._chapter_tags[chapter_id] = tags
            return tags

        tags = self._resolve_content_tags('chapter', chapter_id, fallback_book_id=book_id)
        self._chapter_tags[chapter_id] = tags

        if tags:
            book_tags = self._resolve_book_tags(book_id)
            if tags != book_tags:
                logger.info(
                    "[BookStack] Chapter %d has custom permissions → tags: %s "
                    "(book %d tags: %s)",
                    chapter_id, tags, book_id, book_tags)

        return tags

    def _auto_create_tags(self, tag_names: List[str]):
        """Auto-create *automatic* assistant tags for BookStack role-derived names.

        Creates tags with ``automatic=True`` using ``create_automatic_tag()``.
        Tags prefixed ``bookstack-`` are deletable but not editable (name).

        Must be called from within a Flask app context.
        """
        if not tag_names:
            return

        try:
            from modules.assistant.services import tag_service
            from modules.assistant.dashboard.metrics_service import add_log
        except ImportError:
            logger.warning("[BookStack] tag_service not available — "
                           "skipping auto-creation of tags")
            return

        for name in tag_names:
            if name in self._auto_created_tags:
                continue
            result, err = tag_service.create_automatic_tag(
                name=name,
                description='Auto-created from BookStack role permission mapping',
            )
            if result:
                logger.info("[BookStack] automatic_tag_created '%s' (id=%s)",
                            name, result.get('id'))
                add_log('automatic_tag_created',
                        f"Automatic tag created: {name}",
                        {'tag_name': name, 'tag_id': result.get('id'),
                         'automatic': True})
            else:
                logger.warning("[BookStack] Failed to create automatic tag "
                               "'%s': %s", name, err)
            self._auto_created_tags.add(name)

    # ── URL builders ────────────────────────────────────────────────

    def _book_url(self, book_id: int) -> str:
        slug = self._book_map.get(book_id, {}).get('slug', str(book_id))
        return f"{self.base_url}/books/{slug}"

    def _chapter_url(self, chapter_id: int) -> str:
        ch = self._chapter_map.get(chapter_id, {})
        book_id = ch.get('book_id', 0)
        book_slug = self._book_map.get(book_id, {}).get('slug', str(book_id))
        ch_slug = ch.get('slug', str(chapter_id))
        return f"{self.base_url}/books/{book_slug}/chapter/{ch_slug}"

    def _page_url(self, book_id: int, page_slug: str) -> str:
        book_slug = self._book_map.get(book_id, {}).get('slug', str(book_id))
        return f"{self.base_url}/books/{book_slug}/page/{page_slug}"

    # ── Content fetching ────────────────────────────────────────────

    def _fetch_page_documents(
        self, filter_params: Optional[Dict] = None,
    ) -> List[DocumentChunk]:
        """Fetch pages, convert to DocumentChunks.

        Also populates ``_page_book_map`` for later attachment resolution.
        """
        logger.info("[BookStack] Fetching pages...")
        pages = self._api_get_all('pages', params=filter_params)
        logger.info("[BookStack] Found %d pages, fetching detail...", len(pages))
        emit_progress('fetch', f"{len(pages)} Seiten gefunden, lade Details...",
                      source_name=self.source_name,
                      detail={'page_count': len(pages)})

        # Build page→book map from the listing (avoids extra requests)
        for p in pages:
            self._page_book_map[p['id']] = p.get('book_id', 0)

        documents: List[DocumentChunk] = []
        skipped_pages = 0
        for i, ps in enumerate(pages):
            try:
                detail = self._api_get(f"pages/{ps['id']}")
                time.sleep(self._REQUEST_DELAY)
                if not detail:
                    skipped_pages += 1
                    continue

                text = html_to_text(detail.get('html', ''))
                if not text.strip():
                    skipped_pages += 1
                    continue

                book_id = detail.get('book_id', 0)
                chapter_id = detail.get('chapter_id') or 0
                page_slug = detail.get('slug', '')
                page_url = self._page_url(book_id, page_slug)
                title = detail.get('name', 'Untitled')

                perm_tags = self._resolve_page_tags(detail['id'], book_id)

                documents.append(DocumentChunk(
                    text=text,
                    title=title,
                    source='Wissensdatenbank',
                    source_id=self.source_id,
                    document_url=page_url,
                    permission_tags=perm_tags if perm_tags else [],
                    source_type='page',
                    extra_metadata={
                        'bookstack_type': 'page',
                        'subsource_type': 'page',
                        'subsource_id': f"page_{detail['id']}",
                        'automatic_tags': bool(perm_tags),
                        'book_id': book_id,
                        'book_name': self._book_map.get(book_id, {}).get('name', ''),
                        'chapter_id': chapter_id,
                        'chapter_name': self._chapter_map.get(chapter_id, {}).get('name', ''),
                        'page_id': detail['id'],
                        'page_slug': page_slug,
                    },
                ))

                if perm_tags:
                    from modules.assistant.dashboard.metrics_service import add_log
                    add_log('subsource_tagged_with_automatic_tag',
                            f"Page '{title}' tagged with {perm_tags}",
                            {'subsource_type': 'page', 'subsource_id': f"page_{detail['id']}",
                             'tags': perm_tags, 'automatic_tags': True})
            except Exception as exc:
                logger.error("[BookStack] Error processing page %d (%s): %s",
                             ps.get('id', '?'), ps.get('name', '?'), exc, exc_info=True)
                emit_progress('fetch',
                              f"Fehler bei Seite '{ps.get('name', '?')}': {exc}",
                              source_name=self.source_name, level='warning')
                skipped_pages += 1

            # Yield control to other greenlets periodically — html_to_text()
            # and DocumentChunk construction are CPU-bound.
            if (i + 1) % 5 == 0:
                gevent.sleep(0)

            if (i + 1) % 50 == 0:
                logger.info("[BookStack] Processed %d/%d pages...",
                            i + 1, len(pages))
                emit_progress('fetch', f"Seite {i + 1}/{len(pages)} verarbeitet...",
                              source_name=self.source_name,
                              progress=((i + 1) / max(len(pages), 1)))

        logger.info("[BookStack] Created %d page documents (%d skipped)", len(documents), skipped_pages)
        return documents

    def _fetch_book_documents(self) -> List[DocumentChunk]:
        """Create documents from book descriptions (when non-empty)."""
        documents: List[DocumentChunk] = []
        for book_id, info in self._book_map.items():
            desc = (info.get('description') or '').strip()
            if not desc:
                continue

            perm_tags = self._resolve_book_tags(book_id)
            documents.append(DocumentChunk(
                text=f"Book: {info['name']}\n\n{desc}",
                title=f"Book: {info['name']}",
                source='Wissensdatenbank',
                source_id=self.source_id,
                document_url=self._book_url(book_id),
                permission_tags=perm_tags if perm_tags else [],
                source_type='page',
                extra_metadata={
                    'bookstack_type': 'book',
                    'subsource_type': 'book',
                    'subsource_id': f"book_{book_id}",
                    'automatic_tags': bool(perm_tags),
                    'book_id': book_id,
                    'book_name': info['name'],
                },
            ))
        if documents:
            logger.info("[BookStack] Created %d book description documents",
                        len(documents))
        return documents

    def _fetch_chapter_documents(self) -> List[DocumentChunk]:
        """Create documents from chapter descriptions (when non-empty)."""
        documents: List[DocumentChunk] = []
        for ch_id, info in self._chapter_map.items():
            desc = (info.get('description') or '').strip()
            if not desc:
                continue

            book_id = info.get('book_id', 0)
            perm_tags = self._resolve_chapter_tags(ch_id, book_id)
            documents.append(DocumentChunk(
                text=f"Chapter: {info['name']}\n\n{desc}",
                title=f"Chapter: {info['name']}",
                source='Wissensdatenbank',
                source_id=self.source_id,
                document_url=self._chapter_url(ch_id),
                permission_tags=perm_tags if perm_tags else [],
                source_type='page',
                extra_metadata={
                    'bookstack_type': 'chapter',
                    'subsource_type': 'chapter',
                    'subsource_id': f"chapter_{ch_id}",
                    'automatic_tags': bool(perm_tags),
                    'chapter_id': ch_id,
                    'chapter_name': info['name'],
                    'book_id': book_id,
                    'book_name': self._book_map.get(book_id, {}).get('name', ''),
                },
            ))
        if documents:
            logger.info("[BookStack] Created %d chapter description documents",
                        len(documents))
        return documents

    def _stream_attachment_documents(self):
        """Generator: download, extract and yield attachment DocumentChunks.

        Redesigned for high parallelism:
        1. Attachment metadata is fetched and filtered (serial, fast).
        2. Attachments are batched into groups of ``ATTACHMENT_BATCH_SIZE``.
        3. Each batch is processed in parallel using a gevent pool:
           - Download (base64 decode)
           - Extract via Docling (with chunking) / Tika fallback
        4. Results are yielded immediately so the pipeline can start
           embedding while the next batch is being processed.

        Per-attachment failures are logged and skipped — they never crash
        the pipeline.
        """
        if not self.index_attachments:
            logger.info("[BookStack] Attachment indexing disabled in config")
            return

        from modules.assistant.dashboard.metrics_service import add_log

        attachments = self._api_get_all('attachments')
        total = len(attachments)
        logger.info("[BookStack] Found %d attachments — parallel processing "
                    "(pool=%d, batch=%d)", total, ATTACHMENT_POOL_SIZE,
                    ATTACHMENT_BATCH_SIZE)
        emit_progress('fetch',
                      f"{total} Anhänge gefunden, starte parallele Extraktion "
                      f"(Pool: {ATTACHMENT_POOL_SIZE})...",
                      source_name=self.source_name,
                      detail={'attachment_count': total,
                              'pool_size': ATTACHMENT_POOL_SIZE})

        # ── Phase 1: Filter and collect downloadable attachments ───
        downloadable = []
        skipped = 0
        skipped_size = 0
        for att in attachments:
            if att.get('external', False):
                skipped += 1
                continue

            att_id = att['id']
            att_name = att.get('name', f'attachment_{att_id}')
            page_id = att.get('uploaded_to', 0)
            ext = ('.' + att_name.rsplit('.', 1)[1].lower()) if '.' in att_name else ''

            if ext not in ALL_SUPPORTED_EXTENSIONS:
                logger.debug("[BookStack] Unsupported type '%s' for '%s' — skipping",
                             ext, att_name)
                skipped += 1
                continue

            # Size check: BookStack does not expose file size in the list
            # endpoint, so we must fetch the attachment detail here to read the
            # base64 content length.  If the decoded size would exceed the
            # configured limit we skip the file immediately — before spawning a
            # worker greenlet — to avoid wasting bandwidth and Docling resources.
            # The pre-fetched detail is stored so the worker greenlet can use it
            # directly without a second round-trip.
            prefetched_detail = None
            if self.max_attachment_size_mb > 0:
                detail = self._api_get(f'attachments/{att_id}')
                time.sleep(self._REQUEST_DELAY)
                if detail and detail.get('content'):
                    try:
                        # base64 is ~33 % larger than binary, so multiply by 0.75
                        estimated_size_mb = (len(detail['content']) * 0.75) / (1024 * 1024)
                        if estimated_size_mb > self.max_attachment_size_mb:
                            logger.info(
                                "[BookStack] Attachment '%s' (id=%d, ~%.2f MB) exceeds "
                                "size limit of %.0f MB — skipping",
                                att_name, att_id, estimated_size_mb,
                                self.max_attachment_size_mb,
                            )
                            skipped_size += 1
                            continue
                        # Cache so the worker doesn't re-download
                        prefetched_detail = detail
                    except Exception as size_err:
                        logger.warning(
                            "[BookStack] Size check failed for '%s': %s — skipping",
                            att_name, size_err,
                        )
                        skipped += 1
                        continue

            downloadable.append({
                'att_id': att_id,
                'att_name': att_name,
                'page_id': page_id,
                'ext': ext,
                'prefetched_detail': prefetched_detail,
            })

        logger.info(
            "[BookStack] %d attachments eligible, %d skipped (unsupported/external), "
            "%d skipped (size limit)",
            len(downloadable), skipped, skipped_size,
        )

        if not downloadable:
            return

        # ── Phase 2: Process in parallel batches ───────────────────
        yielded = 0
        failed = 0
        processed_stats: Dict[str, int] = {}

        def _process_single_attachment(att_info: dict) -> Optional[DocumentChunk]:
            """Download + extract a single attachment. Returns DocumentChunk or None."""
            att_id = att_info['att_id']
            att_name = att_info['att_name']
            page_id = att_info['page_id']
            ext = att_info['ext']

            # Download — use the detail pre-fetched during Phase 1 (size check)
            # if available; otherwise fall back to a fresh API request.
            detail = att_info.get('prefetched_detail') or self._api_get(f'attachments/{att_id}')
            if not detail or not detail.get('content'):
                logger.debug("[BookStack] Attachment %d (%s): no content", att_id, att_name)
                return None

            try:
                file_data = base64.b64decode(detail['content'])
            except Exception as e:
                logger.warning("[BookStack] Failed to decode attachment %d (%s): %s",
                               att_id, att_name, e)
                return None

            # ── Size limit check (belt-and-suspenders) ────────────
            # Phase 1 already filtered out oversized attachments when
            # max_attachment_size_mb > 0.  This secondary check catches any
            # edge case where a file slipped through (e.g. no size limit set).
            if self.max_attachment_size_mb > 0:
                file_size_mb = len(file_data) / (1024 * 1024)
                if file_size_mb > self.max_attachment_size_mb:
                    logger.info(
                        "[BookStack] Attachment '%s' (id=%d, %.2f MB) exceeds "
                        "size limit of %.0f MB — skipping",
                        att_name, att_id, file_size_mb, self.max_attachment_size_mb,
                    )
                    add_log(
                        'attachment_skipped_size_limit',
                        f"Anhang '{att_name}' übersprungen: {file_size_mb:.2f} MB "
                        f"> Limit {self.max_attachment_size_mb:.0f} MB",
                        {
                            'attachment_id': att_id,
                            'attachment_name': att_name,
                            'file_extension': ext,
                            'file_size_bytes': len(file_data),
                            'file_size_mb': round(file_size_mb, 2),
                            'limit_mb': self.max_attachment_size_mb,
                            'page_id': page_id,
                        },
                    )
                    return None

            # Extract with chunking support
            t0 = time.monotonic()
            try:
                result = _service_extract_with_chunks(file_data, att_name)
            except Exception as exc:
                logger.error("[BookStack] Extraction error for '%s': %s",
                             att_name, exc)
                return None
            elapsed = time.monotonic() - t0

            if not result.success or not result.text.strip():
                logger.info("[BookStack] Attachment '%s' (%s, %d B): "
                            "no text from %s in %.2fs — skipping",
                            att_name, ext, len(file_data), result.method, elapsed)
                return None

            # Build DocumentChunk — use page-level permissions for attachments
            book_id = self._page_book_map.get(page_id, 0)
            perm_tags = self._resolve_page_tags(page_id, book_id) if page_id else (
                self._resolve_book_tags(book_id) if book_id else []
            )
            att_url = f"{self.base_url}/attachments/{att_id}"

            logger.info("[BookStack] Attachment '%s' (%s, %d B): "
                        "%d chars, %d chunks via %s in %.2fs, tags=%s",
                        att_name, ext, len(file_data), len(result.text),
                        len(result.chunks), result.method, elapsed,
                        perm_tags or 'none')

            add_log('attachment_processed',
                    f"Attachment '{att_name}' processed ({result.method})",
                    {'attachment_id': att_id, 'attachment_name': att_name,
                     'file_extension': ext, 'file_size': len(file_data),
                     'text_length': len(result.text),
                     'chunk_count': len(result.chunks),
                     'extraction_method': result.method,
                     'processing_time_s': round(elapsed, 2),
                     'page_count': result.page_count,
                     'table_count': result.table_count,
                     'tags': perm_tags})

            doc = DocumentChunk(
                text=result.text,
                title=f"Attachment: {att_name}",
                source='Wissensdatenbank',
                source_id=self.source_id,
                document_url=att_url,
                permission_tags=perm_tags if perm_tags else [],
                source_type='attachment',
                extra_metadata={
                    'bookstack_type': 'attachment',
                    'subsource_type': 'attachment',
                    'subsource_id': f"attachment_{att_id}",
                    'automatic_tags': bool(perm_tags),
                    'attachment_id': att_id,
                    'attachment_name': att_name,
                    'uploaded_to_page_id': page_id,
                    'book_id': book_id,
                    'file_extension': ext,
                    'file_size': len(file_data),
                    'extraction_method': result.method,
                    'page_count': result.page_count,
                    'table_count': result.table_count,
                },
            )

            # Attach Docling chunks if available (pipeline will use them
            # instead of running the local TextChunker)
            if result.chunks:
                doc.docling_chunks = result.chunks

            return doc

        # Capture the Flask app object while we are still inside the request
        # context (parent greenlet).  Each worker greenlet must push its own
        # app context because Flask-SQLAlchemy's session is scoped to the
        # application context, which is NOT inherited by gevent greenlets.
        flask_app = current_app._get_current_object()

        # Process in batches using gevent pool
        for batch_start in range(0, len(downloadable), ATTACHMENT_BATCH_SIZE):
            batch = downloadable[batch_start:batch_start + ATTACHMENT_BATCH_SIZE]
            batch_results: List[Optional[DocumentChunk]] = [None] * len(batch)

            pool = GeventPool(size=ATTACHMENT_POOL_SIZE)

            def _worker(idx, att_info):
                with flask_app.app_context():
                    try:
                        batch_results[idx] = _process_single_attachment(att_info)
                    except Exception as exc:
                        logger.error("[BookStack] Worker error for '%s': %s",
                                     att_info['att_name'], exc, exc_info=True)
                        batch_results[idx] = None

            for idx, att_info in enumerate(batch):
                pool.spawn(_worker, idx, att_info)
            pool.join()

            # Yield results from this batch
            for idx, doc in enumerate(batch_results):
                if doc is not None:
                    ext = batch[idx]['ext']
                    processed_stats[ext] = processed_stats.get(ext, 0) + 1
                    yielded += 1
                    yield doc
                else:
                    failed += 1

            batch_end = min(batch_start + ATTACHMENT_BATCH_SIZE, len(downloadable))
            emit_progress(
                'fetch',
                f"Anhänge {batch_end}/{len(downloadable)}: "
                f"{yielded} extrahiert, {failed} fehlgeschlagen...",
                source_name=self.source_name,
                progress=(batch_end / max(len(downloadable), 1)),
            )
            gevent.sleep(0)

        logger.info("[BookStack] Attachment processing done: %d yielded, %d failed, "
                    "%d skipped, by type: %s",
                    yielded, failed, skipped, processed_stats)

    # ── Public interface ────────────────────────────────────────────

    def fetch_documents_stream(self):
        """Streaming fetch: yields DocumentChunks as they become available.

        Ordering:
        1. Pages, book descriptions, chapter descriptions (fast — all in memory).
           These are yielded immediately so the pipeline can start embedding while
           attachments are still being downloaded and extracted.
        2. Attachments (slow — one round-trip + Docling/Tika call per file).
           Each chunk is yielded as soon as extraction completes, not after all
           attachments are done.

        Auto-creates permission tags after the fast section (before attachments)
        so they exist in the DB before the first attachment doc is yielded.
        """
        logger.info("[BookStack] ── Streaming fetch for '%s' (id=%s) ──",
                    self.source_name, self.source_id)
        emit_progress('fetch', f"BookStack-Stream gestartet für '{self.source_name}'...",
                      source_name=self.source_name)

        # Build structural maps
        emit_progress('fetch', 'Lade Bücher und Kapitel...', source_name=self.source_name)
        self._fetch_books()
        self._fetch_chapters()

        if self.map_permissions:
            emit_progress('fetch', 'Lade Rollen für Berechtigungsmapping...',
                          source_name=self.source_name)
            self._fetch_roles()

        # ── Yield fast sections ────────────────────────────────────
        perm_tags_seen: set = set()

        for doc in self._fetch_page_documents():
            perm_tags_seen.update(doc.permission_tags)
            yield doc

        for doc in self._fetch_book_documents():
            perm_tags_seen.update(doc.permission_tags)
            yield doc

        for doc in self._fetch_chapter_documents():
            perm_tags_seen.update(doc.permission_tags)
            yield doc

        # Create auto-tags for everything we've seen so far — before starting
        # the slow attachment phase so they exist by the time the pipeline stores
        # the first attachment chunk.
        if perm_tags_seen:
            self._auto_create_tags(list(perm_tags_seen))

        # Freeze permission tag cache before starting the attachment phase.
        # All attachments processed in any batch will use the tags resolved
        # during the fast section above.  This prevents race conditions where
        # the same attachment receives different permission tags depending on
        # which batch it is processed in.
        self._permission_tags_frozen = True
        logger.info(
            "[BookStack] Permission tags frozen: %d books, %d pages, %d chapters",
            len(self._book_tags), len(self._page_tags), len(self._chapter_tags),
        )

        # ── Stream attachments ─────────────────────────────────────
        # Each DocumentChunk is yielded immediately after extraction so the
        # pipeline can embed it in the current batch while the next attachment
        # is still being downloaded and processed.
        yield from self._stream_attachment_documents()

    def fetch_documents(self) -> List[DocumentChunk]:
        """Fetch ALL content from BookStack (non-streaming wrapper).

        Collects everything from :meth:`fetch_documents_stream` into a list.
        Use ``fetch_documents_stream()`` directly in the pipeline for better
        throughput — pages/chapters will start embedding while attachments are
        still being extracted.
        """
        return list(self.fetch_documents_stream())

    def sync(self, last_sync: Optional[datetime] = None) -> List[DocumentChunk]:
        """Incremental sync: fetch content updated since *last_sync*."""
        if last_sync is None:
            return self.fetch_documents()

        logger.info("[BookStack] ── Incremental sync since %s for '%s' ──",
                    last_sync.isoformat(), self.source_name)

        # Rebuild structural maps (needed for correct URL construction)
        self._fetch_books()
        self._fetch_chapters()
        if self.map_permissions:
            self._fetch_roles()

        sync_str = last_sync.strftime('%Y-%m-%dT%H:%M:%S')
        documents: List[DocumentChunk] = []

        # Fetch only pages updated since last_sync
        documents.extend(self._fetch_page_documents(
            filter_params={'filter[updated_at:gt]': sync_str},
        ))

        # Attachments have no server-side date filter in the API, so
        # we fetch all and let the pipeline overwrite existing vectors.
        if self.index_attachments:
            documents.extend(self._stream_attachment_documents())

        # Auto-create tags
        all_perm_tags: set = set()
        for doc in documents:
            all_perm_tags.update(doc.permission_tags)
        if all_perm_tags:
            self._auto_create_tags(list(all_perm_tags))

        logger.info("[BookStack] ── Incremental sync found %d documents ──",
                    len(documents))
        return documents

    def test_connection(self) -> Dict[str, Any]:
        """Test BookStack API connection and summarise available content."""
        try:
            page_data = self._api_get('pages', params={'count': 1})
            if page_data is None:
                return {'success': False,
                        'message': 'Could not reach BookStack API.'}

            page_total = page_data.get('total', 0)
            book_data = self._api_get('books', params={'count': 1})
            book_total = book_data.get('total', '?') if book_data else '?'
            att_data = self._api_get('attachments', params={'count': 1})
            att_total = att_data.get('total', '?') if att_data else '?'

            return {
                'success': True,
                'message': (f'Connected. {page_total} pages, '
                            f'{book_total} books, '
                            f'{att_total} attachments available.'),
            }
        except Exception as e:
            return {'success': False, 'message': f'Connection failed: {str(e)}'}

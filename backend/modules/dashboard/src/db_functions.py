# Dashboard Module - Database Functions (CRUD)
from datetime import datetime, timezone
from src.db import db
from modules.dashboard.src.db_models import DashboardPage, DashboardTopic, DashboardApplication


# ── Helper ──────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


# ── Pages ───────────────────────────────────────────────────────────

def get_all_pages(include_deleted=False):
    """Return all pages, optionally including soft-deleted ones."""
    query = DashboardPage.query
    if not include_deleted:
        query = query.filter_by(is_deleted=False)
    return [p.to_dict() for p in query.order_by(DashboardPage.sort_order).all()]


def get_page_full(page_id):
    """Return a single page with nested topics and applications."""
    page = DashboardPage.query.get(page_id)
    if not page or page.is_deleted:
        return None
    return page.to_dict_full()


def create_page(name, description=''):
    """Create a new page. Returns (dict, error_string)."""
    name = name.strip()
    if not name:
        return None, 'Name is required.'

    existing = DashboardPage.query.filter_by(name=name, is_deleted=False).first()
    if existing:
        return None, f'A page named "{name}" already exists.'

    # Auto-assign sort_order
    max_order = db.session.query(db.func.coalesce(db.func.max(DashboardPage.sort_order), -1)).filter_by(is_deleted=False).scalar()
    page = DashboardPage(name=name, description=description.strip(), sort_order=max_order + 1)
    db.session.add(page)
    db.session.commit()
    return page.to_dict(), None


def update_page(page_id, name=None, description=None):
    """Update a page. Returns (dict, error_string)."""
    page = DashboardPage.query.get(page_id)
    if not page or page.is_deleted:
        return None, 'Page not found.'

    if name is not None:
        name = name.strip()
        if not name:
            return None, 'Name cannot be empty.'
        dup = DashboardPage.query.filter(
            DashboardPage.name == name,
            DashboardPage.id != page_id,
            DashboardPage.is_deleted == False
        ).first()
        if dup:
            return None, f'A page named "{name}" already exists.'
        page.name = name

    if description is not None:
        page.description = description.strip()

    page.updated_at = _now()
    db.session.commit()
    return page.to_dict(), None


def delete_page(page_id, hard=False):
    """Soft-delete (or hard-delete) a page and cascade to topics/applications."""
    page = DashboardPage.query.get(page_id)
    if not page:
        return None, 'Page not found.'

    if hard:
        # Hard delete – remove from DB entirely
        topics = DashboardTopic.query.filter_by(page_id=page_id).all()
        for topic in topics:
            DashboardApplication.query.filter_by(topic_id=topic.id).delete()
            db.session.delete(topic)
        db.session.delete(page)
    else:
        # Soft delete – cascade to children
        now = _now()
        page.is_deleted = True
        page.updated_at = now
        for topic in DashboardTopic.query.filter_by(page_id=page_id, is_deleted=False).all():
            topic.is_deleted = True
            topic.updated_at = now
            for app in DashboardApplication.query.filter_by(topic_id=topic.id, is_deleted=False).all():
                app.is_deleted = True
                app.updated_at = now

    db.session.commit()
    return {'status': True, 'message': 'Page deleted.'}, None


# ── Topics ──────────────────────────────────────────────────────────

def get_all_topics(page_id=None, include_deleted=False):
    """Return topics, optionally filtered by page."""
    query = DashboardTopic.query
    if not include_deleted:
        query = query.filter_by(is_deleted=False)
    if page_id is not None:
        query = query.filter_by(page_id=page_id)
    return [t.to_dict() for t in query.order_by(DashboardTopic.sort_order).all()]


def get_topic_full(topic_id):
    """Return a single topic with its applications."""
    topic = DashboardTopic.query.get(topic_id)
    if not topic or topic.is_deleted:
        return None
    return topic.to_dict_full()


def create_topic(name, page_id, description=''):
    """Create a new topic under a page. Returns (dict, error_string)."""
    name = name.strip()
    if not name:
        return None, 'Name is required.'

    page = DashboardPage.query.get(page_id)
    if not page or page.is_deleted:
        return None, 'Page not found.'

    existing = DashboardTopic.query.filter_by(name=name, page_id=page_id, is_deleted=False).first()
    if existing:
        return None, f'A topic named "{name}" already exists in this page.'

    # Auto-assign sort_order
    max_order = db.session.query(db.func.coalesce(db.func.max(DashboardTopic.sort_order), -1)).filter(
        DashboardTopic.page_id == page_id, DashboardTopic.is_deleted == False
    ).scalar()
    topic = DashboardTopic(name=name, page_id=page_id, description=description.strip(), sort_order=max_order + 1)
    db.session.add(topic)
    db.session.commit()
    return topic.to_dict(), None


def update_topic(topic_id, name=None, description=None, page_id=None):
    """Update a topic. Returns (dict, error_string)."""
    topic = DashboardTopic.query.get(topic_id)
    if not topic or topic.is_deleted:
        return None, 'Topic not found.'

    target_page_id = page_id if page_id is not None else topic.page_id

    # Validate target page
    if page_id is not None:
        page = DashboardPage.query.get(page_id)
        if not page or page.is_deleted:
            return None, 'Target page not found.'
        topic.page_id = page_id

    if name is not None:
        name = name.strip()
        if not name:
            return None, 'Name cannot be empty.'
        dup = DashboardTopic.query.filter(
            DashboardTopic.name == name,
            DashboardTopic.page_id == target_page_id,
            DashboardTopic.id != topic_id,
            DashboardTopic.is_deleted == False
        ).first()
        if dup:
            return None, f'A topic named "{name}" already exists in the target page.'
        topic.name = name

    if description is not None:
        topic.description = description.strip()

    topic.updated_at = _now()
    db.session.commit()
    return topic.to_dict(), None


def delete_topic(topic_id, hard=False):
    """Soft-delete (or hard-delete) a topic and cascade to applications."""
    topic = DashboardTopic.query.get(topic_id)
    if not topic:
        return None, 'Topic not found.'

    if hard:
        DashboardApplication.query.filter_by(topic_id=topic_id).delete()
        db.session.delete(topic)
    else:
        now = _now()
        topic.is_deleted = True
        topic.updated_at = now
        for app in DashboardApplication.query.filter_by(topic_id=topic_id, is_deleted=False).all():
            app.is_deleted = True
            app.updated_at = now

    db.session.commit()
    return {'status': True, 'message': 'Topic deleted.'}, None


# ── Applications ────────────────────────────────────────────────────

def get_all_applications(topic_id=None, page_id=None, search=None, include_deleted=False):
    """Return applications with optional filtering."""
    query = DashboardApplication.query
    if not include_deleted:
        query = query.filter_by(is_deleted=False)
    if topic_id is not None:
        query = query.filter_by(topic_id=topic_id)
    elif page_id is not None:
        # Filter by page through the topic relationship
        topic_ids = [
            t.id for t in DashboardTopic.query.filter_by(page_id=page_id, is_deleted=False).all()
        ]
        query = query.filter(DashboardApplication.topic_id.in_(topic_ids))
    if search:
        query = query.filter(DashboardApplication.name.ilike(f'%{search}%'))
    return [a.to_dict() for a in query.order_by(DashboardApplication.sort_order).all()]


def get_application(app_id):
    """Return a single application."""
    app = DashboardApplication.query.get(app_id)
    if not app or app.is_deleted:
        return None
    return app.to_dict()


def create_application(name, url, topic_id, description='', icon=''):
    """Create a new application under a topic. Returns (dict, error_string)."""
    name = name.strip()
    url = url.strip()
    if not name:
        return None, 'Name is required.'
    if not url:
        return None, 'URL is required.'

    topic = DashboardTopic.query.get(topic_id)
    if not topic or topic.is_deleted:
        return None, 'Topic not found.'

    # Ensure no duplicate name within the same topic
    existing = DashboardApplication.query.filter_by(name=name, topic_id=topic_id, is_deleted=False).first()
    if existing:
        return None, f'An application named "{name}" already exists in this topic.'

    # Auto-assign sort_order
    max_order = db.session.query(db.func.coalesce(db.func.max(DashboardApplication.sort_order), -1)).filter(
        DashboardApplication.topic_id == topic_id, DashboardApplication.is_deleted == False
    ).scalar()
    app = DashboardApplication(
        name=name,
        description=description.strip(),
        url=url,
        icon=icon.strip() if icon else '',
        topic_id=topic_id,
        sort_order=max_order + 1,
    )
    db.session.add(app)
    db.session.commit()
    return app.to_dict(), None


def update_application(app_id, name=None, description=None, url=None, icon=None, topic_id=None):
    """Update an application. Returns (dict, error_string)."""
    app = DashboardApplication.query.get(app_id)
    if not app or app.is_deleted:
        return None, 'Application not found.'

    target_topic_id = topic_id if topic_id is not None else app.topic_id

    # Validate target topic
    if topic_id is not None:
        topic = DashboardTopic.query.get(topic_id)
        if not topic or topic.is_deleted:
            return None, 'Target topic not found.'
        app.topic_id = topic_id

    if name is not None:
        name = name.strip()
        if not name:
            return None, 'Name cannot be empty.'
        dup = DashboardApplication.query.filter(
            DashboardApplication.name == name,
            DashboardApplication.topic_id == target_topic_id,
            DashboardApplication.id != app_id,
            DashboardApplication.is_deleted == False
        ).first()
        if dup:
            return None, f'An application named "{name}" already exists in the target topic.'
        app.name = name

    if description is not None:
        app.description = description.strip()
    if url is not None:
        url = url.strip()
        if not url:
            return None, 'URL cannot be empty.'
        app.url = url
    if icon is not None:
        app.icon = icon.strip()

    app.updated_at = _now()
    db.session.commit()
    return app.to_dict(), None


def delete_application(app_id, hard=False):
    """Soft-delete (or hard-delete) an application."""
    app = DashboardApplication.query.get(app_id)
    if not app:
        return None, 'Application not found.'

    if hard:
        db.session.delete(app)
    else:
        app.is_deleted = True
        app.updated_at = _now()

    db.session.commit()
    return {'status': True, 'message': 'Application deleted.'}, None


# ── Bulk Operations ─────────────────────────────────────────────────

def bulk_reassign_applications(app_ids, new_topic_id):
    """Move multiple applications to a different topic. Returns (dict, error_string)."""
    topic = DashboardTopic.query.get(new_topic_id)
    if not topic or topic.is_deleted:
        return None, 'Target topic not found.'

    now = _now()
    count = 0
    for app_id in app_ids:
        app = DashboardApplication.query.get(app_id)
        if app and not app.is_deleted:
            # Check for name collision in the target topic
            dup = DashboardApplication.query.filter(
                DashboardApplication.name == app.name,
                DashboardApplication.topic_id == new_topic_id,
                DashboardApplication.id != app.id,
                DashboardApplication.is_deleted == False
            ).first()
            if dup:
                continue  # skip duplicates silently
            app.topic_id = new_topic_id
            app.updated_at = now
            count += 1

    db.session.commit()
    return {'status': True, 'message': f'{count} application(s) reassigned.', 'count': count}, None


def bulk_move_topics(topic_ids, new_page_id):
    """Move multiple topics to a different page. Returns (dict, error_string)."""
    page = DashboardPage.query.get(new_page_id)
    if not page or page.is_deleted:
        return None, 'Target page not found.'

    now = _now()
    count = 0
    for topic_id in topic_ids:
        topic = DashboardTopic.query.get(topic_id)
        if topic and not topic.is_deleted:
            dup = DashboardTopic.query.filter(
                DashboardTopic.name == topic.name,
                DashboardTopic.page_id == new_page_id,
                DashboardTopic.id != topic.id,
                DashboardTopic.is_deleted == False
            ).first()
            if dup:
                continue
            topic.page_id = new_page_id
            topic.updated_at = now
            count += 1

    db.session.commit()
    return {'status': True, 'message': f'{count} topic(s) moved.', 'count': count}, None


# ── Reorder ─────────────────────────────────────────────────────────

def reorder_pages(ordered_ids):
    """Set sort_order for pages based on the given list of IDs."""
    now = _now()
    for idx, page_id in enumerate(ordered_ids):
        page = DashboardPage.query.get(page_id)
        if page and not page.is_deleted:
            page.sort_order = idx
            page.updated_at = now
    db.session.commit()
    return {'status': True, 'message': 'Pages reordered.'}, None


def reorder_topics(page_id, ordered_ids):
    """Set sort_order for topics within a page based on the given list of IDs."""
    page = DashboardPage.query.get(page_id)
    if not page or page.is_deleted:
        return None, 'Page not found.'
    now = _now()
    for idx, topic_id in enumerate(ordered_ids):
        topic = DashboardTopic.query.get(topic_id)
        if topic and not topic.is_deleted and topic.page_id == page_id:
            topic.sort_order = idx
            topic.updated_at = now
    db.session.commit()
    return {'status': True, 'message': 'Topics reordered.'}, None


def reorder_applications(topic_id, ordered_ids):
    """Set sort_order for applications within a topic based on the given list of IDs."""
    topic = DashboardTopic.query.get(topic_id)
    if not topic or topic.is_deleted:
        return None, 'Topic not found.'
    now = _now()
    for idx, app_id in enumerate(ordered_ids):
        app = DashboardApplication.query.get(app_id)
        if app and not app.is_deleted and app.topic_id == topic_id:
            app.sort_order = idx
            app.updated_at = now
    db.session.commit()
    return {'status': True, 'message': 'Applications reordered.'}, None


# ── Flat applications list (for the existing /api/applications) ─────

def get_all_applications_flat():
    """Return all non-deleted applications in a flat list for the Dashboard frontend."""
    apps = DashboardApplication.query.filter_by(is_deleted=False).order_by(DashboardApplication.sort_order).all()
    return [
        {
            'name': a.name,
            'url': a.url,
            'icon': a.icon or '',
            'description': a.description or '',
        }
        for a in apps
    ]

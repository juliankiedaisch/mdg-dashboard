# Assistant Module - Services: Tag Service
"""
CRUD operations for assistant tags and source-tag mappings.
Handles dynamic permission creation/deletion for tags.
Supports automatic tags derived from BookStack role → group UUID mapping.
"""
import logging
from typing import Optional, Dict, Any, List

from src.db import db
from src.permissions import register_dynamic_permission, unregister_dynamic_permission, user_has_permission
from modules.assistant.models.tag import AssistantTag, source_tag_mapping
from modules.assistant.models.source_config import SourceConfig
from modules.assistant.dashboard.metrics_service import add_log

logger = logging.getLogger(__name__)

DEFAULT_TAG_NAME = 'default_assistant_source'
DEFAULT_TAG_DESCRIPTION = 'Default tag for all assistant knowledge sources'

# Cache: bookstack tag name → group UUID for access resolution.
# Populated by BookStackSource._fetch_roles() via set_bookstack_tag_group_uuid().
_bookstack_tag_group_uuid_cache: Dict[str, str] = {}


def set_bookstack_tag_group_uuid(tag_name: str, group_uuid: str):
    """Register a mapping from a ``bookstack-`` tag name to a group UUID.

    Called during ingestion so that ``get_user_allowed_tags()`` can grant
    access to users belonging to the matching group.
    """
    _bookstack_tag_group_uuid_cache[tag_name] = group_uuid
    logger.debug("[TagService] Cached bookstack tag→group: %s → %s",
                 tag_name, group_uuid)


# ── Tag CRUD ────────────────────────────────────────────────────────

def get_all_tags() -> List[Dict]:
    """Get all tags."""
    tags = AssistantTag.query.order_by(AssistantTag.name).all()
    return [t.to_dict() for t in tags]


def get_tag(tag_id: int) -> Optional[Dict]:
    """Get a single tag by ID."""
    tag = AssistantTag.query.get(tag_id)
    return tag.to_dict() if tag else None


def create_tag(name: str, description: str = '') -> tuple:
    """
    Create a new tag and its corresponding dynamic permission.

    Returns:
        (tag_dict, error_string)
    """
    if not name or not name.strip():
        return None, "Tag name is required."

    name = name.strip().lower().replace(' ', '_')

    # Validate name format (allow alphanumeric, underscores, hyphens for UUIDs)
    if not all(c.isalnum() or c in ('_', '-') for c in name):
        return None, "Tag name must contain only letters, numbers, underscores, or hyphens."

    existing = AssistantTag.query.filter_by(name=name).first()
    if existing:
        return existing.to_dict(), None  # return existing tag, no error

    tag = AssistantTag(name=name, description=description.strip())
    db.session.add(tag)
    db.session.commit()

    # Create corresponding dynamic permission
    permission_id = tag.permission_id
    register_dynamic_permission(
        permission_id,
        f"Access assistant sources tagged '{name}'"
    )

    add_log('assistant_tag_created', f"Tag created: {name}", {'tag_id': tag.id, 'permission_id': permission_id})
    add_log('assistant_tag_permission_created', f"Permission created: {permission_id}", {'tag_id': tag.id})

    logger.info(f"Created tag '{name}' with permission '{permission_id}'")
    return tag.to_dict(), None


def create_automatic_tag(name: str, description: str = '') -> tuple:
    """
    Create or retrieve an automatic tag (derived from BookStack role → group UUID).

    Automatic tags:
      - Have ``automatic=True``
      - Cannot be deleted or renamed by admins.
      - Grant access to users belonging to the matching group.

    Returns:
        (tag_dict, error_string)
    """
    if not name or not name.strip():
        return None, "Tag name is required."

    name = name.strip()

    existing = AssistantTag.query.filter_by(name=name).first()
    if existing:
        # Ensure the automatic flag is set even if the tag existed before
        if not existing.automatic:
            existing.automatic = True
            db.session.commit()
            logger.info("Upgraded existing tag '%s' to automatic", name)
        return existing.to_dict(), None

    tag = AssistantTag(name=name, description=description.strip(), automatic=True)
    db.session.add(tag)
    db.session.commit()

    permission_id = tag.permission_id
    register_dynamic_permission(
        permission_id,
        f"Access assistant sources tagged '{name}' (automatic/group-derived)"
    )

    add_log('automatic_tag_created',
            f"Automatic tag created: {name}",
            {'tag_id': tag.id, 'permission_id': permission_id})
    logger.info("Created automatic tag '%s' (id=%d, perm=%s)",
                name, tag.id, permission_id)
    return tag.to_dict(), None


def update_tag(tag_id: int, name: str = None, description: str = None) -> tuple:
    """
    Update a tag. If the name changes, update the permission too.
    Automatic tags cannot be renamed.

    Returns:
        (tag_dict, error_string)
    """
    tag = AssistantTag.query.get(tag_id)
    if not tag:
        return None, "Tag not found."

    if tag.automatic and name is not None and name != tag.name:
        return None, "Automatic tags cannot be renamed."

    old_permission_id = tag.permission_id

    if name is not None:
        name = name.strip().lower().replace(' ', '_')
        if not all(c.isalnum() or c in ('_', '-') for c in name):
            return None, "Tag name must contain only letters, numbers, underscores, or hyphens."

        existing = AssistantTag.query.filter(
            AssistantTag.name == name,
            AssistantTag.id != tag_id
        ).first()
        if existing:
            return None, f"Tag '{name}' already exists."

        if name != tag.name:
            # Remove old permission
            unregister_dynamic_permission(old_permission_id)
            tag.name = name
            # Create new permission
            register_dynamic_permission(
                tag.permission_id,
                f"Access assistant sources tagged '{name}'"
            )

    if description is not None:
        tag.description = description.strip()

    db.session.commit()
    logger.info(f"Updated tag id={tag_id}")
    return tag.to_dict(), None


def delete_tag(tag_id: int) -> tuple:
    """
    Delete a tag and its corresponding permission.
    Automatic tags with ``bookstack-`` prefix CAN be deleted.
    Other automatic tags (non-bookstack) cannot be deleted.

    Returns:
        (result_dict, error_string)
    """
    tag = AssistantTag.query.get(tag_id)
    if not tag:
        return None, "Tag not found."

    if tag.automatic and not tag.name.startswith('bookstack-'):
        return None, "Automatic tags (derived from group mappings) cannot be deleted."

    permission_id = tag.permission_id
    tag_name = tag.name

    # Remove the dynamic permission
    unregister_dynamic_permission(permission_id)

    db.session.delete(tag)
    db.session.commit()

    add_log('assistant_tag_deleted', f"Tag deleted: {tag_name}", {'tag_id': tag_id, 'permission_id': permission_id})

    logger.info(f"Deleted tag '{tag_name}' and permission '{permission_id}'")
    return {'status': True, 'message': f"Tag '{tag_name}' deleted."}, None


# ── Source-Tag Assignment ───────────────────────────────────────────

def get_source_tags(source_id: int) -> List[Dict]:
    """Get tags assigned to a source."""
    source = SourceConfig.query.get(source_id)
    if not source:
        return []
    return [{'id': t.id, 'name': t.name} for t in source.tags]


def set_source_tags(source_id: int, tag_ids: List[int]) -> tuple:
    """
    Set the tags for a source (replaces existing assignments).

    Returns:
        (source_dict, error_string)
    """
    source = SourceConfig.query.get(source_id)
    if not source:
        return None, "Source not found."

    tags = AssistantTag.query.filter(AssistantTag.id.in_(tag_ids)).all() if tag_ids else []
    source.tags = tags
    db.session.commit()

    tag_names = [t.name for t in tags]
    add_log('assistant_source_tag_updated', f"Source '{source.name}' tags updated: {tag_names}",
            {'source_id': source_id, 'tag_ids': tag_ids})

    logger.info(f"Set tags for source {source_id}: {tag_names}")
    return source.to_dict(), None


# ── Permission Helpers ──────────────────────────────────────────────

def get_user_allowed_tags(user_uuid: str) -> List[str]:
    """
    Determine which tag names a user can access.

    Access is granted when **any** of the following is true for a tag:

    1. It is the default tag (``DEFAULT_TAG_NAME``).
    2. The user has the corresponding permission via their profiles/groups.
    3. The tag is *automatic* and its name equals one of the user's group
       UUIDs.  (Legacy path for non-bookstack automatic tags.)
    4. The tag is *automatic* with a ``bookstack-`` prefix.  Access is
       granted when the tag's associated group UUID (looked up via the
       ``bookstack_tag_to_group_uuid`` cache set during ingestion) matches
       one of the user's groups.  This is the BookStack role → group
       mapping path.

    Args:
        user_uuid: The UUID of the user.

    Returns:
        List of tag names the user is allowed to access.
    """
    from src.db_models import User  # local import to avoid circular deps

    all_tags = AssistantTag.query.all()

    # Collect the user's group UUIDs for automatic-tag matching
    user_group_uuids: set = set()
    try:
        user = User.query.filter_by(uuid=user_uuid).first()
        if user:
            user_group_uuids = {g.uuid for g in user.groups if g.uuid}
    except Exception as exc:
        logger.warning("[TagService] Failed to load groups for user %s: %s",
                       user_uuid, exc)

    allowed: List[str] = []
    for tag in all_tags:
        # (1) Default tag is always accessible
        if tag.name == DEFAULT_TAG_NAME:
            allowed.append(tag.name)
            continue

        # (3/4) Automatic tag matching
        if tag.automatic:
            # Legacy path: tag name IS the group UUID
            if tag.name in user_group_uuids:
                allowed.append(tag.name)
                logger.debug("[TagService] user %s matched automatic tag '%s' "
                             "via group membership (UUID match)", user_uuid, tag.name)
                continue

            # bookstack- tag: check if the linked group UUID is in user's groups
            if tag.name.startswith('bookstack-'):
                linked_uuid = _bookstack_tag_group_uuid_cache.get(tag.name)
                if linked_uuid and linked_uuid in user_group_uuids:
                    allowed.append(tag.name)
                    logger.debug("[TagService] user %s matched bookstack tag '%s' "
                                 "via group UUID %s", user_uuid, tag.name, linked_uuid)
                    continue

        # (2) Permission-based check
        if user_has_permission(tag.permission_id, user_uuid):
            allowed.append(tag.name)

    logger.debug("[TagService] user_access_checked_against_group_tags: "
                 "user=%s groups=%s allowed=%s",
                 user_uuid, user_group_uuids, allowed)
    return allowed


def get_user_allowed_source_ids(user_uuid: str) -> List[int]:
    """
    Determine which source IDs a user can access based on their tag permissions.

    Args:
        user_uuid: The UUID of the user.

    Returns:
        List of source IDs the user is allowed to access.
    """
    allowed_tags = get_user_allowed_tags(user_uuid)
    if not allowed_tags:
        return []

    # Find all sources that have at least one of the allowed tags
    sources = SourceConfig.query.join(
        source_tag_mapping,
        SourceConfig.id == source_tag_mapping.c.source_id
    ).join(
        AssistantTag,
        AssistantTag.id == source_tag_mapping.c.tag_id
    ).filter(
        AssistantTag.name.in_(allowed_tags)
    ).distinct().all()

    return [s.id for s in sources]


# ── Migration / Default Tag ─────────────────────────────────────────

def ensure_default_tag():
    """
    Ensure the default tag exists.
    Assign it to any sources that have no tags.
    """
    tag = AssistantTag.query.filter_by(name=DEFAULT_TAG_NAME).first()
    if not tag:
        tag = AssistantTag(name=DEFAULT_TAG_NAME, description=DEFAULT_TAG_DESCRIPTION)
        db.session.add(tag)
        db.session.commit()
        register_dynamic_permission(
            tag.permission_id,
            f"Access assistant sources tagged '{DEFAULT_TAG_NAME}'"
        )
        logger.info(f"Created default tag '{DEFAULT_TAG_NAME}'")

    # Assign default tag to sources without any tags
    untagged_sources = SourceConfig.query.filter(~SourceConfig.tags.any()).all()
    for source in untagged_sources:
        source.tags.append(tag)
        logger.info(f"Assigned default tag to source '{source.name}' (id={source.id})")

    if untagged_sources:
        db.session.commit()


def sync_tag_permissions():
    """
    Ensure every existing tag has its corresponding permission registered.
    Called at startup to handle cases where permissions may have been lost.
    """
    tags = AssistantTag.query.all()
    for tag in tags:
        register_dynamic_permission(
            tag.permission_id,
            f"Access assistant sources tagged '{tag.name}'"
        )
    logger.info(f"Synced permissions for {len(tags)} assistant tags")

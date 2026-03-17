"""
Granular Permission Management System

Handles:
- Permission registration from modules
- Permission calculation for users (via profiles + groups)
- Super Admin bypass
- Per-request caching
"""
from flask import session, g
from src.db import db
from src.db_models import Permission, Profile, User, Group
from src import globals
import os


# ── Super Admin ─────────────────────────────────────────────────────

def is_super_admin(username=None):
    """Check if the given (or session) user is the Super Admin."""
    if not globals.SUPER_ADMIN_USERNAME:
        return False
    if username is None:
        username = session.get("preferred_username", "")
    return username == globals.SUPER_ADMIN_USERNAME


# ── Permission Registration ─────────────────────────────────────────

def register_module_permissions(module_name, permissions_dict):
    """
    Register permissions defined by a module.

    permissions_dict: {"survey.view": "View surveys", ...}

    - Inserts new permissions that don't exist yet.
    - Deletes permissions for this module that are no longer defined.
    """
    # Get existing permissions for this module
    existing = Permission.query.filter_by(module=module_name).all()
    existing_ids = {p.id for p in existing}
    defined_ids = set(permissions_dict.keys())

    # Insert new permissions
    for perm_id, description in permissions_dict.items():
        if perm_id not in existing_ids:
            perm = Permission(id=perm_id, module=module_name, description=description)
            db.session.add(perm)
            print(f"  [Permissions] Registered: {perm_id} ({description})")
        else:
            # Update description if changed
            perm = Permission.query.get(perm_id)
            if perm and perm.description != description:
                perm.description = description
                print(f"  [Permissions] Updated: {perm_id} ({description})")

    # Delete permissions no longer defined by the module
    stale_ids = existing_ids - defined_ids
    for stale_id in stale_ids:
        perm = Permission.query.get(stale_id)
        if perm:
            db.session.delete(perm)
            print(f"  [Permissions] Removed stale: {stale_id}")

    db.session.commit()


def sync_all_module_permissions(modules_list):
    """
    Iterate all loaded modules and register their permissions.
    Called once at startup from app.py.
    """
    print("Server: Syncing module permissions...")
    for module in modules_list:
        perms = getattr(module, 'MODULE_PERMISSIONS', None)
        if perms:
            module_name = module.MODULE_NAME
            print(f"  [Permissions] Module '{module_name}': {len(perms)} permissions")
            register_module_permissions(module_name, perms)
    
    # Also register the built-in permission management permissions
    builtin_perms = {
        "permissions.manage": "Manage permission profiles and assignments",
        "permissions.view_users": "View user permission details",
    }
    register_module_permissions("permissions", builtin_perms)
    print("Server: Permission sync complete.")


# ── Dynamic Permission Registration ────────────────────────────────

def register_dynamic_permission(permission_name, description, module_name="assistant"):
    """
    Register a single dynamic permission at runtime.

    This is used by the tag system to create permissions like
    ASSISTANT_TAG_ENGINEERING_WIKI when a tag is created.

    The permission is:
      - inserted if it doesn't exist
      - updated (description) if it already exists
      - available for role assignment immediately

    Args:
        permission_name: The permission ID string (e.g. 'ASSISTANT_TAG_INTERNAL_DOCS')
        description: Human-readable description
        module_name: The module this permission belongs to (default: 'assistant')
    """
    existing = Permission.query.get(permission_name)
    if existing:
        if existing.description != description:
            existing.description = description
            db.session.commit()
            print(f"  [Permissions] Dynamic updated: {permission_name}")
    else:
        perm = Permission(id=permission_name, module=module_name, description=description)
        db.session.add(perm)
        db.session.commit()
        print(f"  [Permissions] Dynamic registered: {permission_name} ({description})")


def unregister_dynamic_permission(permission_name):
    """
    Remove a dynamically created permission.

    Used when a tag is deleted to clean up its corresponding permission.
    """
    perm = Permission.query.get(permission_name)
    if perm:
        db.session.delete(perm)
        db.session.commit()
        print(f"  [Permissions] Dynamic removed: {permission_name}")


# ── Permission Calculation ──────────────────────────────────────────

def get_user_permissions(user_uuid=None):
    """
    Calculate the merged set of permission IDs for a user.

    Collects permissions from:
      1. Profiles assigned directly to the user
      2. Profiles assigned to the user's groups

    Returns a set of permission ID strings.
    Results are cached in flask.g for the current request.
    """
    if user_uuid is None:
        user_uuid = session.get("user_uuid")

    if not user_uuid:
        return set()

    # Per-request cache
    cache_key = f"_permissions_{user_uuid}"
    cached = getattr(g, cache_key, None)
    if cached is not None:
        return cached

    user = User.query.filter_by(uuid=user_uuid).first()
    if not user:
        setattr(g, cache_key, set())
        return set()

    permission_ids = set()

    # Permissions from direct user profiles
    for profile in user.profiles:
        for perm in profile.permissions:
            permission_ids.add(perm.id)

    # Permissions from group profiles
    for group in user.groups:
        for profile in group.profiles:
            for perm in profile.permissions:
                permission_ids.add(perm.id)

    setattr(g, cache_key, permission_ids)
    return permission_ids


def user_has_permission(permission_id, user_uuid=None):
    """
    Check if the current (or specified) user has a specific permission.

    Super Admin always returns True.
    """
    # Super Admin bypass
    username = session.get("preferred_username", "") if user_uuid is None else None
    if user_uuid is None and is_super_admin(username):
        return True

    # If a specific user_uuid is provided, check if that user is super admin
    if user_uuid is not None:
        user = User.query.filter_by(uuid=user_uuid).first()
        if user and is_super_admin(user.username):
            return True

    permissions = get_user_permissions(user_uuid)
    return permission_id in permissions


def get_user_permissions_detailed(user_uuid):
    """
    Get detailed permission info for a user, showing which profile grants which permission.
    Used by the admin UI to inspect a user's effective permissions.

    Returns:
    {
        "user": {"id": ..., "username": ..., "uuid": ...},
        "is_super_admin": bool,
        "profiles": [
            {"id": ..., "name": ..., "source": "direct"|"group:<name>", "permissions": [...]}
        ],
        "merged_permissions": [{"id": ..., "module": ..., "description": ..., "granted_by": [...]}]
    }
    """
    user = User.query.filter_by(uuid=user_uuid).first()
    if not user:
        return None

    profiles_info = []
    permission_sources = {}  # perm_id -> list of profile names + source

    # Direct user profiles
    for profile in user.profiles:
        profile_data = {
            "id": profile.id,
            "name": profile.name,
            "source": "direct",
            "permissions": [p.to_dict() for p in profile.permissions]
        }
        profiles_info.append(profile_data)
        for perm in profile.permissions:
            permission_sources.setdefault(perm.id, []).append(f"{profile.name} (direct)")

    # Group profiles
    for group in user.groups:
        for profile in group.profiles:
            profile_data = {
                "id": profile.id,
                "name": profile.name,
                "source": f"group:{group.name}",
                "permissions": [p.to_dict() for p in profile.permissions]
            }
            profiles_info.append(profile_data)
            for perm in profile.permissions:
                permission_sources.setdefault(perm.id, []).append(
                    f"{profile.name} (via {group.name})"
                )

    # Merged permissions
    all_perm_ids = set(permission_sources.keys())
    merged = []
    for perm_id in sorted(all_perm_ids):
        perm = Permission.query.get(perm_id)
        if perm:
            merged.append({
                "id": perm.id,
                "module": perm.module,
                "description": perm.description,
                "granted_by": permission_sources[perm_id]
            })

    return {
        "user": {"id": user.id, "username": user.username, "uuid": user.uuid},
        "is_super_admin": is_super_admin(user.username),
        "profiles": profiles_info,
        "merged_permissions": merged
    }

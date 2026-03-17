"""
Permission Management API Routes

Provides REST endpoints for:
- Listing all permissions (grouped by module)
- CRUD for profiles
- Assigning profiles to users/groups
- Viewing a user's effective permissions
- Getting current user's permissions
"""
from flask import Blueprint, jsonify, request, session
from src.decorators import login_required, permission_required
from src.permissions import (
    get_user_permissions, get_user_permissions_detailed,
    is_super_admin, user_has_permission
)
from src.db import db
from src.db_models import Permission, Profile, User, Group


def init_permission_routes(oauth):
    bp = Blueprint('permissions', __name__)

    # ── Current User Permissions ─────────────────────────────────────

    @bp.route('/api/permissions/me', methods=['GET'])
    @login_required(oauth)
    def get_my_permissions():
        """Get the current user's effective permissions."""
        if is_super_admin():
            # Super Admin has all permissions
            all_perms = Permission.query.all()
            return jsonify({
                "is_super_admin": True,
                "permissions": [p.id for p in all_perms]
            })
        
        perms = get_user_permissions()
        return jsonify({
            "is_super_admin": False,
            "permissions": list(perms)
        })

    # ── List All Permissions (grouped by module) ─────────────────────

    @bp.route('/api/permissions/all', methods=['GET'])
    @login_required(oauth)
    @permission_required("permissions.manage")
    def list_all_permissions():
        """List all registered permissions, grouped by module."""
        permissions = Permission.query.order_by(Permission.module, Permission.id).all()
        grouped = {}
        for p in permissions:
            grouped.setdefault(p.module, []).append(p.to_dict())
        return jsonify({"permissions": grouped})

    # ── Profile CRUD ─────────────────────────────────────────────────

    @bp.route('/api/permissions/profiles', methods=['GET'])
    @login_required(oauth)
    @permission_required("permissions.manage")
    def list_profiles():
        """List all profiles with their permissions."""
        profiles = Profile.query.order_by(Profile.name).all()
        return jsonify({
            "profiles": [p.to_dict(include_permissions=True, include_assignments=True) for p in profiles]
        })

    @bp.route('/api/permissions/profiles', methods=['POST'])
    @login_required(oauth)
    @permission_required("permissions.manage")
    def create_profile():
        """Create a new profile."""
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({"error": "Profile name is required"}), 400

        if Profile.query.filter_by(name=data['name']).first():
            return jsonify({"error": "A profile with this name already exists"}), 409

        profile = Profile(
            name=data['name'],
            description=data.get('description', '')
        )

        # Assign permissions if provided
        perm_ids = data.get('permissions', [])
        if perm_ids:
            perms = Permission.query.filter(Permission.id.in_(perm_ids)).all()
            profile.permissions = perms

        db.session.add(profile)
        db.session.commit()
        return jsonify({"profile": profile.to_dict(include_permissions=True)}), 201

    @bp.route('/api/permissions/profiles/<int:profile_id>', methods=['GET'])
    @login_required(oauth)
    @permission_required("permissions.manage")
    def get_profile(profile_id):
        """Get a single profile with full details."""
        profile = Profile.query.get(profile_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
        return jsonify({"profile": profile.to_dict(include_permissions=True, include_assignments=True)})

    @bp.route('/api/permissions/profiles/<int:profile_id>', methods=['PUT'])
    @login_required(oauth)
    @permission_required("permissions.manage")
    def update_profile(profile_id):
        """Update a profile's name, description, and permissions."""
        profile = Profile.query.get(profile_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        if 'name' in data:
            # Check for duplicate name (exclude current profile)
            existing = Profile.query.filter(
                Profile.name == data['name'],
                Profile.id != profile_id
            ).first()
            if existing:
                return jsonify({"error": "A profile with this name already exists"}), 409
            profile.name = data['name']

        if 'description' in data:
            profile.description = data['description']

        if 'permissions' in data:
            perms = Permission.query.filter(Permission.id.in_(data['permissions'])).all()
            profile.permissions = perms

        db.session.commit()
        return jsonify({"profile": profile.to_dict(include_permissions=True, include_assignments=True)})

    @bp.route('/api/permissions/profiles/<int:profile_id>', methods=['DELETE'])
    @login_required(oauth)
    @permission_required("permissions.manage")
    def delete_profile(profile_id):
        """Delete a profile."""
        profile = Profile.query.get(profile_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        db.session.delete(profile)
        db.session.commit()
        return jsonify({"message": "Profile deleted"})

    # ── Profile Assignments ──────────────────────────────────────────

    @bp.route('/api/permissions/profiles/<int:profile_id>/assign-users', methods=['POST'])
    @login_required(oauth)
    @permission_required("permissions.manage")
    def assign_profile_to_users(profile_id):
        """Assign a profile to users. Body: {"user_ids": [1, 2, 3]}"""
        profile = Profile.query.get(profile_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        data = request.get_json()
        user_ids = data.get('user_ids', [])
        users = User.query.filter(User.id.in_(user_ids)).all()
        profile.users = users
        db.session.commit()
        return jsonify({"profile": profile.to_dict(include_permissions=True, include_assignments=True)})

    @bp.route('/api/permissions/profiles/<int:profile_id>/assign-groups', methods=['POST'])
    @login_required(oauth)
    @permission_required("permissions.manage")
    def assign_profile_to_groups(profile_id):
        """Assign a profile to groups. Body: {"group_ids": [1, 2, 3]}"""
        profile = Profile.query.get(profile_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        data = request.get_json()
        group_ids = data.get('group_ids', [])
        groups = Group.query.filter(Group.id.in_(group_ids)).all()
        profile.groups = groups
        db.session.commit()
        return jsonify({"profile": profile.to_dict(include_permissions=True, include_assignments=True)})

    # ── User / Group Listing (for the assignment UI) ────────────────

    @bp.route('/api/permissions/users', methods=['GET'])
    @login_required(oauth)
    @permission_required("permissions.manage")
    def list_users():
        """List all users for assignment UI. Supports ?search=query."""
        search = request.args.get('search', '').strip()
        query = User.query
        if search:
            query = query.filter(User.username.ilike(f'%{search}%'))
        users = query.order_by(User.username).limit(100).all()
        return jsonify({
            "users": [{"id": u.id, "uuid": u.uuid, "username": u.username} for u in users]
        })

    @bp.route('/api/permissions/groups', methods=['GET'])
    @login_required(oauth)
    @permission_required("permissions.manage")
    def list_groups():
        """List all groups for assignment UI. Supports ?search=query."""
        search = request.args.get('search', '').strip()
        query = Group.query
        if search:
            query = query.filter(Group.name.ilike(f'%{search}%'))
        groups = query.order_by(Group.name).limit(100).all()
        return jsonify({
            "groups": [{"id": g.id, "uuid": g.uuid, "name": g.name} for g in groups]
        })

    # ── User Permission Viewer ───────────────────────────────────────

    @bp.route('/api/permissions/user/<user_uuid>/details', methods=['GET'])
    @login_required(oauth)
    @permission_required("permissions.view_users")
    def get_user_permission_details(user_uuid):
        """Get detailed permission breakdown for a user."""
        details = get_user_permissions_detailed(user_uuid)
        if not details:
            return jsonify({"error": "User not found"}), 404
        return jsonify(details)

    return bp

from functools import wraps
from flask import redirect, url_for, session, jsonify, request
from urllib.parse import urlencode
from src import globals
import time


def permission_required(*permission_ids):
    """
    Granular permission-based decorator.
    Accepts one or more permission IDs (OR logic — user needs at least one).

    Usage:
        @permission_required("surveys.manage.all")
        @permission_required("surveys.manage.all", "surveys.normal.manage")

    Checks:
        1. Super Admin → always allowed
        2. User has at least one of the listed permissions
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from src.permissions import user_has_permission, is_super_admin

            # Must be logged in
            if 'user_uuid' not in session:
                if request.path.startswith('/api/'):
                    return jsonify({"error": "Unauthorized", "message": "Authentication required."}), 401
                return redirect(globals.frontend_url + '/login')

            # Super Admin bypasses all permission checks
            if is_super_admin():
                return f(*args, **kwargs)

            # Check granular permissions (OR logic)
            for perm_id in permission_ids:
                if user_has_permission(perm_id):
                    return f(*args, **kwargs)

            # Denied
            if request.path.startswith('/api/'):
                return jsonify({
                    "error": "Forbidden",
                    "message": f"Missing permission: {', '.join(permission_ids)}"
                }), 403
            return redirect(url_for('not_allowed'))
        return decorated_function
    return decorator


def login_required(oauth):
    """
    Decorator für geschützte Endpoints mit Silent Refresh.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'session_id' not in session:
                if request.path.startswith('/api/'):
                    return jsonify({"error": "Unauthorized", "message": "Authentication required."}), 401
                return redirect('/login')
            # Prüfen ob Token noch gültig
            expires_at = session.get('expires_at')
            if not expires_at or expires_at < time.time():
                if request.path.startswith('/api/'):
                    return jsonify({"error": "Unauthorized", "message": "Session expired."}), 401
                return redirect('/login')
            return f(*args, **kwargs)
        return decorated_function
    return decorator
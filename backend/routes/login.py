from flask import session, redirect, url_for, Blueprint, request, jsonify
from src.decorators import login_required
import uuid, sys, time
from datetime import datetime, timedelta
from src import globals
from src.db_functions import upsert_user_with_groups


def get_session_expiry_midnight():
    """Setzt session['expires_at'] auf 0 Uhr nachts heute oder morgen"""
    now = datetime.now()
    # Ablauf um Mitternacht
    midnight = datetime.combine(now.date(), datetime.min.time()) + timedelta(days=1)
    return midnight.timestamp()

def init_routes(oauth, db_session):

    bp = Blueprint('login', __name__)

    @bp.route('/api/login')
    def login():
        """Initiate OAuth login flow"""
        session.permanent = True
        session.modified = True  # Force session save
        # Set session ID if not already set
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        print(f"Login initiated, session ID: {session.get('session_id', 'none')}", flush=True, file=sys.stderr)
        redirect_uri = url_for('login.authorize', _external=True)
        return oauth.oauth_provider.authorize_redirect(redirect_uri=redirect_uri)

    @bp.route('/api/authorize')
    def authorize():
        """Handle OAuth callback and set session"""
        print(f"Authorize callback, session ID: {session.get('session_id', 'none')}", flush=True, file=sys.stderr)
        print(f"Cookies received: {list(request.cookies.keys())}", flush=True, file=sys.stderr)
        print(f"Session data: {dict(session)}", flush=True, file=sys.stderr)
        
        # Build frontend URL from environment variables
        # Use PRODUCTION flag to determine protocol
        protocol = "https" if globals.PRODUCTION else "http"
        if globals.PRODUCTION:
            # Production: use HTTPS without port (external proxy handles SSL)
            frontend_url = f"{protocol}://{globals.FRONTEND_HOST}"
        else:
            # Development: use HTTP with port
            if globals.FRONTEND_PORT == 80:
                frontend_url = f"{protocol}://{globals.FRONTEND_HOST}"
            else:
                frontend_url = f"{protocol}://{globals.FRONTEND_HOST}:{globals.FRONTEND_PORT}"
        
        try:
            token = oauth.oauth_provider.authorize_access_token()
        except Exception as e:
            print(f"OAuth Error: {e}", flush=True, file=sys.stderr)
            print(f"Session state: {session.get('oauth_state')}", flush=True, file=sys.stderr)
            print(f"Request state: {request.args.get('state')}", flush=True, file=sys.stderr)
            print(f"Request args: {dict(request.args)}", flush=True, file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return redirect(f'{frontend_url}/login?error=auth_failed')

        # Set session as permanent
        session.permanent = True
        session.modified = True  # Force session save

        # Set session ID if not already set
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())


        from src.permissions import get_user_permissions, is_super_admin
        from src.db_models import Permission
        
        # Get user's effective permissions
        if is_super_admin():
            all_perms = Permission.query.all()
            permissions = [p.id for p in all_perms]
        else:
            permissions = list(get_user_permissions())

        user_info = token.get("userinfo")                    
        session['access_token'] = token['access_token']
        session['refresh_token'] = token.get('refresh_token')
        session['expires_at'] = get_session_expiry_midnight()
        session['user_uuid'] = user_info['uuid']
        session['preferred_username'] = user_info['preferred_username']
        session['username'] = user_info['name']
        session["permissions"] = permissions
        session["is_super_admin"] = is_super_admin()
        print(f"Session data after token exchange: {dict(session)}", flush=True, file=sys.stderr)
        
        # Store user in database
        upsert_user_with_groups(user_info["uuid"], user_info['preferred_username'], user_info["groups"], db_session)

        # Redirect back to frontend root (not /login to avoid redirect loop)
        print(f"OAuth success! Redirecting to: {frontend_url}/", flush=True, file=sys.stderr)
        return redirect(frontend_url)
    
    @bp.route('/api/logout')
    def logout():
        """Clear session and logout"""
        session.clear()
        return jsonify({"message": "Logged out successfully"})
    
    @bp.route('/api/auth/status')
    def auth_status():
        try:
            """Check if user is authenticated"""
            expires_at = session.get('expires_at')
            if 'user_uuid' in session and expires_at and expires_at > time.time():
                from src.permissions import get_user_permissions, is_super_admin
                from src.db_models import Permission

                # Get user's effective permissions
                if is_super_admin():
                    all_perms = Permission.query.all()
                    permissions = [p.id for p in all_perms]
                else:
                    permissions = list(get_user_permissions())

                return jsonify({
                    "authenticated": True,
                    "username": session.get('username'),
                    "permissions": permissions,
                    "is_super_admin": is_super_admin()
                })
            
            # Session abgelaufen oder kein user_uuid → 401
            return jsonify({"authenticated": False}), 401
        except Exception as e:
            print(f"Auth status error: {e}", flush=True, file=sys.stderr)
            return jsonify({"authenticated": False}), 401
    
    return bp

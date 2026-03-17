# gevent monkey-patch must happen before any other imports so that all
# stdlib sockets/threads are replaced with gevent-compatible versions.
# Monkey patch FIRST, before any other imports (fixes gevent + threading conflicts)
from gevent import monkey
# subprocess=False: prevent gevent from patching the subprocess module.
# pytesseract (used by the ingestion worker for OCR) forks real child processes
# via subprocess.Popen.  When gevent patches subprocess it registers fork hooks
# that assert the main greenlet identity inside the child, which always fails
# and produces noisy "AssertionError" tracebacks.  Leaving subprocess unpatched
# has no effect on Flask-SocketIO or async I/O (only socket/threading matter).
monkey.patch_all(subprocess=False)


from flask import Flask, request, session, jsonify, redirect
from flask_socketio import emit, join_room
from flask_session import Session
from flask_cors import CORS
from src import socketio, globals
from authlib.integrations.flask_client import OAuth
import os
from src.decorators import login_required
from src.db import init_db, db_create_all, get_database_url


def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    
    # Trust proxy headers (required when behind nginx reverse proxy)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Build CORS origins from environment variables
    cors_origins = [
        f"http://{globals.FRONTEND_HOST}:{globals.FRONTEND_PORT}",
        f"https://{globals.FRONTEND_HOST}",  # HTTPS without port
        "https://hub.mdg-hamburg.de",
        "https://dashboard.hub.mdg-hamburg.de"
    ]
    
    # CORS configuration for frontend communication
    CORS(app, supports_credentials=True, origins=cors_origins)
    
    # Database configuration
    database_url = get_database_url()
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = globals.SQLALCHEMY_TRACK_MODIFICATIONS

    # PostgreSQL connection pool settings (ignored for SQLite)
    if database_url.startswith('postgresql'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 10,
            'max_overflow': 20,
            'pool_timeout': 30,
            'pool_recycle': 1800,        # recycle connections every 30 min
            'pool_pre_ping': True,        # verify connections before use
        }
    app.config['SECRET_KEY'] = globals.APP_SECRET_KEY
    app.config['SESSION_TYPE'] = 'filesystem'
    if globals.PRODUCTION:
        app.config['SESSION_FILE_DIR'] = '/app/flask_session'
    else:
        app.config['SESSION_FILE_DIR'] = 'flask_session'
    app.config['SESSION_COOKIE_NAME'] = 'mdg_dash_session'  # Changed to force new cookies
    # Use SESSION_COOKIE_DOMAIN from globals to enable cross-subdomain access
    app.config['SESSION_COOKIE_DOMAIN'] = globals.SESSION_COOKIE_DOMAIN if globals.PRODUCTION else None
    # Only use secure cookies in production (with SSL proxy)
    app.config['SESSION_COOKIE_SECURE'] = globals.PRODUCTION
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'None' if globals.PRODUCTION else 'Lax'  # None required for OAuth redirects in Chromium
    app.config['SESSION_COOKIE_PATH'] = '/'
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True
    app.config['SESSION_USE_SIGNER'] = True  # Sign session IDs for security

    # Initialize database
    if database_url.startswith('sqlite'):
        os.makedirs("db", exist_ok=True)
    if globals.PRODUCTION:
        os.makedirs("/app/flask_session", exist_ok=True)  # Ensure session directory exists
    else:
        os.makedirs("flask_session", exist_ok=True) 
    with app.app_context():
        db_session = init_db(app)
    
    # Initialize Flask-Session BEFORE registering routes and OAuth
    Session(app)
    
    # OAuth configuration - AFTER Session init
    oauth = OAuth(app)
    oauth.register(
        name='oauth_provider',
        client_id=globals.OIDC_CLIENT_ID,
        client_secret=globals.OIDC_CLIENT_SECRET,
        authorize_url=globals.OIDC_AUTHORIZE_URL,
        access_token_url=globals.OIDC_ACCESS_TOKEN_URL,
        userinfo_endpoint=globals.OIDC_USER_ENDPOINT,
        jwks_uri=globals.OIDC_JWK_URL,
        client_kwargs={'scope': 'openid profile uuid email groups', 'response_type': 'code'},
        redirect_uri=globals.OIDC_REDIRECT_URL,
        token_endpoint_auth_method='client_secret_post',
    )

    from authlib.integrations.flask_client import token_update

    @token_update.connect_via(app)
    def on_token_update(sender, name, token, refresh_token=None, access_token=None):
        # Session aktualisieren
        if access_token:
            session['access_token'] = access_token
        if refresh_token:
            session['refresh_token'] = refresh_token
        if 'expires_at' in token:
            session['expires_at'] = token['expires_at']
        session.modified = True
        print(f"[Token Update Signal] Token für {name} wurde aktualisiert")

    socketio.init_app(app, cors_allowed_origins="*")

    # Load modules as blueprints
    print("Server: Start Module loading...")
    modules_list = []
    from routes.login import init_routes as login_routes

    app.register_blueprint(login_routes(oauth, db_session))

    from modules.dashboard.dashboard import Module as DashboardModule
    module = DashboardModule(app, db_session, oauth)
    modules_list.append(module)
    app.register_blueprint(module.blueprint)

    from modules.csvgenerator.csvgenerator import Module as CSVGeneratorModule
    module = CSVGeneratorModule(oauth)
    modules_list.append(module)
    app.register_blueprint(module.blueprint)

    from modules.teachertools.teachertools import Module as TeacherToolModule
    module = TeacherToolModule(app, db_session, oauth)
    modules_list.append(module)
    app.register_blueprint(module.blueprint)

    from modules.unify.unify import Module as UnifyModule
    module = UnifyModule(app, db_session, oauth)
    modules_list.append(module)
    app.register_blueprint(module.blueprint)

    from modules.approvals.approvals import Module as ApprovalModule
    module = ApprovalModule(app, db_session, oauth)
    modules_list.append(module)
    app.register_blueprint(module.blueprint)

    from modules.surveys.surveys import Module as SurveyModule
    module = SurveyModule(app, db_session, oauth)
    modules_list.append(module)
    app.register_blueprint(module.blueprint)

    from modules.assistant.assistant import Module as AssistantModule
    module = AssistantModule(app, db_session, oauth)
    modules_list.append(module)
    app.register_blueprint(module.blueprint)

    print("Server: Module loading finished!")

    # Register permission management routes
    from routes.permission_routes import init_permission_routes
    app.register_blueprint(init_permission_routes(oauth))

    with app.app_context():
        db_create_all()

    # ── Auto-migrate SQLite → PostgreSQL if applicable ──────────────
    if database_url.startswith('postgresql'):
        sqlite_path = os.path.join(os.path.dirname(__file__), 'db', 'main.db')
        if os.path.exists(sqlite_path):
            print("Server: Detected SQLite main.db while running on PostgreSQL — starting auto-migration...")
            try:
                from migrate_sqlite_to_postgres import migrate as sqlite_to_pg
                success = sqlite_to_pg(sqlite_path, database_url, force=False, app=app)
                if success:
                    # Rename for backup
                    from datetime import datetime
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_path = f"{sqlite_path}.migrated.{ts}"
                    os.rename(sqlite_path, backup_path)
                    print(f"Server: SQLite migration complete — backup at {backup_path}")
                else:
                    print("Server: SQLite migration returned failure — main.db kept as-is")
            except Exception as e:
                print(f"Server: SQLite auto-migration failed: {e}")
                print("Server: main.db kept as-is — you can retry or migrate manually")

    # ── Run SQL migrations from backend/migrations/ ─────────────────
    from src.migrations import run_migrations
    run_migrations(app)

    # Sync module permissions to database
    with app.app_context():
        from src.permissions import sync_all_module_permissions, register_module_permissions
        sync_all_module_permissions(modules_list)
        # Register permissions for the permissions management module itself
        register_module_permissions("permissions", {
            "permissions.manage": "Manage permission profiles and user/group assignments",
            "permissions.view_users": "View user permission details",
        })

    # API Routes
    @app.route('/api/modules')
    @login_required(oauth)
    def get_modules():
        """Get list of available modules for current user"""
        from src.permissions import user_has_permission, is_super_admin
        modules = []
        for elem in modules_list:
            # Check if user can access this module:
            # Super admin sees everything
            module_perms = getattr(elem, 'MODULE_PERMISSIONS', {})
            has_any_perm = is_super_admin() or any(
                user_has_permission(p) for p in module_perms
            )
            # Fallback to legacy role check for backward compatibility
            if has_any_perm:
                module_data = {
                    "name": elem.MODULE_NAME,
                    "label": elem.MODULE_MENU_NAME,
                    "icon": elem.MODULE_ICON
                }
                # Add submenu configuration if available
                if hasattr(elem, 'MODULE_SUBMENU_API'):
                    module_data['submenu_api'] = elem.MODULE_SUBMENU_API
                if hasattr(elem, 'MODULE_SUBMENU_TYPE'):
                    module_data['submenu_type'] = elem.MODULE_SUBMENU_TYPE
                modules.append(module_data)
        # Add permissions management for authorized users
        if is_super_admin() or user_has_permission("permissions.manage"):
            modules.append({
                "name": "permissions",
                "label": "Berechtigungen",
                "icon": "M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 2.18l7 3.12v4.7c0 4.83-3.23 9.36-7 10.57-3.77-1.21-7-5.74-7-10.57V6.3l7-3.12zM11 7v2h2V7h-2zm0 4v6h2v-6h-2z"
            })

        return jsonify({"modules": modules})

    @app.route('/api/applications')
    @login_required(oauth)
    def get_applications():
        """Get list of applications from database (flat list for Dashboard)."""
        from modules.dashboard.src.db_functions import get_all_applications_flat
        applications = get_all_applications_flat()
        return jsonify({"applications": applications})

    @app.route('/api/user')
    @login_required(oauth)
    def get_user():
        """Get current user information"""
        from src.permissions import get_user_permissions, is_super_admin
        from src.db_models import Permission
        
        if is_super_admin():
            all_perms = Permission.query.all()
            permissions = [p.id for p in all_perms]
        else:
            permissions = list(get_user_permissions())
        
        return jsonify({
            "username": session.get('username', 'Benutzer'),
            "preferred_username": session.get('preferred_username', ''),
            "user_uuid": session.get('user_uuid', ''),
            "permissions": permissions,
            "is_super_admin": is_super_admin()
        })

    @app.route('/api/health')
    def health():
        """Health check endpoint"""
        return jsonify({"status": "ok"})
    
    @app.route('/not-allowed')
    def not_allowed():
        """Redirect to frontend not-allowed page"""
        frontend_url = f"/not-allowed"
        return redirect(frontend_url)

    # WebSocket handlers
    @socketio.on('load_module', namespace="/main")
    def handle_task_message(data):
        module = data['module']
        emit('module_message', {'module': module}, room=request.sid)

    @socketio.on('connect', namespace="/main")
    def handle_task_connect():
        client_id = request.sid
        join_room(client_id)
        print(f"Server: Client verbunden: {client_id}, Socket-ID: {request.sid}")
        emit('connected', {'client_id': client_id}, room=client_id)

    @socketio.on('disconnect', namespace="/main")
    def handle_task_disconnect():
        print(f"Server: Client {request.sid} getrennt.")
        
    return app, oauth

app, oauth = create_app()
if __name__ == "__main__":
    # use_reloader=False is REQUIRED with gevent.
    # Werkzeug's reloader spawns a subprocess and installs a SIGTERM handler
    # (signal.signal(SIGTERM, lambda: sys.exit(0))).  Gevent intercepts that
    # signal inside the event loop and raises SystemExit, which immediately
    # kills the server before it ever binds the port.  Auto-reload is not
    # useful in production anyway; restart the process manually when needed.
    socketio.run(
        app,
        host=globals.BACKEND_HOST,
        port=globals.BACKEND_PORT,
        debug=globals.DEBUG,
        use_reloader=False,
    )
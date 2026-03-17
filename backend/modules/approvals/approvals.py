from flask import Blueprint, session, request, jsonify, redirect, url_for
from flask_socketio import  join_room, leave_room, emit
from src import socketio, globals
from src.db import register_user_extension, register_group_extension
from src.db_models import User, Group
from src.decorators import login_required, permission_required
from src.permissions import user_has_permission
from modules.approvals.src.db_functions import delete_application_and_approvals, update_application, add_new_approval, create_application, get_approvels_for_user, get_approvels_for_app, delete_approval_from_db, get_approval_given_user, has_active_approval
from modules.approvals.src.db_models import extend_user, extend_group, Applications
import os
from datetime import datetime, timezone

class Module():
    ### CHANGE only this (start)

    #MODULE_NAME must be the same as the folder name in /modules/MODULE_NAME/
    MODULE_NAME = "approvals"

    # showed in main menu
    MODULE_MENU_NAME = "Freigaben"
    MODULE_URL = f"/{MODULE_NAME}"
    MODULE_STATIC_URL = f"{MODULE_URL}/static"
    MODULE_WITH_TASK = True
    MODULE_ICON= "M12 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Zm-6.5 16a6.5 6.5 0 0 1 13 0v1.5a.5.5 0 0 1-.5.5h-12a.5.5 0 0 1-.5-.5V18Zm13.9-6a1.6 1.6 0 0 1 1.6 1.6v.4h.5a.5.5 0 0 1 .5.5v4a.5.5 0 0 1-.5.5h-4a.5.5 0 0 1-.5-.5v-4a.5.5 0 0 1 .5-.5h.5v-.4a1.6 1.6 0 0 1 1.6-1.6Zm0 1a.6.6 0 0 0-.6.6v.4h1.2v-.4a.6.6 0 0 0-.6-.6Z"

    # ── Granular Permissions ────────────────────────────────────────
    MODULE_PERMISSIONS = {
        "approvals.view": "View and submit approvals",
        "approvals.manage": "Create, edit, and delete applications and manage all approvals",
        "approvals.always_access": "Always have access to all approvals",
    }

    # Submenu configuration - API endpoint that returns submenu items
    MODULE_SUBMENU_API = f"/api{MODULE_URL}/applications"
    MODULE_SUBMENU_TYPE = "dynamic"


    def __init__(self, app, db_session, oauth):
        self.app = app
        self.oauth = oauth
        self.db_session = db_session
        self.blueprint = Blueprint(self.MODULE_NAME, __name__, 
            static_folder="static",
            static_url_path=self.MODULE_STATIC_URL
        )
        self.clients = {}
        self.register_db()
        self.register_routes()
        self.register_socketio_events()

    def register_db(self):
        register_group_extension(extend_group)
        register_user_extension(extend_user)

    def register_routes(self):
        # API endpoint for submenu (applications list)
        @self.blueprint.route(f"/api{self.MODULE_URL}/applications", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("approvals.view")
        def get_applications():
            apps = Applications.query.all()
            return jsonify([
                {
                    "id": app.id,
                    "name": app.name,
                    "type": "link",
                    "path": f"/approvals/{app.id}"
                } for app in apps
            ])
        
        # Get user's approvals
        @self.blueprint.route(f"/api{self.MODULE_URL}/my-approvals", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("approvals.view")
        def get_my_approvals():
            approvals = get_approvels_for_user(session["user_uuid"])
            return jsonify({"approvals": approvals})
        
        # Get approval overview for admin (counts per application)
        @self.blueprint.route(f"/api{self.MODULE_URL}/overview", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("approvals.manage")
        def get_approvals_overview():
            from modules.approvals.src.db_models import Approval
            now = datetime.now(timezone.utc)
            
            apps = Applications.query.all()
            overview = []
            
            for app in apps:
                # Count current approvals (active now)
                current_count = Approval.query.filter(
                    Approval.application_id == app.id,
                    Approval.start <= now,
                    Approval.end >= now
                ).count()
                
                # Count planned approvals (start in the future)
                planned_count = Approval.query.filter(
                    Approval.application_id == app.id,
                    Approval.start > now
                ).count()
                
                overview.append({
                    "id": app.id,
                    "name": app.name,
                    "current_count": current_count,
                    "planned_count": planned_count
                })
            
            return jsonify({"overview": overview})
        
        # Get specific application with its approvals
        @self.blueprint.route(f"/api{self.MODULE_URL}/applications/<int:app_id>", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("approvals.view")
        def get_application(app_id):
            app = Applications.query.get_or_404(app_id)
            approvals = get_approvels_for_app(app_id)
            return jsonify({
                "app": {
                    "id": app.id,
                    "name": app.name,
                    "description": app.description,
                    "url": app.url
                },
                "approvals": approvals
            })

        # Create new approval
        @self.blueprint.route(f"/api{self.MODULE_URL}/approvals", methods=["POST"])
        @login_required(self.oauth)
        @permission_required("approvals.view")
        def new_approval():
            data = request.get_json()
            app_id = data.get("app_id", "").strip()
            user_ids = data.get("user_ids", "")
            group_ids = data.get("group_ids", "")
            start_time = data.get("start_time", "")
            end_time = data.get("end_time", "")

            start_time = start_time.rstrip("Z")
            end_time = end_time.rstrip("Z")

            if not app_id or not start_time or not end_time or (not user_ids and not group_ids):
                return jsonify({'status': False, 'message': 'Pflichtfelder fehlen.'}), 400

            # Timestamps parsen
            try:
                start = datetime.fromisoformat(start_time)
                end = datetime.fromisoformat(end_time)
            except ValueError:
                return jsonify({'status': False, 'message': 'Ungültiges Datumsformat.'}), 400

            if start >= end:
                return jsonify({'status': False, 'message': 'Startzeit muss vor Endzeit liegen.'}), 400

            if (end - start).total_seconds() > int(os.getenv("AP_MAX_TIME_DIFFERENCE", 0))*3600:
                return jsonify({'status': False, 'message': f'Maximale Dauer ist {int(os.getenv("AP_MAX_TIME_DIFFERENCE", 0))/60} Stunden.'}), 400

            return jsonify(add_new_approval(app_id, user_ids, group_ids, start, end, session['user_uuid']))

        # Get all approvals for an application (including inactive)
        @self.blueprint.route(f"/api{self.MODULE_URL}/applications/<int:app_id>/all-approvals", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("approvals.manage")
        def get_all_app_approvals(app_id):
            app = Applications.query.get_or_404(app_id)
            approvals = get_approvels_for_app(app_id, only_active=False)
            return jsonify({"name": app.name, "approvals": approvals})

        # Delete application
        @self.blueprint.route(f"/api{self.MODULE_URL}/applications/<int:app_id>", methods=["DELETE"])
        @login_required(self.oauth)
        @permission_required("approvals.manage")
        def delete_app(app_id):
            result = delete_application_and_approvals(app_id)
            socketio.emit('load_menu', namespace='/main')
            return jsonify(result)

        # Delete approval
        @self.blueprint.route(f"/api{self.MODULE_URL}/approvals/<int:approval_id>", methods=["DELETE"])
        @login_required(self.oauth)
        @permission_required("approvals.view")
        def delete_approval(approval_id):
            user = get_approval_given_user(approval_id)
            if not user:
                return jsonify({'status': False, 'message': "Keine Benutzer gefunden, dem die Freigabe gehört"}), 404
            if user.uuid != session["user_uuid"] and not user_has_permission("approvals.manage"):
                return jsonify({'status': False, 'message': "Keine Berechtigung zum Löschen!"}), 403
            return jsonify(delete_approval_from_db(approval_id))

        # Update application
        @self.blueprint.route(f"/api{self.MODULE_URL}/applications/<int:app_id>", methods=["PUT"])
        @login_required(self.oauth)
        @permission_required("approvals.manage")
        def update_app(app_id):
            data = request.get_json()
            new_name = data.get("new_name", "").strip()
            new_description = data.get("new_description", "").strip()
            new_url = data.get("new_url", "").strip()

            if not new_name or not new_url:
                return jsonify({'status': False, 'message': "Name oder URL fehlt, bzw. muss aber gesetzt sein."}), 400

            result = update_application(app_id, new_name, new_description, new_url)
            socketio.emit('load_menu', namespace='/main')
            return jsonify(result)
        
        @self.blueprint.route(f"/api{self.MODULE_URL}/check")
        #@login_required(self.oauth)
        def check():
            if 'session_id' not in session:
                return redirect(url_for('not_allowed'))
            url = request.headers.get("X-Forwarded-Host").split(",")[0]
            if (has_active_approval(session["user_uuid"], url)):
                return "", 200
            return redirect(url_for('not_allowed'))
        
    def register_socketio_events(self):

        @socketio.on('new_application', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("approvals.manage")
        def handle_new_application(data):
            sid = request.sid
            name = data.get('name', '')
            description = data.get('description', '')
            url = data.get('url', '')

            print(f"[Approvals] Received new_application request: name={name}, url={url}")

            if not name or not url:
                error_msg = 'Kein Name oder URL übergeben. Keine neue Anwendung erstellt.'
                print(f"[Approvals] Error: {error_msg}")
                socketio.emit('new_application_error', error_msg, namespace=self.MODULE_URL, room=sid)
                return
            
            try:
                app = create_application(name, description, url)
                print(f"[Approvals] Application created successfully: {app.id} - {app.name}")
                # Trigger menu reload for all clients
                socketio.emit('load_menu', namespace='/main')
                socketio.emit('new_application_success', f'Die Anwendung {name} wurde erfolgreich erstellt.', namespace=self.MODULE_URL, room=sid)
            except Exception as e:
                print(f"[Approvals] Error creating application: {e}")
                socketio.emit('new_application_error', f'Fehler bei der Erstellung der Anwendung {name}: {str(e)}', namespace=self.MODULE_URL, room=sid)        
        
        # Wir benoetigt, damit beim senden von Daten auch immer nur der richtige Client angesprochen wird.
        @socketio.on('connect', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("approvals.manage")
        def handle_connect():
            # Beim Verbinden wird die session ID gespeichert
            self.clients[request.sid] = {"username": session.get('username', 'Unbekannt')}
            join_room(request.sid)

        @socketio.on('disconnect', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        def handle_disconnect():
            # Client-ID beim Trennen entfernen
            leave_room(request.sid)
            if request.sid in self.clients:
                del self.clients[request.sid]

        # SocketIO-Event zum Empfang der Frage und Rückgabe der Antwort
        @socketio.on('load_menu', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("approvals.view")
        def handle_message(data):
            socketio.emit('load_menu', namespace=self.MODULE_URL, room=request.sid)

        @socketio.on('request_approval_infos', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("approvals.view")
        def handle_request_data():
            users = User.query.all()
            groups = Group.query.all()

            user_data = [{"id": u.id, "name": u.username} for u in users]
            group_data = [{"id": g.id, "name": g.name} for g in groups]

            socketio.emit("approval_infos", 
                {
                "users": user_data,
                "groups": group_data,
                "maxTimeDifference": os.getenv("AP_MAX_TIME_DIFFERENCE", 0)
                },
                namespace=self.MODULE_URL,
                room=request.sid)
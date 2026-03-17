"""
Survey Module — Main Module Class

Orchestrates survey types via a registry pattern. Each survey type
(normal, special, …) registers its own routes, permissions, and
management checks. Adding a new survey type requires only:

  1. Create a subfolder (e.g. surveys/newtype/)
  2. Implement routes + DB logic
  3. Register the type in _register_survey_types()
  4. Add its permission to MODULE_PERMISSIONS

No switch-case, no modifications to core logic.
"""
from flask import Blueprint, session, request, jsonify
from flask_socketio import emit, join_room
from src import socketio, globals
from src.db_models import User, Group
from src.decorators import login_required, permission_required
from src.permissions import user_has_permission
from src.db import db

from modules.surveys.common.db_models import Survey, SurveyResponse
from modules.surveys.common.db_functions import _utcnow_naive
from modules.surveys.special.db_models import SpecialSurvey
from modules.surveys.special.db_functions import (
    migrate_class_teacher_constraint,
    migrate_template_type_and_excel_config,
)
from modules.surveys.survey_registry import (
    register_survey_type, get_all_survey_types, can_manage_any_type,
)

# Import route registration functions
from modules.surveys.normal.routes import register_normal_routes, _can_manage_normal
from modules.surveys.special.routes import register_special_routes, _can_manage_special
from src.utils import utc_isoformat


class Module():
    # ── Module Metadata ──────────────────────────────────────────────

    MODULE_NAME = "surveys"
    MODULE_MENU_NAME = "Umfragen"
    MODULE_URL = f"/{MODULE_NAME}"
    MODULE_STATIC_URL = f"{MODULE_URL}/static"
    MODULE_WITH_TASK = True

    MODULE_ICON = (
        "M9 2a1 1 0 0 0-1 1H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 "
        "2-2V5a2 2 0 0 0-2-2h-3a1 1 0 0 0-1-1H9Zm0 2h6v1H9V4Zm-2 5h10v1H7V9Z"
        "m0 3h10v1H7v-1Zm0 3h7v1H7v-1Z"
    )

    # ── Granular Permissions ────────────────────────────────────────
    # New cleaner naming: surveys.<type>.manage
    # Old names kept for backward compatibility
    MODULE_PERMISSIONS = {
        # Global
        "surveys.participate":             "Participate in surveys and view active surveys",
        "surveys.manage.all":              "Create, edit, delete, and manage all survey types (super-permission)",
        "surveys.admin":                   "Admin-only survey operations (recovery, restore, special surveys)",
        "surveys.delete.permanently":      "View trash and permanently delete surveys",

        # Normal survey type
        "surveys.normal.manage":           "Create and manage normal surveys and templates",

        # Special survey type
        "surveys.special.manage":          "Create and manage special surveys (class composition)",
    }

    # ── Constructor ──────────────────────────────────────────────────

    def __init__(self, app, db_session, oauth):
        self.app = app
        self.oauth = oauth
        self.db_session = db_session
        self.blueprint = Blueprint(
            self.MODULE_NAME, __name__,
            static_folder="static",
            static_url_path=self.MODULE_STATIC_URL,
        )

        # Register survey types via the registry
        self._register_survey_types()

        # Register shared (cross-type) routes
        self.register_routes()

        # Register type-specific routes via the registry
        register_normal_routes(self.blueprint, self.MODULE_URL, self.oauth, socketio)
        register_special_routes(self.blueprint, self.MODULE_URL, self.oauth, socketio)

        self.register_socketio_events()

        # Run schema migrations if needed
        with app.app_context():
            migrate_class_teacher_constraint()
            migrate_template_type_and_excel_config()

    # ── Survey Type Registry ─────────────────────────────────────────

    def _register_survey_types(self):
        """
        Register all known survey types. To add a new type:
          1. Create surveys/newtype/ with routes.py, db_functions.py, etc.
          2. Add a register_survey_type() call here.
          3. Add the type's permission to MODULE_PERMISSIONS.
        """
        register_survey_type('normal', {
            'label': 'Normale Umfrage',
            'permission': 'surveys.normal.manage',
            'can_manage': _can_manage_normal,
            'order': 1,
        })

        register_survey_type('special', {
            'label': 'Spezialumfrage',
            'permission': 'surveys.special.manage',
            'can_manage': _can_manage_special,
            'order': 2,
        })

    # ── Shared Routes (cross-type) ───────────────────────────────────

    def register_routes(self):

        # ── Submenu endpoint (kept for backward compat) ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/list-menu", methods=["GET"])
        @login_required(self.oauth)
        def survey_list_menu():
            """Submenu removed — returns empty list."""
            return jsonify([])

        # ── Landing page data: permissions + registered survey types ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/permissions-info", methods=["GET"])
        @login_required(self.oauth)
        def survey_permissions_info():
            """Return the current user's survey-related permission flags and registered types."""
            types_info = []
            for t in get_all_survey_types():
                can_manage_fn = t.get('can_manage', lambda: False)
                types_info.append({
                    'key': t['key'],
                    'label': t['label'],
                    'can_manage': can_manage_fn(),
                })

            return jsonify({
                "can_manage": can_manage_any_type(),
                "can_manage_normal": _can_manage_normal(),
                "can_manage_special": _can_manage_special(),
                "can_delete_permanently": user_has_permission("surveys.delete.permanently"),
                "is_admin": user_has_permission("surveys.admin"),
                "survey_types": types_info,
            })

        # ── Groups helper ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/groups", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("surveys.manage.all", "surveys.normal.manage", "surveys.special.manage")
        def list_groups():
            """Return all available groups for survey assignment."""
            groups = Group.query.order_by(Group.name).all()
            return jsonify({
                "groups": [{"id": g.id, "name": g.name} for g in groups]
            })

        # ── Users helper (for sharing) ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/users", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("surveys.manage.all", "surveys.normal.manage", "surveys.special.manage")
        def list_users_for_sharing():
            """Return management-role users for template sharing."""
            users = User.query.order_by(User.username).all()
            return jsonify({
                "users": [{"uuid": u.uuid, "username": u.username} for u in users
                          if u.uuid != session['user_uuid']]
            })

        # ── Active surveys for current user (participation list) ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/active", methods=["GET"])
        @login_required(self.oauth)
        def get_active_surveys():
            """Get active normal surveys the current user can participate in."""
            user = User.query.filter_by(uuid=session['user_uuid']).first()
            if not user:
                return jsonify({"surveys": []})

            user_group_ids = {g.id for g in user.groups}
            now = _utcnow_naive()

            active_surveys = Survey.query.filter(
                Survey.status == 'active',
                Survey.is_template == False,
                Survey.is_deleted == False,
            ).all()

            available = []
            for survey in active_surveys:
                survey_group_ids = {g.id for g in survey.groups}
                if not survey_group_ids or survey_group_ids & user_group_ids:
                    existing_response = SurveyResponse.query.filter_by(
                        survey_id=survey.id, user_uuid=session['user_uuid']
                    ).first()
                    already_responded = existing_response is not None
                    edit_granted = existing_response.edit_granted if existing_response else False

                    is_expired = False
                    not_yet_started = False
                    if survey.ends_at and survey.ends_at <= now:
                        is_expired = True
                    if survey.starts_at and survey.starts_at > now:
                        not_yet_started = True

                    available.append({
                        'id': survey.id,
                        'title': survey.title,
                        'description': survey.description,
                        'already_responded': already_responded,
                        'allow_edit_response': survey.allow_edit_response,
                        'edit_granted': edit_granted,
                        'creator_uuid': survey.creator_uuid,
                        'starts_at': utc_isoformat(survey.starts_at),
                        'ends_at': utc_isoformat(survey.ends_at),
                        'is_expired': is_expired,
                        'not_yet_started': not_yet_started,
                    })

            return jsonify({"surveys": available})

        # ── Admin overview ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/overview", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("surveys.admin")
        def get_surveys_overview():
            """Admin overview: total surveys, active count, response stats."""
            now = _utcnow_naive()
            total = Survey.query.filter(Survey.is_deleted == False).count()
            active = Survey.query.filter(
                Survey.status == 'active',
                Survey.is_deleted == False,
                db.or_(Survey.starts_at.is_(None), Survey.starts_at <= now),
                db.or_(Survey.ends_at.is_(None), Survey.ends_at > now),
            ).count()
            draft = Survey.query.filter_by(status='draft').filter(Survey.is_deleted == False).count()
            closed = Survey.query.filter_by(status='closed').filter(Survey.is_deleted == False).count()
            total_responses = SurveyResponse.query.count()
            return jsonify({
                'total': total,
                'active': active,
                'draft': draft,
                'closed': closed,
                'total_responses': total_responses,
            })

        # ── Admin: Deleted surveys recovery ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/admin/deleted", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("surveys.admin", "surveys.delete.permanently")
        def list_deleted_survey_users():
            """List users who have soft-deleted surveys (normal + special)."""
            normal_rows = db.session.query(
                Survey.creator_uuid
            ).filter(Survey.is_deleted == True).distinct().all()
            special_rows = db.session.query(
                SpecialSurvey.creator_uuid
            ).filter(SpecialSurvey.is_deleted == True).distinct().all()

            user_uuids = list({r[0] for r in normal_rows} | {r[0] for r in special_rows})
            users = User.query.filter(User.uuid.in_(user_uuids)).order_by(User.username).all()

            result = []
            for u in users:
                normal_count = Survey.query.filter(
                    Survey.creator_uuid == u.uuid, Survey.is_deleted == True
                ).count()
                special_count = SpecialSurvey.query.filter(
                    SpecialSurvey.creator_uuid == u.uuid, SpecialSurvey.is_deleted == True
                ).count()
                result.append({
                    'uuid': u.uuid,
                    'username': u.username,
                    'deleted_count': normal_count + special_count,
                })

            return jsonify({'users': result})

        @self.blueprint.route(f"/api{self.MODULE_URL}/admin/deleted/<user_uuid>", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("surveys.admin", "surveys.delete.permanently")
        def list_deleted_surveys_for_user(user_uuid):
            """List all soft-deleted surveys for a specific user."""
            normal = Survey.query.filter(
                Survey.creator_uuid == user_uuid, Survey.is_deleted == True
            ).order_by(Survey.deleted_at.desc()).all()
            special = SpecialSurvey.query.filter(
                SpecialSurvey.creator_uuid == user_uuid, SpecialSurvey.is_deleted == True
            ).order_by(SpecialSurvey.deleted_at.desc()).all()

            surveys = []
            for s in normal:
                d = s.to_dict()
                d['survey_type'] = 'template' if s.is_template else 'normal'
                surveys.append(d)
            for s in special:
                d = s.to_dict()
                d['survey_type'] = 'special'
                surveys.append(d)

            surveys.sort(key=lambda x: x.get('deleted_at') or '', reverse=True)
            return jsonify({'surveys': surveys})

        @self.blueprint.route(f"/api{self.MODULE_URL}/admin/deleted/<int:survey_id>/restore", methods=["POST"])
        @login_required(self.oauth)
        @permission_required("surveys.admin", "surveys.delete.permanently")
        def restore_deleted_survey(survey_id):
            """Restore a soft-deleted normal survey or template."""
            survey_type = request.args.get('type', 'normal')
            try:
                if survey_type == 'special':
                    ss = SpecialSurvey.query.get(survey_id)
                    if not ss or not ss.is_deleted:
                        return jsonify({'status': False, 'message': 'Gelöschte Umfrage nicht gefunden.'}), 404
                    ss.is_deleted = False
                    ss.deleted_at = None
                    ss.deleted_by = None
                else:
                    survey = Survey.query.get(survey_id)
                    if not survey or not survey.is_deleted:
                        return jsonify({'status': False, 'message': 'Gelöschte Umfrage nicht gefunden.'}), 404
                    survey.is_deleted = False
                    survey.deleted_at = None
                    survey.deleted_by = None

                db.session.commit()
                return jsonify({'status': True, 'message': 'Umfrage wiederhergestellt.'})
            except Exception as e:
                db.session.rollback()
                print(f'[Surveys] Error restoring survey: {e}')
                return jsonify({'status': False, 'message': 'Ein Fehler ist aufgetreten.'}), 500

        @self.blueprint.route(f"/api{self.MODULE_URL}/admin/deleted/<int:survey_id>/permanent", methods=["DELETE"])
        @login_required(self.oauth)
        @permission_required("surveys.admin", "surveys.delete.permanently")
        def permanently_delete_survey(survey_id):
            """Permanently delete a soft-deleted survey and all its data."""
            survey_type = request.args.get('type', 'normal')
            try:
                if survey_type == 'special':
                    ss = SpecialSurvey.query.get(survey_id)
                    if not ss or not ss.is_deleted:
                        return jsonify({'status': False, 'message': 'Gelöschte Umfrage nicht gefunden.'}), 404
                    db.session.delete(ss)
                else:
                    survey = Survey.query.get(survey_id)
                    if not survey or not survey.is_deleted:
                        return jsonify({'status': False, 'message': 'Gelöschte Umfrage nicht gefunden.'}), 404
                    db.session.delete(survey)

                db.session.commit()
                return jsonify({'status': True, 'message': 'Umfrage endgültig gelöscht.'})
            except Exception as e:
                db.session.rollback()
                print(f'[Surveys] Error permanently deleting survey: {e}')
                return jsonify({'status': False, 'message': 'Ein Fehler ist aufgetreten.'}), 500

        # ── Trash: list own soft-deleted surveys (for Trash tab) ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/trash", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("surveys.delete.permanently", "surveys.admin")
        def list_own_trash():
            """List the current user's soft-deleted surveys (normal + special)."""
            user_uuid = session['user_uuid']
            normal = Survey.query.filter(
                Survey.creator_uuid == user_uuid,
                Survey.is_deleted == True,
            ).order_by(Survey.deleted_at.desc()).all()
            special = SpecialSurvey.query.filter(
                SpecialSurvey.creator_uuid == user_uuid,
                SpecialSurvey.is_deleted == True,
            ).order_by(SpecialSurvey.deleted_at.desc()).all()

            surveys = []
            for s in normal:
                d = s.to_dict()
                d['survey_type'] = 'template' if s.is_template else 'normal'
                surveys.append(d)
            for s in special:
                d = s.to_dict()
                d['survey_type'] = 'special'
                surveys.append(d)

            surveys.sort(key=lambda x: x.get('deleted_at') or '', reverse=True)
            return jsonify({'surveys': surveys})

        # ── Registered survey types info (for frontend extensibility) ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/types", methods=["GET"])
        @login_required(self.oauth)
        def list_survey_types():
            """Return all registered survey types and the user's management capability."""
            types_info = []
            for t in get_all_survey_types():
                can_manage_fn = t.get('can_manage', lambda: False)
                types_info.append({
                    'key': t['key'],
                    'label': t['label'],
                    'can_manage': can_manage_fn(),
                })
            return jsonify({'types': types_info})

    # ── SocketIO Events ──────────────────────────────────────────────

    def register_socketio_events(self):
        @socketio.on('connect', namespace='/surveys')
        def handle_connect():
            client_id = request.sid
            join_room(client_id)
            print(f"Surveys: Client connected: {client_id}")
            emit('connected', {'client_id': client_id}, room=client_id)

        @socketio.on('disconnect', namespace='/surveys')
        def handle_disconnect():
            print(f"Surveys: Client disconnected: {request.sid}")

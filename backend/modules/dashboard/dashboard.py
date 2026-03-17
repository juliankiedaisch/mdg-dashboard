from flask import Blueprint, session, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import uuid
from src import socketio, globals
from src.decorators import login_required, permission_required, permission_required
from modules.dashboard.src import db_models  # ensure models are registered
from modules.dashboard.src.db_functions import (
    # Pages
    get_all_pages, get_page_full, create_page, update_page, delete_page,
    # Topics
    get_all_topics, get_topic_full, create_topic, update_topic, delete_topic,
    # Applications
    get_all_applications, get_application, create_application,
    update_application, delete_application,
    # Bulk
    bulk_reassign_applications, bulk_move_topics,
    # Reorder
    reorder_pages, reorder_topics, reorder_applications,
    # Flat list for Dashboard frontend
    get_all_applications_flat,
)


class Module():
    # ── Module metadata ─────────────────────────────────────────────

    MODULE_NAME = "dashboard"
    MODULE_MENU_NAME = "Dashboard"
    MODULE_URL = f"/{MODULE_NAME}"
    MODULE_STATIC_URL = f"{MODULE_URL}/static"
    MODULE_WITH_TASK = False
    MODULE_ICON = (
        "M4 4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2H4Z"
        "M4 14a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2H4Z"
        "M14 4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-4Z"
        "M14 14a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2h-4Z"
    )

    # ── Granular Permissions ────────────────────────────────────────
    MODULE_PERMISSIONS = {
        "dashboard.view": "View dashboard pages and applications",
        "dashboard.manage": "Create, edit, delete pages, topics and applications",
    }

    # ── Constructor ─────────────────────────────────────────────────

    def __init__(self, app, db_session, oauth):
        self.app = app
        self.oauth = oauth
        self.db_session = db_session
        self.blueprint = Blueprint(
            self.MODULE_NAME, __name__,
            static_folder="static",
            static_url_path=self.MODULE_STATIC_URL,
        )
        self.register_routes()

    # ── Routes ──────────────────────────────────────────────────────

    def register_routes(self):
        bp = self.blueprint
        url = self.MODULE_URL
        oauth = self.oauth

        # ────────────────── Pages ──────────────────

        @bp.route(f"/api{url}/pages", methods=["GET"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def list_pages():
            pages = get_all_pages()
            return jsonify({"pages": pages})

        @bp.route(f"/api{url}/pages/<int:page_id>", methods=["GET"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def get_page_detail(page_id):
            page = get_page_full(page_id)
            if not page:
                return jsonify({"error": "Page not found."}), 404
            return jsonify({"page": page})

        @bp.route(f"/api{url}/pages", methods=["POST"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def add_page():
            data = request.get_json(silent=True) or {}
            result, err = create_page(
                name=data.get("name", ""),
                description=data.get("description", ""),
            )
            if err:
                return jsonify({"status": False, "message": err}), 400
            return jsonify({"status": True, "page": result}), 201

        @bp.route(f"/api{url}/pages/<int:page_id>", methods=["PUT"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def edit_page(page_id):
            data = request.get_json(silent=True) or {}
            result, err = update_page(
                page_id,
                name=data.get("name"),
                description=data.get("description"),
            )
            if err:
                return jsonify({"status": False, "message": err}), 400
            return jsonify({"status": True, "page": result})

        @bp.route(f"/api{url}/pages/<int:page_id>", methods=["DELETE"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def remove_page(page_id):
            hard = request.args.get("hard", "false").lower() == "true"
            result, err = delete_page(page_id, hard=hard)
            if err:
                return jsonify({"status": False, "message": err}), 404
            return jsonify(result)

        # ────────────────── Topics ──────────────────

        @bp.route(f"/api{url}/topics", methods=["GET"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def list_topics():
            page_id = request.args.get("page_id", type=int)
            topics = get_all_topics(page_id=page_id)
            return jsonify({"topics": topics})

        @bp.route(f"/api{url}/topics/<int:topic_id>", methods=["GET"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def get_topic_detail(topic_id):
            topic = get_topic_full(topic_id)
            if not topic:
                return jsonify({"error": "Topic not found."}), 404
            return jsonify({"topic": topic})

        @bp.route(f"/api{url}/topics", methods=["POST"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def add_topic():
            data = request.get_json(silent=True) or {}
            page_id = data.get("page_id")
            if page_id is None:
                return jsonify({"status": False, "message": "page_id is required."}), 400
            result, err = create_topic(
                name=data.get("name", ""),
                page_id=page_id,
                description=data.get("description", ""),
            )
            if err:
                return jsonify({"status": False, "message": err}), 400
            return jsonify({"status": True, "topic": result}), 201

        @bp.route(f"/api{url}/topics/<int:topic_id>", methods=["PUT"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def edit_topic(topic_id):
            data = request.get_json(silent=True) or {}
            result, err = update_topic(
                topic_id,
                name=data.get("name"),
                description=data.get("description"),
                page_id=data.get("page_id"),
            )
            if err:
                return jsonify({"status": False, "message": err}), 400
            return jsonify({"status": True, "topic": result})

        @bp.route(f"/api{url}/topics/<int:topic_id>", methods=["DELETE"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def remove_topic(topic_id):
            hard = request.args.get("hard", "false").lower() == "true"
            result, err = delete_topic(topic_id, hard=hard)
            if err:
                return jsonify({"status": False, "message": err}), 404
            return jsonify(result)

        # ────────────────── Applications ──────────────────

        @bp.route(f"/api{url}/applications", methods=["GET"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def list_applications():
            topic_id = request.args.get("topic_id", type=int)
            page_id = request.args.get("page_id", type=int)
            search = request.args.get("search", type=str)
            apps = get_all_applications(
                topic_id=topic_id, page_id=page_id, search=search,
            )
            return jsonify({"applications": apps})

        @bp.route(f"/api{url}/applications/<int:app_id>", methods=["GET"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def get_application_detail(app_id):
            app = get_application(app_id)
            if not app:
                return jsonify({"error": "Application not found."}), 404
            return jsonify({"application": app})

        @bp.route(f"/api{url}/applications", methods=["POST"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def add_application():
            data = request.get_json(silent=True) or {}
            topic_id = data.get("topic_id")
            if topic_id is None:
                return jsonify({"status": False, "message": "topic_id is required."}), 400
            result, err = create_application(
                name=data.get("name", ""),
                url=data.get("url", ""),
                topic_id=topic_id,
                description=data.get("description", ""),
                icon=data.get("icon", ""),
            )
            if err:
                return jsonify({"status": False, "message": err}), 400
            return jsonify({"status": True, "application": result}), 201

        @bp.route(f"/api{url}/applications/<int:app_id>", methods=["PUT"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def edit_application(app_id):
            data = request.get_json(silent=True) or {}
            result, err = update_application(
                app_id,
                name=data.get("name"),
                description=data.get("description"),
                url=data.get("url"),
                icon=data.get("icon"),
                topic_id=data.get("topic_id"),
            )
            if err:
                return jsonify({"status": False, "message": err}), 400
            return jsonify({"status": True, "application": result})

        @bp.route(f"/api{url}/applications/<int:app_id>", methods=["DELETE"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def remove_application(app_id):
            hard = request.args.get("hard", "false").lower() == "true"
            result, err = delete_application(app_id, hard=hard)
            if err:
                return jsonify({"status": False, "message": err}), 404
            return jsonify(result)

        # ────────────────── Bulk Operations ──────────────────

        @bp.route(f"/api{url}/applications/bulk-reassign", methods=["POST"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def bulk_reassign():
            data = request.get_json(silent=True) or {}
            app_ids = data.get("application_ids", [])
            new_topic_id = data.get("topic_id")
            if not app_ids or new_topic_id is None:
                return jsonify({"status": False, "message": "application_ids and topic_id are required."}), 400
            result, err = bulk_reassign_applications(app_ids, new_topic_id)
            if err:
                return jsonify({"status": False, "message": err}), 400
            return jsonify(result)

        @bp.route(f"/api{url}/topics/bulk-move", methods=["POST"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def bulk_move():
            data = request.get_json(silent=True) or {}
            topic_ids = data.get("topic_ids", [])
            new_page_id = data.get("page_id")
            if not topic_ids or new_page_id is None:
                return jsonify({"status": False, "message": "topic_ids and page_id are required."}), 400
            result, err = bulk_move_topics(topic_ids, new_page_id)
            if err:
                return jsonify({"status": False, "message": err}), 400
            return jsonify(result)

        # ────────────────── Full hierarchy ──────────────────

        @bp.route(f"/api{url}/hierarchy", methods=["GET"])
        @login_required(oauth)
        def get_hierarchy():
            """Return the full page -> topic -> application tree."""
            from modules.dashboard.src.db_models import DashboardPage
            pages = DashboardPage.query.filter_by(is_deleted=False).order_by(DashboardPage.sort_order).all()
            return jsonify({"pages": [p.to_dict_full() for p in pages]})

        # ────────────────── Reorder ──────────────────

        @bp.route(f"/api{url}/pages/reorder", methods=["POST"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def reorder_pages_route():
            data = request.get_json(silent=True) or {}
            ordered_ids = data.get("ordered_ids", [])
            if not ordered_ids:
                return jsonify({"status": False, "message": "ordered_ids is required."}), 400
            result, err = reorder_pages(ordered_ids)
            if err:
                return jsonify({"status": False, "message": err}), 400
            return jsonify(result)

        @bp.route(f"/api{url}/topics/reorder", methods=["POST"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def reorder_topics_route():
            data = request.get_json(silent=True) or {}
            page_id = data.get("page_id")
            ordered_ids = data.get("ordered_ids", [])
            if page_id is None or not ordered_ids:
                return jsonify({"status": False, "message": "page_id and ordered_ids are required."}), 400
            result, err = reorder_topics(page_id, ordered_ids)
            if err:
                return jsonify({"status": False, "message": err}), 400
            return jsonify(result)

        @bp.route(f"/api{url}/applications/reorder", methods=["POST"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def reorder_applications_route():
            data = request.get_json(silent=True) or {}
            topic_id = data.get("topic_id")
            ordered_ids = data.get("ordered_ids", [])
            if topic_id is None or not ordered_ids:
                return jsonify({"status": False, "message": "topic_id and ordered_ids are required."}), 400
            result, err = reorder_applications(topic_id, ordered_ids)
            if err:
                return jsonify({"status": False, "message": err}), 400
            return jsonify(result)

        # ────────────────── Icon Upload ──────────────────

        @bp.route(f"/api{url}/icons", methods=["POST"])
        @login_required(oauth)
        @permission_required("dashboard.manage")
        def upload_icon():
            if "file" not in request.files:
                return jsonify({"status": False, "message": "Keine Datei angegeben."}), 400
            f = request.files["file"]
            if not f or not f.filename:
                return jsonify({"status": False, "message": "Keine Datei ausgewählt."}), 400

            ALLOWED_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"}
            if f.content_type not in ALLOWED_TYPES:
                return jsonify({"status": False, "message": "Ungültiger Dateityp. Nur Bilder sind erlaubt."}), 400

            ext_map = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/gif": ".gif",
                "image/webp": ".webp",
                "image/svg+xml": ".svg",
            }
            ext = ext_map.get(f.content_type, os.path.splitext(secure_filename(f.filename))[1].lower() or ".png")
            filename = uuid.uuid4().hex + ext

            save_dir = os.path.join(current_app.static_folder, "images", "apps")
            os.makedirs(save_dir, exist_ok=True)
            f.save(os.path.join(save_dir, filename))

            icon_url = f"/static/images/apps/{filename}"
            return jsonify({"status": True, "url": icon_url}), 201

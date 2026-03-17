from flask import Blueprint, render_template, session, request, url_for, jsonify
from flask_socketio import emit, join_room, leave_room
from src import socketio, globals
from src.db_models import User, Group
from src.decorators import login_required, permission_required
from src.permissions import user_has_permission
from modules.teachertools.src.db_functions import (
    create_wordcloud, update_wordcloud, update_wordcloud_status,
    delete_wordcloud, submit_word, get_wordcloud_results,
)
from modules.teachertools.src.db_models import WordCloud, WordCloudSubmission
from src.db import db
import os, threading, time, csv
import pandas as pd
from pathlib import Path
from io import StringIO

def delete_file_after_delay(filepath, delay):
    time.sleep(delay)
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"Deleted file: {filepath}")

class Module():
    ### CHANGE only this (start)

    #MODULE_NAME must be the same as the folder name in /modules/MODULE_NAME/
    MODULE_NAME = "teachertools"

    # showed in main menu
    MODULE_MENU_NAME = "Unterrichtstools"
    MODULE_URL = f"/{MODULE_NAME}"
    MODULE_STATIC_URL = f"{MODULE_URL}/static"
    MODULE_WITH_TASK = True
    MODULE_ICON= "M3 6.75A2.75 2.75 0 0 1 5.75 4h12.5A2.75 2.75 0 0 1 21 6.75v10.5A2.75 2.75 0 0 1 18.25 20H5.75A2.75 2.75 0 0 1 3 17.25V6.75ZM12 8a1.75 1.75 0 1 0 0 3.5A1.75 1.75 0 0 0 12 8Zm0 5c-1.93 0-3.5 1.57-3.5 3.5a.5.5 0 0 0 .5.5h6a.5.5 0 0 0 .5-.5c0-1.93-1.57-3.5-3.5-3.5Z"

    # Submenu configuration
    MODULE_SUBMENU_API = f"/api/teachertools/list-menu"
    MODULE_SUBMENU_TYPE = "dynamic"

    # ── Granular Permissions ────────────────────────────────────────
    MODULE_PERMISSIONS = {
        "teachertools.view": "View the teachertools site",
        "teachertools.qr-code": "Access and use teacher tools QR codes",
        "teachertools.wordcloud": "Access and use teacher tools word clouds",
    }

    # all scripts in this list will be loaded by main application. You don't need to load them again
    # all functions / variables should start with MODULE_NAME_ to avoid problems with other modules
    # Example: textgenerator_send_message(), textgenerator_data = ...
    MODULE_JS_SCRIPTS = [f"{MODULE_STATIC_URL}/qr-code.js", f"{MODULE_STATIC_URL}/script.js"]
    MODULE_CSS_STYLES = ["style.css"]

    def __init__(self, app, db_session, oauth):
        self.app = app
        self.db_session = db_session
        self.blueprint = Blueprint(self.MODULE_NAME, __name__, 
            template_folder="templates",
            static_folder="static",
            static_url_path=self.MODULE_STATIC_URL
        )
        self.oauth = oauth
        self.clients = {}
        self._run_migrations()
        self.register_routes()
        self.register_socketio_events()

    def _run_migrations(self):
        """Add new columns to word_cloud / word_cloud_submission if they don't exist.

        Uses SQLAlchemy inspect() so it works with both SQLite and PostgreSQL.
        """
        try:
            with self.app.app_context():
                from sqlalchemy import inspect as sa_inspect, text
                engine = db.engine
                inspector = sa_inspect(engine)
                is_pg = engine.dialect.name == 'postgresql'

                def _bool_default(val: bool) -> str:
                    """Return a DB-appropriate boolean literal."""
                    if is_pg:
                        return 'TRUE' if val else 'FALSE'
                    return '1' if val else '0'

                def _existing_cols(table: str) -> set:
                    return {c['name'] for c in inspector.get_columns(table)}

                # ── word_cloud ───────────────────────────────────────
                existing = _existing_cols('word_cloud')
                migrations = [
                    ('allow_participant_download', f'BOOLEAN DEFAULT {_bool_default(False)}'),
                    ('max_chars_per_answer', 'INTEGER DEFAULT 20'),
                    ('anonymous_answers', f'BOOLEAN DEFAULT {_bool_default(True)}'),
                    ('version', 'INTEGER DEFAULT 0'),
                    ("rotation_mode", "VARCHAR(20) DEFAULT 'mixed'"),
                    ("rotation_angles", "TEXT DEFAULT '[0, 90]'"),
                    ('rotation_probability', 'FLOAT DEFAULT 0.5'),
                ]
                with engine.connect() as conn:
                    for col_name, col_def in migrations:
                        if col_name not in existing:
                            conn.execute(text(f'ALTER TABLE word_cloud ADD COLUMN {col_name} {col_def}'))
                            conn.commit()
                            print(f'[WordCloud] Added column: {col_name}')

                    # ── word_cloud_submission ────────────────────────
                    sub_existing = _existing_cols('word_cloud_submission')
                    sub_migrations = [
                        ('is_anonymous', f'BOOLEAN DEFAULT {_bool_default(False)}'),
                    ]
                    for col_name, col_def in sub_migrations:
                        if col_name not in sub_existing:
                            conn.execute(text(f'ALTER TABLE word_cloud_submission ADD COLUMN {col_name} {col_def}'))
                            conn.commit()
                            print(f'[WordCloud] Added column to word_cloud_submission: {col_name}')
        except Exception as e:
            print(f'[WordCloud] Migration error: {e}')

   
    def register_routes(self):
        @self.blueprint.route(self.MODULE_URL, methods=["GET"])
        @login_required(self.oauth)
        @permission_required("teachertools.view")
        def main_page():
            # Return JSON for React SPA - no data needed, just auth check
            return jsonify({"status": "ok", "module": "teachertools"})

        # ── Submenu endpoint (sidebar) ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/list-menu", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("teachertools.view")
        def teachertools_list_menu():
            """Return submenu items for the sidebar."""
            items = []
            if user_has_permission("teachertools.wordcloud"):
                items.append({
                    "id": "wordcloud-list",
                    "name": "Wortwolken",
                    "type": "link",
                    "path": "/teachertools/wordcloud",
                })
            return jsonify(items)

        # ── Word Cloud count (for dashboard card) ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/wordcloud/count", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("teachertools.wordcloud")
        def wordcloud_count():
            """Return the number of word clouds the current user has created."""
            user_uuid = session['user_uuid']
            count = WordCloud.query.filter(
                WordCloud.creator_uuid == user_uuid,
                WordCloud.is_deleted == False,
            ).count()
            active_count = WordCloud.query.filter(
                WordCloud.creator_uuid == user_uuid,
                WordCloud.is_deleted == False,
                WordCloud.status.in_(['active', 'paused']),
            ).count()
            return jsonify({"count": count, "active_count": active_count})

        # ══════════════════════════════════════════════════════════════
        #  WORD CLOUD API ROUTES
        # ══════════════════════════════════════════════════════════════

        # ── Groups helper ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/groups", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("teachertools.wordcloud")
        def list_groups():
            """Return all available groups for word cloud assignment."""
            groups = Group.query.order_by(Group.name).all()
            return jsonify({
                "groups": [{"id": g.id, "name": g.name} for g in groups]
            })

        # ── Word Cloud CRUD ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/wordcloud", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("teachertools.wordcloud")
        def list_wordclouds():
            """List word clouds for the current user."""
            tab = request.args.get('tab', 'active')
            user_uuid = session['user_uuid']

            if tab == 'archived':
                wordclouds = WordCloud.query.filter(
                    WordCloud.creator_uuid == user_uuid,
                    WordCloud.is_deleted == False,
                    WordCloud.status == 'archived',
                ).order_by(WordCloud.created_at.desc()).all()
            else:  # active (includes active, paused, stopped)
                wordclouds = WordCloud.query.filter(
                    WordCloud.creator_uuid == user_uuid,
                    WordCloud.is_deleted == False,
                    WordCloud.status.in_(['active', 'paused', 'stopped']),
                ).order_by(WordCloud.created_at.desc()).all()

            return jsonify({"wordclouds": [wc.to_dict() for wc in wordclouds]})

        @self.blueprint.route(f"/api{self.MODULE_URL}/wordcloud", methods=["POST"])
        @login_required(self.oauth)
        @permission_required("teachertools.wordcloud")
        def create_new_wordcloud():
            """Create a new word cloud."""
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'status': False, 'message': 'Name ist erforderlich.'}), 400
            if len(name) > 255:
                return jsonify({'status': False, 'message': 'Name darf maximal 255 Zeichen lang sein.'}), 400

            description = data.get('description', '')
            if len(description) > 5000:
                return jsonify({'status': False, 'message': 'Beschreibung darf maximal 5000 Zeichen lang sein.'}), 400

            result = create_wordcloud(
                name=name,
                description=description,
                creator_uuid=session['user_uuid'],
                max_answers=int(data.get('max_answers_per_participant', 0)),
                case_sensitive=bool(data.get('case_sensitive', False)),
                show_results=bool(data.get('show_results_to_participants', False)),
                group_ids=data.get('group_ids', []),
                allow_participant_download=bool(data.get('allow_participant_download', False)),
                max_chars_per_answer=int(data.get('max_chars_per_answer', 20)),
                anonymous_answers=bool(data.get('anonymous_answers', True)),
                rotation_mode=data.get('rotation_mode', 'mixed'),
                rotation_angles=data.get('rotation_angles', [0, 90]),
                rotation_probability=float(data.get('rotation_probability', 0.5)),
            )

            socketio.emit('load_menu', namespace='/main')
            code = 201 if result['status'] else 400
            return jsonify(result), code

        @self.blueprint.route(f"/api{self.MODULE_URL}/wordcloud/<int:wc_id>", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("teachertools.wordcloud")
        def get_wordcloud(wc_id):
            """Get a single word cloud with aggregated results."""
            wc = WordCloud.query.get_or_404(wc_id)
            if wc.creator_uuid != session['user_uuid']:
                return jsonify({'error': 'Keine Berechtigung.'}), 403
            return jsonify({"wordcloud": wc.to_dict(include_submissions=True)})

        @self.blueprint.route(f"/api{self.MODULE_URL}/wordcloud/<int:wc_id>", methods=["PUT"])
        @login_required(self.oauth)
        @permission_required("teachertools.wordcloud")
        def update_existing_wordcloud(wc_id):
            """Update word cloud settings."""
            data = request.get_json()
            result = update_wordcloud(wc_id, data, session['user_uuid'])
            code = 200 if result['status'] else 400
            return jsonify(result), code

        @self.blueprint.route(f"/api{self.MODULE_URL}/wordcloud/<int:wc_id>/status", methods=["PUT"])
        @login_required(self.oauth)
        @permission_required("teachertools.wordcloud")
        def change_wordcloud_status(wc_id):
            """Change word cloud status (pause, stop, archive)."""
            data = request.get_json()
            new_status = data.get('status', '').strip()
            if new_status not in ('active', 'paused', 'stopped', 'archived'):
                return jsonify({'status': False, 'message': 'Ungültiger Status.'}), 400

            result = update_wordcloud_status(wc_id, new_status, session['user_uuid'])
            socketio.emit('load_menu', namespace='/main')
            code = 200 if result['status'] else 400
            return jsonify(result), code

        @self.blueprint.route(f"/api{self.MODULE_URL}/wordcloud/<int:wc_id>", methods=["DELETE"])
        @login_required(self.oauth)
        @permission_required("teachertools.wordcloud")
        def delete_existing_wordcloud(wc_id):
            """Delete a word cloud."""
            result = delete_wordcloud(wc_id, session['user_uuid'])
            socketio.emit('load_menu', namespace='/main')
            code = 200 if result['status'] else 400
            return jsonify(result), code

        @self.blueprint.route(f"/api{self.MODULE_URL}/wordcloud/<int:wc_id>/results", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("teachertools.wordcloud")
        def get_wordcloud_results_route(wc_id):
            """Get aggregated word cloud results (for live polling)."""
            wc = WordCloud.query.get_or_404(wc_id)
            if wc.creator_uuid != session['user_uuid']:
                return jsonify({'error': 'Keine Berechtigung.'}), 403
            result = get_wordcloud_results(wc_id)
            code = 200 if result['status'] else 400
            return jsonify(result), code

        # ── Participation Routes ──

        @self.blueprint.route(f"/api{self.MODULE_URL}/wordcloud/join/<string:access_code>", methods=["GET"])
        @login_required(self.oauth)
        @permission_required("teachertools.wordcloud")
        def get_wordcloud_for_participation(access_code):
            """Get word cloud info for a participant."""
            wc = WordCloud.query.filter_by(access_code=access_code, is_deleted=False).first()
            if not wc:
                return jsonify({'error': 'Wortwolke nicht gefunden.'}), 404

            if wc.status == 'archived':
                return jsonify({'error': 'Die Wortwolke ist archiviert.'}), 400

            # Check group membership
            user = User.query.filter_by(uuid=session['user_uuid']).first()
            if wc.groups:
                user_group_ids = {g.id for g in user.groups} if user else set()
                wc_group_ids = {g.id for g in wc.groups}
                if not (user_group_ids & wc_group_ids):
                    return jsonify({'error': 'Sie sind nicht berechtigt teilzunehmen.'}), 403

            # Get user's submissions
            user_submissions_query = WordCloudSubmission.query.filter_by(
                wordcloud_id=wc.id,
                user_uuid=session['user_uuid']
            ).order_by(WordCloudSubmission.submitted_at.desc()).all()
            user_submissions = len(user_submissions_query)
            user_words = [s.word for s in user_submissions_query]

            response_data = {
                "wordcloud": {
                    "id": wc.id,
                    "name": wc.name,
                    "description": wc.description,
                    "max_answers_per_participant": wc.max_answers_per_participant,
                    "case_sensitive": wc.case_sensitive,
                    "show_results_to_participants": wc.show_results_to_participants,
                    "allow_participant_download": wc.allow_participant_download,
                    "max_chars_per_answer": wc.max_chars_per_answer,
                    "anonymous_answers": wc.anonymous_answers,
                    "status": wc.status,
                    "access_code": wc.access_code,
                    "creator_name": wc.creator.username if wc.creator else None,
                    "groups": [{'id': g.id, 'name': g.name} for g in wc.groups],
                },
                "user_submission_count": user_submissions,
                "user_words": user_words,
                "version": wc.version,
            }

            # Include word cloud results if visible to participants
            if wc.show_results_to_participants:
                response_data["words"] = wc._aggregate_words()

            return jsonify(response_data)

        @self.blueprint.route(f"/api{self.MODULE_URL}/wordcloud/join/<string:access_code>/submit", methods=["POST"])
        @login_required(self.oauth)
        def submit_word_to_wordcloud(access_code):
            """Submit a word to a word cloud."""
            wc = WordCloud.query.filter_by(access_code=access_code, is_deleted=False).first()
            if not wc:
                return jsonify({'status': False, 'message': 'Wortwolke nicht gefunden.'}), 404

            data = request.get_json()
            word = data.get('word', '').strip()
            if not word:
                return jsonify({'status': False, 'message': 'Bitte geben Sie ein Wort ein.'}), 400

            result = submit_word(wc.id, session['user_uuid'], word)

            # Emit real-time update to creator via socketio
            if result['status']:
                socketio.emit('wordcloud_update', {
                    'wordcloud_id': wc.id,
                    'words': wc._aggregate_words(),
                    'total_submissions': len(wc.submissions),
                    'unique_words': wc._count_unique_words(),
                    'version': wc.version,
                }, namespace=self.MODULE_URL, room=f'wordcloud_{wc.id}')

                # Include user's submitted words in response
                user_words = WordCloudSubmission.query.filter_by(
                    wordcloud_id=wc.id,
                    user_uuid=session['user_uuid']
                ).order_by(WordCloudSubmission.submitted_at.desc()).all()
                result['user_words'] = [s.word for s in user_words]

            code = 200 if result['status'] else 400
            return jsonify(result), code

        @self.blueprint.route(f"/api{self.MODULE_URL}/wordcloud/join/<string:access_code>/results", methods=["GET"])
        @login_required(self.oauth)
        def get_participant_results(access_code):
            """Get word cloud results and current settings for participant polling."""
            wc = WordCloud.query.filter_by(access_code=access_code, is_deleted=False).first()
            if not wc:
                return jsonify({'error': 'Wortwolke nicht gefunden.'}), 404

            response = {
                'status': True,
                'version': wc.version,
                'wc_status': wc.status,
                'show_results_to_participants': wc.show_results_to_participants,
                'allow_participant_download': wc.allow_participant_download,
                'max_chars_per_answer': wc.max_chars_per_answer,
                'max_answers_per_participant': wc.max_answers_per_participant,
                'anonymous_answers': wc.anonymous_answers,
            }

            if wc.show_results_to_participants:
                response['words'] = wc._aggregate_words()
                response['total_submissions'] = len(wc.submissions)
                response['unique_words'] = wc._count_unique_words()

            return jsonify(response)

    def register_socketio_events(self):

        # Wir benoetigt, damit beim senden von Daten auch immer nur der richtige Client angesprochen wird.
        @socketio.on('connect', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("teachertools.view")
        def handle_connect():
            # Beim Verbinden wird die session ID gespeichert
            self.clients[request.sid] = {"username": session.get('username', 'Unbekannt')}
            join_room(request.sid)
            print(f"Client {request.sid} verbunden.")

        @socketio.on('disconnect', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        @permission_required("teachertools.view")
        def handle_disconnect():
            # Client-ID beim Trennen entfernen
            leave_room(request.sid)
            if request.sid in self.clients:
                del self.clients[request.sid]
            print(f"Client {request.sid} getrennt.")

        @socketio.on('join_wordcloud', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        def handle_join_wordcloud(data):
            """Creator joins a room to receive live updates for their word cloud."""
            wc_id = data.get('wordcloud_id')
            if wc_id:
                room = f'wordcloud_{wc_id}'
                join_room(room)
                print(f"Client {request.sid} joined room {room}")

        @socketio.on('leave_wordcloud', namespace=self.MODULE_URL)
        @login_required(self.oauth)
        def handle_leave_wordcloud(data):
            """Creator leaves a word cloud room."""
            wc_id = data.get('wordcloud_id')
            if wc_id:
                room = f'wordcloud_{wc_id}'
                leave_room(room)
                print(f"Client {request.sid} left room {room}")

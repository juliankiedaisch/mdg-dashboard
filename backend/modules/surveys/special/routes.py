"""
Special Survey Routes

All API routes specific to the special survey type (class composition workflow).
Extracted from the monolithic surveys.py.

Usage (called from the Module class):
    register_special_routes(blueprint, module_url, oauth, socketio_ref)
"""
from flask import session, request, jsonify, send_file
from src.decorators import login_required, permission_required
from src.permissions import user_has_permission
from src.db_models import User
from src.db import db
from modules.surveys.special.db_models import SpecialSurvey
from modules.surveys.common.db_functions import _utcnow_naive
from modules.surveys.special.db_functions import (
    create_special_survey, get_special_survey_classes,
    assign_class_teachers, advance_phase,
    activate_survey, complete_survey,
    archive_special_survey, reactivate_special_survey,
    get_student_phase1_data, submit_student_wishes,
    get_parent_phase2_data, confirm_parent_wishes,
    get_teacher_phase3_data, submit_teacher_evaluation,
    export_special_survey_xlsx, get_active_special_surveys_for_user,
    add_students, add_parents, reset_student_wishes,
    get_participants, remove_participant, add_participant,
)


def _can_manage_special():
    """Return True if the user can manage special surveys."""
    return (
        user_has_permission("surveys.manage.all")
        or user_has_permission("surveys.special.manage")
    )


def register_special_routes(blueprint, module_url, oauth, socketio_ref):
    """Register all special-survey-specific API routes on the given blueprint."""

    # ── Create special survey ──

    @blueprint.route(f"/api{module_url}/special", methods=["POST"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def create_new_special_survey():
        """Create a special survey with CSV uploads for students and parents."""
        title = request.form.get('title', '').strip()
        if not title:
            return jsonify({'status': False, 'message': 'Titel ist erforderlich.'}), 400

        description = request.form.get('description', '')
        grade_level = request.form.get('grade_level', '').strip()
        if not grade_level:
            return jsonify({'status': False, 'message': 'Jahrgang ist erforderlich.'}), 400

        teacher_survey_id = request.form.get('teacher_survey_id')
        if teacher_survey_id:
            try:
                teacher_survey_id = int(teacher_survey_id)
            except (ValueError, TypeError):
                teacher_survey_id = None

        student_file = request.files.get('student_csv')
        parent_file = request.files.get('parent_csv')
        if not student_file or not parent_file:
            return jsonify({'status': False, 'message': 'Beide CSV-Dateien sind erforderlich.'}), 400

        student_csv_content = student_file.read()
        parent_csv_content = parent_file.read()

        result = create_special_survey(
            title=title,
            description=description,
            creator_uuid=session['user_uuid'],
            grade_level=grade_level,
            student_csv_content=student_csv_content,
            parent_csv_content=parent_csv_content,
            teacher_survey_id=teacher_survey_id,
        )

        socketio_ref.emit('load_menu', namespace='/main')
        code = 201 if result['status'] else 400
        return jsonify(result), code

    # ── List special surveys (management) ──

    @blueprint.route(f"/api{module_url}/special", methods=["GET"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def list_special_surveys():
        """List special surveys created by the current user.
        ?tab=archived  → only archived surveys
        ?tab=active    → all non-archived surveys (default)
        ?tab=trash     → soft-deleted surveys
        """
        tab = request.args.get('tab', 'active')
        query = SpecialSurvey.query.filter_by(
            creator_uuid=session['user_uuid']
        )

        if tab == 'trash':
            if not (user_has_permission("surveys.delete.permanently")
                    or user_has_permission("surveys.admin")):
                return jsonify({'error': 'Keine Berechtigung.'}), 403
            query = query.filter(SpecialSurvey.is_deleted == True)
        elif tab == 'archived':
            query = query.filter(
                SpecialSurvey.is_deleted == False,
                SpecialSurvey.status == 'archived',
            )
        else:
            query = query.filter(
                SpecialSurvey.is_deleted == False,
                SpecialSurvey.status != 'archived',
            )

        surveys = query.order_by(SpecialSurvey.created_at.desc()).all()
        return jsonify({"special_surveys": [s.to_dict() for s in surveys]})

    # ── Get special survey detail ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>", methods=["GET"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def get_special_survey(ss_id):
        """Get a single special survey with full details."""
        ss = SpecialSurvey.query.get_or_404(ss_id)
        if ss.creator_uuid != session['user_uuid'] \
                and not user_has_permission("surveys.admin"):
            return jsonify({'error': 'Keine Berechtigung.'}), 403
        return jsonify({"survey": ss.to_dict(include_details=True)})

    # ── Get classes for a special survey ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/classes", methods=["GET"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def get_special_survey_classes_route(ss_id):
        """Get classes and their students from the special survey."""
        classes = get_special_survey_classes(ss_id)
        if classes is None:
            return jsonify({'error': 'Umfrage nicht gefunden.'}), 404
        return jsonify({"classes": classes})

    # ── Assign class teachers ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/assign-teachers", methods=["PUT"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def assign_teachers_route(ss_id):
        """Assign class teachers to classes in the special survey."""
        data = request.get_json()
        assignments = data.get('assignments', [])
        result = assign_class_teachers(ss_id, assignments, session['user_uuid'])
        code = 200 if result['status'] else 400
        return jsonify(result), code

    # ── Advance phase / Activate / Complete / Archive / Reactivate ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/advance-phase", methods=["PUT"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def advance_phase_route(ss_id):
        """Advance the special survey to the next phase."""
        result = advance_phase(ss_id, session['user_uuid'])
        socketio_ref.emit('load_menu', namespace='/main')
        code = 200 if result['status'] else 400
        return jsonify(result), code

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/activate", methods=["PUT"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def activate_survey_route(ss_id):
        """Activate the special survey (setup → active)."""
        result = activate_survey(ss_id, session['user_uuid'])
        socketio_ref.emit('load_menu', namespace='/main')
        code = 200 if result['status'] else 400
        return jsonify(result), code

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/complete", methods=["PUT"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def complete_survey_route(ss_id):
        """Complete the special survey (active → completed)."""
        result = complete_survey(ss_id, session['user_uuid'])
        socketio_ref.emit('load_menu', namespace='/main')
        code = 200 if result['status'] else 400
        return jsonify(result), code

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/archive", methods=["PUT"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def archive_survey_route(ss_id):
        """Archive the special survey."""
        result = archive_special_survey(ss_id, session['user_uuid'])
        socketio_ref.emit('load_menu', namespace='/main')
        code = 200 if result['status'] else 400
        return jsonify(result), code

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/reactivate", methods=["PUT"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def reactivate_survey_route(ss_id):
        """Reactivate a completed/archived survey back to active."""
        result = reactivate_special_survey(ss_id, session['user_uuid'])
        socketio_ref.emit('load_menu', namespace='/main')
        code = 200 if result['status'] else 400
        return jsonify(result), code

    # ── Add participants post-creation ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/add-students", methods=["POST"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def add_students_route(ss_id):
        """Add additional students to the special survey via CSV upload."""
        student_file = request.files.get('student_csv')
        if not student_file:
            return jsonify({'status': False, 'message': 'CSV-Datei ist erforderlich.'}), 400
        csv_content = student_file.read()
        result = add_students(ss_id, session['user_uuid'], csv_content)
        code = 200 if result['status'] else 400
        return jsonify(result), code

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/add-parents", methods=["POST"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def add_parents_route(ss_id):
        """Add additional parents to the special survey via CSV upload."""
        parent_file = request.files.get('parent_csv')
        if not parent_file:
            return jsonify({'status': False, 'message': 'CSV-Datei ist erforderlich.'}), 400
        csv_content = parent_file.read()
        result = add_parents(ss_id, session['user_uuid'], csv_content)
        code = 200 if result['status'] else 400
        return jsonify(result), code

    # ── Reset student wishes ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/reset-wish", methods=["POST"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def reset_wish_route(ss_id):
        """Reset a student's wishes so they can re-submit."""
        data = request.get_json()
        student_id = data.get('student_id')
        if not student_id:
            return jsonify({'status': False, 'message': 'student_id ist erforderlich.'}), 400
        result = reset_student_wishes(ss_id, student_id, session['user_uuid'])
        code = 200 if result['status'] else 400
        return jsonify(result), code

    # ── Delete special survey ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>", methods=["DELETE"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def delete_special_survey(ss_id):
        """Soft-delete a special survey."""
        ss = SpecialSurvey.query.get(ss_id)
        if not ss:
            return jsonify({'status': False, 'message': 'Umfrage nicht gefunden.'}), 404
        if ss.creator_uuid != session['user_uuid'] \
                and not user_has_permission("surveys.admin"):
            return jsonify({'status': False, 'message': 'Keine Berechtigung.'}), 403
        ss.is_deleted = True
        ss.deleted_at = _utcnow_naive()
        ss.deleted_by = session['user_uuid']
        db.session.commit()
        socketio_ref.emit('load_menu', namespace='/main')
        return jsonify({'status': True, 'message': 'Spezialumfrage gelöscht.'})

    # ── Phase 1: Student participation ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/phase1", methods=["GET"])
    @login_required(oauth)
    def get_phase1_data(ss_id):
        """Get Phase 1 data for a student."""
        data, err = get_student_phase1_data(ss_id, session['user_uuid'])
        if err:
            return jsonify({'error': err}), 400
        return jsonify(data)

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/phase1", methods=["POST"])
    @login_required(oauth)
    def submit_phase1(ss_id):
        """Submit student wishes in Phase 1."""
        data = request.get_json()
        result = submit_student_wishes(
            special_survey_id=ss_id,
            user_uuid=session['user_uuid'],
            wish1_student_id=data.get('wish1_student_id'),
            wish2_student_id=data.get('wish2_student_id'),
            selected_parent_id=data.get('selected_parent_id'),
        )
        code = 200 if result['status'] else 400
        return jsonify(result), code

    # ── Phase 2: Parent confirmation ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/phase2", methods=["GET"])
    @login_required(oauth)
    def get_phase2_data(ss_id):
        """Get Phase 2 data for a parent."""
        data, err = get_parent_phase2_data(ss_id, session['user_uuid'])
        if err:
            return jsonify({'error': err}), 400
        return jsonify(data)

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/phase2/confirm", methods=["POST"])
    @login_required(oauth)
    def submit_phase2_confirm(ss_id):
        """Parent confirms a child's wishes."""
        data = request.get_json()
        result = confirm_parent_wishes(
            special_survey_id=ss_id,
            user_uuid=session['user_uuid'],
            wish_id=data.get('wish_id'),
        )
        code = 200 if result['status'] else 400
        return jsonify(result), code

    # ── Phase 3: Teacher evaluation ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/phase3", methods=["GET"])
    @login_required(oauth)
    def get_phase3_data(ss_id):
        """Get Phase 3 data for a teacher."""
        data, err = get_teacher_phase3_data(ss_id, session['user_uuid'])
        if err:
            return jsonify({'error': err}), 400
        return jsonify(data)

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/phase3/evaluate", methods=["POST"])
    @login_required(oauth)
    def submit_phase3_evaluation(ss_id):
        """Submit teacher evaluation for a student."""
        data = request.get_json()
        result = submit_teacher_evaluation(
            special_survey_id=ss_id,
            user_uuid=session['user_uuid'],
            student_id=data.get('student_id'),
            survey_answers=data.get('survey_answers'),
        )
        code = 200 if result['status'] else 400
        return jsonify(result), code

    # ── Excel export ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/export", methods=["GET"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def export_special_survey(ss_id):
        """Download the special survey results as XLSX."""
        ss = SpecialSurvey.query.get_or_404(ss_id)
        if ss.creator_uuid != session['user_uuid'] \
                and not user_has_permission("surveys.admin"):
            return jsonify({'error': 'Keine Berechtigung.'}), 403

        buf, filename = export_special_survey_xlsx(ss_id)
        if buf is None:
            return jsonify({'error': filename}), 404

        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
        )

    # ── Active special surveys for current user (participation) ──

    @blueprint.route(f"/api{module_url}/special/active", methods=["GET"])
    @login_required(oauth)
    def get_active_special_surveys():
        """Get active special surveys the current user can participate in."""
        surveys = get_active_special_surveys_for_user(session['user_uuid'])
        return jsonify({"surveys": surveys})

    # ── Teachers list helper ──

    @blueprint.route(f"/api{module_url}/special/teachers", methods=["GET"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def list_teachers():
        """Return all users who could be class teachers."""
        users = User.query.order_by(User.username).all()
        return jsonify({
            "teachers": [{"uuid": u.uuid, "username": u.username} for u in users]
        })

    # ── Participant management ──

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/participants", methods=["GET"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def get_participants_route(ss_id):
        """List all participants with survey details."""
        participants, err = get_participants(ss_id, session['user_uuid'])
        if err:
            return jsonify({'error': err}), 400
        return jsonify({'participants': participants})

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/participants", methods=["POST"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def add_participant_route(ss_id):
        """Add a single participant by username + role."""
        data = request.get_json()
        username = data.get('username', '')
        role = data.get('role', '')
        class_name = data.get('class_name', '')
        result = add_participant(ss_id, session['user_uuid'], username, role, class_name)
        code = 200 if result['status'] else 400
        return jsonify(result), code

    @blueprint.route(f"/api{module_url}/special/<int:ss_id>/participants/<int:pid>", methods=["DELETE"])
    @login_required(oauth)
    @permission_required("surveys.manage.all", "surveys.special.manage")
    def remove_participant_route(ss_id, pid):
        """Remove a participant from the survey."""
        role = request.args.get('role', '')
        if not role:
            return jsonify({'status': False, 'message': 'Rolle ist erforderlich (?role=student|parent)'}), 400
        result = remove_participant(ss_id, pid, role, session['user_uuid'])
        code = 200 if result['status'] else 400
        return jsonify(result), code

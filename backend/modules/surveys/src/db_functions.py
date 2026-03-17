# Survey Module - Database Functions
from src.db import db
from src.db_models import User, Group
from modules.surveys.src.db_models import (
    Survey, SurveyQuestion, SurveyQuestionOption,
    SurveyResponse, SurveyAnswer,
)
from datetime import datetime, timezone
from src.utils import utc_isoformat


def _add_questions_to_survey(survey_id, questions_data):
    """
    Bulk-create SurveyQuestion + SurveyQuestionOption rows for a survey.
    Returns None on success, or an error-dict on validation failure.
    Must be called inside an active db.session transaction.
    """
    for idx, q_data in enumerate(questions_data):
        q_type = q_data.get('question_type', 'text')
        if q_type not in SurveyQuestion.ALLOWED_TYPES:
            return {'status': False, 'message': f"Ungültiger Fragetyp: {q_type}"}

        question = SurveyQuestion(
            survey_id=survey_id,
            text=q_data['text'],
            question_type=q_type,
            required=q_data.get('required', True),
            order=q_data.get('order', idx),
            config_json=q_data.get('config_json', '{}'),
            excel_config_json=q_data.get('excel_config_json', '{}'),
        )
        db.session.add(question)
        db.session.flush()

        q_group_ids = q_data.get('group_ids', [])
        if q_group_ids:
            q_groups = Group.query.filter(Group.id.in_(q_group_ids)).all()
            question.groups = q_groups

        for o_idx, opt in enumerate(q_data.get('options', [])):
            option = SurveyQuestionOption(
                question_id=question.id,
                text=opt['text'],
                order=opt.get('order', o_idx),
            )
            db.session.add(option)
    return None


def _utcnow_naive():
    """Return current UTC time as a naive datetime (for SQLite compatibility)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_iso_dt(s):
    """Parse an ISO-8601 datetime string to a naive UTC datetime."""
    if not s:
        return None
    # JavaScript toISOString() appends 'Z'; strip it for a naive UTC datetime
    return datetime.fromisoformat(s.replace('Z', '+00:00')).replace(tzinfo=None)


# ── Survey CRUD ─────────────────────────────────────────────────────

def create_survey(title, description, creator_uuid, anonymous=False,
                  starts_at=None, ends_at=None, group_ids=None, questions=None,
                  is_template=False, allow_edit_response=False, template_type='normal'):
    """
    Create a new survey with questions and group assignments.

    `questions` is a list of dicts:
        {
            "text": "...",
            "question_type": "single_choice",
            "required": True,
            "order": 0,
            "group_ids": [] | [1, 2, ...],  # empty = all groups
            "config_json": "{}",
            "options": [{"text": "Option A", "order": 0}, ...]
        }
    """
    try:
        creator = User.query.filter_by(uuid=creator_uuid).first()
        if not creator:
            return {'status': False, 'message': 'Ersteller nicht gefunden.'}

        survey = Survey(
            title=title,
            description=description or '',
            creator_uuid=creator_uuid,
            anonymous=anonymous,
            starts_at=starts_at,
            ends_at=ends_at,
            status='draft',
            is_template=is_template,
            template_type=template_type if is_template else 'normal',
            allow_edit_response=allow_edit_response,
        )

        # Attach groups
        if group_ids:
            groups = Group.query.filter(Group.id.in_(group_ids)).all()
            survey.groups = groups

        db.session.add(survey)
        db.session.flush()  # get survey.id before adding questions

        # Add questions
        if questions:
            err = _add_questions_to_survey(survey.id, questions)
            if err:
                db.session.rollback()
                return err

        db.session.commit()
        return {'status': True, 'message': 'Umfrage erstellt.', 'survey_id': survey.id}

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Fehler beim Erstellen.'}


def update_survey(survey_id, data, user_uuid):
    """Update survey metadata (title, description, groups, status, …)."""
    try:
        survey = Survey.query.get(survey_id)
        if not survey:
            return {'status': False, 'message': 'Umfrage nicht gefunden.'}
        if survey.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}

        if 'title' in data:
            survey.title = data['title']
        if 'description' in data:
            survey.description = data['description']
        if 'anonymous' in data:
            survey.anonymous = data['anonymous']
        if 'starts_at' in data:
            survey.starts_at = _parse_iso_dt(data['starts_at'])
        if 'ends_at' in data:
            survey.ends_at = _parse_iso_dt(data['ends_at'])
        if 'status' in data and data['status'] in ('draft', 'active', 'closed', 'archived'):
            # Prevent setting 'template' status via update; templates use is_template flag
            if survey.is_template:
                return {'status': False, 'message': 'Status von Vorlagen kann nicht geändert werden.'}
            survey.status = data['status']
        if 'group_ids' in data:
            groups = Group.query.filter(Group.id.in_(data['group_ids'])).all()
            survey.groups = groups
        if 'allow_edit_response' in data:
            survey.allow_edit_response = data['allow_edit_response']

        db.session.commit()
        return {'status': True, 'message': 'Umfrage aktualisiert.'}

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def delete_survey(survey_id, user_uuid, is_admin=False):
    """Soft-delete a survey (marks as deleted, preserving all data)."""
    try:
        survey = Survey.query.get(survey_id)
        if not survey:
            return {'status': False, 'message': 'Umfrage nicht gefunden.'}
        if survey.creator_uuid != user_uuid and not is_admin:
            return {'status': False, 'message': 'Keine Berechtigung.'}

        survey.is_deleted = True
        survey.deleted_at = _utcnow_naive()
        survey.deleted_by = user_uuid
        db.session.commit()
        return {'status': True, 'message': 'Umfrage gelöscht.'}

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


# ── Questions CRUD ──────────────────────────────────────────────────

def add_question(survey_id, q_data, user_uuid):
    """Add a single question to an existing survey."""
    try:
        survey = Survey.query.get(survey_id)
        if not survey:
            return {'status': False, 'message': 'Umfrage nicht gefunden.'}
        if survey.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}

        q_type = q_data.get('question_type', 'text')
        if q_type not in SurveyQuestion.ALLOWED_TYPES:
            return {'status': False, 'message': f"Ungültiger Fragetyp: {q_type}"}

        max_order = db.session.query(db.func.max(SurveyQuestion.order))\
            .filter_by(survey_id=survey_id).scalar() or 0

        question = SurveyQuestion(
            survey_id=survey_id,
            text=q_data['text'],
            question_type=q_type,
            required=q_data.get('required', True),
            order=q_data.get('order', max_order + 1),
            config_json=q_data.get('config_json', '{}'),
            excel_config_json=q_data.get('excel_config_json', '{}'),
        )
        db.session.add(question)
        db.session.flush()

        # Attach question-level groups
        q_group_ids = q_data.get('group_ids', [])
        if q_group_ids:
            q_groups = Group.query.filter(Group.id.in_(q_group_ids)).all()
            question.groups = q_groups

        for o_idx, opt in enumerate(q_data.get('options', [])):
            option = SurveyQuestionOption(
                question_id=question.id,
                text=opt['text'],
                order=opt.get('order', o_idx),
            )
            db.session.add(option)

        db.session.commit()
        return {'status': True, 'message': 'Frage hinzugefügt.', 'question_id': question.id}

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def update_question(question_id, q_data, user_uuid):
    """Update a question's text, type, options, or group assignment."""
    try:
        question = SurveyQuestion.query.get(question_id)
        if not question:
            return {'status': False, 'message': 'Frage nicht gefunden.'}
        if question.survey.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}

        if 'text' in q_data:
            question.text = q_data['text']
        if 'question_type' in q_data:
            if q_data['question_type'] not in SurveyQuestion.ALLOWED_TYPES:
                return {'status': False, 'message': f"Ungültiger Fragetyp: {q_data['question_type']}"}
            question.question_type = q_data['question_type']
        if 'required' in q_data:
            question.required = q_data['required']
        if 'order' in q_data:
            question.order = q_data['order']
        if 'group_ids' in q_data:
            q_groups = Group.query.filter(Group.id.in_(q_data['group_ids'])).all() if q_data['group_ids'] else []
            question.groups = q_groups
        if 'config_json' in q_data:
            question.config_json = q_data['config_json']
        if 'excel_config_json' in q_data:
            question.excel_config_json = q_data['excel_config_json']

        # Replace options if provided
        if 'options' in q_data:
            # Remove old options
            SurveyQuestionOption.query.filter_by(question_id=question_id).delete()
            for o_idx, opt in enumerate(q_data['options']):
                option = SurveyQuestionOption(
                    question_id=question_id,
                    text=opt['text'],
                    order=opt.get('order', o_idx),
                )
                db.session.add(option)

        db.session.commit()
        return {'status': True, 'message': 'Frage aktualisiert.'}

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def delete_question(question_id, user_uuid):
    """Delete a question from a survey."""
    try:
        question = SurveyQuestion.query.get(question_id)
        if not question:
            return {'status': False, 'message': 'Frage nicht gefunden.'}
        if question.survey.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}

        db.session.delete(question)
        db.session.commit()
        return {'status': True, 'message': 'Frage gelöscht.'}

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


# ── Responses ────────────────────────────────────────────────────────

def submit_response(survey_id, user_uuid, answers_data):
    """
    Submit a user's response to a survey.

    `answers_data` is a list of dicts:
        {
            "question_id": <int>,
            "answer_text": "..." | null,
            "selected_option_id": <int> | null,
            "selected_option_ids": "1,2,3" | null
        }
    """
    try:
        survey = Survey.query.get(survey_id)
        if not survey:
            return {'status': False, 'message': 'Umfrage nicht gefunden.'}
        if survey.status != 'active':
            return {'status': False, 'message': 'Umfrage ist nicht aktiv.'}

        # Check if user already responded
        existing = SurveyResponse.query.filter_by(
            survey_id=survey_id, user_uuid=user_uuid
        ).first()
        if existing:
            # Allow re-submission if the survey permits editing responses
            # or if the maintainer granted a one-time edit to this user
            if survey.allow_edit_response or existing.edit_granted:
                return update_response(survey_id, user_uuid, answers_data)
            return {'status': False, 'message': 'Sie haben bereits an dieser Umfrage teilgenommen.'}

        response = SurveyResponse(
            survey_id=survey_id,
            user_uuid=user_uuid,
        )
        db.session.add(response)
        db.session.flush()

        # Validate and store answers
        valid_question_ids = {q.id for q in survey.questions}
        for a_data in answers_data:
            qid = a_data.get('question_id')
            if qid not in valid_question_ids:
                db.session.rollback()
                return {'status': False, 'message': 'Ungültige Fragen-ID in den Antworten.'}
            answer = SurveyAnswer(
                response_id=response.id,
                question_id=qid,
                answer_text=a_data.get('answer_text'),
                selected_option_id=a_data.get('selected_option_id'),
                selected_option_ids=a_data.get('selected_option_ids'),
            )
            db.session.add(answer)

        db.session.commit()
        return {'status': True, 'message': 'Antwort gespeichert.'}

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def update_response(survey_id, user_uuid, answers_data):
    """
    Update an existing response. Replaces all answers for the user's response.
    Allowed when the survey has allow_edit_response=True or the individual
    response has edit_granted=True (one-time grant by maintainer).
    """
    try:
        survey = Survey.query.get(survey_id)
        if not survey:
            return {'status': False, 'message': 'Umfrage nicht gefunden.'}
        if survey.status != 'active':
            return {'status': False, 'message': 'Umfrage ist nicht aktiv.'}

        existing = SurveyResponse.query.filter_by(
            survey_id=survey_id, user_uuid=user_uuid
        ).first()
        if not existing:
            return {'status': False, 'message': 'Keine vorherige Antwort gefunden.'}

        if not survey.allow_edit_response and not existing.edit_granted:
            return {'status': False, 'message': 'Bearbeitung der Antworten ist nicht erlaubt.'}

        # Delete old answers and replace with new ones
        SurveyAnswer.query.filter_by(response_id=existing.id).delete()

        # Validate and store answers
        valid_question_ids = {q.id for q in survey.questions}
        for a_data in answers_data:
            qid = a_data.get('question_id')
            if qid not in valid_question_ids:
                db.session.rollback()
                return {'status': False, 'message': 'Ungültige Fragen-ID in den Antworten.'}
            answer = SurveyAnswer(
                response_id=existing.id,
                question_id=qid,
                answer_text=a_data.get('answer_text'),
                selected_option_id=a_data.get('selected_option_id'),
                selected_option_ids=a_data.get('selected_option_ids'),
            )
            db.session.add(answer)

        # Update submission timestamp
        existing.submitted_at = _utcnow_naive()
        # Reset one-time edit grant after successful re-submission
        if existing.edit_granted:
            existing.edit_granted = False

        db.session.commit()
        return {'status': True, 'message': 'Antwort aktualisiert.'}

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


# ── Results / Evaluation ────────────────────────────────────────────

def grant_edit_response(response_id, user_uuid):
    """Grant a one-time edit permission for a specific response."""
    try:
        response = SurveyResponse.query.get(response_id)
        if not response:
            return {'status': False, 'message': 'Antwort nicht gefunden.'}
        if response.survey.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}

        response.edit_granted = True
        db.session.commit()
        return {'status': True, 'message': 'Bearbeitungsrecht erteilt.'}
    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def revoke_edit_response(response_id, user_uuid):
    """Revoke a previously granted one-time edit permission."""
    try:
        response = SurveyResponse.query.get(response_id)
        if not response:
            return {'status': False, 'message': 'Antwort nicht gefunden.'}
        if response.survey.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}

        response.edit_granted = False
        db.session.commit()
        return {'status': True, 'message': 'Bearbeitungsrecht entzogen.'}
    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def get_survey_results(survey_id):
    """
    Aggregate results for a survey.
    Returns per-question summaries suitable for charts / tables.
    For non-anonymous surveys, includes participant names per answer.
    """
    survey = Survey.query.get(survey_id)
    if not survey:
        return None

    # Build a response_id -> username lookup for non-anonymous surveys
    user_by_response = {}
    if not survey.anonymous:
        for resp in survey.responses:
            user_by_response[resp.id] = resp.user.username if resp.user else 'Unbekannt'

    results = {
        'survey_id': survey.id,
        'title': survey.title,
        'anonymous': survey.anonymous,
        'response_count': len(survey.responses),
        'questions': [],
    }

    # Include participant list for non-anonymous surveys
    if not survey.anonymous:
        results['participants'] = [
            {'response_id': resp.id,
             'user_uuid': resp.user_uuid,
             'username': resp.user.username if resp.user else 'Unbekannt',
             'submitted_at': utc_isoformat(resp.submitted_at),
             'edit_granted': resp.edit_granted}
            for resp in survey.responses
        ]

    for question in survey.questions:
        q_result = {
            'question_id': question.id,
            'text': question.text,
            'question_type': question.question_type,
            'group_ids': [g.id for g in question.groups],
            'groups': [{'id': g.id, 'name': g.name} for g in question.groups],
            'answers_count': len(question.answers),
        }

        if question.question_type in ('single_choice', 'multiple_choice'):
            option_counts = {}
            for opt in question.options:
                option_counts[opt.id] = {'text': opt.text, 'count': 0}

            for answer in question.answers:
                if question.question_type == 'single_choice' and answer.selected_option_id:
                    if answer.selected_option_id in option_counts:
                        option_counts[answer.selected_option_id]['count'] += 1
                elif question.question_type == 'multiple_choice' and answer.selected_option_ids:
                    for oid_str in answer.selected_option_ids.split(','):
                        oid_str = oid_str.strip()
                        if not oid_str:
                            continue
                        try:
                            oid = int(oid_str)
                        except ValueError:
                            continue
                        if oid in option_counts:
                            option_counts[oid]['count'] += 1

            q_result['option_results'] = list(option_counts.values())

            # Per-user answers for non-anonymous
            if not survey.anonymous:
                user_answers = []
                for answer in question.answers:
                    username = user_by_response.get(answer.response_id, 'Unbekannt')
                    if question.question_type == 'single_choice' and answer.selected_option_id:
                        opt = option_counts.get(answer.selected_option_id)
                        user_answers.append({'username': username, 'answer': opt['text'] if opt else ''})
                    elif question.question_type == 'multiple_choice' and answer.selected_option_ids:
                        selected = []
                        for oid_str in answer.selected_option_ids.split(','):
                            oid_str = oid_str.strip()
                            if not oid_str:
                                continue
                            try:
                                oid = int(oid_str)
                            except ValueError:
                                continue
                            opt = option_counts.get(oid)
                            if opt:
                                selected.append(opt['text'])
                        user_answers.append({'username': username, 'answer': ', '.join(selected)})
                q_result['user_answers'] = user_answers

        elif question.question_type == 'rating':
            ratings = []
            for answer in question.answers:
                if answer.answer_text:
                    try:
                        ratings.append(float(answer.answer_text))
                    except ValueError:
                        pass
            q_result['average'] = sum(ratings) / len(ratings) if ratings else 0
            q_result['ratings'] = ratings

            if not survey.anonymous:
                q_result['user_answers'] = [
                    {'username': user_by_response.get(a.response_id, 'Unbekannt'), 'answer': a.answer_text}
                    for a in question.answers if a.answer_text
                ]

        elif question.question_type == 'yes_no':
            yes_count = sum(1 for a in question.answers if a.answer_text and a.answer_text.lower() in ('yes', 'ja', 'true', '1'))
            no_count = sum(1 for a in question.answers if a.answer_text and a.answer_text.lower() in ('no', 'nein', 'false', '0'))
            q_result['yes_count'] = yes_count
            q_result['no_count'] = no_count

            if not survey.anonymous:
                q_result['user_answers'] = [
                    {'username': user_by_response.get(a.response_id, 'Unbekannt'),
                     'answer': 'Ja' if a.answer_text and a.answer_text.lower() in ('yes', 'ja', 'true', '1') else 'Nein'}
                    for a in question.answers if a.answer_text
                ]

        elif question.question_type == 'text':
            q_result['text_answers'] = [a.answer_text for a in question.answers if a.answer_text]

            if not survey.anonymous:
                q_result['user_answers'] = [
                    {'username': user_by_response.get(a.response_id, 'Unbekannt'), 'answer': a.answer_text}
                    for a in question.answers if a.answer_text
                ]

        results['questions'].append(q_result)

    return results


# ── Full survey edit (when not active) ──────────────────────────────

def edit_survey_full(survey_id, data, user_uuid):
    """
    Full edit of a survey's metadata AND questions.
    Only allowed when survey is not 'active'.
    """
    try:
        survey = Survey.query.get(survey_id)
        if not survey:
            return {'status': False, 'message': 'Umfrage nicht gefunden.'}
        if survey.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}
        if survey.status == 'active':
            return {'status': False, 'message': 'Aktive Umfragen können nicht bearbeitet werden.'}
        if survey.status == 'archived':
            return {'status': False, 'message': 'Archivierte Umfragen können nicht bearbeitet werden.'}

        # Update metadata
        if 'title' in data:
            survey.title = data['title']
        if 'description' in data:
            survey.description = data['description']
        if 'anonymous' in data:
            survey.anonymous = data['anonymous']
        if 'starts_at' in data:
            survey.starts_at = _parse_iso_dt(data['starts_at'])
        if 'ends_at' in data:
            survey.ends_at = _parse_iso_dt(data['ends_at'])
        if 'group_ids' in data:
            groups = Group.query.filter(Group.id.in_(data['group_ids'])).all()
            survey.groups = groups
        if 'allow_edit_response' in data:
            survey.allow_edit_response = data['allow_edit_response']

        # Replace questions entirely if provided
        if 'questions' in data:
            # Remove all existing questions (cascades to options & answers)
            for q in list(survey.questions):
                db.session.delete(q)
            db.session.flush()

            err = _add_questions_to_survey(survey.id, data['questions'])
            if err:
                db.session.rollback()
                return err

        db.session.commit()
        return {'status': True, 'message': 'Umfrage aktualisiert.'}

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


# ── Template sharing ────────────────────────────────────────────────

def share_template(survey_id, user_uuid, group_ids=None, user_uuids=None):
    """Share a template with groups and/or individual users."""
    try:
        survey = Survey.query.get(survey_id)
        if not survey:
            return {'status': False, 'message': 'Vorlage nicht gefunden.'}
        if survey.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}
        if not survey.is_template:
            return {'status': False, 'message': 'Nur Vorlagen können geteilt werden.'}

        if group_ids is not None:
            groups = Group.query.filter(Group.id.in_(group_ids)).all() if group_ids else []
            survey.shared_with_groups = groups

        if user_uuids is not None:
            users = User.query.filter(User.uuid.in_(user_uuids)).all() if user_uuids else []
            survey.shared_with_users = users

        db.session.commit()
        return {'status': True, 'message': 'Freigabe aktualisiert.'}

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def clone_from_template(template_id, user_uuid, title=None, group_ids=None,
                        starts_at=None, ends_at=None, anonymous=None):
    """Create a new active survey by cloning a template's questions."""
    try:
        template = Survey.query.get(template_id)
        if not template:
            return {'status': False, 'message': 'Vorlage nicht gefunden.'}
        if not template.is_template:
            return {'status': False, 'message': 'Quelle ist keine Vorlage.'}

        # Verify access: owner, shared by user, or shared by group
        user = User.query.filter_by(uuid=user_uuid).first()
        if not user:
            return {'status': False, 'message': 'Benutzer nicht gefunden.'}

        user_group_ids = {g.id for g in user.groups}
        shared_group_ids = {g.id for g in template.shared_with_groups}
        shared_user_uuids = {u.uuid for u in template.shared_with_users}

        is_owner = template.creator_uuid == user_uuid
        is_shared_user = user_uuid in shared_user_uuids
        is_shared_group = bool(shared_group_ids & user_group_ids)

        if not (is_owner or is_shared_user or is_shared_group):
            return {'status': False, 'message': 'Kein Zugriff auf diese Vorlage.'}

        # Build questions data from template
        questions_data = []
        for q in template.questions:
            q_dict = {
                'text': q.text,
                'question_type': q.question_type,
                'required': q.required,
                'order': q.order,
                'config_json': q.config_json,
                'excel_config_json': q.excel_config_json,
                'group_ids': [],  # Templates don't carry group assignments to clones
                'options': [{'text': o.text, 'order': o.order} for o in q.options],
            }
            questions_data.append(q_dict)

        result = create_survey(
            title=title or f"{template.title} (Kopie)",
            description=template.description,
            creator_uuid=user_uuid,
            anonymous=anonymous if anonymous is not None else template.anonymous,
            starts_at=starts_at,
            ends_at=ends_at,
            group_ids=group_ids or [],
            questions=questions_data,
            is_template=False,
        )
        return result

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def save_as_template(survey_id, user_uuid):
    """
    Clone any survey's questions into a new template owned by the user.

    IMPORTANT: Only the survey *structure* (questions + options) is copied.
    All result data (responses, answers) is deliberately excluded so that
    templates never contain participation data, even if the source survey
    already has results.
    """
    try:
        source = Survey.query.get(survey_id)
        if not source:
            return {'status': False, 'message': 'Umfrage nicht gefunden.'}
        if source.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}

        # Copy only structural data — no responses, no group assignments,
        # no time windows.  This guarantees a clean template.
        questions_data = []
        for q in source.questions:
            questions_data.append({
                'text': q.text,
                'question_type': q.question_type,
                'required': q.required,
                'order': q.order,
                'config_json': q.config_json,
                'excel_config_json': q.excel_config_json,
                'group_ids': [],       # Templates don't carry group scoping
                'options': [{'text': o.text, 'order': o.order} for o in q.options],
                # NOTE: q.answers / response data is intentionally NOT copied
            })

        result = create_survey(
            title=f"{source.title} (Vorlage)",
            description=source.description,
            creator_uuid=user_uuid,
            anonymous=source.anonymous,
            starts_at=None,
            ends_at=None,
            group_ids=[],
            questions=questions_data,
            is_template=True,
            template_type=source.template_type if source.is_template else 'normal',
        )
        return result

    except Exception as e:
        db.session.rollback()
        print(f'[Surveys] Error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}

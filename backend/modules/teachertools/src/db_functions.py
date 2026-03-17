# TeacherTools Module - Word Cloud Database Functions
from src.db import db
from src.db_models import User, Group
from modules.teachertools.src.db_models import WordCloud, WordCloudSubmission
from datetime import datetime, timezone
import secrets
import string
import json


def _generate_access_code(length=8):
    """Generate a unique access code for word cloud participation."""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(chars) for _ in range(length))
        existing = WordCloud.query.filter_by(access_code=code).first()
        if not existing:
            return code


def create_wordcloud(name, description, creator_uuid, max_answers=0,
                     case_sensitive=False, show_results=False, group_ids=None,
                     allow_participant_download=False, max_chars_per_answer=20,
                     anonymous_answers=True, rotation_mode='mixed',
                     rotation_angles=None, rotation_probability=0.5):
    """Create a new word cloud."""
    try:
        creator = User.query.filter_by(uuid=creator_uuid).first()
        if not creator:
            return {'status': False, 'message': 'Ersteller nicht gefunden.'}

        access_code = _generate_access_code()

        # Validate max_chars_per_answer
        max_chars = max(1, min(100, int(max_chars_per_answer)))

        # Validate rotation settings
        if rotation_mode not in ('mixed', 'horizontal', 'vertical', 'custom'):
            rotation_mode = 'mixed'
        if rotation_angles is None:
            rotation_angles = [0, 90]
        rotation_probability = max(0.0, min(1.0, float(rotation_probability)))

        wc = WordCloud(
            name=name,
            description=description or '',
            access_code=access_code,
            max_answers_per_participant=max_answers,
            case_sensitive=case_sensitive,
            show_results_to_participants=show_results,
            allow_participant_download=allow_participant_download,
            max_chars_per_answer=max_chars,
            anonymous_answers=anonymous_answers,
            rotation_mode=rotation_mode,
            rotation_angles=json.dumps(rotation_angles),
            rotation_probability=rotation_probability,
            creator_uuid=creator_uuid,
            status='active',
        )

        if group_ids:
            groups = Group.query.filter(Group.id.in_(group_ids)).all()
            wc.groups = groups

        db.session.add(wc)
        db.session.commit()

        return {
            'status': True,
            'message': 'Wortwolke erstellt.',
            'wordcloud_id': wc.id,
            'access_code': wc.access_code,
        }
    except Exception as e:
        db.session.rollback()
        print(f'[WordCloud] Create error: {e}')
        return {'status': False, 'message': 'Fehler beim Erstellen.'}


def update_wordcloud(wordcloud_id, data, user_uuid):
    """Update word cloud settings."""
    try:
        wc = WordCloud.query.get(wordcloud_id)
        if not wc:
            return {'status': False, 'message': 'Wortwolke nicht gefunden.'}
        if wc.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}

        if 'name' in data:
            wc.name = data['name']
        if 'description' in data:
            wc.description = data['description']
        if 'max_answers_per_participant' in data:
            wc.max_answers_per_participant = int(data['max_answers_per_participant'])
        if 'case_sensitive' in data:
            wc.case_sensitive = bool(data['case_sensitive'])
        if 'show_results_to_participants' in data:
            wc.show_results_to_participants = bool(data['show_results_to_participants'])
        if 'allow_participant_download' in data:
            wc.allow_participant_download = bool(data['allow_participant_download'])
        if 'max_chars_per_answer' in data:
            wc.max_chars_per_answer = max(1, min(100, int(data['max_chars_per_answer'])))
        if 'anonymous_answers' in data:
            wc.anonymous_answers = bool(data['anonymous_answers'])
        if 'rotation_mode' in data:
            if data['rotation_mode'] in ('mixed', 'horizontal', 'vertical', 'custom'):
                wc.rotation_mode = data['rotation_mode']
        if 'rotation_angles' in data:
            wc.rotation_angles = json.dumps(data['rotation_angles'])
        if 'rotation_probability' in data:
            wc.rotation_probability = max(0.0, min(1.0, float(data['rotation_probability'])))
        if 'group_ids' in data:
            groups = Group.query.filter(Group.id.in_(data['group_ids'])).all()
            wc.groups = groups

        # Bump version so participants detect settings changes
        wc.version = (wc.version or 0) + 1

        db.session.commit()
        return {'status': True, 'message': 'Wortwolke aktualisiert.', 'version': wc.version}
    except Exception as e:
        db.session.rollback()
        print(f'[WordCloud] Update error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def update_wordcloud_status(wordcloud_id, new_status, user_uuid):
    """Change word cloud status (pause/stop/archive/activate)."""
    try:
        wc = WordCloud.query.get(wordcloud_id)
        if not wc:
            return {'status': False, 'message': 'Wortwolke nicht gefunden.'}
        if wc.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}

        valid_transitions = {
            'active': ['paused', 'stopped', 'archived'],
            'paused': ['active', 'stopped', 'archived'],
            'stopped': ['archived'],
            'archived': [],
        }

        if new_status not in valid_transitions.get(wc.status, []):
            return {
                'status': False,
                'message': f'Ungültiger Statuswechsel von "{wc.status}" zu "{new_status}".'
            }

        wc.status = new_status
        # Bump version so participants detect status changes
        wc.version = (wc.version or 0) + 1
        db.session.commit()
        return {'status': True, 'message': f'Status auf "{new_status}" geändert.', 'version': wc.version}
    except Exception as e:
        db.session.rollback()
        print(f'[WordCloud] Status error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def delete_wordcloud(wordcloud_id, user_uuid):
    """Soft-delete a word cloud."""
    try:
        wc = WordCloud.query.get(wordcloud_id)
        if not wc:
            return {'status': False, 'message': 'Wortwolke nicht gefunden.'}
        if wc.creator_uuid != user_uuid:
            return {'status': False, 'message': 'Keine Berechtigung.'}

        wc.is_deleted = True
        wc.deleted_at = datetime.now(timezone.utc)
        wc.deleted_by = user_uuid
        db.session.commit()
        return {'status': True, 'message': 'Wortwolke gelöscht.'}
    except Exception as e:
        db.session.rollback()
        print(f'[WordCloud] Delete error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def submit_word(wordcloud_id, user_uuid, word):
    """Submit a word to a word cloud."""
    try:
        wc = WordCloud.query.get(wordcloud_id)
        if not wc:
            return {'status': False, 'message': 'Wortwolke nicht gefunden.'}

        # Check status
        if wc.status != 'active':
            if wc.status == 'paused':
                return {'status': False, 'message': 'Die Wortwolke ist pausiert. Bitte warten Sie.'}
            return {'status': False, 'message': 'Die Wortwolke akzeptiert keine Beiträge mehr.'}

        # Check group membership
        if wc.groups:
            user = User.query.filter_by(uuid=user_uuid).first()
            if not user:
                return {'status': False, 'message': 'Benutzer nicht gefunden.'}
            user_group_ids = {g.id for g in user.groups}
            wc_group_ids = {g.id for g in wc.groups}
            if not (user_group_ids & wc_group_ids):
                return {'status': False, 'message': 'Sie sind nicht berechtigt teilzunehmen.'}

        # Check answer limit
        if wc.max_answers_per_participant > 0:
            existing_count = WordCloudSubmission.query.filter_by(
                wordcloud_id=wordcloud_id,
                user_uuid=user_uuid
            ).count()
            if existing_count >= wc.max_answers_per_participant:
                return {
                    'status': False,
                    'message': f'Sie haben die maximale Anzahl von {wc.max_answers_per_participant} Antworten erreicht.'
                }

        # Clean word
        word = word.strip()
        if not word:
            return {'status': False, 'message': 'Bitte geben Sie ein Wort ein.'}
        max_chars = wc.max_chars_per_answer if wc.max_chars_per_answer else 100
        if len(word) > max_chars:
            return {'status': False, 'message': f'Das Wort darf maximal {max_chars} Zeichen lang sein.'}

        submission = WordCloudSubmission(
            wordcloud_id=wordcloud_id,
            user_uuid=user_uuid,
            word=word,
            is_anonymous=bool(wc.anonymous_answers),
        )
        db.session.add(submission)

        # Increment version for optimistic polling
        wc.version = (wc.version or 0) + 1

        db.session.commit()

        # Return current word count for the user
        user_count = WordCloudSubmission.query.filter_by(
            wordcloud_id=wordcloud_id,
            user_uuid=user_uuid
        ).count()

        return {
            'status': True,
            'message': 'Wort eingereicht.',
            'user_submission_count': user_count,
            'version': wc.version,
        }
    except Exception as e:
        db.session.rollback()
        print(f'[WordCloud] Submit error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}


def get_wordcloud_results(wordcloud_id):
    """Get aggregated word frequencies for a word cloud."""
    try:
        wc = WordCloud.query.get(wordcloud_id)
        if not wc:
            return {'status': False, 'message': 'Wortwolke nicht gefunden.'}

        result = {
            'status': True,
            'words': wc._aggregate_words(),
            'total_submissions': len(wc.submissions),
            'unique_words': wc._count_unique_words(),
            'wc_status': wc.status,
            'version': wc.version,
        }
        if not wc.anonymous_answers:
            result['submissions_detail'] = wc._get_submissions_detail()
        return result
    except Exception as e:
        print(f'[WordCloud] Results error: {e}')
        return {'status': False, 'message': 'Ein Fehler ist aufgetreten.'}

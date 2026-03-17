# TeacherTools Module - Word Cloud Database Models
from src.db import db
from datetime import datetime, timezone
import json
from src.utils import utc_isoformat


# ── Association Tables ──────────────────────────────────────────────

wordcloud_group_association = db.Table(
    'wordcloud_group_association',
    db.Column('wordcloud_id', db.Integer, db.ForeignKey('word_cloud.id', ondelete='CASCADE')),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id', ondelete='CASCADE'))
)


# ── Word Cloud ──────────────────────────────────────────────────────

class WordCloud(db.Model):
    __tablename__ = 'word_cloud'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default='')
    access_code = db.Column(db.String(12), unique=True, nullable=False)

    # Settings
    max_answers_per_participant = db.Column(db.Integer, nullable=False, default=0)  # 0 = unlimited
    case_sensitive = db.Column(db.Boolean, default=False)
    show_results_to_participants = db.Column(db.Boolean, default=False)
    allow_participant_download = db.Column(db.Boolean, default=False)
    max_chars_per_answer = db.Column(db.Integer, nullable=False, default=20)  # 1-100
    anonymous_answers = db.Column(db.Boolean, default=True)

    # Version counter – incremented on each submission for optimistic polling
    version = db.Column(db.Integer, nullable=False, default=0)

    # Advanced d3-cloud settings (stored as JSON string)
    # rotation_mode: "mixed" | "horizontal" | "vertical" | "custom"
    rotation_mode = db.Column(db.String(20), nullable=False, default='mixed')
    # rotation_angles: JSON list of angles, e.g. [0, 90] or [-45, 0, 45]
    rotation_angles = db.Column(db.Text, nullable=False, default='[0, 90]')
    # rotation_probability: 0.0–1.0, probability of applying rotation (for "mixed" mode)
    rotation_probability = db.Column(db.Float, nullable=False, default=0.5)

    # Status: active, paused, stopped, archived
    status = db.Column(db.String(20), nullable=False, default='active')

    # Creator
    creator_uuid = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=False)
    creator = db.relationship('User', foreign_keys=[creator_uuid],
                              backref=db.backref('created_wordclouds', lazy='dynamic'))

    # Groups allowed to participate
    groups = db.relationship('Group', secondary=wordcloud_group_association,
                             backref=db.backref('wordclouds', lazy='dynamic'))

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=True)

    # Submissions
    submissions = db.relationship('WordCloudSubmission', back_populates='wordcloud',
                                  cascade='all, delete-orphan')

    def _parse_rotation_angles(self):
        try:
            return json.loads(self.rotation_angles)
        except (json.JSONDecodeError, TypeError):
            return [0, 90]

    def to_dict(self, include_submissions=False):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'access_code': self.access_code,
            'max_answers_per_participant': self.max_answers_per_participant,
            'case_sensitive': self.case_sensitive,
            'show_results_to_participants': self.show_results_to_participants,
            'allow_participant_download': self.allow_participant_download,
            'max_chars_per_answer': self.max_chars_per_answer,
            'anonymous_answers': self.anonymous_answers,
            'version': self.version,
            'rotation_mode': self.rotation_mode,
            'rotation_angles': self._parse_rotation_angles(),
            'rotation_probability': self.rotation_probability,
            'status': self.status,
            'creator_uuid': self.creator_uuid,
            'creator_name': self.creator.username if self.creator else None,
            'groups': [{'id': g.id, 'name': g.name} for g in self.groups],
            'created_at': utc_isoformat(self.created_at),
            'updated_at': utc_isoformat(self.updated_at),
            'submission_count': len(self.submissions),
            'unique_words': self._count_unique_words(),
            'is_deleted': self.is_deleted,
        }
        if include_submissions:
            data['words'] = self._aggregate_words()
            data['submissions_detail'] = self._get_submissions_detail()
        return data

    def _count_unique_words(self):
        words = set()
        for s in self.submissions:
            w = s.word if self.case_sensitive else s.word.lower()
            words.add(w)
        return len(words)

    def _aggregate_words(self):
        """Aggregate submissions into word frequency dict."""
        freq = {}
        for s in self.submissions:
            w = s.word if self.case_sensitive else s.word.lower()
            freq[w] = freq.get(w, 0) + 1
        return [{'text': word, 'value': count} for word, count in freq.items()]

    def _get_submissions_detail(self):
        """Return submissions with submitter info (for identified/non-anonymous mode).
        Submissions marked as is_anonymous=True will show 'Anonym' instead of the real name."""
        details = []
        for s in self.submissions:
            details.append({
                'word': s.word,
                'user_name': 'Anonym' if s.is_anonymous else (s.user.username if s.user else 'Unbekannt'),
                'is_anonymous': s.is_anonymous,
                'submitted_at': utc_isoformat(s.submitted_at),
            })
        return details


# ── Word Cloud Submission ───────────────────────────────────────────

class WordCloudSubmission(db.Model):
    __tablename__ = 'word_cloud_submission'

    id = db.Column(db.Integer, primary_key=True)
    wordcloud_id = db.Column(db.Integer, db.ForeignKey('word_cloud.id', ondelete='CASCADE'), nullable=False)
    user_uuid = db.Column(db.String, db.ForeignKey('user.uuid'), nullable=False)
    word = db.Column(db.String(100), nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    wordcloud = db.relationship('WordCloud', back_populates='submissions')
    user = db.relationship('User', backref=db.backref('wordcloud_submissions', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'wordcloud_id': self.wordcloud_id,
            'user_uuid': self.user_uuid,
            'word': self.word,
            'submitted_at': utc_isoformat(self.submitted_at),
        }

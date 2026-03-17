# Assistant Module - Database Models: Chat Message
from src.db import db
from datetime import datetime, timezone
import json
from src.utils import utc_isoformat


class ChatMessage(db.Model):
    """A single message in a chat session (user or assistant)."""
    __tablename__ = 'assistant_chat_message'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('assistant_chat_session.id', ondelete='CASCADE'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    message = db.Column(db.Text, nullable=False)
    sources_json = db.Column(db.Text, default='[]')  # JSON array of source references
    feedback = db.Column(db.String(20), nullable=True)  # 'helpful', 'incorrect', or None
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    session = db.relationship('ChatSession', back_populates='messages')

    @property
    def sources(self):
        try:
            return json.loads(self.sources_json) if self.sources_json else []
        except (json.JSONDecodeError, TypeError):
            return []

    @sources.setter
    def sources(self, value):
        self.sources_json = json.dumps(value) if value else '[]'

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'role': self.role,
            'message': self.message,
            'sources': self.sources,
            'feedback': self.feedback,
            'created_at': utc_isoformat(self.created_at),
        }

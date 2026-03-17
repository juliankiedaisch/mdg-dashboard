# Assistant Module - Database Models: Chat Session
from src.db import db
from datetime import datetime, timezone
import uuid as uuid_lib
from src.utils import utc_isoformat


class ChatSession(db.Model):
    """Represents a chat conversation between a user and the AI assistant."""
    __tablename__ = 'assistant_chat_session'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    user_id = db.Column(db.String, nullable=False, index=True)
    title = db.Column(db.String(255), default='New Chat')
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    messages = db.relationship('ChatMessage', back_populates='session', lazy='dynamic',
                               order_by='ChatMessage.created_at')

    def to_dict(self):
        return {
            'id': self.id,
            'uuid': self.uuid,
            'user_id': self.user_id,
            'title': self.title,
            'is_archived': self.is_archived,
            'created_at': utc_isoformat(self.created_at),
            'updated_at': utc_isoformat(self.updated_at),
        }

    def to_dict_with_messages(self):
        data = self.to_dict()
        data['messages'] = [m.to_dict() for m in self.messages.all()]
        return data

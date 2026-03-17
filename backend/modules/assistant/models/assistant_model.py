# Assistant Module - Database Models: Assistant Model Configuration
from src.db import db
from datetime import datetime, timezone
from src.utils import utc_isoformat


class AssistantModel(db.Model):
    """Stores the assistant's model configuration (which Ollama models to use)."""
    __tablename__ = 'assistant_model_config'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)  # e.g. 'llm_model', 'embedding_model'
    value = db.Column(db.String(500), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'updated_at': utc_isoformat(self.updated_at),
        }


class AssistantLog(db.Model):
    """Logging table for assistant operations."""
    __tablename__ = 'assistant_log'

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)  # 'query', 'sync', 'error', 'model'
    message = db.Column(db.Text, nullable=False)
    details_json = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'event_type': self.event_type,
            'message': self.message,
            'details': json.loads(self.details_json) if self.details_json else None,
            'user_id': self.user_id,
            'created_at': utc_isoformat(self.created_at),
        }

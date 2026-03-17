# Assistant Module - Database Models: Source Configuration
from src.db import db
from datetime import datetime, timezone
import json
from src.utils import utc_isoformat


class SourceConfig(db.Model):
    """Configuration for a knowledge source (BookStack, filesystem, etc.)."""
    __tablename__ = 'assistant_source_config'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    source_type = db.Column(db.String(50), nullable=False)  # 'bookstack', 'filesystem'
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    config_json = db.Column(db.Text, default='{}')  # JSON config specific to source type
    last_sync_at = db.Column(db.DateTime, nullable=True)
    last_sync_status = db.Column(db.String(50), nullable=True)  # 'success', 'error', 'running'
    last_sync_message = db.Column(db.Text, nullable=True)
    document_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    @property
    def config(self):
        try:
            return json.loads(self.config_json) if self.config_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @config.setter
    def config(self, value):
        self.config_json = json.dumps(value) if value else '{}'

    @property
    def tag_names(self):
        """Return list of tag names for this source."""
        return [t.name for t in self.tags] if self.tags else []

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'source_type': self.source_type,
            'enabled': self.enabled,
            'config': self.config,
            'last_sync_at': utc_isoformat(self.last_sync_at),
            'last_sync_status': self.last_sync_status,
            'last_sync_message': self.last_sync_message,
            'document_count': self.document_count,
            'created_at': utc_isoformat(self.created_at),
            'updated_at': utc_isoformat(self.updated_at),
            'tags': [{'id': t.id, 'name': t.name} for t in self.tags] if self.tags else [],
        }

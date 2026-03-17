# Assistant Module - Database Models: Persistent Sync Task
"""
Tracks ingestion/sync tasks in the database so they survive restarts.
"""
import json
from src.db import db
from datetime import datetime, timezone
from src.utils import utc_isoformat


class SyncTask(db.Model):
    """Persistent record of a sync/ingestion task.

    Lifecycle: pending → running → completed / error / interrupted
    On startup, any tasks in 'running' state are treated as interrupted
    and automatically re-queued.
    """
    __tablename__ = 'assistant_sync_task'

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, nullable=False, index=True)
    task_type = db.Column(db.String(30), nullable=False)  # 'sync', 'rebuild', 'full_rebuild'
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    # status values: pending | running | completed | error | interrupted | cancelled

    progress_json = db.Column(db.Text, nullable=True)
    # JSON: {documents_processed, chunks_stored, message, ...}

    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)

    @property
    def progress(self):
        try:
            return json.loads(self.progress_json) if self.progress_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @progress.setter
    def progress(self, value):
        self.progress_json = json.dumps(value) if value else None

    def to_dict(self):
        return {
            'id': self.id,
            'source_id': self.source_id,
            'task_type': self.task_type,
            'status': self.status,
            'progress': self.progress,
            'message': self.message,
            'created_at': utc_isoformat(self.created_at),
            'started_at': utc_isoformat(self.started_at),
            'completed_at': utc_isoformat(self.completed_at),
            'retry_count': self.retry_count,
        }

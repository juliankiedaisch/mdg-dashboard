# Assistant Module - Database Models: Pipeline Event
"""
Persistent log of every progress event emitted during ingestion.

Each ``emit_progress()`` call writes one row so the admin dashboard can
display a complete history instead of only messages received while the
page is open.
"""
import json
from datetime import datetime, timezone

from src.db import db
from src.utils import utc_isoformat


class PipelineEvent(db.Model):
    """One persisted progress event from the ingestion pipeline.

    Columns
    -------
    id          Auto-increment PK; used as a monotonically increasing
                sequence number for frontend de-duplication.
    task_id     Foreign key to ``assistant_sync_task.id`` (nullable –
                some worker-level events exist outside a task).
    stage       Pipeline stage: fetch / chunk / embed / store / worker /
                error / cancel.
    message     Human-readable status string.
    level       Severity: info / warning / error / success.
    source_name Name of the source being processed (if any).
    detail_json Extra JSON payload (counts, durations, …).
    progress    0.0–1.0 completion fraction for the current sub-step.
    ts          Unix float timestamp from the emitter (``time.time()``).
    created_at  Server-side insert timestamp (indexed for range queries).
    """
    __tablename__ = 'assistant_pipeline_events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(
        db.Integer,
        db.ForeignKey('assistant_sync_task.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    stage = db.Column(db.String(32), nullable=False)
    message = db.Column(db.Text, nullable=False)
    level = db.Column(db.String(16), nullable=False, default='info')
    source_name = db.Column(db.String(256), nullable=True)
    detail_json = db.Column(db.Text, nullable=True)
    progress = db.Column(db.Float, nullable=True)
    ts = db.Column(db.Float, nullable=False)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # ── convenience property ─────────────────────────────────────────
    @property
    def detail(self):
        try:
            return json.loads(self.detail_json) if self.detail_json else None
        except (json.JSONDecodeError, TypeError):
            return None

    @detail.setter
    def detail(self, value):
        self.detail_json = json.dumps(value) if value is not None else None

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'stage': self.stage,
            'message': self.message,
            'level': self.level,
            'source_name': self.source_name,
            'detail': self.detail,
            'progress': self.progress,
            'timestamp': self.ts,
            'created_at': utc_isoformat(self.created_at),
        }

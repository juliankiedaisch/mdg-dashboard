# Assistant Module - Database Models: Scheduled Sync Job
"""
Configurable per-source automatic sync schedules.
Supports daily (at a specific time) and weekly (at a specific day + time).
"""
import json
from src.db import db
from datetime import datetime, timezone
from src.utils import utc_isoformat


class ScheduledSync(db.Model):
    """A recurring sync schedule for a specific source.

    Multiple schedules per source are allowed (e.g. daily at 6:00 AM
    and weekly on Sundays at 2:00 AM).

    Fields
    ------
    frequency : str
        ``'daily'`` or ``'weekly'``.
    time_of_day : str
        ``'HH:MM'`` in 24-hour format (e.g. ``'06:00'``).
    day_of_week : int or None
        0 = Monday … 6 = Sunday.  Only used when ``frequency == 'weekly'``.
    active : bool
        Whether this schedule is currently enabled.
    last_run_at : datetime or None
        Timestamp of the last execution (UTC).
    next_run_at : datetime or None
        Precomputed next execution time (UTC).  Updated by the scheduler
        after each run or when the schedule is modified.
    """
    __tablename__ = 'assistant_scheduled_sync'

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, nullable=False, index=True)
    frequency = db.Column(db.String(20), nullable=False)  # 'daily' | 'weekly'
    time_of_day = db.Column(db.String(5), nullable=False)  # 'HH:MM'
    day_of_week = db.Column(db.Integer, nullable=True)  # 0-6, Mon-Sun; NULL for daily
    active = db.Column(db.Boolean, nullable=False, default=True)
    last_run_at = db.Column(db.DateTime, nullable=True)
    last_run_status = db.Column(db.String(50), nullable=True)
    last_run_message = db.Column(db.Text, nullable=True)
    next_run_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'source_id': self.source_id,
            'frequency': self.frequency,
            'time_of_day': self.time_of_day,
            'day_of_week': self.day_of_week,
            'active': self.active,
            'last_run_at': utc_isoformat(self.last_run_at),
            'last_run_status': self.last_run_status,
            'last_run_message': self.last_run_message,
            'next_run_at': utc_isoformat(self.next_run_at),
            'created_at': utc_isoformat(self.created_at),
            'updated_at': utc_isoformat(self.updated_at),
        }

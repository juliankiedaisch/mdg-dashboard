"""Shared utility functions."""
from datetime import datetime, timezone


def utc_isoformat(dt):
    """Convert a datetime to an ISO-8601 string with explicit UTC offset.

    SQLAlchemy's ``db.Column(db.DateTime)`` strips timezone info, so naive
    datetimes serialized via ``.isoformat()`` lack the ``+00:00`` suffix.
    Browsers then interpret such strings as *local* time, which causes a
    1–2 hour display offset in CET/CEST.

    This helper ensures the serialized string always ends with ``+00:00``
    so ``new Date(...)`` in the browser parses it as UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume naive datetimes are stored as UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

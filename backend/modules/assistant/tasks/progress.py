# Assistant Module - Tasks: Progress Emitter
"""
Real-time progress updates via Flask-SocketIO, with DB persistence.

All pipeline stages (fetch → chunk → embed → store) call ``emit_progress()``
to push structured updates to connected admin clients.  Every event is also
persisted to ``assistant_pipeline_events`` so the admin dashboard can display
a complete activity history when the page loads (not just live messages).

The frontend Pipeline tab listens on the ``assistant_progress`` SocketIO event
and de-duplicates incoming messages by the ``id`` field (DB primary key).
"""
import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Global references – set once by ``init_progress(socketio, app)``
_socketio = None
_app = None


def init_progress(socketio, app=None):
    """Store references to the SocketIO instance and Flask app.

    Parameters
    ----------
    socketio : flask_socketio.SocketIO
        The application SocketIO instance.
    app : Flask, optional
        The Flask application object (needed for DB writes in background
        greenlets that may not have an active app context).
    """
    global _socketio, _app
    _socketio = socketio
    _app = app
    logger.info("[Progress] Initialized SocketIO progress emitter")


def _persist_event(stage, message, level, ts, task_id, source_name, detail, progress):
    """Write one PipelineEvent row and return its auto-assigned id.

    Returns ``None`` on any error so callers can continue safely.
    The call is always wrapped in its own try/except so a DB failure
    never breaks the pipeline.
    """
    try:
        from src.db import db
        from modules.assistant.models.pipeline_event import PipelineEvent

        evt = PipelineEvent(
            task_id=task_id,
            stage=stage,
            message=message,
            level=level,
            source_name=source_name,
            progress=round(progress, 3) if progress is not None else None,
            ts=ts,
        )
        if detail is not None:
            evt.detail = detail

        db.session.add(evt)
        db.session.commit()

        # Prune: keep only the last 1 000 events to cap table growth.
        try:
            cutoff = (
                db.session.query(PipelineEvent.id)
                .order_by(PipelineEvent.id.desc())
                .offset(999)
                .limit(1)
                .scalar()
            )
            if cutoff is not None:
                db.session.query(PipelineEvent).filter(
                    PipelineEvent.id < cutoff
                ).delete(synchronize_session=False)
                db.session.commit()
        except Exception:
            db.session.rollback()

        return evt.id

    except Exception as exc:
        logger.debug("[Progress] DB persist failed: %s", exc)
        try:
            from src.db import db
            db.session.rollback()
        except Exception:
            pass
        return None


def emit_progress(
    stage: str,
    message: str,
    *,
    task_id: Optional[int] = None,
    source_name: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    progress: Optional[float] = None,
    level: str = 'info',
):
    """Emit a progress event to all connected admin clients and persist it.

    Parameters
    ----------
    stage : str
        Pipeline stage identifier, e.g. ``'fetch'``, ``'chunk'``,
        ``'embed'``, ``'store'``, ``'worker'``, ``'error'``.
    message : str
        Human-readable status message (German OK).
    task_id : int, optional
        The current SyncTask id.
    source_name : str, optional
        The source being processed.
    detail : dict, optional
        Extra structured data (counts, durations, ...).
    progress : float, optional
        0.0 – 1.0 completion fraction for the current sub-step.
    level : str
        ``'info'``, ``'warning'``, ``'error'``, ``'success'``.
    """
    ts = time.time()
    payload = {
        'stage': stage,
        'message': message,
        'level': level,
        'timestamp': ts,
    }
    if task_id is not None:
        payload['task_id'] = task_id
    if source_name:
        payload['source_name'] = source_name
    if detail:
        payload['detail'] = detail
    if progress is not None:
        payload['progress'] = round(progress, 3)

    # ── Persist to DB ────────────────────────────────────────────────
    # Always attempt persistence; failures are silently logged so the
    # pipeline is never interrupted by a DB issue.
    event_id = None
    if _app is not None:
        try:
            with _app.app_context():
                event_id = _persist_event(
                    stage, message, level, ts,
                    task_id, source_name, detail, progress
                )
        except Exception as exc:
            logger.debug("[Progress] app_context persist failed: %s", exc)
    else:
        # Already inside an app context (e.g. called from a request handler)
        event_id = _persist_event(
            stage, message, level, ts,
            task_id, source_name, detail, progress
        )

    # Include DB id in payload for frontend deduplication
    if event_id is not None:
        payload['id'] = event_id

    if _socketio is None:
        logger.debug("[Progress] SocketIO not initialized, skipping emit: %s", message)
        return

    try:
        _socketio.emit('assistant_progress', payload, namespace='/main')
    except Exception as e:
        # Never let a failed emit break the pipeline
        logger.debug("[Progress] Emit failed: %s", e)

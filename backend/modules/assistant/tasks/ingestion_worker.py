# Assistant Module - Tasks: Ingestion Worker
"""
Background worker for document ingestion tasks.

Tasks are persisted in the ``assistant_sync_task`` database table so they
survive process restarts.  On startup the worker:
  1. Marks any previously ``running`` tasks as ``interrupted``.
  2. Re-queues interrupted tasks automatically (up to 3 retries).
  3. Processes pending tasks sequentially.

Concurrency model
-----------------
The worker runs as a **gevent greenlet** (spawned in ``assistant.py``).
All I/O — HTTP requests to Ollama / BookStack, database queries via
SQLAlchemy, and ``gevent.sleep()`` — yields cooperatively so the Flask
request-handling greenlets are never blocked by the worker.

A ``gevent.event.Event`` is used instead of ``threading.Event`` so that
the wait/set semantics are explicitly cooperative.
"""
import logging
import gevent
import gevent.event
import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Lightweight in-memory flag so the polling loop can be nudged immediately
# when a new task is enqueued (avoids waiting for the next poll interval).
_new_task_event = gevent.event.Event()

# In-memory snapshot of the currently running task for fast /queue reads.
_current_task: Optional[Dict[str, Any]] = None

# Set to True to signal the worker to abandon its current task and skip pending ones.
_cancel_requested: bool = False

MAX_RETRIES = 3

# Maximum wall-clock time a single task may run before being considered stuck.
# Default: 4 hours — generous enough for very large sources, but prevents
# infinite hangs.
JOB_TIMEOUT_SECONDS = int(__import__('os').getenv('PIPELINE_JOB_TIMEOUT', '14400'))


def check_cancel_requested() -> bool:
    """Non-destructive read of the cancellation flag.

    Unlike the old ``is_cancel_requested()``, this does NOT clear the flag.
    The flag stays set until explicitly cleared via ``clear_cancel_flag()``.
    This allows the flag to be checked repeatedly inside the pipeline
    (embedding loop, batch flush, document loop) without losing the signal.
    """
    return _cancel_requested


def clear_cancel_flag():
    """Clear the cancellation flag after the cancellation has been handled."""
    global _cancel_requested
    _cancel_requested = False


# ── Public API ──────────────────────────────────────────────────────

def enqueue_ingestion(source_id: int, task_type: str = 'sync',
                      source_config: Dict = None) -> Dict:
    """Persist a new ingestion task and notify the worker thread.

    Deduplication: if a task with the same source_id already has status
    ``pending`` or ``running``, the duplicate is silently dropped and the
    existing task dict is returned.  This prevents the scheduler from
    stacking up identical sync jobs when ingestion is still in progress.
    """
    from modules.assistant.models.sync_task import SyncTask
    from src.db import db

    # Guard: one active task per source at a time
    existing = SyncTask.query.filter(
        SyncTask.source_id == source_id,
        SyncTask.status.in_(['pending', 'running']),
    ).first()
    if existing:
        logger.info(
            "[Worker] Skipping duplicate %s task for source %d — "
            "task id=%d is already '%s'",
            task_type, source_id, existing.id, existing.status,
        )
        return existing.to_dict()

    task = SyncTask(
        source_id=source_id,
        task_type=task_type,
        status='pending',
    )
    db.session.add(task)
    db.session.commit()

    logger.info("[Worker] Enqueued %s task id=%d for source %d",
                task_type, task.id, source_id)

    # Wake the worker loop immediately
    _new_task_event.set()
    return task.to_dict()


def get_queue_status() -> Dict[str, Any]:
    """Return current queue status (reads from DB)."""
    try:
        from modules.assistant.models.sync_task import SyncTask
        pending = (SyncTask.query
                   .filter(SyncTask.status.in_(['pending']))
                   .order_by(SyncTask.created_at)
                   .all())
        return {
            'pending_tasks': len(pending),
            'tasks': [t.to_dict() for t in pending],
            'current_task': _current_task,
        }
    except Exception as e:
        logger.error("[Worker] get_queue_status error: %s", e)
        return {'pending_tasks': 0, 'tasks': [], 'current_task': _current_task}


def cancel_all_tasks(app) -> Dict[str, Any]:
    """Signal the worker to stop its current job and mark all pending/running
    tasks as ``cancelled`` in the database.

    The flag is NOT cleared here when a task is actually running —
    ``clear_cancel_flag()`` is called by the worker loop once it has actually
    stopped the current job so that any tasks enqueued *after* the
    cancellation are processed normally.

    If no task is currently running the flag is cleared immediately to avoid
    falsely cancelling future tasks.
    """
    global _cancel_requested
    _cancel_requested = True
    # Wake the worker so it sees the flag immediately instead of waiting
    _new_task_event.set()

    cancelled = 0
    had_running = False
    try:
        with app.app_context():
            from modules.assistant.models.sync_task import SyncTask
            from modules.assistant.tasks.progress import emit_progress
            from src.db import db

            tasks = SyncTask.query.filter(
                SyncTask.status.in_(['pending', 'running'])
            ).all()
            cancelled = len(tasks)
            now = datetime.now(timezone.utc)
            for t in tasks:
                if t.status == 'running':
                    had_running = True
                t.status = 'cancelled'
                t.message = 'Abgebrochen durch Benutzeranfrage.'
                t.completed_at = now
            db.session.commit()
            db.session.remove()

            emit_progress('worker',
                          f"{cancelled} Aufgabe(n) abgebrochen.",
                          level='warning')
            logger.info("[Worker] cancel_all_tasks: cancelled %d task(s)", cancelled)
    except Exception as e:
        logger.error("[Worker] cancel_all_tasks error: %s", e)

    # If no task was actually running in the pipeline, clear the flag now.
    # Otherwise the worker loop / PipelineCancelledError handler will clear it.
    if not had_running:
        clear_cancel_flag()

    return {'cancelled': cancelled}


def cancel_single_task(app, task_id: int) -> Dict[str, Any]:
    """Cancel a single task by its ID.

    If the task is currently running, set the cancel flag so the pipeline
    aborts gracefully.  If it's pending, simply mark it as cancelled.

    Returns a dict with 'cancelled' (bool) and 'message'.
    """
    global _cancel_requested

    try:
        with app.app_context():
            from modules.assistant.models.sync_task import SyncTask
            from modules.assistant.tasks.progress import emit_progress
            from src.db import db

            task = SyncTask.query.get(task_id)
            if not task:
                return {'cancelled': False, 'message': f'Task {task_id} nicht gefunden.'}

            if task.status not in ('pending', 'running'):
                return {'cancelled': False,
                        'message': f'Task {task_id} hat Status \'{task.status}\' und kann nicht abgebrochen werden.'}

            was_running = task.status == 'running'

            task.status = 'cancelled'
            task.message = 'Einzeln abgebrochen durch Benutzeranfrage.'
            task.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            db.session.remove()

            if was_running:
                # Signal the worker to stop the current pipeline run
                _cancel_requested = True
                _new_task_event.set()

            emit_progress('worker',
                          f"Task {task_id} abgebrochen.",
                          task_id=task_id,
                          level='warning')
            logger.info("[Worker] cancel_single_task: task id=%d cancelled "
                        "(was_running=%s)", task_id, was_running)

            return {'cancelled': True,
                    'message': f'Task {task_id} abgebrochen.',
                    'task_id': task_id}

    except Exception as e:
        logger.error("[Worker] cancel_single_task error: %s", e)
        return {'cancelled': False, 'message': str(e)}


def is_cancel_requested() -> bool:
    """Legacy alias — use ``check_cancel_requested()`` for non-destructive reads.

    Kept for backwards compatibility; clears the flag on first True return.
    The worker loop now uses ``check_cancel_requested()`` + ``clear_cancel_flag()``
    so that the flag survives multiple in-pipeline checks.
    """
    global _cancel_requested
    if _cancel_requested:
        _cancel_requested = False
        return True
    return False


# ── Startup recovery ───────────────────────────────────────────────

def _recover_interrupted_tasks(app):
    """Mark ``running`` tasks as ``interrupted`` and re-queue them.

    Called once at startup before the worker loop begins processing.

    Also cleans up stale ``pending`` tasks whose source no longer exists or
    is disabled, and validates source existence before re-queuing interrupted
    tasks.
    """
    with app.app_context():
        from modules.assistant.models.sync_task import SyncTask
        from modules.assistant.services.source_service import get_source
        from modules.assistant.dashboard.metrics_service import add_log
        from src.db import db

        # ── 1. Handle tasks that were 'running' when we crashed ─────
        running = SyncTask.query.filter_by(status='running').all()
        re_queued = 0
        for task in running:
            task.status = 'interrupted'
            task.message = 'Interrupted by service restart'
            task.completed_at = datetime.now(timezone.utc)
            logger.warning("[Worker] Task id=%d (%s, source=%d) was running "
                           "during restart — marking interrupted",
                           task.id, task.task_type, task.source_id)

            # Re-queue unless max retries exceeded
            if task.retry_count < MAX_RETRIES:
                # Validate source still exists before re-queuing
                # (full_rebuild uses source_id=0 — always valid)
                if task.source_id != 0:
                    source = get_source(task.source_id)
                    if not source:
                        task.status = 'error'
                        task.message = (
                            f'Source {task.source_id} no longer exists — '
                            f'not re-queuing')
                        logger.warning(
                            "[Worker] Task id=%d references missing source %d "
                            "— not re-queuing", task.id, task.source_id)
                        continue

                new_task = SyncTask(
                    source_id=task.source_id,
                    task_type=task.task_type,
                    status='pending',
                    retry_count=task.retry_count + 1,
                    message=f'Resumed after restart (retry #{task.retry_count + 1})',
                )
                db.session.add(new_task)
                re_queued += 1
                logger.info("[Worker] Re-queued interrupted task id=%d as new "
                            "pending task (retry #%d)",
                            task.id, new_task.retry_count)
            else:
                task.status = 'error'
                task.message = f'Exceeded max retry count ({MAX_RETRIES}) after interruptions'
                logger.warning("[Worker] Task id=%d exceeded max retries — "
                               "marking as error", task.id)

        if running:
            db.session.commit()
            add_log('sync_recovery',
                    f"{len(running)} interrupted task(s) detected after restart, "
                    f"{re_queued} re-queued",
                    {'task_ids': [t.id for t in running],
                     're_queued': re_queued})
            logger.info("[Worker] Recovered %d interrupted task(s), "
                        "re-queued %d", len(running), re_queued)

        # ── 2. Clean up stale pending tasks for missing sources ─────
        pending = SyncTask.query.filter_by(status='pending').all()
        stale_count = 0
        for task in pending:
            if task.source_id == 0:
                continue  # full_rebuild is always valid
            source = get_source(task.source_id)
            if not source:
                task.status = 'error'
                task.message = (
                    f'Source {task.source_id} no longer exists — '
                    f'removed stale pending task')
                task.completed_at = datetime.now(timezone.utc)
                stale_count += 1
                logger.warning(
                    "[Worker] Stale pending task id=%d references missing "
                    "source %d — marking as error", task.id, task.source_id)

        if stale_count:
            db.session.commit()
            logger.info("[Worker] Cleaned up %d stale pending task(s)",
                        stale_count)

        db.session.remove()


# ── Worker loop ─────────────────────────────────────────────────────

def run_ingestion_worker(app):
    """Background worker loop.  Processes tasks from the DB sequentially."""
    global _current_task

    logger.info("[Worker] Ingestion worker starting...")

    # Recover from previous crash / restart
    _recover_interrupted_tasks(app)
    logger.info("[Worker] Ingestion worker ready — polling for tasks")

    while True:
        task_dict = None

        with app.app_context():
            from modules.assistant.models.sync_task import SyncTask
            from src.db import db

            task = (SyncTask.query
                    .filter_by(status='pending')
                    .order_by(SyncTask.created_at)
                    .first())

            if task:
                task.status = 'running'
                task.started_at = datetime.now(timezone.utc)
                db.session.commit()
                task_dict = task.to_dict()

        if task_dict is None:
            # No work — wait for notification or poll every 5s
            _new_task_event.wait(timeout=5)
            _new_task_event.clear()
            continue

        # Check for cancellation before starting the task
        if check_cancel_requested():
            logger.info("[Worker] Cancellation requested — skipping task id=%s",
                        task_dict.get('id', '?') if task_dict else '?')
            # Mark the task as cancelled in DB (it was already set to 'running')
            try:
                with app.app_context():
                    from modules.assistant.models.sync_task import SyncTask
                    from src.db import db
                    db_task = SyncTask.query.get(task_dict['id'])
                    if db_task and db_task.status == 'running':
                        db_task.status = 'cancelled'
                        db_task.message = 'Abgebrochen vor Verarbeitungsbeginn.'
                        db_task.completed_at = datetime.now(timezone.utc)
                        db.session.commit()
                    db.session.remove()
            except Exception as e:
                logger.error("[Worker] Failed to mark skipped task as cancelled: %s", e)
            clear_cancel_flag()
            _current_task = None
            gevent.sleep(0)
            continue

        task_id = task_dict['id']

        # Re-check task status from DB to guard against race condition with
        # cancel_single_task() running in a parallel request greenlet.
        try:
            with app.app_context():
                from modules.assistant.models.sync_task import SyncTask
                from src.db import db
                fresh = SyncTask.query.get(task_id)
                if not fresh or fresh.status != 'running':
                    logger.info(
                        "[Worker] Task id=%d status changed to '%s' before "
                        "pipeline start — skipping",
                        task_id, fresh.status if fresh else 'deleted')
                    _current_task = None
                    if check_cancel_requested():
                        clear_cancel_flag()
                    db.session.remove()
                    gevent.sleep(0)
                    continue
                db.session.remove()
        except Exception as e:
            logger.error("[Worker] Race-check failed for task %d: %s", task_id, e)

        _current_task = task_dict
        task_started_at = time.monotonic()
        logger.info("[Worker] Processing task id=%d type=%s source=%d (retry #%d)",
                    task_id, task_dict['task_type'], task_dict['source_id'],
                    task_dict.get('retry_count', 0))

        from modules.assistant.tasks.progress import emit_progress
        emit_progress('worker', f"Task gestartet: {task_dict['task_type']} (Source {task_dict['source_id']})",
                      task_id=task_id, level='info')

        try:
            with app.app_context():
                from modules.assistant.ingestion.pipeline import (
                    IngestionPipeline, PipelineCancelledError,
                )
                from modules.assistant.services.source_service import (
                    get_source, update_sync_status, get_all_sources
                )
                from modules.assistant.dashboard.metrics_service import add_log
                from modules.assistant.models.sync_task import SyncTask
                from src.db import db

                def _timeout_or_cancel_check() -> bool:
                    """Combined check: cancel requested OR job exceeded timeout."""
                    if check_cancel_requested():
                        return True
                    elapsed = time.monotonic() - task_started_at
                    if elapsed > JOB_TIMEOUT_SECONDS:
                        logger.error(
                            "[Worker] Task id=%d exceeded timeout of %ds (elapsed=%.0fs)",
                            task_id, JOB_TIMEOUT_SECONDS, elapsed,
                        )
                        emit_progress(
                            'error',
                            f"Task abgebrochen: Zeitüberschreitung nach {int(elapsed)}s.",
                            task_id=task_id, level='error',
                        )
                        return True
                    return False

                try:
                    # Sync embedding model from DB config to singleton
                    from modules.assistant.services.model_service import get_config_value
                    from modules.assistant.rag.embeddings import get_embedding_service
                    configured_embed = get_config_value('embedding_model', 'nomic-embed-text')
                    embed_svc = get_embedding_service()
                    if embed_svc.model != configured_embed:
                        logger.info("[Worker] Updating embedding model: %s -> %s",
                                    embed_svc.model, configured_embed)
                        embed_svc.set_model(configured_embed)

                    pipeline = IngestionPipeline()

                    if task_dict['task_type'] == 'full_rebuild':
                        # Rebuild all sources — pass cancel_check so every
                        # batch can abort early when cancel is requested.
                        all_sources = get_all_sources()
                        result = pipeline.rebuild_all(
                            all_sources,
                            cancel_check=_timeout_or_cancel_check,
                        )

                        # Persist per-source document counts and sync status
                        for sr in result.get('source_results', []):
                            if sr.get('source_id'):
                                update_sync_status(
                                    sr['source_id'],
                                    status='success' if sr['success'] else 'error',
                                    message=sr['message'],
                                    document_count=sr['documents_processed'],
                                )
                                add_log(
                                    'sync',
                                    f"Full rebuild — {sr['name']}: {sr['message']}",
                                    details=sr,
                                )

                        add_log('sync', f"Full rebuild complete: {result['message']}")
                    else:
                        # Single source sync/rebuild — pass cancel_check
                        source = get_source(task_dict['source_id'])
                        if not source:
                            raise ValueError(
                                f"Source {task_dict['source_id']} not found")

                        incremental = task_dict['task_type'] == 'sync'
                        result = pipeline.ingest_source(
                            source,
                            incremental=incremental,
                            cancel_check=_timeout_or_cancel_check,
                        )

                        # Only update document_count in the DB when documents
                        # were actually processed.  Incremental syncs that find
                        # no new content must NOT reset the count to 0.
                        docs = result.get('documents_processed', 0)
                        doc_count_kwarg = {}
                        if not incremental:
                            # Full rebuild: always set (could be 0 if source empty)
                            doc_count_kwarg['document_count'] = docs
                        elif docs > 0:
                            # Incremental with new docs: update count
                            doc_count_kwarg['document_count'] = docs

                        update_sync_status(
                            task_dict['source_id'],
                            status='success' if result['success'] else 'error',
                            message=result['message'],
                            **doc_count_kwarg,
                        )
                        add_log('sync',
                                f"Source {source['name']}: {result['message']}",
                                details=result)

                    # Mark DB task as completed
                    db_task = SyncTask.query.get(task_id)
                    if db_task and db_task.status != 'cancelled':
                        db_task.status = ('completed' if result.get('success')
                                          else 'error')
                        db_task.message = result.get('message', '')
                        db_task.progress = {
                            'documents_processed': result.get(
                                'documents_processed', 0),
                            'chunks_stored': result.get('chunks_stored', 0),
                        }
                        db_task.completed_at = datetime.now(timezone.utc)
                        db.session.commit()

                    logger.info("[Worker] Task id=%d completed: %s",
                                task_id, result.get('message', ''))

                    elapsed_s = time.monotonic() - task_started_at
                    emit_progress('worker',
                                  f"Task abgeschlossen: {result.get('message', '')} ({int(elapsed_s)}s)",
                                  task_id=task_id,
                                  level='success' if result.get('success') else 'error',
                                  detail={
                                      'documents_processed': result.get('documents_processed', 0),
                                      'chunks_stored': result.get('chunks_stored', 0),
                                      'elapsed_seconds': round(elapsed_s, 1),
                                  })

                    # ── GPU cleanup: unload embedding model from Ollama VRAM ──
                    # Only the chat model should stay resident; embedding and
                    # summarization models are unloaded after each pipeline run
                    # to free GPU memory.
                    try:
                        _unload_pipeline_models()
                    except Exception as unload_err:
                        logger.warning("[Worker] GPU cleanup failed: %s", unload_err)

                except PipelineCancelledError as ce:
                    # Pipeline aborted cleanly due to a cancellation request.
                    logger.info("[Worker] Task id=%d cancelled mid-pipeline: %s",
                                task_id, ce)
                    # Update DB task if it hasn't already been marked cancelled
                    # by cancel_all_tasks() running in a parallel request greenlet.
                    db_task = SyncTask.query.get(task_id)
                    if db_task and db_task.status not in ('cancelled',):
                        db_task.status = 'cancelled'
                        db_task.message = 'Abgebrochen während der Verarbeitung.'
                        db_task.completed_at = datetime.now(timezone.utc)
                        db.session.commit()

                    emit_progress(
                        'worker',
                        'Ingestion abgebrochen — verbleibende Dokumente werden nicht verarbeitet.',
                        task_id=task_id,
                        level='warning',
                    )
                    # Clear the flag so the next legitimately-enqueued task runs.
                    clear_cancel_flag()

                finally:
                    # Always clean up the scoped session so the background
                    # greenlet does not hold locks or stale connections.
                    db.session.remove()

        except Exception as e:
            logger.error("[Worker] Task id=%d error: %s",
                         task_id, e, exc_info=True)
            emit_progress('worker', f"Task fehlgeschlagen: {e}",
                          task_id=task_id, level='error')
            try:
                with app.app_context():
                    from modules.assistant.models.sync_task import SyncTask
                    from src.db import db
                    db_task = SyncTask.query.get(task_id)
                    if db_task and db_task.status not in ('cancelled',):
                        db_task.status = 'error'
                        db_task.message = str(e)
                        db_task.completed_at = datetime.now(timezone.utc)
                        db.session.commit()
                    db.session.remove()
            except Exception:
                pass

        _current_task = None
        # Explicit yield point: give Flask request greenlets a chance to run
        # between tasks, especially after long-running ingestion jobs.
        gevent.sleep(0)


def _unload_pipeline_models():
    """Unload embedding and summarization models from Ollama VRAM.

    Sends a ``keep_alive=0`` request to Ollama for each non-chat model so the
    GPU memory is released.  The chat model is left loaded for low-latency
    responses.
    """
    import requests
    from modules.assistant.services.model_service import get_config_value
    from modules.assistant.rag.embeddings import get_embedding_service

    ollama_url = get_embedding_service().ollama_url
    chat_model = get_config_value('llm_model', 'gemma3:12b')
    embedding_model = get_config_value('embedding_model', 'nomic-embed-text')
    summarization_model = get_config_value('summarization_model', '')

    models_to_unload = set()
    if embedding_model and embedding_model != chat_model:
        models_to_unload.add(embedding_model)
    if summarization_model and summarization_model != chat_model:
        models_to_unload.add(summarization_model)

    for model_name in models_to_unload:
        try:
            resp = requests.post(
                f"{ollama_url}/api/generate",
                json={"model": model_name, "keep_alive": 0},
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info("[Worker] Unloaded model '%s' from VRAM", model_name)
            else:
                logger.warning("[Worker] Unload '%s' returned status %d",
                               model_name, resp.status_code)
        except Exception as e:
            logger.warning("[Worker] Failed to unload model '%s': %s", model_name, e)

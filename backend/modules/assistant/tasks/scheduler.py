# Assistant Module - Tasks: Scheduler
"""
Scheduled tasks for automatic source syncing.

Supports two modes:
1. **Per-source schedules** — configurable daily/weekly sync jobs stored in
   ``assistant_scheduled_sync``.  Each schedule defines a source, frequency
   (daily/weekly), time-of-day, and optional day-of-week.
2. **Global fallback** — if no per-source schedules exist, a global periodic
   sync of all enabled sources runs every ``_FALLBACK_INTERVAL`` seconds
   (same behaviour as the previous implementation).

Uses a gevent greenlet with a periodic sleep loop.  This is the simplest
and most reliable approach because the entire application already runs
under ``gevent.monkey.patch_all()`` — no need for a separate scheduler
library with its own internal thread management.
"""
import logging
import gevent
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Check interval — how often the scheduler wakes up to look for due jobs.
_CHECK_INTERVAL_SECONDS = 30  # 30 seconds

# Fallback global sync interval (used only when NO per-source schedules exist).
_FALLBACK_INTERVAL_SECONDS = 30 * 60  # 30 minutes

# Reference to the scheduler greenlet so it can be stopped cleanly.
_scheduler_greenlet: Optional[gevent.Greenlet] = None


def compute_next_run(frequency: str, time_of_day: str,
                     day_of_week: Optional[int] = None,
                     after: Optional[datetime] = None) -> datetime:
    """Compute the next run datetime (UTC) for a schedule.

    Parameters
    ----------
    frequency : 'daily' | 'weekly'
    time_of_day : 'HH:MM'
    day_of_week : 0-6 (Mon-Sun), required for weekly
    after : base datetime; defaults to now(UTC)
    """
    if after is None:
        after = datetime.now(timezone.utc)

    hour, minute = map(int, time_of_day.split(':'))

    if frequency == 'daily':
        candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= after:
            candidate += timedelta(days=1)
        return candidate

    elif frequency == 'weekly':
        if day_of_week is None:
            day_of_week = 0  # default Monday
        candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Move to the correct day of week
        days_ahead = day_of_week - candidate.weekday()
        if days_ahead < 0 or (days_ahead == 0 and candidate <= after):
            days_ahead += 7
        candidate += timedelta(days=days_ahead)
        return candidate

    else:
        # Unknown frequency — schedule 24h from now as safe fallback
        logger.warning("[Scheduler] Unknown frequency '%s', defaulting to +24h",
                       frequency)
        return after + timedelta(hours=24)


def init_scheduler(app):
    """Start a gevent greenlet that checks for due scheduled syncs."""
    global _scheduler_greenlet

    def _scheduler_loop():
        logger.info("[Scheduler] Started (check interval: %ds, "
                    "fallback global interval: %d min)",
                    _CHECK_INTERVAL_SECONDS,
                    _FALLBACK_INTERVAL_SECONDS // 60)
        _last_fallback_run = datetime.now(timezone.utc)

        while True:
            try:
                gevent.sleep(_CHECK_INTERVAL_SECONDS)
            except gevent.GreenletExit:
                logger.info("[Scheduler] Greenlet received exit signal")
                break

            try:
                _process_due_schedules(app)
            except Exception as e:
                logger.error("[Scheduler] Error in schedule processing: %s",
                             e, exc_info=True)

            # Fallback: global sync when no per-source schedules exist
            try:
                elapsed = (datetime.now(timezone.utc) - _last_fallback_run).total_seconds()
                if elapsed >= _FALLBACK_INTERVAL_SECONDS:
                    _last_fallback_run = datetime.now(timezone.utc)
                    _maybe_fallback_sync(app)
            except Exception as e:
                logger.error("[Scheduler] Fallback sync error: %s", e)

    _scheduler_greenlet = gevent.spawn(_scheduler_loop)
    _scheduler_greenlet.name = 'assistant-scheduler'


def _process_due_schedules(app):
    """Check for due scheduled syncs and enqueue them."""
    now = datetime.now(timezone.utc)

    try:
        with app.app_context():
            from modules.assistant.models.scheduled_sync import ScheduledSync
            from modules.assistant.tasks.ingestion_worker import enqueue_ingestion
            from modules.assistant.services.source_service import get_source
            from modules.assistant.dashboard.metrics_service import add_log
            from src.db import db

            due_schedules = ScheduledSync.query.filter(
                ScheduledSync.active == True,
                ScheduledSync.next_run_at <= now,
            ).all()

            if not due_schedules:
                return

            for schedule in due_schedules:
                source = get_source(schedule.source_id)
                if not source:
                    logger.warning(
                        "[Scheduler] Schedule %d references missing source %d "
                        "— skipping", schedule.id, schedule.source_id)
                    schedule.last_run_status = 'error'
                    schedule.last_run_message = (
                        f'Source {schedule.source_id} not found')
                    schedule.next_run_at = compute_next_run(
                        schedule.frequency, schedule.time_of_day,
                        schedule.day_of_week, after=now)
                    continue

                if not source.get('enabled', False):
                    logger.info(
                        "[Scheduler] Source %d (%s) is disabled — "
                        "skipping scheduled sync %d",
                        schedule.source_id, source.get('name', '?'),
                        schedule.id)
                    schedule.last_run_status = 'skipped'
                    schedule.last_run_message = 'Source is disabled'
                    schedule.next_run_at = compute_next_run(
                        schedule.frequency, schedule.time_of_day,
                        schedule.day_of_week, after=now)
                    continue

                try:
                    enqueue_ingestion(
                        schedule.source_id,
                        task_type='sync',
                        source_config=source,
                    )
                    schedule.last_run_at = now
                    schedule.last_run_status = 'enqueued'
                    schedule.last_run_message = (
                        f'Sync enqueued for source {source.get("name", "?")}')

                    logger.info(
                        "[Scheduler] Enqueued scheduled sync for source %d "
                        "(%s) — schedule %d (%s %s)",
                        schedule.source_id, source.get('name', '?'),
                        schedule.id, schedule.frequency, schedule.time_of_day)

                    add_log('scheduled_sync',
                            f"Scheduled sync enqueued: {source.get('name', '?')} "
                            f"({schedule.frequency} {schedule.time_of_day})",
                            {
                                'schedule_id': schedule.id,
                                'source_id': schedule.source_id,
                                'source_name': source.get('name', '?'),
                                'frequency': schedule.frequency,
                                'time_of_day': schedule.time_of_day,
                                'day_of_week': schedule.day_of_week,
                            })

                except Exception as e:
                    logger.error(
                        "[Scheduler] Failed to enqueue sync for schedule %d: %s",
                        schedule.id, e)
                    schedule.last_run_at = now
                    schedule.last_run_status = 'error'
                    schedule.last_run_message = str(e)

                # Compute next run regardless of success/failure
                schedule.next_run_at = compute_next_run(
                    schedule.frequency, schedule.time_of_day,
                    schedule.day_of_week, after=now)

            db.session.commit()
            db.session.remove()

    except Exception as e:
        logger.error("[Scheduler] _process_due_schedules error: %s",
                     e, exc_info=True)


def _maybe_fallback_sync(app):
    """Run global sync of all enabled sources when no schedules exist."""
    try:
        with app.app_context():
            from modules.assistant.models.scheduled_sync import ScheduledSync
            from modules.assistant.services.source_service import get_all_sources
            from modules.assistant.tasks.ingestion_worker import enqueue_ingestion

            count = ScheduledSync.query.filter_by(active=True).count()
            if count > 0:
                # Per-source schedules are in use — skip fallback
                return

            sources = get_all_sources()
            enqueued = 0
            for source in sources:
                if source.get('enabled', False):
                    enqueue_ingestion(
                        source['id'],
                        task_type='sync',
                        source_config=source,
                    )
                    enqueued += 1

            if enqueued:
                logger.info(
                    "[Scheduler] Fallback global sync: enqueued %d of %d sources",
                    enqueued, len(sources))
    except Exception as e:
        logger.error("[Scheduler] Fallback sync error: %s", e)


def stop_scheduler():
    """Stop the scheduler greenlet."""
    global _scheduler_greenlet
    if _scheduler_greenlet:
        _scheduler_greenlet.kill()
        _scheduler_greenlet = None
        logger.info("[Scheduler] Stopped")

"""
SQL Migration Runner
====================
Scans ``backend/migrations/`` for numbered ``.sql`` files and executes any
that have not yet been applied.  Applied migrations are tracked in a
``_schema_migrations`` table that is created automatically.

Usage from *app.py*::

    from src.migrations import run_migrations
    run_migrations(app)          # call once, after db_create_all()

``.sql`` files must follow the naming convention::

    NNN_short_description.sql    (e.g. 002_add_feedback_column.sql)

Files are sorted lexicographically by filename and each one is executed
inside its own transaction.
"""

import os
import logging
from sqlalchemy import text

log = logging.getLogger(__name__)

# Relative to backend/ working directory
MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")


def _ensure_migrations_table(connection):
    """Create the bookkeeping table if it does not exist."""
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS _schema_migrations (
            filename  VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    connection.commit()


def _applied_migrations(connection):
    """Return the set of filenames already applied."""
    rows = connection.execute(text("SELECT filename FROM _schema_migrations")).fetchall()
    return {row[0] for row in rows}


def _pending_files(applied):
    """
    Return a sorted list of (filename, full_path) tuples for ``.sql`` files
    that have not been applied yet.
    """
    if not os.path.isdir(MIGRATIONS_DIR):
        log.warning("Migrations directory not found: %s", MIGRATIONS_DIR)
        return []

    files = sorted(
        f for f in os.listdir(MIGRATIONS_DIR)
        if f.endswith(".sql") and f not in applied
    )
    return [(f, os.path.join(MIGRATIONS_DIR, f)) for f in files]


def run_migrations(app):
    """
    Execute all pending SQL migration files against the app's database.

    Call this **after** ``db_create_all()`` so that the base schema exists.
    """
    from src.db import db  # local import to avoid circular refs

    with app.app_context():
        engine = db.engine
        with engine.connect() as conn:
            _ensure_migrations_table(conn)
            applied = _applied_migrations(conn)
            pending = _pending_files(applied)

            if not pending:
                log.info("No pending SQL migrations.")
                return

            for filename, filepath in pending:
                log.info("Applying migration: %s", filename)
                sql = open(filepath, "r", encoding="utf-8").read().strip()
                if not sql:
                    log.warning("Skipping empty migration file: %s", filename)
                    continue

                try:
                    # Execute the whole file in one transaction
                    conn.execute(text(sql))
                    conn.execute(
                        text("INSERT INTO _schema_migrations (filename) VALUES (:fn)"),
                        {"fn": filename},
                    )
                    conn.commit()
                    log.info("Migration applied successfully: %s", filename)
                except Exception:
                    conn.rollback()
                    log.exception("Migration FAILED: %s — rolling back", filename)
                    raise  # stop on first failure so we don't skip dependencies

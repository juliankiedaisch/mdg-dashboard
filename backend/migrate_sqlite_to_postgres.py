#!/usr/bin/env python3
"""
migrate_sqlite_to_postgres.py
─────────────────────────────────────────────────────────────────────────
Migrates all data from the existing SQLite database (backend/db/main.db)
to a PostgreSQL database.

Usage:
  # 1. Set DATABASE_URL to your PostgreSQL connection string:
  export DATABASE_URL="postgresql://mdg_admin:mdg_secure_password_change_me@localhost:5432/mdg_dashboard"

  # 2. (Optional) Set the SQLite path if it differs from the default:
  export SQLITE_PATH="db/main.db"

  # 3. Run the script from the backend/ directory:
  python migrate_sqlite_to_postgres.py

The script will:
  - Read all table schemas from the SQLite database
  - Create equivalent tables in PostgreSQL (via SQLAlchemy create_all)
  - Copy all rows, preserving foreign key relationships
  - Reset PostgreSQL auto-increment sequences to the correct values

It is safe to run repeatedly — it will skip tables that already contain
data in the target database, or you can pass --force to overwrite.
"""
import os
import sys
import sqlite3
import argparse
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("migrate")

# ── Ensure the backend package is importable ────────────────────────
# When running from inside the backend/ folder the imports work as-is.
# When running from the project root we need to add backend/ to sys.path.
backend_dir = os.path.abspath(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


def get_sqlite_path() -> str:
    """Resolve the SQLite database path."""
    explicit = os.getenv("SQLITE_PATH", "").strip()
    if explicit:
        if os.path.isabs(explicit):
            return explicit
        return os.path.join(backend_dir, explicit)
    return os.path.join(backend_dir, "db", "main.db")


def get_postgres_url() -> str:
    """Resolve the PostgreSQL connection string."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        logger.error(
            "DATABASE_URL environment variable is not set.\n"
            "Example: export DATABASE_URL='postgresql://user:pass@localhost:5432/dbname'"
        )
        sys.exit(1)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


# ── Table ordering (respects foreign keys) ──────────────────────────
# Tables are listed in dependency order so that referenced rows exist
# before referencing rows are inserted.
TABLE_ORDER = [
    # Core tables (no FK dependencies)
    "user",
    "group",
    "permission",
    "profile",
    # Association tables
    "user_group_association",
    "profile_permission",
    "user_profile",
    "group_profile",
    # Dashboard module
    "dashboard_page",
    "dashboard_topic",
    "applications",
    "dashboard_application",
    # Unify module
    "device_group",
    "device",
    "device_location",
    # Approvals module
    "approvals",
    "approval_group_association",
    "approval_user_association",
    # Word Cloud module
    "word_cloud",
    "wordcloud_group_association",
    "word_cloud_submission",
    # Survey module
    "survey",
    "survey_group_association",
    "survey_question",
    "question_group_association",
    "survey_question_option",
    "survey_response",
    "survey_answer",
    "special_survey",
    "special_survey_student",
    "special_survey_parent",
    "special_survey_class_teacher",
    "special_survey_student_wish",
    "special_survey_teacher_evaluation",
    "template_share_group",
    "template_share_user",
    # Assistant module
    "assistant_model_config",
    "assistant_log",
    "assistant_source_config",
    "assistant_tag",
    "assistant_source_tag_mapping",
    "assistant_chat_session",
    "assistant_chat_message",
]


def sqlite_tables(conn: sqlite3.Connection) -> list:
    """Return the list of user tables in the SQLite database."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return [row[0] for row in cursor.fetchall()]


def sqlite_columns(conn: sqlite3.Connection, table: str) -> list:
    """Return column names for a SQLite table."""
    cursor = conn.execute(f"PRAGMA table_info([{table}])")
    return [row[1] for row in cursor.fetchall()]


def migrate(sqlite_path: str, pg_url: str, force: bool = False, app=None):
    """
    Run the full SQLite → PostgreSQL migration.

    Parameters
    ----------
    sqlite_path : str
        Absolute or relative path to the SQLite ``main.db`` file.
    pg_url : str
        PostgreSQL connection string.
    force : bool
        If *True*, overwrite data in PostgreSQL tables that already have rows.
    app : Flask application instance, optional
        When called from within ``create_app()`` pass the already-initialised
        Flask app so we don't need to create a second one (which would cause
        circular imports).  When *None* the function boots its own app.
    """
    from sqlalchemy import create_engine, text, inspect

    # ── Connect to SQLite ───────────────────────────────────────────
    if not os.path.exists(sqlite_path):
        logger.error(f"SQLite database not found at: {sqlite_path}")
        return False

    logger.info(f"SQLite source : {sqlite_path}")
    logger.info(f"PostgreSQL target: {pg_url.split('@')[1] if '@' in pg_url else pg_url}")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    src_tables = sqlite_tables(sqlite_conn)
    logger.info(f"SQLite tables found: {len(src_tables)}")

    # ── Connect to PostgreSQL ───────────────────────────────────────
    pg_engine = create_engine(pg_url, pool_pre_ping=True)

    # ── Create all tables via SQLAlchemy models ─────────────────────
    # If an app was supplied (startup path) the schema already exists
    # because db_create_all() ran before us.  Otherwise we boot a
    # temporary app so every model is registered.
    if app is None:
        logger.info("Creating tables in PostgreSQL via SQLAlchemy models...")
        os.environ["DATABASE_URL"] = pg_url  # ensure app picks up PG
        from app import create_app
        app, _ = create_app()
        with app.app_context():
            from src.db import db, db_create_all
            db_create_all()
        logger.info("PostgreSQL schema created successfully.")
    else:
        logger.info("Using existing app context — schema already created.")

    # ── Determine migration order ───────────────────────────────────
    pg_inspector = inspect(pg_engine)
    pg_tables = pg_inspector.get_table_names()

    # Build ordered list: use TABLE_ORDER for known tables, append any
    # unknown tables at the end.
    ordered = [t for t in TABLE_ORDER if t in src_tables and t in pg_tables]
    remaining = [t for t in src_tables if t in pg_tables and t not in ordered]
    ordered.extend(remaining)

    skipped_no_pg = [t for t in src_tables if t not in pg_tables]
    if skipped_no_pg:
        logger.warning(f"Tables in SQLite but not in PG schema (skipped): {skipped_no_pg}")

    # ── Migrate data ────────────────────────────────────────────────
    with pg_engine.connect() as pg_conn:
        for table in ordered:
            src_cols = sqlite_columns(sqlite_conn, table)
            # Only transfer columns that exist in both databases
            pg_cols_set = {c["name"] for c in pg_inspector.get_columns(table)}
            common_cols = [c for c in src_cols if c in pg_cols_set]

            if not common_cols:
                logger.warning(f"  [{table}] No common columns — skipping")
                continue

            # Check if target table already has data
            count_result = pg_conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
            existing_count = count_result.scalar()
            if existing_count > 0 and not force:
                logger.info(f"  [{table}] Already has {existing_count} rows — skipping (use --force to overwrite)")
                continue
            elif existing_count > 0 and force:
                logger.info(f"  [{table}] Clearing {existing_count} existing rows (--force)")
                pg_conn.execute(text(f'DELETE FROM "{table}"'))
                pg_conn.commit()

            # Read all rows from SQLite
            cols_quoted = ", ".join(f"[{c}]" for c in common_cols)
            rows = sqlite_conn.execute(f"SELECT {cols_quoted} FROM [{table}]").fetchall()

            if not rows:
                logger.info(f"  [{table}] Empty — nothing to migrate")
                continue

            # Detect boolean columns in the PostgreSQL schema so we can cast
            # SQLite's integer 0/1 values to proper Python bools.
            from sqlalchemy.types import Boolean
            pg_bool_cols = {
                c['name'] for c in pg_inspector.get_columns(table)
                if isinstance(c['type'], Boolean)
            }

            # Insert into PostgreSQL
            pg_cols_str = ", ".join(f'"{c}"' for c in common_cols)
            pg_placeholders = ", ".join(f":{c}" for c in common_cols)
            insert_sql = text(f'INSERT INTO "{table}" ({pg_cols_str}) VALUES ({pg_placeholders})')

            batch_size = 500
            total_inserted = 0
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                params = []
                for row in batch:
                    row_dict = dict(zip(common_cols, row))
                    # Coerce SQLite integer booleans → Python bool for PG
                    for col in pg_bool_cols:
                        if col in row_dict and row_dict[col] is not None:
                            row_dict[col] = bool(row_dict[col])
                    params.append(row_dict)
                pg_conn.execute(insert_sql, params)
                total_inserted += len(batch)

            pg_conn.commit()
            logger.info(f"  [{table}] Migrated {total_inserted} rows")

        # ── Reset PostgreSQL sequences ──────────────────────────────
        logger.info("Resetting PostgreSQL auto-increment sequences...")
        for table in ordered:
            try:
                pg_cols = pg_inspector.get_columns(table)
                # Find auto-increment (SERIAL) columns
                for col in pg_cols:
                    if col.get("autoincrement", False) or col["name"] == "id":
                        col_name = col["name"]
                        seq_name = f"{table}_{col_name}_seq"
                        # Check if sequence exists
                        seq_check = pg_conn.execute(
                            text("SELECT 1 FROM pg_class WHERE relname = :seq AND relkind = 'S'"),
                            {"seq": seq_name},
                        )
                        if seq_check.fetchone():
                            max_result = pg_conn.execute(
                                text(f'SELECT COALESCE(MAX("{col_name}"), 0) FROM "{table}"')
                            )
                            max_val = max_result.scalar()
                            pg_conn.execute(
                                text(f"SELECT setval('{seq_name}', :val, true)"),
                                {"val": max(max_val, 1)},
                            )
                pg_conn.commit()
            except Exception as e:
                logger.debug(f"  Sequence reset for {table}: {e}")

    sqlite_conn.close()
    logger.info("Migration complete!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite → PostgreSQL")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite data in PostgreSQL tables that already have rows",
    )
    parser.add_argument(
        "--sqlite-path",
        default=None,
        help="Override path to SQLite database (default: backend/db/main.db)",
    )
    args = parser.parse_args()

    sqlite_path = args.sqlite_path or get_sqlite_path()
    pg_url = get_postgres_url()

    migrate(sqlite_path, pg_url, force=args.force)


if __name__ == "__main__":
    main()

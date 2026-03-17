# database.py
from flask_sqlalchemy import SQLAlchemy
from flask import current_app
from sqlalchemy.orm import scoped_session, sessionmaker, configure_mappers
from sqlalchemy import event
import os


# Erstelle eine SQLAlchemy-Instanz, die später von der App verwendet wird
db = SQLAlchemy()

plugin_field_user_hooks = []
plugin_field_group_hooks = []

def register_user_extension(func):
    plugin_field_user_hooks.append(func)

def register_group_extension(func):
    plugin_field_group_hooks.append(func)


def _is_sqlite(app) -> bool:
    """Check whether the configured database is SQLite."""
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    return uri.startswith('sqlite')


def _enable_sqlite_wal(dbapi_connection, connection_record):
    """Enable WAL journal mode and a longer busy timeout for SQLite.

    WAL allows concurrent readers while a single writer operates, which
    prevents the 'database is locked' errors that occur when the background
    ingestion worker and the Flask request thread write simultaneously.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=10000")   # 10 seconds
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_database_url() -> str:
    """Resolve the database URL from environment variables.

    Priority:
      1. DATABASE_URL  (full URI, e.g. postgresql://user:pass@host/db)
      2. SQLALCHEMY_DATABASE_URI  (legacy, may be a relative sqlite path)

    For PostgreSQL DATABASE_URL the value is used as-is.
    For SQLite (legacy) we prepend the sqlite:/// scheme + absolute path.
    """
    database_url = os.getenv('DATABASE_URL', '').strip()
    if database_url:
        # Support Heroku-style postgres:// which SQLAlchemy 1.4+ rejects
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return database_url

    # Fallback: legacy SQLite path from env / globals
    sqlite_path = os.getenv('SQLALCHEMY_DATABASE_URI', 'db/main.db')
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))  # backend/
    return f'sqlite:///{os.path.join(base_dir, sqlite_path)}'


# Scoped Session für Thread-Sicherheit
def init_db(app):
    db.init_app(app)

    # If using SQLite, enable WAL + busy_timeout on every raw connection
    if _is_sqlite(app):
        with app.app_context():
            event.listen(db.engine, "connect", _enable_sqlite_wal)

    # Scoped Session erstellen
    db_session = scoped_session(sessionmaker(bind=db.engine))
    return db_session

# Funktion zum Erstellen der Tabellen
def db_create_all():
    with current_app.app_context():
        # Felder dynamisch anhängen
        
        from src.db_models import User, Group
        for hook in plugin_field_user_hooks:
            hook(User, db)
        for hook in plugin_field_group_hooks:
            hook(Group, db)
        #db.configure_mappers()
        db.create_all()

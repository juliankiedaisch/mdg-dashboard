# Assistant Module - Main Module
"""
AI Assistant module using RAG (Retrieval Augmented Generation).
Provides a chat interface backed by Ollama + Qdrant.
"""
from flask import Blueprint

from modules.assistant.api.assistant_routes import register_chat_routes
from modules.assistant.api.admin_routes import register_admin_routes
from modules.assistant.api.webhook_routes import register_webhook_routes
# Ensure models are registered with SQLAlchemy
from modules.assistant.models import chat_session, chat_message, source_config, assistant_model  # noqa: F401
from modules.assistant.models import tag as _tag_model  # noqa: F401
from modules.assistant.models import sync_task as _sync_task_model  # noqa: F401
from modules.assistant.models import pipeline_event as _pipeline_event_model  # noqa: F401
from modules.assistant.models import retrieval_config as _retrieval_config_model  # noqa: F401
from modules.assistant.models import scheduled_sync as _scheduled_sync_model  # noqa: F401
from src.globals import OLLAMA_API_URL, VECTOR_DB_URL, ASSISTANT_MODEL, EMBEDDING_MODEL

class Module:
    # ── Module metadata ─────────────────────────────────────────────

    MODULE_NAME = "assistant"
    MODULE_MENU_NAME = "KI-Assistent"
    MODULE_URL = "/assistant"
    MODULE_STATIC_URL = "/assistant/static"
    MODULE_WITH_TASK = False
    MODULE_ICON = (
        "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 "
        "8-8 8 3.59 8 8-3.59 8-8 8zm-1-4h2v2h-2v-2zm1-10c-2.21 0-4 1.79-4 4h2c0-1.1.9-2 2-2s2 .9 2 2c0 "
        "2-3 1.75-3 5h2c0-2.25 3-2.5 3-5 0-2.21-1.79-4-4-4z"
    )

    # ── Granular Permissions ────────────────────────────────────────
    MODULE_PERMISSIONS = {
        "assistant.use": "Use the AI assistant chat",
        "assistant.configure": "Access and modify personal retrieval settings",
        "assistant.manage": "Manage AI assistant sources, models and pipeline",
    }

    # ── Constructor ─────────────────────────────────────────────────

    def __init__(self, app, db_session, oauth):
        self.app = app
        self.oauth = oauth
        self.db_session = db_session
        self.blueprint = Blueprint(
            self.MODULE_NAME, __name__,
            static_folder="static",
            static_url_path=self.MODULE_STATIC_URL,
        )
        self._register_routes()
        self._init_services(app)

    def _register_routes(self):
        """Register all routes on the blueprint."""
        register_chat_routes(self.blueprint, self.oauth)
        register_admin_routes(self.blueprint, self.oauth)
        register_webhook_routes(self.blueprint)

    def _init_services(self, app):
        """Initialize background services (worker, scheduler)."""
        import gevent
        import os
        from modules.assistant.tasks.ingestion_worker import run_ingestion_worker
        from modules.assistant.tasks.scheduler import init_scheduler
        from modules.assistant.tasks.progress import init_progress
        from modules.assistant.rag.embeddings import get_embedding_service
        from modules.assistant.rag.vector_store import get_vector_store
        from src import socketio as sio_instance

        # Initialize real-time progress emitter (uses the shared socketio)
        init_progress(sio_instance, app)

        # Initialize singletons with config (no DB access yet)
        get_embedding_service(ollama_url=OLLAMA_API_URL, model=EMBEDDING_MODEL)
        get_vector_store(qdrant_url=VECTOR_DB_URL)

        # Defer DB seeding until after db_create_all() has run (first request).
        # Querying the DB here would trigger SQLAlchemy mapper configuration before
        # extend_group() / extend_user() have been called, causing InvalidRequestError.
        _seeded = []

        @app.before_request
        def _seed_defaults():
            if not _seeded:
                _seeded.append(True)
                from modules.assistant.services.model_service import set_config_value, get_config_value
                if not get_config_value('llm_model'):
                    set_config_value('llm_model', ASSISTANT_MODEL, 'Default LLM model for chat')
                if not get_config_value('embedding_model'):
                    set_config_value('embedding_model', EMBEDDING_MODEL, 'Default embedding model')
                if not get_config_value('ollama_url'):
                    set_config_value('ollama_url', OLLAMA_API_URL, 'Ollama API URL')
                if not get_config_value('qdrant_url'):
                    set_config_value('qdrant_url', VECTOR_DB_URL, 'Qdrant vector DB URL')
                # Ensure default tag exists and sync dynamic tag permissions
                from modules.assistant.services.tag_service import ensure_default_tag, sync_tag_permissions
                ensure_default_tag()
                sync_tag_permissions()

        # Start background ingestion worker as a gevent greenlet.
        # The entire app runs under gevent.monkey.patch_all(), so all I/O
        # (HTTP requests, DB queries, time.sleep) yields cooperatively.
        worker_greenlet = gevent.spawn(run_ingestion_worker, app)
        worker_greenlet.name = 'assistant-ingestion-worker'

        # Start scheduler for periodic sync (also a gevent greenlet)
        init_scheduler(app)

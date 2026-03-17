# Assistant Module - API: Chat Routes (user-facing)
"""
Routes for the chat interface.
Requires: assistant.use permission.
"""
import json
import logging
from flask import Blueprint, request, jsonify, session, Response, stream_with_context

from src.decorators import login_required, permission_required
from src.permissions import is_super_admin
from modules.assistant.services import chat_service
from modules.assistant.services.rag_service import get_rag_service
from modules.assistant.services.model_service import get_config_value
from modules.assistant.services.tag_service import get_user_allowed_tags
from modules.assistant.dashboard.metrics_service import add_log

logger = logging.getLogger(__name__)


def register_chat_routes(bp, oauth):
    """Register chat API routes on the given Blueprint."""
    url = '/api/assistant'

    # ── Sessions ────────────────────────────────────────────────────

    @bp.route(f"{url}/sessions", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.use")
    def list_sessions():
        user_id = session.get('user_uuid', '')
        include_archived = request.args.get('archived', 'false').lower() == 'true'
        sessions = chat_service.get_user_sessions(user_id, include_archived=include_archived)
        return jsonify({"sessions": sessions})

    @bp.route(f"{url}/sessions", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.use")
    def create_session():
        user_id = session.get('user_uuid', '')
        data = request.get_json(silent=True) or {}
        title = data.get('title', 'New Chat')
        sess = chat_service.create_session(user_id, title=title)
        return jsonify({"session": sess}), 201

    @bp.route(f"{url}/sessions/<session_uuid>", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.use")
    def get_session(session_uuid):
        user_id = session.get('user_uuid', '')
        sess = chat_service.get_session(session_uuid, user_id)
        if not sess:
            return jsonify({"error": "Session not found."}), 404
        return jsonify({"session": sess})

    @bp.route(f"{url}/sessions/<session_uuid>", methods=["PUT"])
    @login_required(oauth)
    @permission_required("assistant.use")
    def update_session(session_uuid):
        user_id = session.get('user_uuid', '')
        data = request.get_json(silent=True) or {}
        title = data.get('title', '')
        if not title:
            return jsonify({"error": "Title is required."}), 400
        sess = chat_service.update_session_title(session_uuid, user_id, title)
        if not sess:
            return jsonify({"error": "Session not found."}), 404
        return jsonify({"session": sess})

    @bp.route(f"{url}/sessions/<session_uuid>", methods=["DELETE"])
    @login_required(oauth)
    @permission_required("assistant.use")
    def delete_session(session_uuid):
        user_id = session.get('user_uuid', '')
        success = chat_service.delete_session(session_uuid, user_id)
        if not success:
            return jsonify({"error": "Session not found."}), 404
        return jsonify({"status": True, "message": "Session deleted."})

    @bp.route(f"{url}/sessions/<session_uuid>/archive", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.use")
    def archive_session(session_uuid):
        user_id = session.get('user_uuid', '')
        success = chat_service.archive_session(session_uuid, user_id)
        if not success:
            return jsonify({"error": "Session not found."}), 404
        return jsonify({"status": True, "message": "Session archived."})

    # ── Chat ────────────────────────────────────────────────────────

    @bp.route(f"{url}/chat", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.use")
    def chat():
        """Send a message and get a response (non-streaming)."""
        user_id = session.get('user_uuid', '')
        data = request.get_json(silent=True) or {}
        question = data.get('message', '').strip()
        session_uuid = data.get('session_uuid', '')

        if not question:
            return jsonify({"error": "Message is required."}), 400

        # Create session if not provided
        if not session_uuid:
            sess = chat_service.create_session(user_id, title=question[:80])
            session_uuid = sess['uuid']

        # Store user message
        chat_service.add_message(session_uuid, user_id, 'user', question)

        # Get chat history for context
        history = chat_service.get_chat_history_for_prompt(session_uuid, user_id)

        # Get configured model
        llm_model = get_config_value('llm_model', 'llama3')
        rag_service = get_rag_service()
        rag_service.set_model(llm_model)

        # Execute RAG pipeline with tag-based filtering
        # Super admins bypass tag filtering (user_has_permission inside handles this too,
        # but setting None skips the Qdrant filter entirely for performance).
        if is_super_admin():
            user_tags = None
            logger.info("[Chat] User %s is super_admin — bypassing tag filter", user_id)
        else:
            user_tags = get_user_allowed_tags(user_id)
            logger.info("[Chat] User %s resolved tags: %s", user_id, user_tags)

        # Load effective retrieval configuration (admin defaults + user overrides)
        from modules.assistant.models.retrieval_config import get_effective_retrieval_config
        retrieval_cfg = get_effective_retrieval_config(user_id)

        result = rag_service.answer(
            question=question,
            chat_history=history,
            permission_tags=user_tags,
            retrieval_config=retrieval_cfg,
        )

        # Log filtered query (includes group-derived automatic tags)
        add_log('user_access_checked_against_group_tags',
                f"User access checked — allowed tags: {user_tags}",
                {'user_id': user_id, 'allowed_tags': user_tags},
                user_id=user_id)

        # Store assistant response
        chat_service.add_message(
            session_uuid, user_id, 'assistant',
            result['answer'],
            sources=result.get('sources', []),
        )

        # Log the query
        add_log('query', f"User query: {question[:100]}", user_id=user_id)

        return jsonify({
            "session_uuid": session_uuid,
            "answer": result['answer'],
            "sources": result.get('sources', []),
            "model": result.get('model', ''),
        })

    @bp.route(f"{url}/chat/stream", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.use")
    def chat_stream():
        """Send a message and get a streaming response (SSE)."""
        user_id = session.get('user_uuid', '')
        data = request.get_json(silent=True) or {}
        question = data.get('message', '').strip()
        session_uuid = data.get('session_uuid', '')

        if not question:
            return jsonify({"error": "Message is required."}), 400

        # Create session if not provided
        if not session_uuid:
            sess = chat_service.create_session(user_id, title=question[:80])
            session_uuid = sess['uuid']

        # Store user message
        chat_service.add_message(session_uuid, user_id, 'user', question)

        # Get chat history
        history = chat_service.get_chat_history_for_prompt(session_uuid, user_id)

        # Get configured model
        llm_model = get_config_value('llm_model', 'llama3')
        rag_service = get_rag_service()
        rag_service.set_model(llm_model)

        # Resolve user tag permissions for filtering
        if is_super_admin():
            user_tags = None
            logger.info("[ChatStream] User %s is super_admin — bypassing tag filter", user_id)
        else:
            user_tags = get_user_allowed_tags(user_id)
            logger.info("[ChatStream] User %s resolved tags: %s", user_id, user_tags)

        add_log('user_access_checked_against_group_tags',
                f"User access checked (stream) — allowed tags: {user_tags}",
                {'user_id': user_id, 'allowed_tags': user_tags},
                user_id=user_id)

        # Load effective retrieval configuration (admin defaults + user overrides)
        from modules.assistant.models.retrieval_config import get_effective_retrieval_config
        retrieval_cfg = get_effective_retrieval_config(user_id)

        # Check if debug mode is enabled
        debug_mode = get_config_value('debug_mode', 'false').lower() == 'true'

        def generate():
            full_answer = ''
            sources = []
            retrieval_diagnostics = None

            for chunk in rag_service.answer_stream(
                question=question,
                chat_history=history,
                permission_tags=user_tags,
                retrieval_config=retrieval_cfg,
            ):
                if chunk['type'] == 'sources':
                    sources = chunk['data']
                    yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"
                    # If debug mode: send debug info right after sources
                    if debug_mode:
                        debug_info = {
                            'retrieval_count': len(sources),
                            'sources_detail': [
                                {
                                    'title': s.get('title', '?'),
                                    'source': s.get('source', '?'),
                                    'score': round(s.get('score', 0), 4),
                                }
                                for s in sources
                            ],
                            'permission_tags': user_tags,
                            'model': llm_model,
                        }
                        yield f"data: {json.dumps({'type': 'debug', 'data': debug_info})}\n\n"
                elif chunk['type'] == 'diagnostics':
                    retrieval_diagnostics = chunk['data']
                    if debug_mode:
                        yield f"data: {json.dumps({'type': 'diagnostics', 'data': retrieval_diagnostics})}\n\n"
                elif chunk['type'] == 'chunk':
                    full_answer += chunk['data']
                    yield f"data: {json.dumps({'type': 'chunk', 'data': chunk['data']})}\n\n"
                elif chunk['type'] == 'done':
                    # Store complete assistant response
                    chat_service.add_message(
                        session_uuid, user_id, 'assistant',
                        full_answer, sources=sources,
                    )
                    yield f"data: {json.dumps({'type': 'done', 'session_uuid': session_uuid})}\n\n"
                elif chunk['type'] == 'error':
                    yield f"data: {json.dumps({'type': 'error', 'data': chunk['data']})}\n\n"

            add_log('query', f"Stream query: {question[:100]}", user_id=user_id)

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            },
        )

    # ── Feedback ────────────────────────────────────────────────────

    @bp.route(f"{url}/messages/<int:message_id>/feedback", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.use")
    def set_feedback(message_id):
        user_id = session.get('user_uuid', '')
        data = request.get_json(silent=True) or {}
        feedback = data.get('feedback', '')

        if feedback not in ('helpful', 'incorrect', ''):
            return jsonify({"error": "Invalid feedback value."}), 400

        result = chat_service.set_message_feedback(message_id, user_id, feedback or None)
        if not result:
            return jsonify({"error": "Message not found."}), 404

        return jsonify({"message": result})

    # ── User Retrieval Settings ─────────────────────────────────────

    @bp.route(f"{url}/retrieval-config", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.configure")
    def get_user_retrieval_settings():
        """Return the effective retrieval config for the current user.

        Returns both the admin defaults and the user's overrides (if any).
        Requires ``assistant.configure`` permission.
        """
        from modules.assistant.models.retrieval_config import (
            get_admin_retrieval_config, get_user_retrieval_config, get_effective_retrieval_config
        )
        user_id = session.get('user_uuid', '')
        return jsonify({
            "admin_config": get_admin_retrieval_config(),
            "user_config": get_user_retrieval_config(user_id),
            "effective_config": get_effective_retrieval_config(user_id),
        })

    @bp.route(f"{url}/retrieval-config", methods=["PUT"])
    @login_required(oauth)
    @permission_required("assistant.configure")
    def update_user_retrieval_settings():
        """Update the current user's retrieval config overrides.

        Requires ``assistant.configure`` permission.
        """
        from modules.assistant.models.retrieval_config import save_user_retrieval_config
        user_id = session.get('user_uuid', '')
        data = request.get_json(silent=True) or {}
        config = save_user_retrieval_config(user_id, data)
        return jsonify({"status": True, "config": config})

    @bp.route(f"{url}/retrieval-config", methods=["DELETE"])
    @login_required(oauth)
    @permission_required("assistant.configure")
    def reset_user_retrieval_settings():
        """Reset user retrieval overrides to admin defaults.

        Requires ``assistant.configure`` permission.
        """
        from modules.assistant.models.retrieval_config import delete_user_retrieval_config
        user_id = session.get('user_uuid', '')
        delete_user_retrieval_config(user_id)
        return jsonify({"status": True, "message": "Settings reset to admin defaults."})

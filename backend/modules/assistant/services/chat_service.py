# Assistant Module - Services: Chat Service
"""
Manages chat sessions and messages.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from src.db import db
from modules.assistant.models.chat_session import ChatSession
from modules.assistant.models.chat_message import ChatMessage

logger = logging.getLogger(__name__)


def get_user_sessions(user_id: str, include_archived: bool = False) -> List[Dict]:
    """Get all chat sessions for a user."""
    query = ChatSession.query.filter_by(user_id=user_id)
    if not include_archived:
        query = query.filter_by(is_archived=False)
    sessions = query.order_by(ChatSession.updated_at.desc()).all()
    return [s.to_dict() for s in sessions]


def get_session(session_uuid: str, user_id: str) -> Optional[Dict]:
    """Get a specific chat session with messages."""
    session = ChatSession.query.filter_by(uuid=session_uuid, user_id=user_id).first()
    if not session:
        return None
    return session.to_dict_with_messages()


def create_session(user_id: str, title: str = 'New Chat') -> Dict:
    """Create a new chat session."""
    session = ChatSession(user_id=user_id, title=title)
    db.session.add(session)
    db.session.commit()
    logger.info(f"Created session {session.uuid} for user {user_id}")
    return session.to_dict()


def update_session_title(session_uuid: str, user_id: str, title: str) -> Optional[Dict]:
    """Update a session's title."""
    session = ChatSession.query.filter_by(uuid=session_uuid, user_id=user_id).first()
    if not session:
        return None
    session.title = title
    db.session.commit()
    return session.to_dict()


def archive_session(session_uuid: str, user_id: str) -> bool:
    """Archive (soft-delete) a chat session."""
    session = ChatSession.query.filter_by(uuid=session_uuid, user_id=user_id).first()
    if not session:
        return False
    session.is_archived = True
    db.session.commit()
    return True


def delete_session(session_uuid: str, user_id: str) -> bool:
    """Permanently delete a chat session and its messages."""
    session = ChatSession.query.filter_by(uuid=session_uuid, user_id=user_id).first()
    if not session:
        return False
    ChatMessage.query.filter_by(session_id=session.id).delete()
    db.session.delete(session)
    db.session.commit()
    logger.info(f"Deleted session {session_uuid}")
    return True


def add_message(session_uuid: str, user_id: str, role: str, message: str,
                sources: Optional[List[Dict]] = None) -> Optional[Dict]:
    """Add a message to a chat session."""
    session = ChatSession.query.filter_by(uuid=session_uuid, user_id=user_id).first()
    if not session:
        return None
    msg = ChatMessage(
        session_id=session.id,
        role=role,
        message=message,
    )
    if sources:
        msg.sources = sources
    db.session.add(msg)

    # Update session title from first user message if still default
    if role == 'user' and session.title == 'New Chat':
        session.title = message[:80] + ('...' if len(message) > 80 else '')

    session.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return msg.to_dict()


def set_message_feedback(message_id: int, user_id: str, feedback: str) -> Optional[Dict]:
    """Set feedback on a message (helpful/incorrect)."""
    msg = ChatMessage.query.get(message_id)
    if not msg:
        return None
    # Verify ownership
    session = ChatSession.query.get(msg.session_id)
    if not session or session.user_id != user_id:
        return None
    msg.feedback = feedback
    db.session.commit()
    return msg.to_dict()


def get_chat_history_for_prompt(session_uuid: str, user_id: str, limit: int = 6) -> List[Dict]:
    """Get recent chat history for prompt context."""
    session = ChatSession.query.filter_by(uuid=session_uuid, user_id=user_id).first()
    if not session:
        return []
    messages = (ChatMessage.query
                .filter_by(session_id=session.id)
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
                .all())
    messages.reverse()
    return [{'role': m.role, 'content': m.message} for m in messages]

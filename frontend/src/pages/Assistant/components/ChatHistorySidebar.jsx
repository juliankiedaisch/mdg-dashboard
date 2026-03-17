// Assistant Module - Chat History Sidebar Component
import { useState, useRef, useEffect } from 'react';
import { Button } from '../../../components/shared';
import './ChatHistorySidebar.css';

function ChatHistorySidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onRenameSession,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [openMenuId, setOpenMenuId] = useState(null);
  const menuRef = useRef(null);

  // Close menu when clicking outside
  useEffect(() => {
    if (!openMenuId) return;
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [openMenuId]);

  const startRename = (session) => {
    setOpenMenuId(null);
    setEditingId(session.uuid);
    setEditTitle(session.title);
  };

  const confirmRename = () => {
    if (editTitle.trim() && editingId) {
      onRenameSession?.(editingId, editTitle.trim());
    }
    setEditingId(null);
    setEditTitle('');
  };

  const handleDelete = (sessUuid) => {
    setOpenMenuId(null);
    onDeleteSession?.(sessUuid);
  };

  const formatDate = (isoStr) => {
    if (!isoStr) return '';
    const d = new Date(isoStr);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) return 'Heute';
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return 'Gestern';
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
  };

  return (
    <div className="chat-history-sidebar">
      {/* New Chat Button */}
      <div className="chat-history-sidebar__header">
        <Button
          onClick={onNewChat}
          variant="primary"
          size="md"
          className="chat-history-sidebar__new-chat-btn"
        >
          <span className="chat-history-sidebar__new-chat-icon">+</span> Neuer Chat
        </Button>
      </div>

      {/* Session List */}
      <div className="chat-history-sidebar__list">
        {sessions.length === 0 && (
          <p className="chat-history-sidebar__empty">
            Keine Chats vorhanden
          </p>
        )}
        {sessions.map((sess) => (
          <div
            key={sess.uuid}
            onClick={() => { if (editingId !== sess.uuid) onSelectSession?.(sess.uuid); }}
            className={`chat-history-sidebar__item${activeSessionId === sess.uuid ? ' chat-history-sidebar__item--active' : ''}`}
          >
            {editingId === sess.uuid ? (
              <input
                autoFocus
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onBlur={confirmRename}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') confirmRename();
                  if (e.key === 'Escape') setEditingId(null);
                }}
                onClick={(e) => e.stopPropagation()}
                className="chat-history-sidebar__edit-input"
              />
            ) : (
              <>
                <div className="chat-history-sidebar__item-body">
                  <div className="chat-history-sidebar__item-title">
                    {sess.title}
                  </div>
                  <div className="chat-history-sidebar__item-date">
                    {formatDate(sess.updated_at)}
                  </div>
                </div>

                {/* Three-dot menu */}
                <div
                  className="chat-history-sidebar__menu-wrapper"
                  ref={openMenuId === sess.uuid ? menuRef : null}
                >
                  <button
                    className="chat-history-sidebar__menu-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenMenuId(openMenuId === sess.uuid ? null : sess.uuid);
                    }}
                    title="Optionen"
                    aria-label="Optionen"
                  >
                    ⋯
                  </button>

                  {openMenuId === sess.uuid && (
                    <div className="chat-history-sidebar__dropdown">
                      <button
                        className="chat-history-sidebar__dropdown-item"
                        onClick={(e) => { e.stopPropagation(); startRename(sess); }}
                      >
                      Umbenennen
                      </button>
                      <button
                        className="chat-history-sidebar__dropdown-item chat-history-sidebar__dropdown-item--danger"
                        onClick={(e) => { e.stopPropagation(); handleDelete(sess.uuid); }}
                      >
                      Löschen
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default ChatHistorySidebar;

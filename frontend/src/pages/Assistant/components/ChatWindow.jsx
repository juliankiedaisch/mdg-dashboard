// Assistant Module - Chat Window Component
import { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import SourceReferences from './SourceReferences';
import { Button, TextInput } from '../../../components/shared';
import './ChatWindow.css';

function ChatWindow({
  messages,
  streamingMessage,
  streamingSources,
  streamingDebug,
  isLoading,
  onSendMessage,
  onFeedback,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessage]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    onSendMessage(trimmed);
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-window">
      {/* Messages Area */}
      <div className="chat-window__messages">
        {messages.length === 0 && !streamingMessage && (
          <div className="chat-window__empty-state">
            <div className="chat-window__empty-icon">🤖</div>
            <h3 className="chat-window__empty-title">KI-Assistent</h3>
            <p className="chat-window__empty-text">
              Stellen Sie Fragen zu Ihren Dokumenten. Der Assistent durchsucht die
              verfügbaren Quellen und gibt Ihnen eine Antwort mit Quellenangaben.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble
            key={msg.id || `msg-${msg.created_at}`}
            message={msg}
            onFeedback={onFeedback}
          />
        ))}

        {/* Streaming response */}
        {streamingMessage && (
          <>
            <MessageBubble
              message={{
                role: 'assistant',
                message: streamingMessage,
                sources: [],
                created_at: new Date().toISOString(),
                _streaming: true,
              }}
            />
            {streamingSources && streamingSources.length > 0 && (
              <SourceReferences sources={streamingSources} />
            )}
            {/* Debug panel (shown when debug_mode is enabled in backend) */}
            {streamingDebug && (
              <div className="chat-window__debug-panel">
                <div className="chat-window__debug-header">🔍 Retrieval Debug</div>
                <p className="chat-window__debug-text">
                  Modell: <strong>{streamingDebug.model}</strong> |
                  Ergebnisse: <strong>{streamingDebug.retrieval_count}</strong> |
                  Tags: <strong>{streamingDebug.permission_tags === null ? 'super_admin (alle)' : (streamingDebug.permission_tags?.join(', ') || 'keine')}</strong>
                </p>
                {streamingDebug.sources_detail && streamingDebug.sources_detail.length > 0 && (
                  <div className="chat-window__debug-sources">
                    {streamingDebug.sources_detail.map((s, i) => (
                      <div key={i} className="chat-window__debug-source-item">
                        {i + 1}. <strong>{s.title}</strong> ({s.source}) — Score: {(s.score * 100).toFixed(1)}%
                      </div>
                    ))}
                  </div>
                )}
                {streamingDebug.retrieval_count === 0 && (
                  <p className="chat-window__debug-text chat-window__debug-text--warning">
                    ⚠ Keine Dokumente abgerufen — der Kontext ist leer!
                  </p>
                )}
              </div>
            )}
          </>
        )}

        {/* Loading indicator */}
        {isLoading && !streamingMessage && (
          <div className="chat-window__loading">
            <div className="chat-window__loading-dots">
              <span className="chat-window__loading-dot">●</span>
              <span className="chat-window__loading-dot">●</span>
              <span className="chat-window__loading-dot">●</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="chat-window__input-area">
        <div className="chat-window__input-row">
          <TextInput
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Stellen Sie eine Frage..."
            rows={1}
            disabled={isLoading}
            onInput={(e) => {
              // Dynamic height computed from scrollHeight at runtime — must stay inline
              e.target.style.height = 'auto';
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
            }}
          />
          <Button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            variant="primary"
            size="md"
          >
            Senden
          </Button>
        </div>
      </div>
    </div>
  );
}

export default ChatWindow;

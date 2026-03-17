// Assistant Module - Chat Page
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import ChatWindow from './components/ChatWindow';
import ChatHistorySidebar from './components/ChatHistorySidebar';
import {
  getSessions,
  createSession,
  getSession,
  deleteSession,
  updateSession,
  sendMessageStream,
  setMessageFeedback,
  getUserRetrievalConfig,
  updateUserRetrievalConfig,
  resetUserRetrievalConfig,
} from './services/assistantApi';
import { PageContainer, Card, Button, MessageBox, Modal, TextInput, FormGroup, Spinner } from '../../components/shared';
import './AssistantChatPage.css';

function AssistantChatPage() {
  const { hasPermission } = useUser();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [activeSessionUuid, setActiveSessionUuid] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState('');
  const [streamingSources, setStreamingSources] = useState([]);
  const [streamingDebug, setStreamingDebug] = useState(null);
  const [error, setError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [confirmModal, setConfirmModal] = useState({ open: false, message: '', onConfirm: null });
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [adminDefaults, setAdminDefaults] = useState(null);
  const [settingsForm, setSettingsForm] = useState({
    tag_weights: {},
    top_k: '',
    top_k_distribution: {},
    summarization_enabled: null,
    summarization_model: '',
  });

  const showConfirm = (message, onConfirm) => setConfirmModal({ open: true, message, onConfirm });
  const closeConfirm = () => setConfirmModal({ open: false, message: '', onConfirm: null });

  const loadSettingsModal = async () => {
    setShowSettingsModal(true);
    setSettingsLoading(true);
    try {
      const res = await getUserRetrievalConfig();
      const { admin_config, user_config, effective_config } = res.data;
      setAdminDefaults(admin_config);
      setSettingsForm({
        tag_weights: user_config.tag_weights || {},
        top_k: user_config.top_k != null ? String(user_config.top_k) : '',
        top_k_distribution: user_config.top_k_distribution || {},
        summarization_enabled: user_config.summarization_enabled,
        summarization_model: user_config.summarization_model || '',
      });
    } catch (err) {
      console.error('Failed to load retrieval settings:', err);
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleSaveSettings = async () => {
    setSettingsSaving(true);
    try {
      const payload = {};
      if (Object.keys(settingsForm.tag_weights).length > 0) payload.tag_weights = settingsForm.tag_weights;
      if (settingsForm.top_k !== '') payload.top_k = parseInt(settingsForm.top_k, 10);
      if (Object.keys(settingsForm.top_k_distribution).length > 0) payload.top_k_distribution = settingsForm.top_k_distribution;
      if (settingsForm.summarization_enabled !== null) payload.summarization_enabled = settingsForm.summarization_enabled;
      if (settingsForm.summarization_model) payload.summarization_model = settingsForm.summarization_model;
      await updateUserRetrievalConfig(payload);
      setShowSettingsModal(false);
    } catch (err) {
      console.error('Failed to save retrieval settings:', err);
    } finally {
      setSettingsSaving(false);
    }
  };

  const handleResetSettings = async () => {
    setSettingsSaving(true);
    try {
      await resetUserRetrievalConfig();
      setSettingsForm({
        tag_weights: {},
        top_k: '',
        top_k_distribution: {},
        summarization_enabled: null,
        summarization_model: '',
      });
      setShowSettingsModal(false);
    } catch (err) {
      console.error('Failed to reset retrieval settings:', err);
    } finally {
      setSettingsSaving(false);
    }
  };

  // Check permission
  if (!hasPermission('assistant.use')) {
    return (
      <div className="assistant-chat-page__no-access">
        <h2>Kein Zugriff</h2>
        <p>Sie haben keine Berechtigung, den KI-Assistenten zu verwenden.</p>
      </div>
    );
  }

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const res = await getSessions();
      setSessions(res.data.sessions || []);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  };

  const loadSession = async (uuid) => {
    try {
      const res = await getSession(uuid);
      const sess = res.data.session;
      setMessages(sess.messages || []);
      setActiveSessionUuid(uuid);
    } catch (err) {
      console.error('Failed to load session:', err);
    }
  };

  const handleNewChat = async () => {
    setActiveSessionUuid(null);
    setMessages([]);
    setStreamingMessage('');
    setStreamingSources([]);
    setStreamingDebug(null);
    setError('');
    setSidebarOpen(false);
  };

  const handleSelectSession = (uuid) => {
    loadSession(uuid);
    setStreamingMessage('');
    setStreamingSources([]);
    setStreamingDebug(null);
    setError('');
    setSidebarOpen(false);
  };

  const handleDeleteSession = (uuid) => {
    showConfirm('Chat wirklich löschen?', async () => {
      closeConfirm();
      try {
        await deleteSession(uuid);
        if (activeSessionUuid === uuid) {
          setActiveSessionUuid(null);
          setMessages([]);
        }
        loadSessions();
      } catch (err) {
        console.error('Failed to delete session:', err);
      }
    });
  };

  const handleRenameSession = async (uuid, newTitle) => {
    try {
      await updateSession(uuid, newTitle);
      loadSessions();
    } catch (err) {
      console.error('Failed to rename session:', err);
    }
  };

  const handleSendMessage = useCallback(async (text) => {
    setIsLoading(true);
    setStreamingMessage('');
    setStreamingSources([]);
    setStreamingDebug(null);
    setError('');

    // Optimistically add user message to UI
    const userMsg = {
      role: 'user',
      message: text,
      sources: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    let currentSessionUuid = activeSessionUuid;

    try {
      let fullAnswer = '';

      await sendMessageStream(
        text,
        currentSessionUuid || '',
        // onChunk
        (chunk) => {
          fullAnswer += chunk;
          setStreamingMessage(fullAnswer);
        },
        // onSources
        (sources) => {
          setStreamingSources(sources);
        },
        // onDone
        (sessionUuid) => {
          // Add the complete assistant message
          const assistantMsg = {
            role: 'assistant',
            message: fullAnswer,
            sources: streamingSources,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, assistantMsg]);
          setStreamingMessage('');
          setStreamingSources([]);
          setStreamingDebug(null);
          setIsLoading(false);

          // Set active session if new
          if (sessionUuid && !currentSessionUuid) {
            setActiveSessionUuid(sessionUuid);
          }

          // Reload sessions list & session messages
          loadSessions();
          if (sessionUuid) {
            loadSession(sessionUuid);
          }
        },
        // onError
        (errMsg) => {
          setError(errMsg);
          setStreamingMessage('');
          setIsLoading(false);
        },
        // onDebug (when debug_mode is enabled in config)
        (debugData) => {
          setStreamingDebug(debugData);
        }
      );
    } catch (err) {
      setError('Fehler beim Senden der Nachricht.');
      setIsLoading(false);
    }
  }, [activeSessionUuid, streamingSources]);

  const handleFeedback = async (messageId, feedback) => {
    try {
      await setMessageFeedback(messageId, feedback);
    } catch (err) {
      console.error('Failed to set feedback:', err);
    }
  };

  return (
    <PageContainer>
      <Card variant="header" title="MDG Assistent">
        {/* Mobile overlay */}
        {sidebarOpen && (
          <div
            className="assistant-chat-page__overlay"
            onClick={() => setSidebarOpen(false)}
          />
        )}
        {/* Mobile header bar */}
        <div className="assistant-chat-page__mobile-bar">
          <Button
            variant="ghost"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Menü öffnen"
          >
            ☰
          </Button>
        </div>

        {hasPermission('assistant.configure') && (
          <Button
            variant="white"
            className="assistant-chat-page__settings-btn"
            onClick={loadSettingsModal}
            title="Retrieval-Einstellungen"
          >
            🔧 Einstellungen
          </Button>
        )}

        {hasPermission('assistant.manage') && (
            <Button
              variant="secondary"
              className="assistant-chat-page__admin-btn"
              onClick={() => navigate('/assistant/admin')}
            >
              ⚙️ Admin-Bereich
            </Button>
        )}
      </Card>

      <Card>
        <div className="assistant-chat-page">
      <div className={`assistant-chat-page__sidebar-column${sidebarOpen ? ' assistant-chat-page__sidebar-column--open' : ''}`}>

        <ChatHistorySidebar
          sessions={sessions}
          activeSessionId={activeSessionUuid}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          onDeleteSession={handleDeleteSession}
          onRenameSession={handleRenameSession}
        />
      </div>

      <div className="assistant-chat-page__main">

        {error && (
          <MessageBox
            message={error}
            type="error"
            onDismiss={() => setError('')}
          />
        )}
        <ChatWindow
          messages={messages}
          streamingMessage={streamingMessage}
          streamingSources={streamingSources}
          streamingDebug={streamingDebug}
          isLoading={isLoading}
          onSendMessage={handleSendMessage}
          onFeedback={handleFeedback}
        />
      </div>
      </div>
    </Card>

    {confirmModal.open && (
      <Modal
        title="Bestätigung"
        size="sm"
        onClose={closeConfirm}
        footer={
          <>
            <Button variant="secondary" onClick={closeConfirm}>Abbrechen</Button>
            <Button variant="danger" onClick={confirmModal.onConfirm}>Löschen</Button>
          </>
        }
      >
        <p>{confirmModal.message}</p>
      </Modal>
    )}

    {showSettingsModal && (
      <Modal
        title="Retrieval-Einstellungen"
        size="md"
        onClose={() => setShowSettingsModal(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowSettingsModal(false)}>Abbrechen</Button>
            <Button variant="danger" onClick={handleResetSettings} disabled={settingsSaving}>Auf Standard zurücksetzen</Button>
            <Button variant="primary" onClick={handleSaveSettings} disabled={settingsSaving}>
              {settingsSaving ? 'Speichern...' : 'Speichern'}
            </Button>
          </>
        }
      >
        {settingsLoading ? (
          <div className="assistant-chat-page__settings-loading"><Spinner /></div>
        ) : (
          <div className="assistant-chat-page__settings">
            <p className="assistant-chat-page__settings-hint">
              Eigene Einstellungen überschreiben die Admin-Vorgaben. Leere Felder verwenden den Admin-Standard.
            </p>

            {/* Tag Weights */}
            <FormGroup label="Tag-Gewichtung" hint="Gewichtung der Quelltypen (leer = Admin-Standard)">
              {adminDefaults && (
                <p className="assistant-chat-page__settings-default">
                  Admin-Standard: {Object.entries(adminDefaults.tag_weights || {}).map(([k, v]) => `${k}: ${v}`).join(', ') || '–'}
                </p>
              )}
              <table className="assistant-chat-page__settings-table">
                <thead>
                  <tr><th>Quelltyp</th><th>Gewicht</th><th></th></tr>
                </thead>
                <tbody>
                  {Object.entries(settingsForm.tag_weights).map(([key, val]) => (
                    <tr key={key}>
                      <td>{key}</td>
                      <td>
                        <TextInput
                          type="number"
                          step="0.1"
                          min="0"
                          value={val}
                          onChange={(e) => setSettingsForm(prev => ({
                            ...prev,
                            tag_weights: { ...prev.tag_weights, [key]: parseFloat(e.target.value) || 0 }
                          }))}
                          className="assistant-chat-page__settings-num-input"
                        />
                      </td>
                      <td>
                        <Button variant="danger" size="sm" onClick={() => {
                          setSettingsForm(prev => {
                            const copy = { ...prev.tag_weights };
                            delete copy[key];
                            return { ...prev, tag_weights: copy };
                          });
                        }}>×</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {adminDefaults && Object.keys(adminDefaults.tag_weights || {}).filter(k => !(k in settingsForm.tag_weights)).length > 0 && (
                <div className="assistant-chat-page__settings-add-row">
                  {Object.keys(adminDefaults.tag_weights).filter(k => !(k in settingsForm.tag_weights)).map(k => (
                    <Button key={k} variant="secondary" size="sm" onClick={() => {
                      setSettingsForm(prev => ({
                        ...prev,
                        tag_weights: { ...prev.tag_weights, [k]: adminDefaults.tag_weights[k] }
                      }));
                    }}>+ {k}</Button>
                  ))}
                </div>
              )}
            </FormGroup>

            {/* Top K */}
            <FormGroup label="Top K" hint={adminDefaults ? `Admin-Standard: ${adminDefaults.top_k}` : ''}>
              <TextInput
                type="number"
                min="1"
                placeholder={adminDefaults ? String(adminDefaults.top_k) : '20'}
                value={settingsForm.top_k}
                onChange={(e) => setSettingsForm(prev => ({ ...prev, top_k: e.target.value }))}
                className="assistant-chat-page__settings-num-input"
              />
            </FormGroup>

            {/* Top K Distribution */}
            <FormGroup label="Top-K Verteilung (%)" hint="Prozentuale Verteilung nach Quelltyp (leer = Admin-Standard)">
              {adminDefaults && (
                <p className="assistant-chat-page__settings-default">
                  Admin-Standard: {Object.entries(adminDefaults.top_k_distribution || {}).map(([k, v]) => `${k}: ${v}%`).join(', ') || '–'}
                </p>
              )}
              <table className="assistant-chat-page__settings-table">
                <thead>
                  <tr><th>Quelltyp</th><th>Anteil (%)</th><th></th></tr>
                </thead>
                <tbody>
                  {Object.entries(settingsForm.top_k_distribution).map(([key, val]) => (
                    <tr key={key}>
                      <td>{key}</td>
                      <td>
                        <TextInput
                          type="number"
                          min="0"
                          max="100"
                          value={val}
                          onChange={(e) => setSettingsForm(prev => ({
                            ...prev,
                            top_k_distribution: { ...prev.top_k_distribution, [key]: parseInt(e.target.value, 10) || 0 }
                          }))}
                          className="assistant-chat-page__settings-num-input"
                        />
                      </td>
                      <td>
                        <Button variant="danger" size="sm" onClick={() => {
                          setSettingsForm(prev => {
                            const copy = { ...prev.top_k_distribution };
                            delete copy[key];
                            return { ...prev, top_k_distribution: copy };
                          });
                        }}>×</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {adminDefaults && Object.keys(adminDefaults.top_k_distribution || {}).filter(k => !(k in settingsForm.top_k_distribution)).length > 0 && (
                <div className="assistant-chat-page__settings-add-row">
                  {Object.keys(adminDefaults.top_k_distribution).filter(k => !(k in settingsForm.top_k_distribution)).map(k => (
                    <Button key={k} variant="secondary" size="sm" onClick={() => {
                      setSettingsForm(prev => ({
                        ...prev,
                        top_k_distribution: { ...prev.top_k_distribution, [k]: adminDefaults.top_k_distribution[k] }
                      }));
                    }}>+ {k}</Button>
                  ))}
                </div>
              )}
            </FormGroup>

            {/* Summarization */}
            <FormGroup label="Zusammenfassung" hint={adminDefaults ? `Admin-Standard: ${adminDefaults.summarization_enabled ? 'Aktiviert' : 'Deaktiviert'}` : ''}>
              <div className="assistant-chat-page__settings-radio-row">
                <label className="assistant-chat-page__settings-radio-label">
                  <input
                    type="radio"
                    name="user_summarization"
                    checked={settingsForm.summarization_enabled === null}
                    onChange={() => setSettingsForm(prev => ({ ...prev, summarization_enabled: null }))}
                  /> Standard
                </label>
                <label className="assistant-chat-page__settings-radio-label">
                  <input
                    type="radio"
                    name="user_summarization"
                    checked={settingsForm.summarization_enabled === true}
                    onChange={() => setSettingsForm(prev => ({ ...prev, summarization_enabled: true }))}
                  /> An
                </label>
                <label className="assistant-chat-page__settings-radio-label">
                  <input
                    type="radio"
                    name="user_summarization"
                    checked={settingsForm.summarization_enabled === false}
                    onChange={() => setSettingsForm(prev => ({ ...prev, summarization_enabled: false }))}
                  /> Aus
                </label>
              </div>
              <TextInput
                placeholder={adminDefaults ? adminDefaults.summarization_model || 'Kein Modell' : ''}
                value={settingsForm.summarization_model}
                onChange={(e) => setSettingsForm(prev => ({ ...prev, summarization_model: e.target.value }))}
              />
              <p className="assistant-chat-page__settings-default">Zusammenfassungs-Modell (leer = Admin-Standard)</p>
            </FormGroup>
          </div>
        )}
      </Modal>
    )}
    </PageContainer>
  );
}

export default AssistantChatPage;

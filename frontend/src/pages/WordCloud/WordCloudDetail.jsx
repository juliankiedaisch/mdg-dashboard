import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import QRCodeStyling from 'qr-code-styling';
import { toPng } from 'html-to-image';
import { io } from 'socket.io-client';
import api from '../../utils/api';
import { useUser } from '../../contexts/UserContext';
import {
  PageContainer, Card, Button, Modal, MessageBox, Spinner,
  CheckboxInput, FormGroup, StatCard, TextInput,
} from '../../components/shared';
import GroupSelectModal from '../Surveys/components/GroupSelectModal';
import WordCloudCanvas from './WordCloudCanvas';
import './WordCloud.css';

const WordCloudDetail = () => {
  const { hasPermission } = useUser();
  const { wcId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const fromArchive = location.state?.fromArchive || false;

  const [wordcloud, setWordcloud] = useState(null);
  const [words, setWords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [showQR, setShowQR] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showSubmissions, setShowSubmissions] = useState(false);
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fullscreenDims, setFullscreenDims] = useState({ w: 1200, h: 800 });

  // Settings editing state
  const [editCaseSensitive, setEditCaseSensitive] = useState(false);
  const [editShowResults, setEditShowResults] = useState(false);
  const [editGroups, setEditGroups] = useState([]);
  const [editAllowDownload, setEditAllowDownload] = useState(false);
  const [editMaxChars, setEditMaxChars] = useState(20);
  const [editAnonymous, setEditAnonymous] = useState(true);
  const [editRotationMode, setEditRotationMode] = useState('mixed');
  const [editRotationAngles, setEditRotationAngles] = useState('0, 90');
  const [editRotationProbability, setEditRotationProbability] = useState(0.5);
  const [groups, setGroups] = useState([]);
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);

  const qrRef = useRef(null);
  const qrCodeInstance = useRef(null);
  const cloudRef = useRef(null);
  const socketRef = useRef(null);
  const fullscreenRef = useRef(null);

  const participateUrl = `${window.location.origin}/teachertools/wordcloud/join/${wordcloud?.access_code || ''}`;

  // Load word cloud data
  const loadWordcloud = useCallback(async () => {
    try {
      const response = await api.get(`/api/teachertools/wordcloud/${wcId}`);
      const wc = response.data.wordcloud;
      setWordcloud(wc);
      setWords(wc.words || []);
    } catch (err) {
      setError('Fehler beim Laden der Wortwolke.');
      console.error('Error loading word cloud:', err);
    } finally {
      setLoading(false);
    }
  }, [wcId]);

  // Initial load
  useEffect(() => {
    loadWordcloud();
  }, [loadWordcloud]);

  // Socket.IO for real-time updates (event-based only, no polling)
  useEffect(() => {
    if (!wordcloud) return;

    const socketUrl = import.meta.env.VITE_SOCKET_URL || 'http://localhost:5000';
    const socket = io(`${socketUrl}/teachertools`, {
      withCredentials: true,
      transports: ['websocket', 'polling'],
    });

    socket.on('connect', () => {
      socket.emit('join_wordcloud', { wordcloud_id: parseInt(wcId) });
    });

    socket.on('wordcloud_update', (data) => {
      if (data.wordcloud_id === parseInt(wcId)) {
        setWords(data.words || []);
        setWordcloud((prev) => prev ? {
          ...prev,
          submission_count: data.total_submissions,
          unique_words: data.unique_words,
        } : prev);
        // Re-fetch full data to update submissions_detail
        api.get(`/api/teachertools/wordcloud/${wcId}`)
          .then((res) => {
            const wc = res.data.wordcloud;
            setWordcloud(wc);
            setWords(wc.words || []);
          })
          .catch(() => {});
      }
    });

    socketRef.current = socket;

    return () => {
      if (socketRef.current) {
        socketRef.current.emit('leave_wordcloud', { wordcloud_id: parseInt(wcId) });
        socketRef.current.disconnect();
      }
    };
  }, [wcId, wordcloud?.id]);

  // Fullscreen dimensions with resize tracking
  useEffect(() => {
    const updateDims = () => {
      setFullscreenDims({
        w: Math.floor(window.innerWidth * 0.94),
        h: Math.floor(window.innerHeight * 0.92),
      });
    };
    updateDims();
    window.addEventListener('resize', updateDims);
    return () => window.removeEventListener('resize', updateDims);
  }, []);

  // Generate QR code when modal opens
  useEffect(() => {
    if (showQR && qrRef.current && wordcloud) {
      qrRef.current.innerHTML = '';
      const qr = new QRCodeStyling({
        width: 600,
        height: 600,
        type: 'svg',
        data: participateUrl,
        dotsOptions: { color: '#001d1d', type: 'rounded' },
        backgroundOptions: { color: '#ffffff' },
      });
      qr.append(qrRef.current);
      qrCodeInstance.current = qr;

      const svg = qrRef.current.querySelector('svg');
      if (svg) {
        svg.setAttribute('viewBox', '0 0 600 600');
        svg.setAttribute('preserveAspectRatio', 'xMinYMin meet');
      }
    }
  }, [showQR, wordcloud, participateUrl]);

  // Status actions
  const handleStatusChange = async (newStatus) => {
    try {
      const response = await api.put(`/api/teachertools/wordcloud/${wcId}/status`, { status: newStatus });
      if (response.data.status) {
        setWordcloud((prev) => ({ ...prev, status: newStatus }));
        setMessage(response.data.message);
        setTimeout(() => setMessage(''), 3000);
      } else {
        setError(response.data.message);
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Fehler beim Statuswechsel.');
    }
  };

  const handleDelete = async () => {
    try {
      const response = await api.delete(`/api/teachertools/wordcloud/${wcId}`);
      if (response.data.status) {
        navigate('/teachertools/wordcloud');
      } else {
        setError(response.data.message);
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Fehler beim Löschen.');
    }
    setShowDeleteConfirm(false);
  };

  const handleExportPng = async () => {
    if (!cloudRef.current) return;
    try {
      const dataUrl = await toPng(cloudRef.current, { backgroundColor: '#ffffff' });
      const link = document.createElement('a');
      link.download = `wortwolke-${wordcloud?.name || 'export'}.png`;
      link.href = dataUrl;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      console.error('Export error:', err);
      setError('Fehler beim Exportieren.');
    }
  };

  const handleDownloadQR = () => {
    if (qrCodeInstance.current) {
      qrCodeInstance.current.download({ name: `wortwolke-qr-${wordcloud?.access_code}`, extension: 'png' });
    }
  };

  const copyLink = () => {
    const text = participateUrl;
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      navigator.clipboard.writeText(text).then(() => {
        setLinkCopied(true);
        setTimeout(() => setLinkCopied(false), 2000);
      }).catch(() => {
        fallbackCopy(text);
      });
    } else {
      fallbackCopy(text);
    }
  };

  const fallbackCopy = (text) => {
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      setError('Link konnte nicht kopiert werden. Bitte manuell kopieren.');
      setTimeout(() => setError(''), 3000);
    }
  };

  // Fullscreen toggle
  const toggleFullscreen = () => {
    setIsFullscreen((prev) => !prev);
  };

  // Close fullscreen on Escape key
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isFullscreen]);

  // Settings modal helpers
  const openSettingsModal = () => {
    setEditCaseSensitive(wordcloud?.case_sensitive || false);
    setEditShowResults(wordcloud?.show_results_to_participants || false);
    setEditGroups(wordcloud?.groups?.map(g => g.id) || []);
    setEditAllowDownload(wordcloud?.allow_participant_download || false);
    setEditMaxChars(wordcloud?.max_chars_per_answer || 20);
    setEditAnonymous(wordcloud?.anonymous_answers !== false);
    setEditRotationMode(wordcloud?.rotation_mode || 'mixed');
    setEditRotationAngles(
      Array.isArray(wordcloud?.rotation_angles)
        ? wordcloud.rotation_angles.join(', ')
        : '0, 90'
    );
    setEditRotationProbability(wordcloud?.rotation_probability ?? 0.5);
    // Load available groups
    api.get('/api/teachertools/groups')
      .then(res => setGroups(res.data.groups || []))
      .catch(() => {});
    setShowSettings(true);
  };

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      const parsedAngles = editRotationAngles.split(',').map(a => parseInt(a.trim(), 10)).filter(a => !isNaN(a));
      const response = await api.put(`/api/teachertools/wordcloud/${wcId}`, {
        case_sensitive: editCaseSensitive,
        show_results_to_participants: editShowResults,
        group_ids: editGroups,
        allow_participant_download: editAllowDownload,
        max_chars_per_answer: Math.max(1, Math.min(100, parseInt(editMaxChars, 10) || 20)),
        anonymous_answers: editAnonymous,
        rotation_mode: editRotationMode,
        rotation_angles: parsedAngles.length > 0 ? parsedAngles : [0, 90],
        rotation_probability: Math.max(0, Math.min(1, parseFloat(editRotationProbability) || 0.5)),
      });
      if (response.data.status) {
        setWordcloud((prev) => ({
          ...prev,
          case_sensitive: editCaseSensitive,
          show_results_to_participants: editShowResults,
          allow_participant_download: editAllowDownload,
          max_chars_per_answer: Math.max(1, Math.min(100, parseInt(editMaxChars, 10) || 20)),
          anonymous_answers: editAnonymous,
          rotation_mode: editRotationMode,
          rotation_angles: parsedAngles.length > 0 ? parsedAngles : [0, 90],
          rotation_probability: Math.max(0, Math.min(1, parseFloat(editRotationProbability) || 0.5)),
          groups: editGroups.map(id => {
            const g = groups.find(gr => gr.id === id);
            return g || { id, name: `Gruppe ${id}` };
          }),
        }));
        setMessage('Einstellungen gespeichert.');
        setTimeout(() => setMessage(''), 2000);
        setShowSettings(false);
      } else {
        setError(response.data.message || 'Fehler beim Speichern.');
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Fehler beim Speichern.');
    } finally {
      setSavingSettings(false);
    }
  };

  const groupNames = (ids) =>
    ids.map((id) => groups.find((g) => g.id === id)?.name).filter(Boolean);

  if (loading) {
    return (
      <PageContainer>
        <Spinner />
      </PageContainer>
    );
  }

  if (!wordcloud) {
    return (
      <PageContainer>
        <MessageBox type="error" text="Wortwolke nicht gefunden." />
        <Button variant="secondary" onClick={() => navigate('/teachertools/wordcloud')}>
          Zurück
        </Button>
      </PageContainer>
    );
  }

  const statusLabels = {
    active: 'Aktiv',
    paused: 'Pausiert',
    stopped: 'Beendet',
    archived: 'Archiviert',
  };

  const statusColors = {
    active: '#16a34a',
    paused: '#d97706',
    stopped: '#dc2626',
    archived: '#6b7280',
  };

  return (
    <PageContainer>
    {hasPermission('teachertools.wordcloud') && (
        <>
      <Card variant="header" title={wordcloud.name}>
        <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center', flexWrap: 'wrap' }}>
          <span
            className="wc-card__status"
            style={{ backgroundColor: statusColors[wordcloud.status] }}
          >
            {statusLabels[wordcloud.status]}
          </span>
          <Button variant="secondary" onClick={() => navigate('/teachertools/wordcloud', { state: fromArchive ? { tab: 'archived' } : undefined })}>
            Zurück
          </Button>
        </div>
      </Card>

      {message && <MessageBox type="success" text={message} />}
      {error && <MessageBox type="error" text={error} />}
      <div className="wc-stats-row" style={{ marginBottom: 'var(--space-lg)' }}>
      {/* Participation Access */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <h3 style={{ marginBottom: 'var(--space-md)' }}>Teilnahme-Zugang</h3>
        <div className="wc-access-section">
          <div className="wc-access-info">
            <div className="wc-access-row">
              <span className="wc-access-label">Zugangscode:</span>
              <span className="wc-access-value wc-access-code">{wordcloud.access_code}</span>
            </div>
            <div className="wc-access-row">
              <span className="wc-access-label">Link:</span>
              <span className="wc-access-value wc-access-link">{participateUrl}</span>
            </div>
          </div>
          <div className="wc-access-actions">
            <Button variant={linkCopied ? 'primary' : 'secondary'} size="sm" onClick={copyLink}>
              {linkCopied ? '✓ Kopiert!' : 'Link kopieren'}
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setShowQR(true)}>
              QR-Code anzeigen
            </Button>
          </div>
        </div>
      </Card>
      {/* Session Controls (archive/delete – pause/resume is in header) */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <h3 style={{ marginBottom: 'var(--space-md)' }}>Steuerung</h3>

        <div className="wc-controls">
          {wordcloud.status === 'active' && (
            <Button variant="ghost" onClick={() => handleStatusChange('paused')}>
              Pausieren
            </Button>
          )}
          {wordcloud.status === 'paused' && (
            <Button variant="primary" onClick={() => handleStatusChange('active')}>
              Fortsetzen
            </Button>
          )}
          {wordcloud.status !== 'archived' && (
            <Button variant="secondary" onClick={() => setShowArchiveConfirm(true)}>
              Archivieren
            </Button>
          )}
          <Button variant="danger" onClick={() => setShowDeleteConfirm(true)}>
            Löschen
          </Button>
        </div>
      </Card>
      </div>

      {/* Statistics */}
      <div className="wc-stats-row" style={{ marginBottom: 'var(--space-lg)' }}>
        <StatCard value={wordcloud.submission_count} label="Einreichungen" variant="info" />
        <StatCard value={wordcloud.unique_words} label="Verschiedene Wörter" variant="default" />
        <StatCard value={wordcloud.groups?.length || 'Alle'} label="Gruppen" variant="default" />
        <StatCard value={wordcloud.max_answers_per_participant || '∞'} label="Max. Antworten" variant="default" />
      </div>

      {/* Live Word Cloud */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <div className="wc-cloud-header">
          <h3>Live Wortwolke</h3>
          <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
            <Button variant="secondary" size="sm" onClick={toggleFullscreen} disabled={words.length === 0}>
              Vollbild
            </Button>
            <Button variant="secondary" size="sm" onClick={handleExportPng} disabled={words.length === 0}>
              Als PNG exportieren
            </Button>
          </div>
        </div>
        <div ref={cloudRef} className="wc-cloud-container">
          <WordCloudCanvas
            words={words}
            width={800}
            height={500}
            rotationMode={wordcloud.rotation_mode || 'mixed'}
            rotationAngles={wordcloud.rotation_angles || [0, 90]}
            rotationProbability={wordcloud.rotation_probability ?? 0.5}
          />
        </div>
      </Card>



      {/* Word Cloud Settings Info */}
      <Card>
        <div className="wc-cloud-header">
          <h3>Einstellungen</h3>
          <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
            {wordcloud.submissions_detail && wordcloud.submissions_detail.length > 0 && (
              <Button variant="secondary" size="sm" onClick={() => setShowSubmissions(true)}>
                Antworten ({wordcloud.submissions_detail.length})
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={openSettingsModal}>
              Bearbeiten
            </Button>
          </div>
        </div>
        <div className="wc-settings-info">
          <div className="wc-settings-row">
            <span>Groß-/Kleinschreibung:</span>
            <span>{wordcloud.case_sensitive ? 'Wird beachtet' : 'Wird nicht beachtet'}</span>
          </div>
          <div className="wc-settings-row">
            <span>Ergebnisse für Teilnehmer:</span>
            <span>{wordcloud.show_results_to_participants ? 'Sichtbar' : 'Nicht sichtbar'}</span>
          </div>
          <div className="wc-settings-row">
            <span>Download für Teilnehmer:</span>
            <span>{wordcloud.allow_participant_download ? 'Erlaubt' : 'Nicht erlaubt'}</span>
          </div>
          <div className="wc-settings-row">
            <span>Max. Antworten pro Teilnehmer:</span>
            <span>{wordcloud.max_answers_per_participant === 0 ? 'Unbegrenzt' : wordcloud.max_answers_per_participant}</span>
          </div>
          <div className="wc-settings-row">
            <span>Max. Zeichen pro Antwort:</span>
            <span>{wordcloud.max_chars_per_answer || 20}</span>
          </div>
          <div className="wc-settings-row">
            <span>Antwortmodus:</span>
            <span>{wordcloud.anonymous_answers !== false ? 'Anonym' : 'Identifiziert'}</span>
          </div>
          <div className="wc-settings-row">
            <span>Rotation:</span>
            <span>
              {wordcloud.rotation_mode === 'horizontal' && 'Nur horizontal'}
              {wordcloud.rotation_mode === 'vertical' && 'Nur vertikal'}
              {wordcloud.rotation_mode === 'mixed' && `Gemischt (${Math.round((wordcloud.rotation_probability ?? 0.5) * 100)}%)`}
              {wordcloud.rotation_mode === 'custom' && `Benutzerdefiniert (${Array.isArray(wordcloud.rotation_angles) ? wordcloud.rotation_angles.join('°, ') + '°' : '0°, 90°'})`}
            </span>
          </div>
          <div className="wc-settings-row">
            <span>Gruppen:</span>
            <span>
              {wordcloud.groups?.length > 0 ? (
                <span className="wc-group-tags">
                  {wordcloud.groups.map((g) => (
                    <span key={g.id} className="wc-group-tag">{g.name}</span>
                  ))}
                </span>
              ) : 'Alle Gruppen'}
            </span>
          </div>
          {wordcloud.description && (
            <div className="wc-settings-row">
              <span>Beschreibung:</span>
              <span>{wordcloud.description}</span>
            </div>
          )}
        </div>
      </Card>

      {/* QR Code Modal */}
      {showQR && (
        <Modal
          title="QR-Code für Teilnahme"
          onClose={() => setShowQR(false)}
          size="md"
          footer={
            <>
              <Button variant="secondary" onClick={() => setShowQR(false)}>Schließen</Button>
              <Button variant="primary" onClick={handleDownloadQR}>Download</Button>
            </>
          }
        >
          <div className="wc-qr-modal-content">
            <div ref={qrRef} className="wc-qr-code"></div>
            <p className="wc-qr-url">{participateUrl}</p>
            <p className="wc-qr-code-text">Code: <strong>{wordcloud.access_code}</strong></p>
          </div>
        </Modal>
      )}

      {/* Archive Confirmation Modal */}
      {showArchiveConfirm && (
        <Modal
          title="Wortwolke archivieren"
          onClose={() => setShowArchiveConfirm(false)}
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setShowArchiveConfirm(false)}>Abbrechen</Button>
              <Button variant="danger" onClick={() => { handleStatusChange('archived'); setShowArchiveConfirm(false); }}>Archivieren</Button>
            </>
          }
        >
          <p>Möchten Sie die Wortwolke <strong>{wordcloud.name}</strong> wirklich archivieren?</p>
          <p>Die Wortwolke wird dauerhaft inaktiv. Teilnehmer können keine neuen Wörter mehr einreichen.</p>
          <p>Bestehende Einreichungen bleiben je nach Einstellungen sichtbar.</p>
        </Modal>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <Modal
          title="Wortwolke löschen"
          onClose={() => setShowDeleteConfirm(false)}
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setShowDeleteConfirm(false)}>Abbrechen</Button>
              <Button variant="danger" onClick={handleDelete}>Endgültig löschen</Button>
            </>
          }
        >
          <p>Möchten Sie die Wortwolke <strong>{wordcloud.name}</strong> wirklich löschen?</p>
          <p>Diese Aktion kann nicht rückgängig gemacht werden.</p>
        </Modal>
      )}

      {/* Settings Edit Modal */}
      {showSettings && (
        <Modal
          title="Einstellungen bearbeiten"
          onClose={() => setShowSettings(false)}
          size="md"
          footer={
            <>
              <Button variant="secondary" onClick={() => setShowSettings(false)}>Abbrechen</Button>
              <Button variant="primary" onClick={handleSaveSettings} loading={savingSettings}>Speichern</Button>
            </>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            <div>
              <CheckboxInput
                id="edit-case-sensitive"
                label="Groß-/Kleinschreibung beachten"
                checked={editCaseSensitive}
                onChange={(e) => setEditCaseSensitive(e.target.checked)}
              />
              <div className="wc-setting-hint">
                {editCaseSensitive
                  ? '"Wort" und "wort" werden als unterschiedliche Einträge gezählt.'
                  : '"Wort" und "wort" werden zusammengeführt.'}
              </div>
            </div>

            <div>
              <CheckboxInput
                id="edit-show-results"
                label="Ergebnisse für Teilnehmer sichtbar"
                checked={editShowResults}
                onChange={(e) => setEditShowResults(e.target.checked)}
              />
              <div className="wc-setting-hint">
                {editShowResults
                  ? 'Teilnehmer können die Wortwolke live sehen.'
                  : 'Nur Sie können die Wortwolke sehen.'}
              </div>
            </div>

            <div>
              <CheckboxInput
                id="edit-allow-download"
                label="Teilnehmer dürfen Wortwolke als PNG herunterladen"
                checked={editAllowDownload}
                onChange={(e) => setEditAllowDownload(e.target.checked)}
              />
            </div>

            <div>
              <CheckboxInput
                id="edit-anonymous"
                label="Anonyme Antworten"
                checked={editAnonymous}
                onChange={(e) => setEditAnonymous(e.target.checked)}
              />
              <div className="wc-setting-hint">
                {editAnonymous
                  ? 'Antworten sind anonym.'
                  : 'Sie können sehen, wer welches Wort eingereicht hat.'}
              </div>
            </div>

            <FormGroup label="Max. Zeichen pro Antwort" htmlFor="edit-max-chars">
              <TextInput
                id="edit-max-chars"
                type="number"
                value={editMaxChars}
                onChange={(e) => setEditMaxChars(e.target.value)}
                min="1"
                max="100"
                helperText="Min: 1, Max: 100"
              />
            </FormGroup>

            <div>
              <h4 style={{ marginBottom: 'var(--space-sm)' }}>Rotation</h4>
              <FormGroup label="Rotationsmodus" htmlFor="edit-rotation-mode">
                <select
                  id="edit-rotation-mode"
                  className="wc-select-input"
                  value={editRotationMode}
                  onChange={(e) => setEditRotationMode(e.target.value)}
                >
                  <option value="mixed">Gemischt</option>
                  <option value="horizontal">Nur horizontal</option>
                  <option value="vertical">Nur vertikal</option>
                  <option value="custom">Benutzerdefiniert</option>
                </select>
              </FormGroup>

              {(editRotationMode === 'mixed' || editRotationMode === 'custom') && (
                <FormGroup label="Winkel (kommagetrennt)" htmlFor="edit-rotation-angles" style={{ marginTop: 'var(--space-sm)' }}>
                  <TextInput
                    id="edit-rotation-angles"
                    value={editRotationAngles}
                    onChange={(e) => setEditRotationAngles(e.target.value)}
                    placeholder="0, 90"
                    helperText="z.B. -45, 0, 45, 90"
                  />
                </FormGroup>
              )}

              {editRotationMode === 'mixed' && (
                <FormGroup label="Rotationswahrscheinlichkeit" htmlFor="edit-rotation-prob" style={{ marginTop: 'var(--space-sm)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                    <input
                      id="edit-rotation-prob"
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={editRotationProbability}
                      onChange={(e) => setEditRotationProbability(parseFloat(e.target.value))}
                      style={{ flex: 1 }}
                    />
                    <span style={{ minWidth: '3ch', textAlign: 'center' }}>{Math.round(editRotationProbability * 100)}%</span>
                  </div>
                </FormGroup>
              )}
            </div>

            <div>
              <h4 style={{ marginBottom: 'var(--space-sm)' }}>Teilnehmergruppen</h4>
              <p className="wc-setting-hint" style={{ marginBottom: 'var(--space-sm)' }}>
                Beschränken Sie die Teilnahme auf bestimmte Gruppen. Ohne Auswahl können alle teilnehmen.
              </p>
              {editGroups.length > 0 ? (
                <div className="wc-selected-groups">
                  <div className="wc-group-tags">
                    {groupNames(editGroups).map((name, i) => (
                      <span key={i} className="wc-group-tag">{name}</span>
                    ))}
                  </div>
                  <Button variant="secondary" size="sm" onClick={() => setShowGroupModal(true)}>
                    Gruppen ändern
                  </Button>
                </div>
              ) : (
                <Button variant="secondary" size="sm" onClick={() => setShowGroupModal(true)}>
                  Gruppen auswählen
                </Button>
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* Group Select Modal */}
      {showGroupModal && (
        <GroupSelectModal
          groups={groups}
          selectedIds={editGroups}
          onConfirm={(ids) => {
            setEditGroups(ids);
            setShowGroupModal(false);
          }}
          onClose={() => setShowGroupModal(false)}
        />
      )}

      {/* Submissions Modal */}
      {showSubmissions && (
        <Modal
          title="Einreichungen"
          onClose={() => setShowSubmissions(false)}
          size="lg"
          footer={
            <Button variant="secondary" onClick={() => setShowSubmissions(false)}>Schließen</Button>
          }
        >
          {wordcloud.submissions_detail && wordcloud.submissions_detail.length > 0 ? (
            <div className="wc-submissions-table-wrapper">
              <table className="wc-submissions-table">
                <thead>
                  <tr>
                    <th>Wort</th>
                    <th>Teilnehmer</th>
                    <th>Zeitpunkt</th>
                  </tr>
                </thead>
                <tbody>
                  {wordcloud.submissions_detail.map((s, i) => (
                    <tr key={i}>
                      <td>{s.word}</td>
                      <td>
                        {s.is_anonymous
                          ? <span style={{ color: 'var(--color-text-muted)', fontStyle: 'italic' }}>Anonym</span>
                          : s.user_name
                        }
                      </td>
                      <td>{s.submitted_at ? new Date(s.submitted_at).toLocaleString('de-DE') : '–'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p style={{ color: 'var(--color-text-secondary)', textAlign: 'center', padding: 'var(--space-lg)' }}>
              Noch keine Einreichungen vorhanden.
            </p>
          )}
        </Modal>
      )}

      {/* Fullscreen Overlay */}
      {isFullscreen && (
        <div className="wc-fullscreen-overlay" ref={fullscreenRef} onClick={toggleFullscreen}>
          <div className="wc-fullscreen-content" onClick={(e) => e.stopPropagation()}>
            <Button
              variant="secondary"
              size="sm"
              className="wc-fullscreen-close"
              onClick={toggleFullscreen}
            >
              ✕ Schließen
            </Button>
            <WordCloudCanvas
              words={words}
              width={fullscreenDims.w}
              height={fullscreenDims.h}
              rotationMode={wordcloud.rotation_mode || 'mixed'}
              rotationAngles={wordcloud.rotation_angles || [0, 90]}
              rotationProbability={wordcloud.rotation_probability ?? 0.5}
            />
          </div>
        </div>
      )}
      </>
        )}
    </PageContainer>
  );
};

export default WordCloudDetail;

import { useState, useEffect } from 'react';
import api from '../../utils/api';
import { PageContainer, Card, Button, MessageBox, Spinner, Modal, SearchInput } from '../../components/shared';
import { STATUS_LABELS, STATUS_LABELS_SPECIAL } from './surveyConstants';
import useAutoMessage from './useAutoMessage';
import './Surveys.css';

const SURVEY_TYPE_LABELS = {
  normal: 'Umfrage',
  template: 'Vorlage',
  special: 'Spezialumfrage',
};

/**
 * Admin-only page to recover or permanently delete soft-deleted surveys.
 * Split layout: user list on the left, deleted surveys for selected user on the right.
 */
const SurveyRecovery = () => {
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [deletedSurveys, setDeletedSurveys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingSurveys, setLoadingSurveys] = useState(false);
  const [message, setMessage] = useAutoMessage();
  const [confirmAction, setConfirmAction] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const res = await api.get('/api/surveys/admin/deleted');
      setUsers(res.data.users || []);
      // If previously selected user is gone, deselect
      if (selectedUser && !(res.data.users || []).find(u => u.uuid === selectedUser.uuid)) {
        setSelectedUser(null);
        setDeletedSurveys([]);
      }
    } catch {
      setMessage({ text: 'Fehler beim Laden der Benutzer', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const loadDeletedSurveys = async (user) => {
    try {
      setLoadingSurveys(true);
      const res = await api.get(`/api/surveys/admin/deleted/${user.uuid}`);
      setDeletedSurveys(res.data.surveys || []);
    } catch {
      setMessage({ text: 'Fehler beim Laden der gelöschten Umfragen', type: 'error' });
    } finally {
      setLoadingSurveys(false);
    }
  };

  const selectUser = (user) => {
    setSelectedUser(user);
    loadDeletedSurveys(user);
  };

  const handleRestore = async (survey) => {
    setActionLoading(true);
    try {
      const type = survey.survey_type === 'special' ? 'special' : 'normal';
      const res = await api.post(`/api/surveys/admin/deleted/${survey.id}/restore?type=${type}`);
      if (res.data.status) {
        setMessage({ text: res.data.message, type: 'success' });
        // Refresh both user list and survey list
        await Promise.all([loadUsers(), loadDeletedSurveys(selectedUser)]);
      } else {
        setMessage({ text: res.data.message, type: 'error' });
      }
    } catch {
      setMessage({ text: 'Fehler beim Wiederherstellen', type: 'error' });
    } finally {
      setActionLoading(false);
      setConfirmAction(null);
    }
  };

  const handlePermanentDelete = async (survey) => {
    setActionLoading(true);
    try {
      const type = survey.survey_type === 'special' ? 'special' : 'normal';
      const res = await api.delete(`/api/surveys/admin/deleted/${survey.id}/permanent?type=${type}`);
      if (res.data.status) {
        setMessage({ text: res.data.message, type: 'success' });
        await Promise.all([loadUsers(), loadDeletedSurveys(selectedUser)]);
      } else {
        setMessage({ text: res.data.message, type: 'error' });
      }
    } catch {
      setMessage({ text: 'Fehler beim endgültigen Löschen', type: 'error' });
    } finally {
      setActionLoading(false);
      setConfirmAction(null);
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return '—';
    return new Date(isoString).toLocaleDateString('de-DE', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  const getStatusLabel = (survey) => {
    if (survey.survey_type === 'special') {
      return STATUS_LABELS_SPECIAL[survey.status] || survey.status;
    }
    return STATUS_LABELS[survey.status] || survey.status;
  };

  const filteredUsers = users.filter(u =>
    u.username.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return <PageContainer><Card variant="header" title="Papierkorb" /><Spinner /></PageContainer>;
  }

  return (
    <PageContainer>
      <Card variant="header" title="Papierkorb – Gelöschte Umfragen" />
      {message && <MessageBox text={message.text} type={message.type} />}

      {users.length === 0 ? (
        <div className="surveys-empty">
          <div className="surveys-empty__icon">🗑️</div>
          <div className="surveys-empty__text">Keine gelöschten Umfragen vorhanden</div>
        </div>
      ) : (
        <div className="recovery-layout">
          {/* Left panel: User list */}
          <div className="recovery-users">
            <div className="recovery-users__header">
              <h3 className="recovery-users__title">Benutzer</h3>
              <SearchInput
                placeholder="Suchen..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="recovery-users__search"
              />
            </div>
            <div className="recovery-users__list">
              {filteredUsers.map(user => (
                <div
                  key={user.uuid}
                  className={`recovery-user-item ${selectedUser?.uuid === user.uuid ? 'recovery-user-item--active' : ''}`}
                  onClick={() => selectUser(user)}
                >
                  <span className="recovery-user-item__name">{user.username}</span>
                  <span className="recovery-user-item__badge">{user.deleted_count}</span>
                </div>
              ))}
              {filteredUsers.length === 0 && (
                <div className="recovery-users__empty">Keine Benutzer gefunden</div>
              )}
            </div>
          </div>

          {/* Right panel: Deleted surveys */}
          <div className="recovery-surveys">
            {!selectedUser ? (
              <div className="recovery-surveys__placeholder">
                <div className="recovery-surveys__placeholder-icon">👈</div>
                <div className="recovery-surveys__placeholder-text">
                  Wählen Sie einen Benutzer aus, um gelöschte Umfragen anzuzeigen
                </div>
              </div>
            ) : loadingSurveys ? (
              <Spinner />
            ) : (
              <>
                <h3 className="recovery-surveys__title">
                  Gelöschte Umfragen von {selectedUser.username}
                </h3>
                {deletedSurveys.length === 0 ? (
                  <div className="recovery-surveys__placeholder">
                    <div className="recovery-surveys__placeholder-text">Keine gelöschten Umfragen</div>
                  </div>
                ) : (
                  <div className="recovery-surveys__list">
                    {deletedSurveys.map(survey => (
                      <div key={`${survey.survey_type}-${survey.id}`} className="recovery-survey-card">
                        <div className="recovery-survey-card__header">
                          <div className="recovery-survey-card__title">{survey.title}</div>
                          <span className={`survey-card__status survey-card__status--${survey.survey_type === 'special' ? 'special' : (survey.is_template ? 'template' : survey.status)}`}>
                            {SURVEY_TYPE_LABELS[survey.survey_type]}
                          </span>
                        </div>
                        {survey.description && (
                          <div className="recovery-survey-card__description">{survey.description}</div>
                        )}
                        <div className="recovery-survey-card__meta">
                          <span>Status: {getStatusLabel(survey)}</span>
                          <span>Gelöscht am: {formatDate(survey.deleted_at)}</span>
                          {survey.survey_type !== 'special' && (
                            <span>Antworten: {survey.response_count ?? 0}</span>
                          )}
                          {survey.survey_type === 'special' && (
                            <span>Schüler: {survey.student_count ?? 0}</span>
                          )}
                        </div>
                        <div>
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => setConfirmAction({ type: 'restore', survey })}
                            disabled={actionLoading}
                          >
                            Wiederherstellen
                          </Button>
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => setConfirmAction({ type: 'permanent', survey })}
                            disabled={actionLoading}
                          >
                            Löschen
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Confirmation Modal */}
      {confirmAction && (
        <Modal
          title={confirmAction.type === 'restore' ? 'Umfrage wiederherstellen?' : 'Endgültig löschen?'}
          onClose={() => !actionLoading && setConfirmAction(null)}
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmAction(null)} disabled={actionLoading}>
                Abbrechen
              </Button>
              <Button
                variant={confirmAction.type === 'restore' ? 'primary' : 'danger'}
                onClick={() => confirmAction.type === 'restore'
                  ? handleRestore(confirmAction.survey)
                  : handlePermanentDelete(confirmAction.survey)
                }
                disabled={actionLoading}
              >
                {actionLoading ? 'Bitte warten...' : (confirmAction.type === 'restore' ? 'Wiederherstellen' : 'Endgültig löschen')}
              </Button>
            </>
          }
        >
          {confirmAction.type === 'restore' ? (
            <p>
              Möchten Sie die Umfrage <strong>{confirmAction.survey.title}</strong> wiederherstellen?
              Sie wird dem Ersteller wieder zur Verfügung stehen.
            </p>
          ) : (
            <p style={{ color: 'var(--color-danger, #dc2626)' }}>
              Möchten Sie die Umfrage <strong>{confirmAction.survey.title}</strong> endgültig löschen?
              Alle zugehörigen Daten (Antworten, Teilnehmer, Bewertungen) werden unwiderruflich gelöscht.
            </p>
          )}
        </Modal>
      )}
    </PageContainer>
  );
};

export default SurveyRecovery;

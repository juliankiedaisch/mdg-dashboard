import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../utils/api';
import {
  PageContainer, Card, Button, Modal, MessageBox, Spinner, Tabs,
} from '../../components/shared';
import NewQuestionModal from './NewQuestionModal';
import SurveyResults from './SurveyResults';
import { QUESTION_TYPE_LABELS, STATUS_LABELS } from './surveyConstants';
import useAutoMessage from './useAutoMessage';
import './Surveys.css';

const SurveyDetail = () => {
  const { surveyId } = useParams();
  const navigate = useNavigate();

  const [survey, setSurvey] = useState(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useAutoMessage();
  const [showAddQuestion, setShowAddQuestion] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [tab, setTab] = useState('questions'); // 'questions' | 'results'

  const [templateSaved, setTemplateSaved] = useState(false);

  useEffect(() => {
    loadSurvey();
  }, [surveyId]);

  const loadSurvey = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/api/surveys/${surveyId}`);
      setSurvey(response.data.survey);
    } catch (error) {
      console.error('Error loading survey:', error);
      setMessage({ text: 'Fehler beim Laden der Umfrage', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (newStatus) => {
    try {
      await api.put(`/api/surveys/${surveyId}`, { status: newStatus });
      setMessage({ text: `Status geändert: ${STATUS_LABELS[newStatus]}`, type: 'success' });
      loadSurvey();
    } catch (error) {
      setMessage({ text: 'Fehler beim Statuswechsel', type: 'error' });
    }
  };

  const handleDelete = async () => {
    try {
      await api.delete(`/api/surveys/${surveyId}`);
      setMessage({ text: 'Umfrage gelöscht', type: 'success' });
      navigate('/surveys');
    } catch (error) {
      setMessage({ text: 'Fehler beim Löschen', type: 'error' });
    }
  };

  const handleDeleteQuestion = async (questionId) => {
    try {
      await api.delete(`/api/surveys/questions/${questionId}`);
      setMessage({ text: 'Frage gelöscht', type: 'success' });
      loadSurvey();
    } catch (error) {
      setMessage({ text: 'Fehler beim Löschen der Frage', type: 'error' });
    }
  };

  const handleSaveAsTemplate = async () => {
    try {
      await api.post(`/api/surveys/${surveyId}/save-as-template`);
      setTemplateSaved(true);
      setTimeout(() => setTemplateSaved(false), 3000);
    } catch (error) {
      setMessage({ text: 'Fehler beim Erstellen der Vorlage', type: 'error' });
    }
  };

  const handleQuestionAdded = () => {
    setShowAddQuestion(false);
    loadSurvey();
    setMessage({ text: 'Frage hinzugefügt', type: 'success' });
  };

  if (loading) return <PageContainer><Card variant="header" title="Umfrage" /><Spinner /></PageContainer>;
  if (!survey) return <PageContainer><Card variant="header" title="Umfrage" /><p>Umfrage nicht gefunden.</p></PageContainer>;

  return (
    <PageContainer>
      <Card variant="header" title={survey.title}>
        <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center', flexWrap: 'wrap' }}>
          <span className={`survey-card__status survey-card__status--${survey.status}`}>
            {STATUS_LABELS[survey.status] || survey.status}
          </span>
          <Button variant="secondary" onClick={() => {
            const backTab = survey.is_template ? 'templates' : survey.status === 'archived' ? 'archived' : 'active';
            navigate(`/surveys?tab=${backTab}`);
          }}>← Zurück</Button>


        </div>
      </Card>
      {message && <MessageBox text={message.text} type={message.type} />}
      {survey.description && (
        <p style={{ marginTop: '8px', color: 'var(--color-text-secondary)' }}>{survey.description}</p>
      )}

      {/* Info Card */}
      <div className="grid-lg-2to1">
      <Card className="survey-info-card">
        <div className="survey-info-grid">
          <div className="survey-info-item">
            <span className="survey-info-label">Antworten</span>
            <span className="survey-info-value">{survey.response_count}</span>
          </div>
          <div className="survey-info-item">
            <span className="survey-info-label">Fragen</span>
            <span className="survey-info-value">{survey.questions?.length || 0}</span>
          </div>
          <div className="survey-info-item">
            <span className="survey-info-label">Anonym</span>
            <span className="survey-info-value">{survey.anonymous ? 'Ja' : 'Nein'}</span>
          </div>
          {!survey.is_template && (
            <div className="survey-info-item">
              <span className="survey-info-label">Bearbeitbar</span>
              <span className="survey-info-value">{survey.allow_edit_response ? 'Ja' : 'Nein'}</span>
            </div>
          )}
          {!survey.is_template && (
            <div className="survey-info-item">
              <span className="survey-info-label">Gruppen</span>
              <span className="survey-info-value">
                {survey.groups?.length > 0
                  ? survey.groups.map((g) => g.name).join(', ')
                  : 'Alle'}
              </span>
            </div>
          )}
          <div className="survey-info-item">
            <span className="survey-info-label">Erstellt</span>
            <span className="survey-info-value">
              {survey.created_at ? new Date(survey.created_at).toLocaleDateString('de-DE') : '—'}
            </span>
          </div>
        </div>
      </Card>
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <h3 style={{ marginBottom: 'var(--space-md)' }}>Steuerung</h3>
        <div className="grid">
          {!survey.is_template && (
            <Button variant={templateSaved ? 'success' : 'secondary'} onClick={handleSaveAsTemplate} disabled={templateSaved}>
              {templateSaved ? '✓ Vorlage erstellt' : 'Als Vorlage speichern'}
            </Button>
          )}
          {survey.status !== 'active' && survey.status !== 'archived' && (
            <Button variant="secondary" onClick={() => navigate(`/surveys/${surveyId}/edit`)}>
              Bearbeiten
            </Button>
          )}
          {survey.status === 'draft' && (
            <Button variant="success" onClick={() => handleStatusChange('active')}>
              Aktivieren
            </Button>
          )}
          {survey.status === 'active' && (
            <Button variant="secondary" onClick={() => handleStatusChange('closed')}>
              Deaktivieren
            </Button>
          )}
          {survey.status === 'closed' && (
            <Button variant="success" onClick={() => handleStatusChange('active')}>
              Reaktivieren
            </Button>
          )}
          {survey.status === 'closed' && (
            <Button variant="secondary" onClick={() => setConfirmArchive(true)}>
              Archivieren
            </Button>
          )}
          <Button variant="danger" onClick={() => setConfirmDelete(true)}>
            Löschen
          </Button>
        </div>
      </Card>
      </div>
      {/* Tabs */}
      <Tabs
        tabs={[
          { id: 'questions', label: `Fragen (${survey.questions?.length || 0})` },
          { id: 'results', label: `Ergebnisse (${survey.response_count})` },
        ]}
        activeTab={tab}
        onChange={setTab}
      />

      {/* Questions Tab */}
      {tab === 'questions' && (
        <div className="questions-section">
          <div className="questions-section__header">
            <span className="questions-section__title">Fragen</span>
          </div>

          {survey.questions?.length === 0 ? (
            <div className="surveys-empty">
              <div className="surveys-empty__text">Keine Fragen vorhanden</div>
            </div>
          ) : (
            survey.questions.map((q, idx) => (
              <div
                key={q.id}
                className={`question-card ${q.groups?.length > 0 ? 'question-card--group-specific' : ''}`}
              >
                <div className="question-card__header">
                  <span className="question-card__number">Frage {idx + 1}</span>
                </div>
                <div className="question-card__text">{q.text}</div>
                <div>
                  <span className="question-card__type-badge">
                    {QUESTION_TYPE_LABELS[q.question_type] || q.question_type}
                  </span>
                  {q.required && (
                    <span className="question-card__type-badge">Pflicht</span>
                  )}
                  {q.groups?.length > 0 && (
                    <span className="question-card__group-badge">
                      Nur: {q.groups.map((g) => g.name).join(', ')}
                    </span>
                  )}
                </div>
                {q.options?.length > 0 && (
                  <div className="question-card__options">
                    {q.options.map((opt) => (
                      <div key={opt.id} className="question-card__option">
                        • {opt.text}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Results Tab */}
      {tab === 'results' && <SurveyResults surveyId={surveyId} />}

      {/* Add Question Modal */}
      {showAddQuestion && (
        <NewQuestionModal
          surveyId={surveyId}
          groups={survey.groups || []}
          onClose={() => setShowAddQuestion(false)}
          onAdded={handleQuestionAdded}
        />
      )}

      {/* Archive Confirmation */}
      {confirmArchive && (
        <Modal
          title="Umfrage archivieren?"
          onClose={() => setConfirmArchive(false)}
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmArchive(false)}>Abbrechen</Button>
              <Button variant="danger" onClick={() => { setConfirmArchive(false); handleStatusChange('archived'); }}>Archivieren</Button>
            </>
          }
        >
          <p>
            Die Umfrage wird archiviert und kann danach <strong>nicht mehr reaktiviert</strong> werden.
            Alle bisherigen Antworten bleiben erhalten, aber die Umfrage ist dauerhaft geschlossen.
          </p>
        </Modal>
      )}

      {/* Delete Confirmation */}
      {confirmDelete && (
        <Modal
          title="Umfrage löschen?"
          onClose={() => setConfirmDelete(false)}
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmDelete(false)}>Abbrechen</Button>
              <Button variant="danger" onClick={handleDelete}>Endgültig löschen</Button>
            </>
          }
        >
          <p>
            Sind Sie sicher, dass Sie die Umfrage <strong>"{survey.title}"</strong> und alle
            zugehörigen Antworten unwiderruflich löschen möchten?
          </p>
        </Modal>
      )}
    </PageContainer>
  );
};

export default SurveyDetail;

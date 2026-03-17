import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import DatePicker, { registerLocale } from 'react-datepicker';
import { de } from 'date-fns/locale';
import 'react-datepicker/dist/react-datepicker.css';
import api from '../../../../utils/api';
import { useUser } from '../../../../contexts/UserContext';
import { PageContainer, Card, Button, FormGroup, MessageBox, TextInput, TextArea, CheckboxInput } from '../../../../components/shared';
import GroupSelectModal from '../../components/GroupSelectModal';
import QuestionEditor from '../../components/QuestionEditor';
import useAutoMessage from '../../useAutoMessage';
import '../../Surveys.css';

registerLocale('de', de);

/**
 * Full-page survey creation form (reached via /surveys/new).
 * Permission-gated: requires surveys.manage.all or surveys.normal.manage.
 */
const NewSurvey = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const { hasPermission } = useUser();
  const canManageNormal = hasPermission(['surveys.manage.all', 'surveys.normal.manage']);
  const isTemplate = searchParams.get('template') === '1';
  // Template pre-fill: passed via navigate state from SurveyLanding
  const fromTemplate = location.state?.fromTemplate ?? null;
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [anonymous, setAnonymous] = useState(false);
  const [allowEditResponse, setAllowEditResponse] = useState(false);
  const [startsAt, setStartsAt] = useState(null);
  const [endsAt, setEndsAt] = useState(null);
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [groups, setGroups] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useAutoMessage();
  // Modal state
  const [showSurveyGroupModal, setShowSurveyGroupModal] = useState(false);
  const [questionGroupModalIdx, setQuestionGroupModalIdx] = useState(null);

  useEffect(() => {
    if (!canManageNormal) return;
    loadGroups();
    if (fromTemplate) {
      // Pre-fill form from template data (questions are included in the list response)
      setTitle(fromTemplate.title || '');
      setDescription(fromTemplate.description || '');
      setAnonymous(fromTemplate.anonymous || false);
      setAllowEditResponse(fromTemplate.allow_edit_response || false);
      setQuestions(
        (fromTemplate.questions || []).map((q) => ({
          text: q.text,
          question_type: q.question_type,
          required: q.required ?? true,
          group_ids: [], // clear template-specific group assignments
          options: (q.options || []).map((o) => ({ text: o.text })),
        }))
      );
    }
  }, [canManageNormal]);

  if (!canManageNormal) {
    return (
      <PageContainer>
        <Card variant="header" title="Keine Berechtigung">
          <Button variant="secondary" onClick={() => navigate('/surveys')}>← Zurück</Button>
        </Card>
        <MessageBox text="Sie haben keine Berechtigung, Umfragen zu erstellen." type="error" />
      </PageContainer>
    );
  }

  const loadGroups = async () => {
    try {
      const response = await api.get('/api/surveys/groups');
      setGroups(response.data.groups || []);
    } catch (err) {
      console.error('Error loading groups:', err);
    }
  };

  /** Helper to get group names from IDs */
  const groupNames = (ids) =>
    ids.map((id) => groups.find((g) => g.id === id)?.name).filter(Boolean);

  /** Update a single field on a question by index */
  const updateQuestion = (index, field, value) => {
    setQuestions((prev) => prev.map((q, i) => (i === index ? { ...q, [field]: value } : q)));
  };

  /* ── Submit ──────────────────────────────────────────── */
  const handleSubmit = async () => {
    if (!title.trim()) { setError('Bitte einen Titel eingeben.'); return; }

    for (let i = 0; i < questions.length; i++) {
      if (!questions[i].text.trim()) { setError(`Frage ${i + 1}: Text fehlt.`); return; }
      if (['single_choice', 'multiple_choice'].includes(questions[i].question_type)) {
        const nonEmpty = questions[i].options.filter((o) => o.text.trim());
        if (nonEmpty.length < 2) { setError(`Frage ${i + 1}: Mindestens 2 Optionen erforderlich.`); return; }
      }
    }

    setLoading(true);
    setError('');

    try {
      const payload = {
        title: title.trim(),
        description: description.trim(),
        anonymous,
        allow_edit_response: allowEditResponse,
        is_template: isTemplate,
        starts_at: !isTemplate && startsAt ? startsAt.toISOString() : null,
        ends_at: !isTemplate && endsAt ? endsAt.toISOString() : null,
        group_ids: !isTemplate ? selectedGroups : [],
        questions: questions.map((q, idx) => ({
          text: q.text.trim(),
          question_type: q.question_type,
          required: q.required,
          order: idx,
          group_ids: q.group_ids || [],
          options: q.options
            .filter((o) => o.text.trim())
            .map((o, oi) => ({ text: o.text.trim(), order: oi })),
        })),
      };

      await api.post('/api/surveys', payload);
      navigate('/surveys');
    } catch (err) {
      const msg = err.response?.data?.message || 'Fehler beim Erstellen.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageContainer>
      <Card variant="header" title={isTemplate ? 'Neue Vorlage erstellen' : fromTemplate ? 'Umfrage aus Vorlage erstellen' : 'Neue Umfrage erstellen'}>
        <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <Button variant="secondary" onClick={() => navigate('/surveys')}>Abbrechen</Button>
          <Button variant="primary" onClick={handleSubmit} loading={loading}>{isTemplate ? 'Vorlage erstellen' : 'Umfrage erstellen'}</Button>
        </div>
      </Card>
      {fromTemplate && (
        <MessageBox
          message={`Vorlage: „${fromTemplate.title}" (${fromTemplate.questions?.length || 0} Fragen). Daten vorausgefüllt – bitte anpassen.`}
          type="info"
        />
      )}
      {message && <MessageBox text={message.text} type={message.type} />}
      {error && <div style={{ color: '#ef4444', marginBottom: '12px' }}>{error}</div>}

      {/* ── Basic info ──────────────────────────────────── */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <TextInput
          id="survey-title"
          label="Titel"
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Umfrage-Titel"
          fullWidth
        />

        <TextArea
          id="survey-desc"
          label="Beschreibung"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optionale Beschreibung"
          rows={3}
          fullWidth
        />

        {!isTemplate && (
          <div className="survey-form-row">
            <FormGroup label="Startzeit" htmlFor="survey-start">
              <DatePicker
                id="survey-start"
                selected={startsAt}
                onChange={(date) => setStartsAt(date)}
                showTimeSelect
                timeIntervals={15}
                timeCaption="Uhrzeit"
                dateFormat="dd.MM.yyyy HH:mm"
                locale="de"
                placeholderText="Startzeit wählen"
                className="shared-input"
                isClearable
                autoComplete="off"
              />
            </FormGroup>

            <FormGroup label="Endzeit" htmlFor="survey-end">
              <DatePicker
                id="survey-end"
                selected={endsAt}
                onChange={(date) => setEndsAt(date)}
                showTimeSelect
                timeIntervals={15}
                timeCaption="Uhrzeit"
                dateFormat="dd.MM.yyyy HH:mm"
                locale="de"
                placeholderText="Endzeit wählen"
                className="shared-input"
                minDate={startsAt}
                isClearable
                autoComplete="off"
              />
            </FormGroup>
          </div>
        )}

        <FormGroup label="Anonym">
          <CheckboxInput
            label="Antworten anonym erfassen"
            checked={anonymous}
            onChange={(e) => setAnonymous(e.target.checked)}
          />
        </FormGroup>

        {!isTemplate && (
          <FormGroup label="Antworten bearbeitbar">
            <CheckboxInput
              label="Teilnehmer dürfen ihre Antworten nachträglich bearbeiten"
              checked={allowEditResponse}
              onChange={(e) => setAllowEditResponse(e.target.checked)}
            />
          </FormGroup>
        )}
      </Card>

      {/* ── Groups (only for non-templates) ─────────────── */}
      {!isTemplate && (
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <FormGroup label="Gruppen auswählen" hint="Wer soll teilnehmen? (Keine = alle)">
          <div className="group-picker">
            <Button variant="secondary" onClick={() => setShowSurveyGroupModal(true)}>
              Gruppen wählen…
            </Button>
            {selectedGroups.length > 0 && (
              <div className="group-picker__tags">
                {groupNames(selectedGroups).map((name, i) => (
                  <span key={i} className="group-picker__tag">{name}</span>
                ))}
              </div>
            )}
            {selectedGroups.length === 0 && (
              <span className="group-picker__hint">Alle Gruppen (keine Einschränkung)</span>
            )}
          </div>
        </FormGroup>
      </Card>
      )}

      {/* ── Questions ───────────────────────────────────── */}
      <Card>
        <div className="questions-section">
          <div className="questions-section__header">
            <span className="questions-section__title">Fragen</span>
            <Button variant="secondary" onClick={() => setQuestions([
              ...questions,
              { text: '', question_type: 'text', required: true, group_ids: [], options: [] },
            ])}>+ Frage</Button>
          </div>

          <QuestionEditor
            questions={questions}
            setQuestions={setQuestions}
            groups={groups}
            isTemplate={isTemplate}
            onOpenGroupModal={(qIdx) => setQuestionGroupModalIdx(qIdx)}
            emptyText="Noch keine Fragen hinzugefügt. Fragen können auch nachträglich ergänzt werden."
          />
        </div>
      </Card>

      {/* ── Group modals ────────────────────────────────── */}
      {!isTemplate && showSurveyGroupModal && (
        <GroupSelectModal
          groups={groups}
          selectedIds={selectedGroups}
          onConfirm={(ids) => { setSelectedGroups(ids); setShowSurveyGroupModal(false); }}
          onClose={() => setShowSurveyGroupModal(false)}
          title="Teilnehmende Gruppen auswählen"
        />
      )}

      {!isTemplate && questionGroupModalIdx !== null && (
        <GroupSelectModal
          groups={selectedGroups.length > 0 ? groups.filter((g) => selectedGroups.includes(g.id)) : groups}
          selectedIds={questions[questionGroupModalIdx]?.group_ids || []}
          onConfirm={(ids) => {
            updateQuestion(questionGroupModalIdx, 'group_ids', ids);
            setQuestionGroupModalIdx(null);
          }}
          onClose={() => setQuestionGroupModalIdx(null)}
          title={`Gruppen für Frage ${questionGroupModalIdx + 1}`}
        />
      )}
    </PageContainer>
  );
};

export default NewSurvey;

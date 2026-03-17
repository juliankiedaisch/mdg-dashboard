import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import DatePicker, { registerLocale } from 'react-datepicker';
import { de } from 'date-fns/locale';
import 'react-datepicker/dist/react-datepicker.css';
import api from '../../../../utils/api';
import { PageContainer, Card, Button, FormGroup, MessageBox, Spinner, TextInput, TextArea, CheckboxInput } from '../../../../components/shared';
import GroupSelectModal from '../../components/GroupSelectModal';
import NewQuestionModal from '../../components/NewQuestionModal';
import QuestionEditor from '../../components/QuestionEditor';
import useAutoMessage from '../../useAutoMessage';
import '../../Surveys.css';

registerLocale('de', de);

/**
 * Full-page survey edit form for non-active surveys.
 */
const EditSurvey = () => {
  const { surveyId } = useParams();
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [anonymous, setAnonymous] = useState(false);
  const [allowEditResponse, setAllowEditResponse] = useState(false);
  const [isTemplate, setIsTemplate] = useState(false);
  const [startsAt, setStartsAt] = useState(null);
  const [endsAt, setEndsAt] = useState(null);
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [groups, setGroups] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useAutoMessage();
  const [showSurveyGroupModal, setShowSurveyGroupModal] = useState(false);
  const [showAddQuestion, setShowAddQuestion] = useState(false);
  const [questionGroupModalIdx, setQuestionGroupModalIdx] = useState(null);

  useEffect(() => {
    loadData();
  }, [surveyId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [surveyRes, groupsRes] = await Promise.all([
        api.get(`/api/surveys/${surveyId}`),
        api.get('/api/surveys/groups'),
      ]);
      const survey = surveyRes.data.survey;

      if (survey.status === 'active') {
        setError('Aktive Umfragen können nicht bearbeitet werden.');
        setLoading(false);
        return;
      }

      setTitle(survey.title || '');
      setDescription(survey.description || '');
      setAnonymous(survey.anonymous || false);
      setAllowEditResponse(survey.allow_edit_response || false);
      setIsTemplate(survey.is_template || false);
      setStartsAt(survey.starts_at ? new Date(survey.starts_at) : null);
      setEndsAt(survey.ends_at ? new Date(survey.ends_at) : null);
      setSelectedGroups(survey.groups?.map((g) => g.id) || []);
      setGroups(groupsRes.data.groups || []);

      // Convert questions to editable format
      setQuestions(
        (survey.questions || []).map((q) => ({
          text: q.text,
          question_type: q.question_type,
          required: q.required,
          group_ids: q.group_ids || [],
          options: (q.options || []).map((o) => ({ text: o.text })),
        }))
      );
    } catch (err) {
      console.error('Error loading survey:', err);
      setError('Fehler beim Laden der Umfrage.');
    } finally {
      setLoading(false);
    }
  };

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

    setSaving(true);
    setError('');

    try {
      const payload = {
        title: title.trim(),
        description: description.trim(),
        anonymous,
        allow_edit_response: allowEditResponse,
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

      // Only include scheduling & groups for non-templates
      if (!isTemplate) {
        payload.starts_at = startsAt ? startsAt.toISOString() : null;
        payload.ends_at = endsAt ? endsAt.toISOString() : null;
        payload.group_ids = selectedGroups;
      }

      await api.put(`/api/surveys/${surveyId}/edit`, payload);
      setMessage({ text: 'Umfrage gespeichert', type: 'success' });
      navigate(`/surveys/${surveyId}`);
    } catch (err) {
      const msg = err.response?.data?.message || 'Fehler beim Speichern.';
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <PageContainer><Card variant="header" title="Umfrage bearbeiten" /><Spinner /></PageContainer>;
  if (error && !title) {
    return (
      <PageContainer>
        <Card variant="header" title="Umfrage bearbeiten" />
        <div style={{ color: '#ef4444' }}>{error}</div>
        <Button variant="secondary" onClick={() => navigate(-1)} style={{ marginTop: '12px' }}>
          Zurück
        </Button>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <Card variant="header" title={isTemplate ? 'Vorlage bearbeiten' : 'Umfrage bearbeiten'}>
        <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <Button variant="secondary" onClick={() => navigate(`/surveys/${surveyId}`)}>Abbrechen</Button>
          <Button variant="primary" onClick={handleSubmit} loading={saving}>Speichern</Button>
        </div>
      </Card>
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

      {/* ── Groups (only for non-templates) ──────────────── */}
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
            <Button variant="secondary" onClick={() => setShowAddQuestion(true)}>+ Frage</Button>
          </div>

          <QuestionEditor
            questions={questions}
            setQuestions={setQuestions}
            groups={groups}
            isTemplate={isTemplate}
            onOpenGroupModal={(qIdx) => setQuestionGroupModalIdx(qIdx)}
          />
        </div>
      </Card>

      {/* ── Add Question Modal ─────────────────────────────── */}
      {showAddQuestion && (
        <NewQuestionModal
          groups={isTemplate ? [] : (selectedGroups.length > 0 ? groups.filter((g) => selectedGroups.includes(g.id)) : groups)}
          onClose={() => setShowAddQuestion(false)}
          onAddLocal={(qData) => {
            setQuestions([
              ...questions,
              { ...qData, options: qData.options.map((o) => ({ text: o.text })) },
            ]);
            setShowAddQuestion(false);
          }}
        />
      )}

      {/* ── Group modals ────────────────────────────────── */}
      {showSurveyGroupModal && (
        <GroupSelectModal
          groups={groups}
          selectedIds={selectedGroups}
          onConfirm={(ids) => { setSelectedGroups(ids); setShowSurveyGroupModal(false); }}
          onClose={() => setShowSurveyGroupModal(false)}
          title="Teilnehmende Gruppen auswählen"
        />
      )}

      {questionGroupModalIdx !== null && (
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

export default EditSurvey;

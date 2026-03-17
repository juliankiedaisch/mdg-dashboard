import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../../../../utils/api';
import {
  PageContainer, Card, Button, FormGroup, MessageBox, TextInput, TextArea,
  CheckboxInput, SelectInput,
} from '../../../../components/shared';
import { QUESTION_TYPES, TEMPLATE_TYPES } from '../../surveyConstants';
import ExcelConfigEditor from '../components/ExcelConfigEditor';
import useAutoMessage from '../../useAutoMessage';
import '../../Surveys.css';

/**
 * Create / Edit a Teacher Evaluation Template.
 *
 * These templates are separated from normal survey templates:
 *  - template_type = 'teacher_evaluation'
 *  - Include per-question Excel export configuration
 *  - Only appear in the special survey template picker
 *
 * Route: /surveys/new/evaluation-template         (create)
 * Route: /surveys/evaluation-template/:surveyId   (edit)
 */
const NewEvaluationTemplate = () => {
  const navigate = useNavigate();
  const { surveyId } = useParams();
  const isEdit = Boolean(surveyId);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [anonymous, setAnonymous] = useState(false);
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(isEdit);
  const [message, setMessage] = useAutoMessage();
  const [error, setError] = useState('');

  useEffect(() => {
    if (isEdit) {
      loadExisting();
    }
  }, [surveyId]);

  const loadExisting = async () => {
    try {
      setInitialLoading(true);
      const res = await api.get(`/api/surveys/${surveyId}`);
      const survey = res.data.survey;
      setTitle(survey.title || '');
      setDescription(survey.description || '');
      setAnonymous(survey.anonymous || false);
      setQuestions(
        (survey.questions || []).map((q) => ({
          text: q.text,
          question_type: q.question_type,
          required: q.required,
          options: (q.options || []).map((o) => ({ text: o.text })),
          excel_config: _parseExcelConfig(q.excel_config_json),
        }))
      );
    } catch (err) {
      setError('Fehler beim Laden der Vorlage.');
    } finally {
      setInitialLoading(false);
    }
  };

  /** Parse excel_config_json from string to object */
  const _parseExcelConfig = (jsonStr) => {
    try {
      const parsed = JSON.parse(jsonStr || '{}');
      return typeof parsed === 'object' ? parsed : {};
    } catch {
      return {};
    }
  };

  // ── Question management ──

  const addQuestion = () => {
    setQuestions([
      ...questions,
      { text: '', question_type: 'single_choice', required: true, options: [{ text: '' }, { text: '' }], excel_config: {} },
    ]);
  };

  const updateQuestion = (index, field, value) => {
    const updated = [...questions];
    updated[index] = { ...updated[index], [field]: value };
    // Auto-manage options when type changes
    if (field === 'question_type' && !['single_choice', 'multiple_choice'].includes(value)) {
      updated[index].options = [];
    }
    if (field === 'question_type' && ['single_choice', 'multiple_choice'].includes(value) && updated[index].options.length === 0) {
      updated[index].options = [{ text: '' }, { text: '' }];
    }
    setQuestions(updated);
  };

  const removeQuestion = (index) => setQuestions(questions.filter((_, i) => i !== index));

  const addOption = (qIndex) => {
    const updated = [...questions];
    updated[qIndex].options = [...updated[qIndex].options, { text: '' }];
    setQuestions(updated);
  };

  const updateOption = (qIndex, oIndex, value) => {
    const updated = [...questions];
    updated[qIndex].options = [...updated[qIndex].options];
    updated[qIndex].options[oIndex] = { text: value };
    setQuestions(updated);
  };

  const removeOption = (qIndex, oIndex) => {
    const updated = [...questions];
    updated[qIndex].options = updated[qIndex].options.filter((_, i) => i !== oIndex);
    setQuestions(updated);
  };

  const updateExcelConfig = (qIndex, newConfig) => {
    const updated = [...questions];
    updated[qIndex] = { ...updated[qIndex], excel_config: newConfig };
    setQuestions(updated);
  };

  // ── Submit ──

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
        is_template: true,
        template_type: 'teacher_evaluation',
        questions: questions.map((q, idx) => ({
          text: q.text.trim(),
          question_type: q.question_type,
          required: q.required,
          order: idx,
          group_ids: [],
          options: q.options
            .filter((o) => o.text.trim())
            .map((o, oi) => ({ text: o.text.trim(), order: oi })),
          excel_config_json: JSON.stringify(q.excel_config || {}),
        })),
      };

      if (isEdit) {
        await api.put(`/api/surveys/${surveyId}/edit`, payload);
        setMessage({ text: 'Bewertungsvorlage aktualisiert.', type: 'success' });
      } else {
        const res = await api.post('/api/surveys', payload);
        if (res.data.status) {
          navigate(`/surveys/evaluation-template/${res.data.survey_id}`);
        } else {
          setError(res.data.message);
        }
      }
    } catch (err) {
      const msg = err.response?.data?.message || 'Fehler beim Speichern.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (initialLoading) {
    return <PageContainer><Card variant="header" title="Bewertungsvorlage laden..." /></PageContainer>;
  }

  return (
    <PageContainer>
      <Card variant="header" title={isEdit ? 'Bewertungsvorlage bearbeiten' : 'Neue Bewertungsvorlage erstellen'}>
        <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <Button variant="secondary" onClick={() => navigate('/surveys')}>Abbrechen</Button>
          <Button variant="primary" onClick={handleSubmit} loading={loading}>
            {isEdit ? 'Speichern' : 'Vorlage erstellen'}
          </Button>
        </div>
      </Card>

      {message && <MessageBox text={message.text} type={message.type} />}
      {error && <div style={{ color: '#ef4444', marginBottom: '12px' }}>{error}</div>}

      {/* Template type badge */}
      <div style={{ marginBottom: 'var(--space-md)' }}>
        <span className="template-type-badge template-type-badge--evaluation">
          🎓 {TEMPLATE_TYPES.teacher_evaluation}
        </span>
        <span style={{ marginLeft: 'var(--space-sm)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
          Diese Vorlage wird ausschließlich für die Lehrerbewertung in Spezialumfragen verwendet.
        </span>
      </div>

      {/* ── Basic info ── */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <TextInput
          id="eval-title"
          label="Titel"
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="z.B. Lehrerbewertung Klassenzusammensetzung"
          fullWidth
        />
        <TextArea
          id="eval-desc"
          label="Beschreibung"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optionale Beschreibung für die Lehrkräfte"
          rows={3}
          fullWidth
        />
        <FormGroup label="Anonym">
          <CheckboxInput
            label="Antworten anonym erfassen"
            checked={anonymous}
            onChange={(e) => setAnonymous(e.target.checked)}
          />
        </FormGroup>
      </Card>

      {/* ── Questions with Excel Config ── */}
      <Card>
        <div className="questions-section">
          <div className="questions-section__header">
            <span className="questions-section__title">Bewertungsfragen</span>
            <Button variant="secondary" onClick={addQuestion}>+ Frage</Button>
          </div>

          {questions.map((q, qIdx) => (
            <div key={qIdx} className="question-card question-card--evaluation">
              <div className="question-card__header">
                <span className="question-card__number">Frage {qIdx + 1}</span>
                <div className="question-card__actions">
                  <Button variant="danger" size="sm" onClick={() => removeQuestion(qIdx)}>✕</Button>
                </div>
              </div>

              <FormGroup label="Fragetext" required>
                <TextInput
                  value={q.text}
                  onChange={(e) => updateQuestion(qIdx, 'text', e.target.value)}
                  placeholder="Frage eingeben..."
                  fullWidth
                />
              </FormGroup>

              <div className="survey-form-row">
                <FormGroup label="Typ">
                  <SelectInput
                    value={q.question_type}
                    onChange={(e) => updateQuestion(qIdx, 'question_type', e.target.value)}
                    fullWidth
                  >
                    {QUESTION_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </SelectInput>
                </FormGroup>
              </div>

              <FormGroup label="Pflichtfrage">
                <CheckboxInput
                  label="Antwort erforderlich"
                  checked={q.required}
                  onChange={(e) => updateQuestion(qIdx, 'required', e.target.checked)}
                />
              </FormGroup>

              {/* Options for choice questions */}
              {['single_choice', 'multiple_choice'].includes(q.question_type) && (
                <FormGroup label="Optionen">
                  <div className="option-list">
                    {q.options.map((opt, oIdx) => (
                      <div key={oIdx} className="option-row">
                        <TextInput
                          value={opt.text}
                          onChange={(e) => updateOption(qIdx, oIdx, e.target.value)}
                          placeholder={`Option ${oIdx + 1}`}
                          fullWidth
                        />
                        <Button variant="danger" size="sm" onClick={() => removeOption(qIdx, oIdx)}>✕</Button>
                      </div>
                    ))}
                    <Button variant="ghost" size="sm" onClick={() => addOption(qIdx)}>+ Option</Button>
                  </div>
                </FormGroup>
              )}

              {/* Excel Export Configuration */}
              <ExcelConfigEditor
                config={q.excel_config}
                onChange={(newConfig) => updateExcelConfig(qIdx, newConfig)}
                questionType={q.question_type}
                options={q.options}
              />
            </div>
          ))}

          {questions.length === 0 && (
            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--color-text-secondary)' }}>
              Noch keine Fragen hinzugefügt. Klicken Sie auf &quot;+ Frage&quot; um Bewertungsfragen zu erstellen.
            </div>
          )}
        </div>
      </Card>
    </PageContainer>
  );
};

export default NewEvaluationTemplate;

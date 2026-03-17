import { Button, FormGroup, TextInput, SelectInput, CheckboxInput } from '../../../components/shared';
import { QUESTION_TYPES } from '../surveyConstants';
import '../Surveys.css';

/**
 * Reusable inline question editor used by NewSurvey and EditSurvey.
 *
 * Props:
 *  - questions        : array of question objects
 *  - setQuestions      : state setter
 *  - groups           : available groups list [{ id, name }]
 *  - isTemplate       : hide group pickers when true
 *  - onOpenGroupModal : (qIdx) => void — open group select modal for question
 *  - emptyText        : text shown when no questions exist
 */
const QuestionEditor = ({
  questions,
  setQuestions,
  groups = [],
  isTemplate = false,
  onOpenGroupModal,
  emptyText = 'Noch keine Fragen hinzugefügt.',
}) => {
  /* ── Helpers ────────────────────────────────────────── */
  const updateQuestion = (index, field, value) => {
    const updated = [...questions];
    updated[index] = { ...updated[index], [field]: value };
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

  const groupNames = (ids) =>
    ids.map((id) => groups.find((g) => g.id === id)?.name).filter(Boolean);

  /* ── Render ─────────────────────────────────────────── */
  return (
    <>
      {questions.map((q, qIdx) => (
        <div key={qIdx} className={`question-card ${q.group_ids.length > 0 ? 'question-card--group-specific' : ''}`}>
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

            {!isTemplate && onOpenGroupModal && (
              <FormGroup label="Nur für Gruppen" hint="Leer = alle Gruppen">
                <div className="group-picker group-picker--compact">
                  <Button variant="secondary" onClick={() => onOpenGroupModal(qIdx)}>
                    Gruppen…
                  </Button>
                  {q.group_ids.length > 0 && (
                    <div className="group-picker__tags">
                      {groupNames(q.group_ids).map((name, i) => (
                        <span key={i} className="group-picker__tag group-picker__tag--sm">{name}</span>
                      ))}
                    </div>
                  )}
                </div>
              </FormGroup>
            )}
          </div>

          <FormGroup label="Pflichtfrage">
            <CheckboxInput
              label="Antwort erforderlich"
              checked={q.required}
              onChange={(e) => updateQuestion(qIdx, 'required', e.target.checked)}
            />
          </FormGroup>

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
        </div>
      ))}

      {questions.length === 0 && (
        <div style={{ textAlign: 'center', padding: '20px', color: 'var(--color-text-secondary)' }}>
          {emptyText}
        </div>
      )}
    </>
  );
};

export default QuestionEditor;

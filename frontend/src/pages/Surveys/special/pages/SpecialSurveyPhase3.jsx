import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../../../utils/api';
import { PageContainer, Card, Button, MessageBox, Spinner, SelectInput, TextArea, CheckboxInput, RadioOption } from '../../../../components/shared';
import '../../Surveys.css';

/**
 * Phase 3: Teacher evaluates students in their assigned class.
 * Renders ONLY the questions from the linked survey template –
 * no hardcoded evaluation fields.
 * Uses the same participation-* CSS classes as SurveyParticipate
 * for visual consistency with normal surveys.
 *
 * Sequential workflow: one student at a time with dropdown selection
 * and Back / Save & Next navigation.
 */
const SpecialSurveyPhase3 = () => {
  const { ssId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  // Currently selected student index (across flattened list)
  const [currentIdx, setCurrentIdx] = useState(0);

  // Answers state keyed by student ID → question ID → value
  const [answers, setAnswers] = useState({});

  // Track which students have been evaluated (from server data)
  const [evaluatedSet, setEvaluatedSet] = useState(new Set());

  // Track local dirty state per-student
  const dirtyRef = useRef(new Set());

  useEffect(() => {
    loadData();
  }, [ssId]);

  /** Flatten all students across classes into a single ordered list */
  const getAllStudents = useCallback(() => {
    if (!data) return [];
    const list = [];
    for (const cls of data.classes || []) {
      for (const student of cls.students) {
        list.push({ ...student, class_name: cls.class_name, existing_evaluations: cls.existing_evaluations });
      }
    }
    return list;
  }, [data]);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await api.get(`/api/surveys/special/${ssId}/phase3`);
      setData(res.data);

      // Pre-fill existing answers from survey responses
      const ansState = {};
      const evSet = new Set();
      for (const cls of res.data.classes || []) {
        for (const student of cls.students) {
          const existing = cls.existing_evaluations?.[student.id];
          if (existing?.answers) {
            evSet.add(student.id);
            const studentAnswers = {};
            for (const q of res.data.teacher_questions || []) {
              const a = existing.answers[q.id];
              if (!a) continue;
              switch (q.question_type) {
                case 'text':
                  studentAnswers[q.id] = a.answer_text || '';
                  break;
                case 'single_choice':
                  studentAnswers[q.id] = a.selected_option_id || null;
                  break;
                case 'multiple_choice':
                  studentAnswers[q.id] = a.selected_option_ids
                    ? a.selected_option_ids.split(',').map(Number).filter(Boolean)
                    : [];
                  break;
                case 'rating':
                  studentAnswers[q.id] = a.answer_text ? parseInt(a.answer_text, 10) : null;
                  break;
                case 'yes_no':
                  studentAnswers[q.id] = a.answer_text || '';
                  break;
                default:
                  studentAnswers[q.id] = a.answer_text || '';
              }
            }
            ansState[student.id] = studentAnswers;
          } else {
            ansState[student.id] = {};
          }
        }
      }
      setAnswers(ansState);
      setEvaluatedSet(evSet);
      dirtyRef.current = new Set();
    } catch (err) {
      setMessage({ text: err.response?.data?.error || 'Fehler beim Laden', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const updateAnswer = (studentId, questionId, value) => {
    dirtyRef.current.add(studentId);
    setAnswers((prev) => ({
      ...prev,
      [studentId]: { ...prev[studentId], [questionId]: value },
    }));
  };

  const toggleMultiChoice = (studentId, questionId, optionId) => {
    dirtyRef.current.add(studentId);
    setAnswers((prev) => {
      const current = prev[studentId]?.[questionId] || [];
      const updated = current.includes(optionId)
        ? current.filter((id) => id !== optionId)
        : [...current, optionId];
      return {
        ...prev,
        [studentId]: { ...prev[studentId], [questionId]: updated },
      };
    });
  };

  /** Save a single student's evaluation – returns true on success */
  const saveStudent = async (studentId) => {
    const questions = data.teacher_questions || [];
    const studentAnswers = answers[studentId] || {};

    // Validate required questions
    for (const q of questions) {
      if (q.required) {
        const answer = studentAnswers[q.id];
        if (answer === undefined || answer === null || answer === '') {
          setMessage({ text: `Bitte beantworten Sie: "${q.text}"`, type: 'error' });
          return false;
        }
        if (Array.isArray(answer) && answer.length === 0) {
          setMessage({ text: `Bitte beantworten Sie: "${q.text}"`, type: 'error' });
          return false;
        }
      }
    }

    setSaving(true);
    setMessage(null);

    try {
      const formattedAnswers = questions.map((q) => {
        const answer = studentAnswers[q.id];
        const result = { question_id: q.id };
        switch (q.question_type) {
          case 'text':
            result.answer_text = answer || '';
            break;
          case 'single_choice':
            result.selected_option_id = answer || null;
            break;
          case 'multiple_choice':
            result.selected_option_ids = Array.isArray(answer) ? answer.join(',') : '';
            break;
          case 'rating':
            result.answer_text = answer?.toString() || '';
            break;
          case 'yes_no':
            result.answer_text = answer || '';
            break;
          default:
            result.answer_text = answer || '';
        }
        return result;
      });

      const res = await api.post(`/api/surveys/special/${ssId}/phase3/evaluate`, {
        student_id: studentId,
        survey_answers: formattedAnswers,
      });

      if (res.data.status) {
        dirtyRef.current.delete(studentId);
        setEvaluatedSet((prev) => new Set(prev).add(studentId));
        setMessage({ text: res.data.message, type: 'success' });
        return true;
      } else {
        setMessage({ text: res.data.message, type: 'error' });
        return false;
      }
    } catch (err) {
      setMessage({ text: err.response?.data?.message || 'Fehler beim Speichern', type: 'error' });
      return false;
    } finally {
      setSaving(false);
    }
  };

  /** Navigate to a different student, auto-saving dirty data */
  const goToStudent = async (newIdx) => {
    const students = getAllStudents();
    if (newIdx < 0 || newIdx >= students.length) return;
    const currentStudent = students[currentIdx];

    // Auto-save if there are unsaved changes
    if (currentStudent && dirtyRef.current.has(currentStudent.id)) {
      const ok = await saveStudent(currentStudent.id);
      if (!ok) return; // don't navigate if save failed
    }

    setCurrentIdx(newIdx);
    setMessage(null);
  };

  /** Save & Next handler */
  const handleSaveAndNext = async () => {
    const students = getAllStudents();
    const currentStudent = students[currentIdx];
    if (!currentStudent) return;

    const ok = await saveStudent(currentStudent.id);
    if (!ok) return;

    if (currentIdx < students.length - 1) {
      setCurrentIdx(currentIdx + 1);
      setMessage(null);
    }
  };

  // ── Render ──────────────────────────────────────────────────

  if (loading) return <PageContainer><Card variant="header" title="Lehrerbewertung" /><Spinner /></PageContainer>;

  if (!data) {
    return (
      <PageContainer>
        <Card variant="header" title="Lehrerbewertung">
          <Button variant="secondary" onClick={() => navigate('/surveys')}>Zurück</Button>
        </Card>
        {message && <MessageBox text={message.text} type={message.type} />}
        
      </PageContainer>
    );
  }

  const questions = data.teacher_questions || [];

  if (questions.length === 0) {
    return (
      <PageContainer>
        <Card variant="header" title={data.survey_title} />
        {message && <MessageBox text={message.text} type={message.type} />}
        <Card>
          <p style={{ color: 'var(--color-text-secondary)' }}>
            Kein Fragebogen-Template zugewiesen. Bitte wenden Sie sich an den Ersteller der Umfrage.
          </p>
        </Card>
        <div style={{ marginTop: 'var(--space-lg)' }}>
          <Button variant="secondary" onClick={() => navigate('/surveys')}>Zurück zur Übersicht</Button>
        </div>
      </PageContainer>
    );
  }

  const students = getAllStudents();
  const currentStudent = students[currentIdx];
  const studentAnswers = currentStudent ? (answers[currentStudent.id] || {}) : {};
  const isExisting = currentStudent ? evaluatedSet.has(currentStudent.id) : false;
  const evaluatedCount = students.filter((s) => evaluatedSet.has(s.id)).length;
  const isFirst = currentIdx === 0;
  const isLast = currentIdx === students.length - 1;

  return (
    <PageContainer>
      <Card variant="header" title={data.survey_title}>
        <Button variant="secondary" onClick={() => navigate('/surveys')}>Zurück zur Übersicht</Button>
      </Card>
      {message && <MessageBox text={message.text} type={message.type} />}

      {/* Header info */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          <strong>Lehrerbewertung</strong><br />
          Bitte bewerten Sie jeden Schüler / jede Schülerin Ihrer zugewiesenen Klasse.
          Wählen Sie einen Schüler aus oder navigieren Sie mit den Buttons.
        </p>
        {/* Progress indicator */}
        <div className="phase3-progress" style={{ marginTop: 'var(--space-md)' }}>
          <div className="phase3-progress__bar">
            <div
              className="phase3-progress__fill"
              style={{ width: students.length > 0 ? `${(evaluatedCount / students.length) * 100}%` : '0%' }}
            />
          </div>
          <span>{evaluatedCount} / {students.length} bewertet</span>
        </div>
      </Card>

      {/* Student selector */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <div className="phase3-student-selector">
          <label className="phase3-student-selector__label" htmlFor="student-select">
            Schüler/in:
          </label>
          <SelectInput
            id="student-select"
            className="phase3-student-selector__select"
            value={currentIdx}
            onChange={(e) => goToStudent(Number(e.target.value))}
          >
            {students.map((s, idx) => (
              <option key={s.id} value={idx}>
                {s.display_name} ({s.class_name}){evaluatedSet.has(s.id) ? ' ✓' : ''}
              </option>
            ))}
          </SelectInput>
          <span className="phase3-student-selector__counter">
            {currentIdx + 1} von {students.length}
          </span>
        </div>
      </Card>

      {/* Current student evaluation */}
      {currentStudent && (
        <Card
          className={isExisting ? 'special-eval-card--done' : ''}
          style={{ marginBottom: 'var(--space-md)' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
            <h3 style={{ margin: 0 }}>
              {currentStudent.display_name}
              <span style={{ fontWeight: 'normal', color: 'var(--color-text-secondary)', marginLeft: '8px', fontSize: 'var(--font-size-sm)' }}>
                Klasse {currentStudent.class_name}
              </span>
              {isExisting && <span style={{ color: '#22c55e', marginLeft: '8px', fontSize: 'var(--font-size-sm)' }}>✅ bewertet</span>}
            </h3>
          </div>

          {/* Render template questions using participation-* classes */}
          {questions.map((q, idx) => (
            <div key={q.id} className="participation-question">
              <div className="participation-question__text">
                {idx + 1}. {q.text}
                {q.required && <span className="participation-question__required">*</span>}
              </div>

              {/* Text Input */}
              {q.question_type === 'text' && (
                <TextArea
                  className="participation-textarea"
                  value={studentAnswers[q.id] || ''}
                  onChange={(e) => updateAnswer(currentStudent.id, q.id, e.target.value)}
                  placeholder="Ihre Antwort..."
                  fullWidth
                />
              )}

              {/* Single Choice */}
              {q.question_type === 'single_choice' && (
                <div className="participation-options">
                  {q.options.map((opt) => (
                    <div
                      key={opt.id}
                      className={`participation-option ${studentAnswers[q.id] === opt.id ? 'participation-option--selected' : ''}`}
                      onClick={() => updateAnswer(currentStudent.id, q.id, opt.id)}
                    >
                      <RadioOption
                        name={`q-${q.id}-s-${currentStudent.id}`}
                        value={opt.id}
                        checked={studentAnswers[q.id] === opt.id}
                        onChange={() => updateAnswer(currentStudent.id, q.id, opt.id)}
                        label={opt.text}
                      />
                    </div>
                  ))}
                </div>
              )}

              {/* Multiple Choice */}
              {q.question_type === 'multiple_choice' && (
                <div className="participation-options">
                  {q.options.map((opt) => (
                    <div
                      key={opt.id}
                      className={`participation-option ${(studentAnswers[q.id] || []).includes(opt.id) ? 'participation-option--selected' : ''}`}
                      onClick={() => toggleMultiChoice(currentStudent.id, q.id, opt.id)}
                    >
                      <CheckboxInput
                        checked={(studentAnswers[q.id] || []).includes(opt.id)}
                        onChange={() => toggleMultiChoice(currentStudent.id, q.id, opt.id)}
                      />
                      {opt.text}
                    </div>
                  ))}
                </div>
              )}

              {/* Rating */}
              {q.question_type === 'rating' && (
                <div className="participation-rating">
                  {[1, 2, 3, 4, 5].map((val) => (
                    <Button
                      key={val}
                      variant="ghost"
                      className={`participation-rating__btn ${studentAnswers[q.id] === val ? 'participation-rating__btn--selected' : ''}`}
                      onClick={() => updateAnswer(currentStudent.id, q.id, val)}
                    >
                      {val}
                    </Button>
                  ))}
                </div>
              )}

              {/* Yes/No */}
              {q.question_type === 'yes_no' && (
                <div className="participation-yesno">
                  <Button
                    variant="ghost"
                    className={`participation-yesno__btn ${studentAnswers[q.id] === 'ja' ? 'participation-yesno__btn--selected' : ''}`}
                    onClick={() => updateAnswer(currentStudent.id, q.id, 'ja')}
                  >
                    Ja
                  </Button>
                  <Button
                    variant="ghost"
                    className={`participation-yesno__btn ${studentAnswers[q.id] === 'nein' ? 'participation-yesno__btn--selected' : ''}`}
                    onClick={() => updateAnswer(currentStudent.id, q.id, 'nein')}
                  >
                    Nein
                  </Button>
                </div>
              )}
            </div>
          ))}

          {/* Navigation buttons */}
          <div className="phase3-nav">
            <Button
              variant="secondary"
              disabled={isFirst || saving}
              onClick={() => goToStudent(currentIdx - 1)}
            >
              ← Zurück
            </Button>

            <span className="phase3-nav__info">
              {currentIdx + 1} / {students.length}
            </span>

            {isLast ? (
              <Button
                variant="primary"
                loading={saving}
                onClick={() => saveStudent(currentStudent.id)}
              >
                Speichern
              </Button>
            ) : (
              <Button
                variant="primary"
                loading={saving}
                onClick={handleSaveAndNext}
              >
                Speichern & Weiter →
              </Button>
            )}
          </div>
        </Card>
      )}
    </PageContainer>
  );
};

export default SpecialSurveyPhase3;

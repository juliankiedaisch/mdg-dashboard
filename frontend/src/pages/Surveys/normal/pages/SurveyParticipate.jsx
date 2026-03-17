import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../../../utils/api';
import { PageContainer, Card, Button, MessageBox, Spinner, TextArea, CheckboxInput, RadioOption } from '../../../../components/shared';
import '../../Surveys.css';

const SurveyParticipate = () => {
  const { surveyId } = useParams();
  const navigate = useNavigate();
  const [surveyData, setSurveyData] = useState(null);
  const [answers, setAnswers] = useState({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [isEdit, setIsEdit] = useState(false);

  useEffect(() => {
    loadSurvey();
  }, [surveyId]);

  const loadSurvey = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/api/surveys/${surveyId}/participate`);
      setSurveyData(response.data);

      // Pre-fill answers when editing an existing response
      if (response.data.is_edit && response.data.existing_answers) {
        setIsEdit(true);
        const prefilled = {};
        for (const q of response.data.questions) {
          const existing = response.data.existing_answers[q.id];
          if (!existing) continue;

          switch (q.question_type) {
            case 'text':
              prefilled[q.id] = existing.answer_text || '';
              break;
            case 'single_choice':
              prefilled[q.id] = existing.selected_option_id || null;
              break;
            case 'multiple_choice':
              prefilled[q.id] = existing.selected_option_ids
                ? existing.selected_option_ids.split(',').map(Number).filter(Boolean)
                : [];
              break;
            case 'rating':
              prefilled[q.id] = existing.answer_text ? parseInt(existing.answer_text, 10) : null;
              break;
            case 'yes_no':
              prefilled[q.id] = existing.answer_text || '';
              break;
            default:
              prefilled[q.id] = existing.answer_text || '';
          }
        }
        setAnswers(prefilled);
      }
    } catch (error) {
      if (error.response?.data?.already_responded) {
        setMessage({ text: 'Sie haben bereits an dieser Umfrage teilgenommen.', type: 'info' });
        setSubmitted(true);
      } else {
        setMessage({ text: error.response?.data?.error || 'Fehler beim Laden', type: 'error' });
      }
    } finally {
      setLoading(false);
    }
  };

  const updateAnswer = (questionId, value) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const toggleMultiChoice = (questionId, optionId) => {
    setAnswers((prev) => {
      const current = prev[questionId] || [];
      const updated = current.includes(optionId)
        ? current.filter((id) => id !== optionId)
        : [...current, optionId];
      return { ...prev, [questionId]: updated };
    });
  };

  const handleSubmit = async () => {
    if (!surveyData) return;

    // Validate required questions
    for (const q of surveyData.questions) {
      if (q.required) {
        const answer = answers[q.id];
        if (answer === undefined || answer === null || answer === '') {
          setMessage({ text: `Bitte beantworten Sie: "${q.text}"`, type: 'error' });
          return;
        }
        if (Array.isArray(answer) && answer.length === 0) {
          setMessage({ text: `Bitte beantworten Sie: "${q.text}"`, type: 'error' });
          return;
        }
      }
    }

    setSubmitting(true);
    setMessage(null);

    try {
      const formattedAnswers = surveyData.questions.map((q) => {
        const answer = answers[q.id];
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

      await api.post(`/api/surveys/${surveyId}/respond`, { answers: formattedAnswers });
      setSubmitted(true);
      setMessage({ text: isEdit ? 'Ihre Antwort wurde aktualisiert!' : 'Vielen Dank für Ihre Teilnahme!', type: 'success' });
    } catch (error) {
      setMessage({ text: error.response?.data?.message || 'Fehler beim Absenden', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <PageContainer><Card variant="header" title="Umfrage" /><Spinner /></PageContainer>;

  if (submitted) {
    return (
      <PageContainer>
        <Card variant="header" title="Umfrage" >
        </Card>
        {message && <MessageBox text={message.text} type={message.type} />}
        <div className="surveys-empty">
          <div className="surveys-empty__icon">✅</div>
          <div className="surveys-empty__text">
            {isEdit ? 'Ihre Antwort wurde aktualisiert!' : 'Danke für Ihre Teilnahme!'}
          </div>
          <Button variant="primary" onClick={() => navigate('/surveys')}>
            Zurück zur Übersicht
          </Button>
        </div>
      </PageContainer>
    );
  }

  if (!surveyData) {
    return (
      <PageContainer>
        <Card variant="header" title="Umfrage" />
        {message && <MessageBox text={message.text} type={message.type} />}
        <Button variant="secondary" onClick={() => navigate('/surveys')}>Zurück</Button>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <Card variant="header" title={surveyData.survey.title} >
        <Button variant="primary" onClick={handleSubmit} loading={submitting}>
          {isEdit ? 'Antwort aktualisieren' : 'Absenden'}
        </Button>
          <Button variant="secondary" onClick={() => navigate('/surveys')}>
            Abbrechen
          </Button>      
      </Card>
      {message && <MessageBox text={message.text} type={message.type} />}

      {surveyData.survey.description && (
        <Card style={{ marginBottom: 'var(--space-lg)' }}>
          <p style={{ color: 'var(--color-text-secondary)' }}>{surveyData.survey.description}</p>
          {surveyData.survey.anonymous && (
            <p style={{ color: 'var(--color-text-secondary)', fontStyle: 'italic', marginTop: '8px' }}>
              🔒 Diese Umfrage ist anonym.
            </p>
          )}
        </Card>
      )}

      {isEdit && (
        <Card style={{ marginBottom: 'var(--space-lg)', background: 'var(--color-info-bg, #e8f4fd)', border: '1px solid var(--color-info-border, #b3d9f2)' }}>
          <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
            ✏️ Sie bearbeiten Ihre bereits abgegebene Antwort. Die vorherigen Antworten sind vorausgefüllt.
          </p>
        </Card>
      )}

      {surveyData.questions.map((q, idx) => (
        <div key={q.id} className="participation-question">
          <div className="participation-question__text">
            {idx + 1}. {q.text}
            {q.required && <span className="participation-question__required">*</span>}
          </div>

          {/* Text Input */}
          {q.question_type === 'text' && (
            <TextArea
              className="participation-textarea"
              value={answers[q.id] || ''}
              onChange={(e) => updateAnswer(q.id, e.target.value)}
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
                  className={`participation-option ${answers[q.id] === opt.id ? 'participation-option--selected' : ''}`}
                  onClick={() => updateAnswer(q.id, opt.id)}
                >
                  <RadioOption
                    name={`q-${q.id}`}
                    value={opt.id}
                    checked={answers[q.id] === opt.id}
                    onChange={() => updateAnswer(q.id, opt.id)}
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
                  className={`participation-option ${(answers[q.id] || []).includes(opt.id) ? 'participation-option--selected' : ''}`}
                  onClick={() => toggleMultiChoice(q.id, opt.id)}
                >
                  <CheckboxInput
                    checked={(answers[q.id] || []).includes(opt.id)}
                    onChange={() => toggleMultiChoice(q.id, opt.id)}
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
                  className={`participation-rating__btn ${answers[q.id] === val ? 'participation-rating__btn--selected' : ''}`}
                  onClick={() => updateAnswer(q.id, val)}
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
                className={`participation-yesno__btn ${answers[q.id] === 'ja' ? 'participation-yesno__btn--selected' : ''}`}
                onClick={() => updateAnswer(q.id, 'ja')}
              >
                Ja
              </Button>
              <Button
                variant="ghost"
                className={`participation-yesno__btn ${answers[q.id] === 'nein' ? 'participation-yesno__btn--selected' : ''}`}
                onClick={() => updateAnswer(q.id, 'nein')}
              >
                Nein
              </Button>
            </div>
          )}
        </div>
      ))}
    </PageContainer>
  );
};

export default SurveyParticipate;

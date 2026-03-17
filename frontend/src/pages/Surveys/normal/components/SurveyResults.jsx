import { useState, useEffect } from 'react';
import api from '../../../../utils/api';
import { Card, Spinner, StatCard, Button } from '../../../../components/shared';
import '../../Surveys.css';

const SurveyResults = ({ surveyId }) => {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [grantingId, setGrantingId] = useState(null);

  useEffect(() => {
    loadResults();
  }, [surveyId]);

  const loadResults = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/api/surveys/${surveyId}/results`);
      setResults(response.data.results);
    } catch (err) {
      setError('Fehler beim Laden der Ergebnisse.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const response = await api.get(`/api/surveys/${surveyId}/results/xlsx`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `umfrage_${surveyId}_ergebnisse.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download error:', err);
    } finally {
      setDownloading(false);
    }
  };

  const handleToggleEditGrant = async (participant) => {
    setGrantingId(participant.response_id);
    try {
      const action = participant.edit_granted ? 'revoke-edit' : 'grant-edit';
      await api.put(`/api/surveys/responses/${participant.response_id}/${action}`);
      // Refresh results to reflect the change
      const response = await api.get(`/api/surveys/${surveyId}/results`);
      setResults(response.data.results);
    } catch (err) {
      console.error('Error toggling edit grant:', err);
    } finally {
      setGrantingId(null);
    }
  };

  if (loading) return <Spinner />;
  if (error) return <p style={{ color: '#ef4444' }}>{error}</p>;
  if (!results) return <p>Keine Ergebnisse.</p>;

  const isAnonymous = results.anonymous;

  return (
    <div>
      {/* Summary + Download */}
      <div className="results-summary">
        <StatCard label="Antworten gesamt" value={results.response_count} />
        <StatCard label="Fragen" value={results.questions.length} />
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <Button variant="secondary" onClick={handleDownload} loading={downloading}>
            ⬇ XLSX herunterladen
          </Button>
        </div>
      </div>

      {/* Participants list for non-anonymous surveys */}
      {!isAnonymous && results.participants && results.participants.length > 0 && (
        <div className="result-participants">
          <h3 style={{ marginBottom: 'var(--space-sm)', fontSize: 'var(--font-size-base)' }}>
            Teilnehmer ({results.participants.length})
          </h3>
          <div className="result-participants__list">
            {results.participants.map((p, idx) => (
              <div key={idx} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', marginRight: '8px', marginBottom: '4px' }}>
                <span className="result-participants__tag">{p.username}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className={`edit-grant-btn ${p.edit_granted ? 'edit-grant-btn--active' : ''}`}
                  onClick={() => handleToggleEditGrant(p)}
                  disabled={grantingId === p.response_id}
                  title={p.edit_granted ? 'Bearbeitungsrecht entziehen' : 'Einmalige Bearbeitung erlauben'}
                  style={{
                    background: p.edit_granted ? 'var(--color-primary, #3b82f6)' : 'transparent',
                    color: p.edit_granted ? '#fff' : 'var(--color-text-secondary)',
                    border: `1px solid ${p.edit_granted ? 'var(--color-primary, #3b82f6)' : 'var(--color-border, #d1d5db)'}`,
                    borderRadius: '4px',
                    padding: '2px 6px',
                    cursor: 'pointer',
                    fontSize: 'var(--font-size-sm, 0.8rem)',
                    lineHeight: '1.2',
                    opacity: grantingId === p.response_id ? 0.5 : 1,
                  }}
                >
                  ✏️
                </Button>
              </div>
            ))}
          </div>
          <p style={{ fontSize: 'var(--font-size-sm, 0.8rem)', color: 'var(--color-text-secondary)', marginTop: 'var(--space-xs)' }}>
            ✏️ = Einmalige Bearbeitung erlauben (auch wenn globale Bearbeitung deaktiviert ist)
          </p>
        </div>
      )}

      {results.response_count === 0 ? (
        <div className="surveys-empty">
          <div className="surveys-empty__text">Noch keine Antworten eingegangen</div>
        </div>
      ) : (
        results.questions.map((q) => (
          <div key={q.question_id} className="result-question">
            <div className="result-question__text">
              {q.text}
              {q.groups?.length > 0 && (
                <span className="question-card__group-badge" style={{ marginLeft: '8px' }}>
                  Nur: {q.groups.map((g) => g.name).join(', ')}
                </span>
              )}
            </div>

            {/* Choice results (bar chart) */}
            {(q.question_type === 'single_choice' || q.question_type === 'multiple_choice') &&
              q.option_results && (
                <div>
                  {q.option_results.map((opt, idx) => {
                    const maxCount = Math.max(...q.option_results.map((o) => o.count), 1);
                    const percentage = (opt.count / maxCount) * 100;
                    return (
                      <div key={idx} className="result-bar">
                        <span className="result-bar__label">{opt.text}</span>
                        <div className="result-bar__track">
                          <div
                            className="result-bar__fill"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                        <span className="result-bar__count">{opt.count}</span>
                      </div>
                    );
                  })}
                </div>
              )}

            {/* Rating result */}
            {q.question_type === 'rating' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <span style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--color-primary)' }}>
                  {q.average?.toFixed(1) || '—'}
                </span>
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  Durchschnitt ({q.answers_count} Antwort{q.answers_count !== 1 ? 'en' : ''})
                </span>
              </div>
            )}

            {/* Yes/No result */}
            {q.question_type === 'yes_no' && (
              <div style={{ display: 'flex', gap: '32px' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#22c55e' }}>
                    {q.yes_count || 0}
                  </div>
                  <div style={{ color: 'var(--color-text-secondary)' }}>Ja</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#ef4444' }}>
                    {q.no_count || 0}
                  </div>
                  <div style={{ color: 'var(--color-text-secondary)' }}>Nein</div>
                </div>
              </div>
            )}

            {/* Text answers */}
            {q.question_type === 'text' && q.text_answers && (
              <ul className="result-text-answers">
                {!isAnonymous && q.user_answers ? (
                  q.user_answers.map((ua, idx) => (
                    <li key={idx}>
                      <strong>{ua.username}:</strong> {ua.answer}
                    </li>
                  ))
                ) : q.text_answers.length > 0 ? (
                  q.text_answers.map((answer, idx) => <li key={idx}>{answer}</li>)
                ) : (
                  <li style={{ color: 'var(--color-text-secondary)' }}>Keine Textantworten</li>
                )}
              </ul>
            )}

            {/* Per-user answers for non-anonymous (choice, rating, yes_no) */}
            {!isAnonymous && q.question_type !== 'text' && q.user_answers && q.user_answers.length > 0 && (
              <details className="result-user-details" style={{ marginTop: 'var(--space-sm)' }}>
                <summary style={{ cursor: 'pointer', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                  Einzelantworten anzeigen
                </summary>
                <ul className="result-text-answers" style={{ marginTop: 'var(--space-xs)' }}>
                  {q.user_answers.map((ua, idx) => (
                    <li key={idx}>
                      <strong>{ua.username}:</strong> {ua.answer}
                    </li>
                  ))}
                </ul>
              </details>
            )}

            <div style={{ marginTop: '8px', fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
              {q.answers_count} Antwort{q.answers_count !== 1 ? 'en' : ''}
            </div>
          </div>
        ))
      )}
    </div>
  );
};

export default SurveyResults;

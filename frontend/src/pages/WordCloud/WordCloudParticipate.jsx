import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { toPng } from 'html-to-image';
import api from '../../utils/api';
import { PageContainer, Card, Button, TextInput, MessageBox, Spinner } from '../../components/shared';
import WordCloudCanvas from './WordCloudCanvas';
import './WordCloud.css';

const WordCloudParticipate = () => {
  const { accessCode } = useParams();

  const [wordcloud, setWordcloud] = useState(null);
  const [words, setWords] = useState([]);
  const [inputWord, setInputWord] = useState('');
  const [submissionCount, setSubmissionCount] = useState(0);
  const [userWords, setUserWords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [currentVersion, setCurrentVersion] = useState(0);
  const [highlightEnabled, setHighlightEnabled] = useState(false);
  const [fullscreenDims, setFullscreenDims] = useState({ w: 1200, h: 800 });
  const pollIntervalRef = useRef(null);
  const participantCloudRef = useRef(null);

  // Load word cloud info
  const loadWordcloud = useCallback(async () => {
    try {
      const response = await api.get(`/api/teachertools/wordcloud/join/${accessCode}`);
      setWordcloud(response.data.wordcloud);
      setSubmissionCount(response.data.user_submission_count || 0);
      setUserWords(response.data.user_words || []);
      setCurrentVersion(response.data.version || 0);
      if (response.data.words) {
        setWords(response.data.words);
      }
    } catch (err) {
      const msg = err.response?.data?.error || 'Wortwolke nicht gefunden.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [accessCode]);

  useEffect(() => {
    loadWordcloud();
  }, [loadWordcloud]);

  // Poll for updates: words, settings, and status (version-based)
  useEffect(() => {
    if (!wordcloud) return;

    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await api.get(`/api/teachertools/wordcloud/join/${accessCode}/results`);
        if (response.data.status) {
          const serverVersion = response.data.version ?? 0;
          if (serverVersion !== currentVersion) {
            // Update words if results are visible
            if (response.data.show_results_to_participants && response.data.words) {
              setWords(response.data.words);
            } else if (!response.data.show_results_to_participants) {
              setWords([]);
            }
            // Update settings dynamically
            setWordcloud((prev) => prev ? {
              ...prev,
              status: response.data.wc_status || prev.status,
              show_results_to_participants: response.data.show_results_to_participants ?? prev.show_results_to_participants,
              allow_participant_download: response.data.allow_participant_download ?? prev.allow_participant_download,
              max_chars_per_answer: response.data.max_chars_per_answer ?? prev.max_chars_per_answer,
              max_answers_per_participant: response.data.max_answers_per_participant ?? prev.max_answers_per_participant,
              anonymous_answers: response.data.anonymous_answers ?? prev.anonymous_answers,
            } : prev);
            setCurrentVersion(serverVersion);
          }
        }
      } catch (err) {
        // Silently ignore
      }
    }, 3000);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [accessCode, wordcloud?.id, currentVersion]);

  const handleSubmit = async (e) => {
    e?.preventDefault();
    const word = inputWord.trim();
    if (!word) return;

    setSubmitting(true);
    setError('');
    setMessage('');

    try {
      const response = await api.post(`/api/teachertools/wordcloud/join/${accessCode}/submit`, {
        word,
      });

      if (response.data.status) {
        setInputWord('');
        setSubmissionCount(response.data.user_submission_count || submissionCount + 1);
        if (response.data.user_words) {
          setUserWords(response.data.user_words);
        } else {
          setUserWords((prev) => [word, ...prev]);
        }
        setMessage('Wort eingereicht!');
        setTimeout(() => setMessage(''), 2000);

        // Refresh results if visible
        if (wordcloud?.show_results_to_participants) {
          try {
            const resultsResponse = await api.get(`/api/teachertools/wordcloud/join/${accessCode}/results`);
            if (resultsResponse.data.status && resultsResponse.data.words) {
              setWords(resultsResponse.data.words);
            }
          } catch (err) {
            // Ignore
          }
        }
      } else {
        setError(response.data.message);
      }
    } catch (err) {
      const msg = err.response?.data?.message || 'Fehler beim Einreichen.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSubmit(e);
    }
  };

  // Fullscreen toggle
  const toggleFullscreen = () => {
    setIsFullscreen((prev) => !prev);
  };

  // Download word cloud as PNG (participant)
  const handleDownloadPng = async () => {
    if (!participantCloudRef.current) return;
    try {
      const dataUrl = await toPng(participantCloudRef.current, { backgroundColor: '#ffffff' });
      const link = document.createElement('a');
      link.download = `wortwolke-${wordcloud?.name || 'download'}.png`;
      link.href = dataUrl;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      console.error('Download error:', err);
    }
  };

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isFullscreen]);

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
        <Card>
          <MessageBox type="error" text={error || 'Wortwolke nicht gefunden.'} />
        </Card>
      </PageContainer>
    );
  }

  const isPaused = wordcloud.status === 'paused';
  const isStopped = wordcloud.status === 'stopped' || wordcloud.status === 'archived';
  const maxReached = wordcloud.max_answers_per_participant > 0
    && submissionCount >= wordcloud.max_answers_per_participant;
  const canSubmit = !isPaused && !isStopped && !maxReached;
  const maxChars = wordcloud.max_chars_per_answer || 100;

  return (
    <PageContainer>
      {/* Header Card: Split Layout */}
      <Card>
        <div className="wc-participate-header">
          <div className="wc-participate-header__left">
            <h2 className="wc-participate-header__title">{wordcloud.name}</h2>
            {wordcloud.description && (
              <p className="wc-participate-description">{wordcloud.description}</p>
            )}
          </div>
          <div className="wc-participate-header__right">
            <span className={`wc-anonymity-badge ${wordcloud.anonymous_answers !== false ? 'wc-anonymity-badge--anonymous' : 'wc-anonymity-badge--identified'}`}>
              {wordcloud.anonymous_answers !== false ? '🔒 Anonym' : '👤 Nicht anonym'}
            </span>
            {wordcloud.creator_name && (
              <span className="wc-participate-meta-item">👤Author:  {wordcloud.creator_name}</span>
            )}
            {wordcloud.groups && wordcloud.groups.length > 0 && (
              <span className="wc-participate-meta-item">
                📋Gruppen:  {wordcloud.groups.map(g => g.name).join(', ')}
              </span>
            )}
          </div>
        </div>
      </Card>

      {message && <MessageBox type="success" text={message} />}
      {error && <MessageBox type="error" text={error} />}

      {/* Status messages */}
      {isPaused && (
        <MessageBox type="warning" text="Die Wortwolke ist aktuell pausiert. Bitte warten Sie, bis sie fortgesetzt wird." />
      )}
      {isStopped && (
        <MessageBox type="info" text="Die Wortwolke ist beendet. Es können keine weiteren Wörter eingereicht werden." />
      )}
      {maxReached && !isStopped && !isPaused && (
        <MessageBox
          type="info"
          text={`Sie haben die maximale Anzahl von ${wordcloud.max_answers_per_participant} Antworten erreicht.`}
        />
      )}

      {/* Submission Form */}
      {!isStopped && (
        <Card style={{ marginBottom: 'var(--space-lg)' }}>
          <h3 style={{ marginBottom: 'var(--space-md)' }}>Wort einreichen</h3>
          <form onSubmit={handleSubmit} className="wc-submit-form">
            <div className="wc-input-wrapper">
              <TextInput
                id="wc-word-input"
                value={inputWord}
                onChange={(e) => {
                  if (e.target.value.length <= maxChars) {
                    setInputWord(e.target.value);
                  }
                }}
                onKeyDown={handleKeyPress}
                placeholder="Ein Wort eingeben..."
                disabled={!canSubmit || submitting}
                fullWidth
                autoFocus
                maxLength={maxChars}
              />
              <span className={`wc-char-counter ${inputWord.length >= maxChars ? 'wc-char-counter--limit' : ''}`}>
                {inputWord.length}/{maxChars}
              </span>
            </div>
            <div className="wc-input-submit">
            <Button
              type="submit"
              variant="primary"
              disabled={!canSubmit || submitting || !inputWord.trim()}
              loading={submitting}
            >
              Einreichen
            </Button>
            </div>
          </form>
          {wordcloud.max_answers_per_participant > 0 && (
            <p className="wc-submit-counter">
              {submissionCount} / {wordcloud.max_answers_per_participant} Antworten
            </p>
          )}
          {/* Submitted Words Feedback */}
          {userWords.length > 0 && (
            <>
              <br />
              <h3 style={{ marginBottom: 'var(--space-md)' }}>Deine eingereichten Wörter</h3>
              <div className="wc-user-words">
                {userWords.map((w, i) => (
                  <span key={i} className="wc-user-word-tag">{w}</span>
                ))}
              </div>
            </>
          )}
        </Card>
      )}

      {/* Word Cloud Display (if allowed) */}
      {wordcloud.show_results_to_participants && (
        <Card style={{ marginBottom: 'var(--space-lg)' }}>
          <div className="wc-cloud-header">
            <h3>Wortwolke</h3>
            <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center' }}>
              {userWords.length > 0 && (
                <label className="wc-highlight-toggle">
                  <input
                    type="checkbox"
                    checked={highlightEnabled}
                    onChange={(e) => setHighlightEnabled(e.target.checked)}
                  />
                  Meine Wörter hervorheben
                </label>
              )}
              {wordcloud.allow_participant_download && (
                <Button variant="secondary" size="sm" onClick={handleDownloadPng} disabled={words.length === 0}>
                  Als PNG herunterladen
                </Button>
              )}
              <Button variant="secondary" size="sm" onClick={toggleFullscreen} disabled={words.length === 0}>
                Vollbild
              </Button>
            </div>
          </div>
          <div ref={participantCloudRef} className="wc-cloud-container">
            <WordCloudCanvas
              words={words}
              width={700}
              height={450}
              highlightWords={highlightEnabled ? userWords : []}
            />
          </div>
        </Card>
      )}

      {/* Fullscreen Overlay */}
      {isFullscreen && wordcloud.show_results_to_participants && (
        <div className="wc-fullscreen-overlay" onClick={toggleFullscreen}>
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
              highlightWords={highlightEnabled ? userWords : []}
            />
          </div>
        </div>
      )}
    </PageContainer>
  );
};

export default WordCloudParticipate;

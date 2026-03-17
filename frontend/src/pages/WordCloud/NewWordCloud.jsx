import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../utils/api';
import { useUser } from '../../contexts/UserContext';
import {
  PageContainer, Card, Button, FormGroup, TextInput, TextArea,
  CheckboxInput, MessageBox,
} from '../../components/shared';
import GroupSelectModal from '../Surveys/components/GroupSelectModal';
import './WordCloud.css';

const NewWordCloud = () => {
  const navigate = useNavigate();
  const { hasPermission } = useUser();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [maxAnswers, setMaxAnswers] = useState(0);
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [allowParticipantDownload, setAllowParticipantDownload] = useState(false);
  const [maxCharsPerAnswer, setMaxCharsPerAnswer] = useState(20);
  const [anonymousAnswers, setAnonymousAnswers] = useState(true);
  const [rotationMode, setRotationMode] = useState('mixed');
  const [rotationAngles, setRotationAngles] = useState('0, 90');
  const [rotationProbability, setRotationProbability] = useState(0.5);
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [groups, setGroups] = useState([]);
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadGroups();
  }, []);

  const loadGroups = async () => {
    try {
      const response = await api.get('/api/teachertools/groups');
      setGroups(response.data.groups || []);
    } catch (err) {
      console.error('Error loading groups:', err);
    }
  };

  const groupNames = (ids) =>
    ids.map((id) => groups.find((g) => g.id === id)?.name).filter(Boolean);

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Bitte einen Namen eingeben.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        max_answers_per_participant: parseInt(maxAnswers, 10) || 0,
        case_sensitive: caseSensitive,
        show_results_to_participants: showResults,
        group_ids: selectedGroups,
        allow_participant_download: allowParticipantDownload,
        max_chars_per_answer: Math.max(1, Math.min(100, parseInt(maxCharsPerAnswer, 10) || 20)),
        anonymous_answers: anonymousAnswers,
        rotation_mode: rotationMode,
        rotation_angles: rotationAngles.split(',').map((a) => parseInt(a.trim(), 10)).filter((a) => !isNaN(a)),
        rotation_probability: Math.max(0, Math.min(1, parseFloat(rotationProbability) || 0.5)),
      };

      const response = await api.post('/api/teachertools/wordcloud', payload);
      if (response.data.status) {
        navigate(`/teachertools/wordcloud/${response.data.wordcloud_id}`);
      } else {
        setError(response.data.message || 'Fehler beim Erstellen.');
      }
    } catch (err) {
      const msg = err.response?.data?.message || 'Fehler beim Erstellen.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageContainer>
    {hasPermission('teachertools.wordcloud') && (
        <>
      <Card variant="header" title="Neue Wortwolke erstellen">
        <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <Button variant="secondary" onClick={() => navigate('/teachertools/wordcloud')}>
            Abbrechen
          </Button>
          <Button variant="primary" onClick={handleSubmit} loading={loading}>
            Wortwolke erstellen
          </Button>
        </div>
      </Card>

      {error && <MessageBox type="error" text={error} />}

      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <TextInput
          id="wc-name"
          label="Name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name der Wortwolke"
          fullWidth
        />
        <TextArea
          id="wc-description"
          label="Beschreibung"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Beschreibung für die Teilnehmer (optional)"
          rows={3}
          fullWidth
          helperText="Diese Beschreibung wird den Teilnehmern auf der Beitragsseite angezeigt."
        />
      </Card>

      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <h3 style={{ marginBottom: 'var(--space-md)' }}>Einstellungen</h3>

        <FormGroup label="Maximale Antworten pro Teilnehmer" htmlFor="wc-max-answers">
          <TextInput
            id="wc-max-answers"
            type="number"
            value={maxAnswers}
            onChange={(e) => setMaxAnswers(e.target.value)}
            min="0"
            helperText="0 = unbegrenzte Antworten"
          />
        </FormGroup>

        <div style={{ marginTop: 'var(--space-md)' }}>
          <CheckboxInput
            id="wc-case-sensitive"
            label="Groß-/Kleinschreibung beachten"
            checked={caseSensitive}
            onChange={(e) => setCaseSensitive(e.target.checked)}
          />
          <div className="wc-setting-hint">
            {caseSensitive
              ? '"Wort" und "wort" werden als unterschiedliche Einträge gezählt.'
              : '"Wort" und "wort" werden zusammengeführt.'}
          </div>
        </div>

        <div style={{ marginTop: 'var(--space-md)' }}>
          <CheckboxInput
            id="wc-show-results"
            label="Ergebnisse für Teilnehmer sichtbar"
            checked={showResults}
            onChange={(e) => setShowResults(e.target.checked)}
          />
          <div className="wc-setting-hint">
            {showResults
              ? 'Teilnehmer können die Wortwolke live sehen.'
              : 'Nur Sie können die Wortwolke sehen.'}
          </div>
        </div>

        <div style={{ marginTop: 'var(--space-md)' }}>
          <CheckboxInput
            id="wc-allow-download"
            label="Teilnehmer dürfen Wortwolke als PNG herunterladen"
            checked={allowParticipantDownload}
            onChange={(e) => setAllowParticipantDownload(e.target.checked)}
          />
          <div className="wc-setting-hint">
            {allowParticipantDownload
              ? 'Teilnehmer können die Wortwolke als Bild herunterladen.'
              : 'Nur Sie können die Wortwolke exportieren.'}
          </div>
        </div>

        <div style={{ marginTop: 'var(--space-md)' }}>
          <CheckboxInput
            id="wc-anonymous"
            label="Anonyme Antworten"
            checked={anonymousAnswers}
            onChange={(e) => setAnonymousAnswers(e.target.checked)}
          />
          <div className="wc-setting-hint">
            {anonymousAnswers
              ? 'Antworten sind anonym – Sie sehen nicht, wer welches Wort eingereicht hat.'
              : 'Antworten sind identifiziert – Sie können sehen, wer welches Wort eingereicht hat.'}
          </div>
        </div>

        <FormGroup label="Maximale Zeichen pro Antwort" htmlFor="wc-max-chars" style={{ marginTop: 'var(--space-md)' }}>
          <TextInput
            id="wc-max-chars"
            type="number"
            value={maxCharsPerAnswer}
            onChange={(e) => setMaxCharsPerAnswer(e.target.value)}
            min="1"
            max="100"
            helperText="Min: 1, Max: 100 Zeichen pro Wort/Antwort"
          />
        </FormGroup>
      </Card>

      {/* Advanced d3-cloud Settings */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <div className="wc-cloud-header" style={{ cursor: 'pointer' }} onClick={() => setShowAdvanced(!showAdvanced)}>
          <h3>Erweiterte Darstellungseinstellungen</h3>
          <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); setShowAdvanced(!showAdvanced); }}>
            {showAdvanced ? 'Einklappen' : 'Aufklappen'}
          </Button>
        </div>
        {showAdvanced && (
          <div style={{ marginTop: 'var(--space-md)', display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            <FormGroup label="Rotationsmodus" htmlFor="wc-rotation-mode">
              <select
                id="wc-rotation-mode"
                className="wc-select-input"
                value={rotationMode}
                onChange={(e) => setRotationMode(e.target.value)}
              >
                <option value="mixed">Gemischt (horizontal + rotiert)</option>
                <option value="horizontal">Nur horizontal</option>
                <option value="vertical">Nur vertikal</option>
                <option value="custom">Benutzerdefiniert</option>
              </select>
            </FormGroup>

            {(rotationMode === 'mixed' || rotationMode === 'custom') && (
              <FormGroup label="Rotationswinkel (kommagetrennt)" htmlFor="wc-rotation-angles">
                <TextInput
                  id="wc-rotation-angles"
                  value={rotationAngles}
                  onChange={(e) => setRotationAngles(e.target.value)}
                  placeholder="0, 90"
                  helperText="Winkel in Grad, z.B. -45, 0, 45, 90"
                />
              </FormGroup>
            )}

            {rotationMode === 'mixed' && (
              <FormGroup label="Rotationswahrscheinlichkeit" htmlFor="wc-rotation-prob">
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                  <input
                    id="wc-rotation-prob"
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={rotationProbability}
                    onChange={(e) => setRotationProbability(parseFloat(e.target.value))}
                    style={{ flex: 1 }}
                  />
                  <span style={{ minWidth: '3ch', textAlign: 'center' }}>{Math.round(rotationProbability * 100)}%</span>
                </div>
                <div className="wc-setting-hint">
                  Wie häufig werden Wörter rotiert statt horizontal angezeigt.
                </div>
              </FormGroup>
            )}
          </div>
        )}
      </Card>

      <Card>
        <h3 style={{ marginBottom: 'var(--space-md)' }}>Teilnehmergruppen</h3>
        <p className="wc-setting-hint" style={{ marginBottom: 'var(--space-md)' }}>
          Beschränken Sie die Teilnahme auf bestimmte Gruppen. Ohne Auswahl können alle angemeldeten Benutzer teilnehmen.
        </p>

        {selectedGroups.length > 0 ? (
          <div className="wc-selected-groups">
            <div className="wc-group-tags">
              {groupNames(selectedGroups).map((name, i) => (
                <span key={i} className="wc-group-tag">{name}</span>
              ))}
            </div>
            <Button variant="secondary" size="sm" onClick={() => setShowGroupModal(true)}>
              Gruppen bearbeiten
            </Button>
          </div>
        ) : (
          <Button variant="secondary" onClick={() => setShowGroupModal(true)}>
            Gruppen auswählen
          </Button>
        )}
      </Card>

      {showGroupModal && (
        <GroupSelectModal
          groups={groups}
          selectedIds={selectedGroups}
          onConfirm={(ids) => {
            setSelectedGroups(ids);
            setShowGroupModal(false);
          }}
          onClose={() => setShowGroupModal(false)}
        />
      )}
      </>
    )}
    </PageContainer>
  );
};

export default NewWordCloud;

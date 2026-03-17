import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import api from '../../utils/api';
import { PageContainer, Card, Button, MessageBox, Spinner, Tabs } from '../../components/shared';
import './WordCloud.css';

const WordCloudList = () => {
  const navigate = useNavigate();
  const { hasPermission } = useUser();
  const location = useLocation();
  const [wordclouds, setWordclouds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState(location.state?.tab || 'active');

  useEffect(() => {
    loadWordclouds();
  }, [activeTab]);

  const loadWordclouds = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.get(`/api/teachertools/wordcloud?tab=${activeTab}`);
      setWordclouds(response.data.wordclouds || []);
    } catch (err) {
      setError('Fehler beim Laden der Wortwolken.');
      console.error('Error loading word clouds:', err);
    } finally {
      setLoading(false);
    }
  };

  const statusLabels = {
    active: 'Aktiv',
    paused: 'Pausiert',
    stopped: 'Beendet',
    archived: 'Archiviert',
  };

  const statusColors = {
    active: '#16a34a',
    paused: '#d97706',
    stopped: '#dc2626',
    archived: '#6b7280',
  };

  const tabs = [
    { id: 'active', label: 'Aktiv' },
    { id: 'archived', label: 'Archiv' },
  ];

  return (
    <PageContainer>
        {hasPermission('teachertools.wordcloud') && (
        <>
      <Card variant="header" title="Wortwolken">
        <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <Button variant="secondary" onClick={() => navigate('/teachertools')}>
            Zurück
          </Button>
          <Button variant="primary" onClick={() => navigate('/teachertools/wordcloud/new')}>
            Neue Wortwolke
          </Button>
        </div>
      </Card>

      {error && <MessageBox type="error" text={error} />}

      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {loading ? (
        <Spinner />
      ) : wordclouds.length === 0 ? (
        <Card>
          <div className="wc-empty-state">
            <p>{activeTab === 'active' ? 'Keine aktiven Wortwolken vorhanden.' : 'Keine archivierten Wortwolken vorhanden.'}</p>
            {activeTab === 'active' && (
              <Button variant="primary" onClick={() => navigate('/teachertools/wordcloud/new')}>
                Erste Wortwolke erstellen
              </Button>
            )}
          </div>
        </Card>
      ) : (
        <div className="wc-grid">
          {wordclouds.map((wc) => (
            <Card
              key={wc.id}
              className="wc-card"
              hoverable
              onClick={() => navigate(`/teachertools/wordcloud/${wc.id}`, { state: activeTab === 'archived' ? { fromArchive: true } : undefined })}
            >
              <div className="wc-card__header">
                <h3 className="wc-card__title">{wc.name}</h3>
                <span
                  className="wc-card__status"
                  style={{ backgroundColor: statusColors[wc.status] }}
                >
                  {statusLabels[wc.status]}
                </span>
              </div>
              {wc.description && (
                <p className="wc-card__description">{wc.description}</p>
              )}
              <div className="wc-card__meta">
                <span>{wc.submission_count} Einreichungen</span>
                <span>{wc.unique_words} Wörter</span>
                <span>{wc.groups.length > 0 ? `${wc.groups.length} Gruppen` : 'Alle Gruppen'}</span>
              </div>
              <div className="wc-card__footer">
                <span className="wc-card__code">Code: {wc.access_code}</span>
                <span className="wc-card__date">
                  {new Date(wc.created_at).toLocaleDateString('de-DE')}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
      </>
    )}
    </PageContainer>
  );
};

export default WordCloudList;

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../../../utils/api';
import { PageContainer, Card, Button, MessageBox, Spinner } from '../../../../components/shared';
import '../../Surveys.css';

/**
 * Phase 2: Parent views and confirms their child's wishes.
 */
const SpecialSurveyPhase2 = () => {
  const { ssId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [confirmingId, setConfirmingId] = useState(null);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    loadData();
  }, [ssId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await api.get(`/api/surveys/special/${ssId}/phase2`);
      setData(res.data);
    } catch (err) {
      setMessage({ text: err.response?.data?.error || 'Fehler beim Laden', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (wishId) => {
    setConfirmingId(wishId);
    setMessage(null);

    try {
      const res = await api.post(`/api/surveys/special/${ssId}/phase2/confirm`, {
        wish_id: wishId,
      });

      if (res.data.status) {
        setMessage({ text: res.data.message, type: 'success' });
        loadData(); // Refresh to show updated confirmation status
      } else {
        setMessage({ text: res.data.message, type: 'error' });
      }
    } catch (err) {
      setMessage({ text: err.response?.data?.message || 'Fehler beim Bestätigen', type: 'error' });
    } finally {
      setConfirmingId(null);
    }
  };

  if (loading) return <PageContainer><Card variant="header" title="Elternbestätigung" /><Spinner /></PageContainer>;

  if (!data) {
    return (
      <PageContainer>
        <Card variant="header" title="Elternbestätigung" >
          <Button variant="secondary" onClick={() => navigate('/surveys')}>Zurück</Button>
        </Card>
        {message && <MessageBox text={message.text} type={message.type} />}
        
      </PageContainer>
    );
  }

  const allConfirmed = data.children.every((c) => c.parent_confirmed);

  return (
    <PageContainer>
      <Card variant="header" title={data.survey_title} >
        <Button variant="secondary" onClick={() => navigate('/surveys')}>Zurück</Button>
      </Card>
      {message && <MessageBox text={message.text} type={message.type} />}

      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          <strong>Elternbestätigung</strong><br />
          Bitte überprüfen und bestätigen Sie die Wünsche Ihres Kindes.
          Nach der Bestätigung können die Wünsche nicht mehr geändert werden.
        </p>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)', marginTop: '8px' }}>
          Angemeldet als: {data.parent.display_name}
        </p>
      </Card>

      {data.children.map((child) => (
        <Card key={child.wish_id} style={{ marginBottom: 'var(--space-lg)' }}>
          <h3 style={{ marginBottom: 'var(--space-md)' }}>
            {child.student.display_name}
            <span style={{ fontWeight: 'normal', color: 'var(--color-text-secondary)', marginLeft: '8px' }}>
              (Klasse {child.student.class_name})
            </span>
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '8px', marginBottom: 'var(--space-md)' }}>
            <span style={{ fontWeight: 'bold' }}>Wunsch 1:</span>
            <span>{child.wish1 ? child.wish1.display_name : '–'}</span>

            <span style={{ fontWeight: 'bold' }}>Wunsch 2:</span>
            <span>{child.wish2 ? child.wish2.display_name : '–'}</span>
          </div>

          {child.parent_confirmed ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#22c55e', fontWeight: 'bold' }}>
              ✅ Bestätigt und gesperrt
            </div>
          ) : (
            <Button
              variant="success"
              onClick={() => handleConfirm(child.wish_id)}
              loading={confirmingId === child.wish_id}
            >
              ✓ Wünsche bestätigen
            </Button>
          )}
        </Card>
      ))}

    </PageContainer>
  );
};

export default SpecialSurveyPhase2;

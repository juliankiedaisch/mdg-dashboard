import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../../../utils/api';
import { PageContainer, Card, Button, MessageBox, Spinner, SearchInput } from '../../../../components/shared';
import '../../Surveys.css';

/**
 * Phase 1: Student selects two classmates and one parent account.
 */
const SpecialSurveyPhase1 = () => {
  const { ssId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [wish1, setWish1] = useState(null);
  const [wish2, setWish2] = useState(null);
  const [selectedParent, setSelectedParent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [message, setMessage] = useState(null);
  const [searchStudent1, setSearchStudent1] = useState('');
  const [searchStudent2, setSearchStudent2] = useState('');
  const [searchParent, setSearchParent] = useState('');

  useEffect(() => {
    loadData();
  }, [ssId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await api.get(`/api/surveys/special/${ssId}/phase1`);
      setData(res.data);

      // Pre-fill existing wishes
      if (res.data.existing_wish) {
        setWish1(res.data.existing_wish.wish1_student_id);
        setWish2(res.data.existing_wish.wish2_student_id);
        setSelectedParent(res.data.existing_wish.selected_parent_id);
      }
    } catch (err) {
      setMessage({ text: err.response?.data?.error || 'Fehler beim Laden', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!wish1 || !wish2) {
      setMessage({ text: 'Bitte wählen Sie zwei Mitschüler/innen aus.', type: 'error' });
      return;
    }
    if (wish1 === wish2) {
      setMessage({ text: 'Die beiden Wünsche müssen unterschiedlich sein.', type: 'error' });
      return;
    }
    if (!selectedParent) {
      setMessage({ text: 'Bitte wählen Sie einen Elternaccount aus.', type: 'error' });
      return;
    }

    setSubmitting(true);
    setMessage(null);

    try {
      const res = await api.post(`/api/surveys/special/${ssId}/phase1`, {
        wish1_student_id: wish1,
        wish2_student_id: wish2,
        selected_parent_id: selectedParent,
      });

      if (res.data.status) {
        setSubmitted(true);
        setMessage({ text: 'Wünsche erfolgreich gespeichert!', type: 'success' });
      } else {
        setMessage({ text: res.data.message, type: 'error' });
      }
    } catch (err) {
      setMessage({ text: err.response?.data?.message || 'Fehler beim Speichern', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const filterStudents = (students, term) => {
    if (!term.trim()) return students;
    const lower = term.toLowerCase();
    return students.filter((s) =>
      s.display_name.toLowerCase().includes(lower) ||
      s.account.toLowerCase().includes(lower) ||
      s.class_name.toLowerCase().includes(lower)
    );
  };

  const filterParents = (parents) => {
    if (!searchParent.trim()) return parents;
    const term = searchParent.toLowerCase();
    return parents.filter((p) =>
      p.display_name.toLowerCase().includes(term) ||
      p.account.toLowerCase().includes(term)
    );
  };

  if (loading) return <PageContainer><Card variant="header" title="Schülerwünsche" /><Spinner /></PageContainer>;

  if (submitted) {
    return (
      <PageContainer>
        <Card variant="header" title="Schülerwünsche" />
        {message && <MessageBox text={message.text} type={message.type} />}
        <div className="surveys-empty">
          <div className="surveys-empty__icon">✅</div>
          <div className="surveys-empty__text">Ihre Wünsche wurden gespeichert!</div>
          <Button variant="primary" onClick={() => navigate('/surveys')}>
            Zurück zur Übersicht
          </Button>
        </div>
      </PageContainer>
    );
  }

  if (!data) {
    return (
      <PageContainer>
        <Card variant="header" title="Schülerwünsche">
          <Button variant="secondary" onClick={() => navigate('/surveys')}>Zurück</Button>
        </Card>
        {message && <MessageBox text={message.text} type={message.type} />}
        
      </PageContainer>
    );
  }

  const getStudentName = (id) => {
    const s = data.classmates.find((c) => c.id === id);
    return s ? s.display_name : '';
  };

  const getParentName = (id) => {
    const p = data.parents.find((pa) => pa.id === id);
    return p ? p.display_name : '';
  };

  return (
    <PageContainer>
      <Card variant="header" title={data.survey_title} >
        <Button variant="primary" onClick={handleSubmit} loading={submitting}>
          Wünsche absenden
        </Button>
        <Button variant="secondary" onClick={() => navigate('/surveys')}>Abbrechen</Button>
      </Card>
      {message && <MessageBox text={message.text} type={message.type} />}

      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          <strong>Schülerwünsche</strong><br />
          Wählen Sie zwei Mitschüler/innen, mit denen Sie gerne in einer Klasse sein möchten,
          und wählen Sie einen Elternaccount aus, der Ihre Wahl bestätigen muss.
        </p>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)', marginTop: '8px' }}>
          Hallo {data.student.display_name} (Klasse {data.student.class_name})
        </p>
      </Card>

      {data.existing_wish && (
        <Card style={{ marginBottom: 'var(--space-lg)', background: 'var(--color-info-bg, #e8f4fd)', border: '1px solid var(--color-info-border, #b3d9f2)' }}>
          <p style={{ margin: 0 }}>
            ✏️ Sie bearbeiten Ihre bereits abgegebenen Wünsche.
          </p>
        </Card>
      )}

      {/* Wish 1 */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <h3>Wunsch 1 – Mitschüler/in</h3>
        {wish1 && (
          <div className="special-selected" style={{ marginBottom: '8px' }}>
            Ausgewählt: <strong>{getStudentName(wish1)}</strong>
            <Button variant="ghost" size="sm" onClick={() => setWish1(null)}>✕</Button>
          </div>
        )}
        <SearchInput
          placeholder="Suchen..."
          value={searchStudent1}
          onChange={(e) => setSearchStudent1(e.target.value)}
          style={{ marginBottom: '8px' }}
        />
        <div className="special-select-list">
          {filterStudents(data.classmates, searchStudent1).map((s) => (
            <div
              key={s.id}
              className={`special-select-item ${wish1 === s.id ? 'special-select-item--selected' : ''} ${wish2 === s.id ? 'special-select-item--disabled' : ''}`}
              onClick={() => {
                if (wish2 !== s.id) setWish1(s.id);
              }}
            >
              <span>{s.display_name}</span>
              <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>
                Klasse {s.class_name}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {/* Wish 2 */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <h3>Wunsch 2 – Mitschüler/in</h3>
        {wish2 && (
          <div className="special-selected" style={{ marginBottom: '8px' }}>
            Ausgewählt: <strong>{getStudentName(wish2)}</strong>
            <Button variant="ghost" size="sm" onClick={() => setWish2(null)}>✕</Button>
          </div>
        )}
        <SearchInput
          placeholder="Suchen..."
          value={searchStudent2}
          onChange={(e) => setSearchStudent2(e.target.value)}
          style={{ marginBottom: '8px' }}
        />
        <div className="special-select-list">
          {filterStudents(data.classmates, searchStudent2).map((s) => (
            <div
              key={s.id}
              className={`special-select-item ${wish2 === s.id ? 'special-select-item--selected' : ''} ${wish1 === s.id ? 'special-select-item--disabled' : ''}`}
              onClick={() => {
                if (wish1 !== s.id) setWish2(s.id);
              }}
            >
              <span>{s.display_name}</span>
              <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>
                Klasse {s.class_name}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {/* Parent Selection */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <h3>Elternaccount auswählen</h3>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)', marginBottom: '8px' }}>
          Wählen Sie den Elternaccount, der Ihre Wünsche bestätigen soll.
        </p>
        {selectedParent && (
          <div className="special-selected" style={{ marginBottom: '8px' }}>
            Ausgewählt: <strong>{getParentName(selectedParent)}</strong>
            <Button variant="ghost" size="sm" onClick={() => setSelectedParent(null)}>✕</Button>
          </div>
        )}
        <SearchInput
          placeholder="Eltern suchen..."
          value={searchParent}
          onChange={(e) => setSearchParent(e.target.value)}
          style={{ marginBottom: '8px' }}
        />
        <div className="special-select-list">
          {filterParents(data.parents).map((p) => (
            <div
              key={p.id}
              className={`special-select-item ${selectedParent === p.id ? 'special-select-item--selected' : ''}`}
              onClick={() => setSelectedParent(p.id)}
            >
              <span>{p.display_name}</span>
              <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>
                {p.account}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {/* Summary & Submit */}
      <Card style={{ marginBottom: 'var(--space-lg)' }}>
        <h3>Zusammenfassung</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '8px', marginBottom: 'var(--space-md)' }}>
          <span style={{ fontWeight: 'bold' }}>Wunsch 1:</span>
          <span>{wish1 ? getStudentName(wish1) : '–'}</span>
          <span style={{ fontWeight: 'bold' }}>Wunsch 2:</span>
          <span>{wish2 ? getStudentName(wish2) : '–'}</span>
          <span style={{ fontWeight: 'bold' }}>Elternteil:</span>
          <span>{selectedParent ? getParentName(selectedParent) : '–'}</span>
        </div>
      </Card>
    </PageContainer>
  );
};

export default SpecialSurveyPhase1;

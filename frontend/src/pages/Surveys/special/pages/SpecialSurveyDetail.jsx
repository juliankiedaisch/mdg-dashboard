import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../../../utils/api';
import {
  PageContainer, Card, Button, Modal, MessageBox, Spinner,
} from '../../../../components/shared';
import TeacherSelectModal from '../modals/TeacherSelectModal';
import ParticipantEditModal from '../modals/ParticipantEditModal';
import { STATUS_LABELS_SPECIAL } from '../../surveyConstants';
import useAutoMessage from '../../useAutoMessage';
import '../../Surveys.css';

/**
 * Management view for a special survey.
 * Shows activation controls, class assignments, progress, participant management, and wish resets.
 */
const SpecialSurveyDetail = () => {
  const { ssId } = useParams();
  const navigate = useNavigate();
  const [survey, setSurvey] = useState(null);
  const [classes, setClasses] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [assignments, setAssignments] = useState({});  // class_name -> [teacher_uuid, ...]
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useAutoMessage();
  const [confirmActivate, setConfirmActivate] = useState(false);
  const [confirmComplete, setConfirmComplete] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [confirmReactivate, setConfirmReactivate] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [addingStudents, setAddingStudents] = useState(false);
  const [addingParents, setAddingParents] = useState(false);
  const [teacherModalClass, setTeacherModalClass] = useState(null); // class_name or null
  const [copiedLink, setCopiedLink] = useState(null);
  const [showParticipantModal, setShowParticipantModal] = useState(false);
  const [savingClass, setSavingClass] = useState(null);  // class_name being saved
  const [savedClass, setSavedClass] = useState(null);    // class_name recently saved (feedback)
  const studentFileRef = useRef(null);
  const parentFileRef = useRef(null);

  useEffect(() => {
    loadData();
  }, [ssId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [surveyRes, classesRes, teachersRes] = await Promise.all([
        api.get(`/api/surveys/special/${ssId}`),
        api.get(`/api/surveys/special/${ssId}/classes`),
        api.get('/api/surveys/special/teachers'),
      ]);
      setSurvey(surveyRes.data.survey);
      setClasses(classesRes.data.classes || []);
      setTeachers(teachersRes.data.teachers || []);

      // Initialize assignments from existing data (multiple teachers per class)
      const aMap = {};
      for (const c of classesRes.data.classes || []) {
        if (c.teachers && c.teachers.length > 0) {
          aMap[c.class_name] = c.teachers.map((t) => t.teacher_uuid);
        } else {
          aMap[c.class_name] = [];
        }
      }
      setAssignments(aMap);
    } catch (err) {
      console.error('Error loading special survey:', err);
      setMessage({ text: 'Fehler beim Laden der Spezialumfrage', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  /** Save teacher assignments for one class immediately; sends full list to avoid clearing others. */
  const handleAssignTeacherForClass = async (className, uuids) => {
    setSavingClass(className);
    const newAssignments = { ...assignments, [className]: uuids };
    const assignmentsList = Object.entries(newAssignments)
      .filter(([, u]) => u && u.length > 0)
      .map(([cn, u]) => ({ class_name: cn, teacher_uuids: u }));
    try {
      const res = await api.put(`/api/surveys/special/${ssId}/assign-teachers`, {
        assignments: assignmentsList,
      });
      if (res.data.status) {
        setAssignments(newAssignments);
        setSavedClass(className);
        setTimeout(() => setSavedClass(null), 2500);
      } else {
        setMessage({ text: res.data.message, type: 'error' });
      }
    } catch {
      setMessage({ text: 'Fehler beim Zuweisen', type: 'error' });
    } finally {
      setSavingClass(null);
    }
  };

  const handleActivate = async () => {
    try {
      const res = await api.put(`/api/surveys/special/${ssId}/activate`);
      if (res.data.status) {
        setMessage({ text: res.data.message, type: 'success' });
        setConfirmActivate(false);
        loadData();
      } else {
        setMessage({ text: res.data.message, type: 'error' });
        setConfirmActivate(false);
      }
    } catch (err) {
      setMessage({ text: err.response?.data?.message || 'Fehler beim Aktivieren', type: 'error' });
      setConfirmActivate(false);
    }
  };

  const handleComplete = async () => {
    try {
      const res = await api.put(`/api/surveys/special/${ssId}/complete`);
      if (res.data.status) {
        setMessage({ text: res.data.message, type: 'success' });
        setConfirmComplete(false);
        loadData();
      } else {
        setMessage({ text: res.data.message, type: 'error' });
        setConfirmComplete(false);
      }
    } catch (err) {
      setMessage({ text: err.response?.data?.message || 'Fehler beim Abschließen', type: 'error' });
      setConfirmComplete(false);
    }
  };

  const handleArchive = async () => {
    try {
      const res = await api.put(`/api/surveys/special/${ssId}/archive`);
      if (res.data.status) {
        setMessage({ text: res.data.message, type: 'success' });
        setConfirmArchive(false);
        loadData();
      } else {
        setMessage({ text: res.data.message, type: 'error' });
        setConfirmArchive(false);
      }
    } catch (err) {
      setMessage({ text: err.response?.data?.message || 'Fehler beim Archivieren', type: 'error' });
      setConfirmArchive(false);
    }
  };

  const handleReactivate = async () => {
    try {
      const res = await api.put(`/api/surveys/special/${ssId}/reactivate`);
      if (res.data.status) {
        setMessage({ text: res.data.message, type: 'success' });
        setConfirmReactivate(false);
        loadData();
      } else {
        setMessage({ text: res.data.message, type: 'error' });
        setConfirmReactivate(false);
      }
    } catch (err) {
      setMessage({ text: err.response?.data?.message || 'Fehler beim Reaktivieren', type: 'error' });
      setConfirmReactivate(false);
    }
  };

  const handleDelete = async () => {
    try {
      await api.delete(`/api/surveys/special/${ssId}`);
      navigate('/surveys');
    } catch { // delete error
      setMessage({ text: 'Fehler beim Löschen', type: 'error' });
    }
  };

  const handleExport = async () => {
    setDownloading(true);
    try {
      const response = await api.get(`/api/surveys/special/${ssId}/export`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `spezialumfrage_${ssId}_ergebnisse.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch { // export error
      setMessage({ text: 'Fehler beim Exportieren', type: 'error' });
    } finally {
      setDownloading(false);
    }
  };

  const handleAddStudents = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAddingStudents(true);
    try {
      const formData = new FormData();
      formData.append('student_csv', file);
      const res = await api.post(`/api/surveys/special/${ssId}/add-students`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (res.data.status) {
        setMessage({ text: res.data.message, type: 'success' });
        loadData();
      } else {
        setMessage({ text: res.data.message, type: 'error' });
      }
    } catch (err) {
      setMessage({ text: err.response?.data?.message || 'Fehler beim Hinzufügen', type: 'error' });
    } finally {
      setAddingStudents(false);
      if (studentFileRef.current) studentFileRef.current.value = '';
    }
  };

  const handleAddParents = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAddingParents(true);
    try {
      const formData = new FormData();
      formData.append('parent_csv', file);
      const res = await api.post(`/api/surveys/special/${ssId}/add-parents`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (res.data.status) {
        setMessage({ text: res.data.message, type: 'success' });
        loadData();
      } else {
        setMessage({ text: res.data.message, type: 'error' });
      }
    } catch (err) {
      setMessage({ text: err.response?.data?.message || 'Fehler beim Hinzufügen', type: 'error' });
    } finally {
      setAddingParents(false);
      if (parentFileRef.current) parentFileRef.current.value = '';
    }
  };

  const getWishStats = () => {
    if (!survey?.wishes) return { total: 0, confirmed: 0 };
    const wishes = Object.values(survey.wishes);
    return { total: wishes.length, confirmed: wishes.filter((w) => w.parent_confirmed).length };
  };

  const getEvalStats = () => {
    if (!survey?.evaluations) return { total: 0 };
    return { total: Object.keys(survey.evaluations).length };
  };

  const copyLink = (path) => {
    const fullUrl = `${window.location.origin}${path}`;
    const doCopy = () => {
      if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(fullUrl);
      const ta = document.createElement('textarea');
      ta.value = fullUrl;
      ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); return Promise.resolve(); }
      catch { return Promise.reject(new Error('Copy failed')); }
      finally { document.body.removeChild(ta); }
    };
    doCopy()
      .then(() => { setCopiedLink(path); setTimeout(() => setCopiedLink(null), 2000); })
      .catch(() => setMessage({ text: 'Kopieren fehlgeschlagen. Bitte manuell markieren und kopieren.', type: 'error' }));
  };

  const isSetup = survey?.status === 'setup';
  const isActive = survey?.status === 'active' || ['phase1', 'phase2', 'phase3'].includes(survey?.status);
  const isCompleted = survey?.status === 'completed';
  const isArchived = survey?.status === 'archived';
  const showManagement = isSetup || isActive;

  if (loading) return <PageContainer><Card variant="header" title="Spezialumfrage" /><Spinner /></PageContainer>;
  if (!survey) return <PageContainer><Card variant="header" title="Spezialumfrage" /><p>Nicht gefunden.</p></PageContainer>;

  const wishStats = getWishStats();
  const evalStats = getEvalStats();
  const statusVariant = isArchived ? 'archived' : isCompleted ? 'closed' : isActive ? 'active' : 'draft';

  const participationLinks = [
    { label: 'Schüler (Phase 1 – Wünsche)', path: `/surveys/special/${ssId}/phase1` },
    { label: 'Eltern (Phase 2 – Bestätigung)', path: `/surveys/special/${ssId}/phase2` },
    { label: 'Lehrkräfte (Phase 3 – Bewertung)', path: `/surveys/special/${ssId}/phase3` },
  ];

  return (
    <PageContainer>
      {/* ── Header ─────────────────────────────────────────────── */}
      <Card variant="header" title={survey.title}>
        <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center', flexWrap: 'wrap' }}>
          <span className={`survey-card__status survey-card__status--${statusVariant}`}>
            {STATUS_LABELS_SPECIAL[survey.status] || survey.status}
          </span>
          <span style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
            Jahrgang: {survey.grade_level}
          </span>
          <Button variant="secondary" onClick={() => navigate('/surveys')}>← Zurück</Button>
        </div>
      </Card>

      {message && <MessageBox message={message.text} type={message.type} />}

      {/* ── Compact Stats Strip ─────────────────────────────────── */}
      <div className="special-compact-stats">
        <div className="special-stat-item special-stat-item--students">
          <div className="special-stat-item__value">{survey.student_count ?? '–'}</div>
          <div className="special-stat-item__label">Schüler/innen</div>
        </div>
        <div className="special-stat-item special-stat-item--parents">
          <div className="special-stat-item__value">{survey.parent_count ?? '–'}</div>
          <div className="special-stat-item__label">Elternaccounts</div>
        </div>
        <div className="special-stat-item special-stat-item--teachers">
          <div className="special-stat-item__value">{survey.class_teacher_count ?? '–'}</div>
          <div className="special-stat-item__label">Klassenlehrkräfte</div>
        </div>
        <div className="special-stat-item special-stat-item--wishes">
          <div className="special-stat-item__value">{wishStats.total}</div>
          <div className="special-stat-item__label">Wünsche gesamt</div>
        </div>
        <div className="special-stat-item special-stat-item--confirmed">
          <div className="special-stat-item__value">{wishStats.confirmed}</div>
          <div className="special-stat-item__label">Wünsche bestätigt</div>
        </div>
        <div className="special-stat-item special-stat-item--evals">
          <div className="special-stat-item__value">{evalStats.total}</div>
          <div className="special-stat-item__label">Bewertungen</div>
        </div>
      </div>

      {/* ── Row 1: Participation Links + Control ─────────────────── */}
      <div className="grid-lg-2to1" style={{ marginTop: 'var(--space-md)' }}>

        {/* Participation Links (active only) */}
        {isActive && (
          <Card style={{ marginBottom: 0 }}>
            <h3 style={{ marginBottom: 'var(--space-sm)' }}>Teilnahme-Links</h3>
            <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-md)', fontSize: 'var(--font-size-sm)' }}>
              Teilen Sie diese Links mit den jeweiligen Teilnehmergruppen.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              {participationLinks.map(({ label, path }) => {
                const fullUrl = `${window.location.origin}${path}`;
                return (
                  <div key={path} className="special-link-row">
                    <span className="special-link-row__label">{label}</span>
                    <code className="special-link-row__url">{fullUrl}</code>
                    <Button variant="secondary" size="sm" onClick={() => copyLink(path)}>
                      {copiedLink === path ? '✓ Kopiert' : 'Kopieren'}
                    </Button>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {/* Control / Survey Management */}
        <Card style={{ marginBottom: 0, gridColumn: !isActive ? '1 / -1' : undefined }}>
          <h3 style={{ marginBottom: 'var(--space-md)' }}>Steuerung</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            <Button variant="blue" onClick={handleExport} loading={downloading}>
              Excel-Export herunterladen
            </Button>
            {isSetup && (
              <Button variant="success" onClick={() => setConfirmActivate(true)}>
                Umfrage aktivieren
              </Button>
            )}
            {isActive && (
              <Button variant="primary" onClick={() => setConfirmComplete(true)}>
                Umfrage abschließen
              </Button>
            )}
            {(isActive || isCompleted) && (
              <Button variant="secondary" onClick={() => setConfirmArchive(true)}>
                Archivieren
              </Button>
            )}
            {(isCompleted || isArchived) && (
              <Button variant="primary" onClick={() => setConfirmReactivate(true)}>
                Reaktivieren
              </Button>
            )}
            <Button variant="danger" onClick={() => setConfirmDelete(true)}>
              Umfrage löschen
            </Button>
          </div>
        </Card>

      </div>

      {/* ── Row 2: Teacher Management + Participant Management ──── */}
      {showManagement && (
        <div className="grid-lg-2to1">

          {/* Teacher Assignment */}
          <Card style={{ marginBottom: 0 }}>
            <h3 style={{ marginBottom: 'var(--space-sm)' }}>Klassenlehrkräfte</h3>
            <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-md)', fontSize: 'var(--font-size-sm)' }}>
              Klicken Sie auf eine Klasse, um Lehrkräfte zuzuweisen. Die Änderung wird sofort gespeichert.
            </p>
            <div className="special-teacher-assign-grid">
              {classes.map((cls) => {
                const selected = assignments[cls.class_name] || [];
                const isSaving = savingClass === cls.class_name;
                const justSaved = savedClass === cls.class_name;
                return (
                  <div key={cls.class_name} className="special-teacher-assign-row">
                    <div className="special-teacher-assign-label">
                      <strong>{cls.class_name}</strong>
                      <span style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)' }}>
                        {cls.student_count} Schüler
                      </span>
                    </div>
                    <div className="special-teacher-assign-select">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
                        <Button
                          variant="secondary"
                          size="sm"
                          loading={isSaving}
                          onClick={() => setTeacherModalClass(cls.class_name)}
                        >
                          {selected.length > 0
                            ? `${selected.length} Lehrkraft${selected.length !== 1 ? 'kräfte' : ''}`
                            : 'Zuweisen'}
                        </Button>
                        {justSaved && (
                          <span className="special-save-hint">Gespeichert</span>
                        )}
                      </div>
                      {selected.length > 0 && (
                        <div className="special-teacher-tags">
                          {selected.map((uuid) => {
                            const t = teachers.find((te) => te.uuid === uuid);
                            return (
                              <span key={uuid} className="special-teacher-tag">
                                {t?.username || uuid}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="special-teacher-tag__remove"
                                  onClick={() => handleAssignTeacherForClass(
                                    cls.class_name,
                                    selected.filter((u) => u !== uuid),
                                  )}
                                  aria-label="Entfernen"
                                >
                                  ×
                                </Button>
                              </span>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Participant Management */}
          <Card style={{ marginBottom: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-sm)' }}>
              <h3 style={{ margin: 0 }}>Teilnehmer</h3>

            </div>
            <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-md)', fontSize: 'var(--font-size-sm)' }}>
              Laden Sie eine CSV-Datei hoch, um weitere Schüler/innen oder Eltern hinzuzufügen,
              oder bearbeiten Sie einzelne Teilnehmer über den Button "Bearbeiten".
            </p>
            <div style={{ display: 'flex', flexDirection: 'row', justifyContent: 'space-between', marginBottom: 'var(--space-md)' }}>
              <Button variant="secondary" onClick={() => setShowParticipantModal(true)}>
                Bearbeiten
              </Button>

            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
              <div>
                <input type="file" accept=".csv" ref={studentFileRef} onChange={handleAddStudents}
                  style={{ display: 'none' }} id="add-students-csv" />
                <Button variant="secondary" onClick={() => studentFileRef.current?.click()} loading={addingStudents}>
                  + Schüler-CSV hochladen
                </Button>
              </div>
              <div>
                <input type="file" accept=".csv" ref={parentFileRef} onChange={handleAddParents}
                  style={{ display: 'none' }} id="add-parents-csv" />
                <Button variant="secondary" onClick={() => parentFileRef.current?.click()} loading={addingParents}>
                  + Eltern-CSV hochladen
                </Button>
              </div>
            </div>
          </Card>

        </div>
      )}

      {/* ── Classes & Students Overview ─────────────────────────── */}
      <Card style={{ marginTop: 'var(--space-md)' }}>
        <h3 style={{ marginBottom: 'var(--space-md)' }}>Klassen & Schüler</h3>
        {classes.map((cls) => (
          <div key={cls.class_name} style={{ marginBottom: 'var(--space-lg)' }}>
            <h4 style={{ marginBottom: 'var(--space-sm)' }}>
              Klasse {cls.class_name}
              <span style={{ fontWeight: 'normal', color: 'var(--color-text-secondary)', marginLeft: '8px' }}>
                ({cls.student_count} Schüler)
              </span>
              {cls.teachers?.length > 0 && (
                <span style={{ fontWeight: 'normal', color: 'var(--color-text-secondary)', marginLeft: '8px', fontSize: 'var(--font-size-sm)' }}>
                  – Lehrkräfte: {cls.teachers.map((t) => t.teacher_name).join(', ')}
                </span>
              )}
            </h4>
            <div className="result-participants__list">
              {cls.students.map((s) => {
                const wish = survey.wishes?.[s.id];
                const ev = survey.evaluations?.[s.id];
                return (
                  <div key={s.id} className="result-participants__tag" style={{ marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>{s.display_name}</span>
                    {wish && (
                      <span style={{ fontSize: 'var(--font-size-sm)' }}>
                        {wish.parent_confirmed ? '✅' : wish.wish1_student_id ? '📝' : ''}
                      </span>
                    )}
                    {ev && <span style={{ fontSize: 'var(--font-size-sm)' }}>📊</span>}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </Card>

      {/* ── Confirmation Modals ─────────────────────────────────── */}

      {confirmActivate && (
        <Modal title="Umfrage aktivieren?" onClose={() => setConfirmActivate(false)} size="md"
          footer={<><Button variant="secondary" onClick={() => setConfirmActivate(false)}>Abbrechen</Button>
            <Button variant="success" onClick={handleActivate}>Aktivieren</Button></>}>
          <p>Möchten Sie die Umfrage aktivieren?</p>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
            Nach der Aktivierung können <strong>alle Rollen gleichzeitig</strong> teilnehmen:
            Schüler/innen wählen Wünsche, Eltern bestätigen, Lehrkräfte bewerten.
          </p>
        </Modal>
      )}

      {confirmComplete && (
        <Modal title="Umfrage abschließen?" onClose={() => setConfirmComplete(false)} size="md"
          footer={<><Button variant="secondary" onClick={() => setConfirmComplete(false)}>Abbrechen</Button>
            <Button variant="primary" onClick={handleComplete}>Abschließen</Button></>}>
          <p>Möchten Sie die Umfrage abschließen?</p>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
            Nach dem Abschluss können keine weiteren Eingaben mehr gemacht werden.
            Die Umfrage kann später reaktiviert werden.
          </p>
        </Modal>
      )}

      {confirmDelete && (
        <Modal title="Spezialumfrage löschen?" onClose={() => setConfirmDelete(false)} size="sm"
          footer={<><Button variant="secondary" onClick={() => setConfirmDelete(false)}>Abbrechen</Button>
            <Button variant="danger" onClick={handleDelete}>Endgültig löschen</Button></>}>
          <p>
            Sind Sie sicher, dass Sie die Spezialumfrage <strong>&ldquo;{survey.title}&rdquo;</strong> und alle
            zugehörigen Daten unwiderruflich löschen möchten?
          </p>
        </Modal>
      )}

      {confirmArchive && (
        <Modal title="Spezialumfrage archivieren?" onClose={() => setConfirmArchive(false)} size="sm"
          footer={<><Button variant="secondary" onClick={() => setConfirmArchive(false)}>Abbrechen</Button>
            <Button variant="primary" onClick={handleArchive}>Archivieren</Button></>}>
          <p>Möchten Sie die Spezialumfrage <strong>&ldquo;{survey.title}&rdquo;</strong> archivieren?</p>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
            Alle Daten bleiben erhalten und der Excel-Export funktioniert weiterhin.
            Die Umfrage kann jederzeit reaktiviert werden.
          </p>
        </Modal>
      )}

      {confirmReactivate && (
        <Modal title="Spezialumfrage reaktivieren?" onClose={() => setConfirmReactivate(false)} size="sm"
          footer={<><Button variant="secondary" onClick={() => setConfirmReactivate(false)}>Abbrechen</Button>
            <Button variant="primary" onClick={handleReactivate}>Reaktivieren</Button></>}>
          <p>Möchten Sie die Spezialumfrage <strong>&ldquo;{survey.title}&rdquo;</strong> reaktivieren?</p>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
            Die Umfrage wird wieder aktiv und alle Rollen können erneut teilnehmen.
            Bereits vorhandene Daten bleiben erhalten.
          </p>
        </Modal>
      )}

      {/* ── Modals ─────────────────────────────────────────────── */}

      {teacherModalClass && (
        <TeacherSelectModal
          teachers={teachers}
          selectedUuids={assignments[teacherModalClass] || []}
          onConfirm={(uuids) => {
            handleAssignTeacherForClass(teacherModalClass, uuids);
            setTeacherModalClass(null);
          }}
          onClose={() => setTeacherModalClass(null)}
          title={`Lehrkräfte für Klasse ${teacherModalClass}`}
        />
      )}

      {showParticipantModal && (
        <ParticipantEditModal
          ssId={ssId}
          onClose={() => setShowParticipantModal(false)}
          onChanged={loadData}
        />
      )}
    </PageContainer>
  );
};

export default SpecialSurveyDetail;

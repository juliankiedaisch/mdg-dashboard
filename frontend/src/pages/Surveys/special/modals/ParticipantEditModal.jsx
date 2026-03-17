import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import api from '../../../../utils/api';
import { Modal, Button, Spinner, MessageBox, SearchInput, TextInput, SelectInput } from '../../../../components/shared';
import '../../Surveys.css';

/**
 * ParticipantEditModal – wide modal to view, search, add and remove
 * students and parents in a special survey.
 *
 * Left side: searchable participant list
 * Right side: details of selected participant
 */
const ParticipantEditModal = ({ ssId, onClose, onChanged }) => {
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all'); // all | student | parent
  const [message, setMessage] = useState(null);
  const [removing, setRemoving] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(null); // participant obj
  const [showAddForm, setShowAddForm] = useState(false);
  const [addUsername, setAddUsername] = useState('');
  const [addRole, setAddRole] = useState('student');
  const [addClass, setAddClass] = useState('');
  const [adding, setAdding] = useState(false);
  const [allUsers, setAllUsers] = useState([]);
  const [userSearch, setUserSearch] = useState('');
  const [confirmReset, setConfirmReset] = useState(null); // participant obj
  const [resetting, setResetting] = useState(false);
  const msgTimerRef = useRef(null);

  // Auto-dismiss success messages after 4 seconds
  const showMessage = useCallback((msg) => {
    if (msgTimerRef.current) clearTimeout(msgTimerRef.current);
    setMessage(msg);
    if (msg?.type === 'success') {
      msgTimerRef.current = setTimeout(() => setMessage(null), 4000);
    }
  }, []);

  useEffect(() => {
    loadParticipants();
    loadUsers();
    return () => { if (msgTimerRef.current) clearTimeout(msgTimerRef.current); };
  }, [ssId]);

  // After reloading participants, refresh the selected detail so it isn't stale
  const refreshSelected = useCallback((freshList) => {
    setSelected((prev) => {
      if (!prev) return null;
      const match = freshList.find(
        (p) => p.participant_id === prev.participant_id && p.role === prev.role
      );
      return match || null;
    });
  }, []);

  const loadParticipants = async () => {
    try {
      setLoading(true);
      const res = await api.get(`/api/surveys/special/${ssId}/participants`);
      const list = res.data.participants || [];
      setParticipants(list);
      refreshSelected(list);
    } catch (err) {
      showMessage({ text: err.response?.data?.error || 'Fehler beim Laden', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    try {
      const res = await api.get('/api/surveys/special/teachers');
      setAllUsers(res.data.teachers || []);
    } catch {
      // non-fatal
    }
  };

  const filtered = useMemo(() => {
    let list = participants;
    if (roleFilter !== 'all') {
      list = list.filter((p) => p.role === roleFilter);
    }
    const term = search.toLowerCase().trim();
    if (term) {
      list = list.filter(
        (p) =>
          p.display_name.toLowerCase().includes(term) ||
          p.account.toLowerCase().includes(term) ||
          (p.class_name || '').toLowerCase().includes(term)
      );
    }
    return list;
  }, [participants, roleFilter, search]);

  const filteredUsers = useMemo(() => {
    const term = userSearch.toLowerCase().trim();
    if (!term) return allUsers.slice(0, 50);
    return allUsers.filter((u) => u.username.toLowerCase().includes(term));
  }, [allUsers, userSearch]);

  // Derive existing class names for the add-student dropdown
  const existingClasses = useMemo(() => {
    const set = new Set();
    for (const p of participants) {
      if (p.class_name) set.add(p.class_name);
    }
    return [...set].sort();
  }, [participants]);

  const handleRemove = async () => {
    if (!confirmRemove) return;
    setRemoving(true);
    showMessage(null);
    try {
      const res = await api.delete(
        `/api/surveys/special/${ssId}/participants/${confirmRemove.participant_id}?role=${confirmRemove.role}`
      );
      if (res.data.status) {
        // Clear selection if the removed participant was selected
        if (selected?.participant_id === confirmRemove.participant_id && selected?.role === confirmRemove.role) {
          setSelected(null);
        }
        setConfirmRemove(null);
        await loadParticipants();
        onChanged?.();
        showMessage({ text: res.data.message, type: 'success' });
      } else {
        showMessage({ text: res.data.message, type: 'error' });
      }
    } catch (err) {
      showMessage({ text: err.response?.data?.message || 'Fehler beim Entfernen', type: 'error' });
    } finally {
      setRemoving(false);
    }
  };

  const resetAddForm = useCallback(() => {
    setShowAddForm(false);
    setAddUsername('');
    setAddRole('student');
    setAddClass('');
    setUserSearch('');
  }, []);

  const handleAdd = async () => {
    if (!addUsername.trim()) {
      showMessage({ text: 'Benutzername ist erforderlich.', type: 'error' });
      return;
    }
    if (addRole === 'student' && !addClass.trim()) {
      showMessage({ text: 'Klasse ist erforderlich für Schüler.', type: 'error' });
      return;
    }
    setAdding(true);
    showMessage(null);
    try {
      const res = await api.post(`/api/surveys/special/${ssId}/participants`, {
        username: addUsername.trim(),
        role: addRole,
        class_name: addClass.trim(),
      });
      if (res.data.status) {
        resetAddForm();
        await loadParticipants();
        onChanged?.();
        showMessage({ text: res.data.message, type: 'success' });
      } else {
        showMessage({ text: res.data.message, type: 'error' });
      }
    } catch (err) {
      showMessage({ text: err.response?.data?.message || 'Fehler beim Hinzufügen', type: 'error' });
    } finally {
      setAdding(false);
    }
  };

  const studentCount = participants.filter((p) => p.role === 'student').length;
  const parentCount = participants.filter((p) => p.role === 'parent').length;

  const handleResetWish = async () => {
    if (!confirmReset) return;
    // Capture identity before clearing confirm state
    const targetId = confirmReset.participant_id;
    const targetRole = confirmReset.role;
    setResetting(true);
    showMessage(null);
    try {
      const res = await api.post(`/api/surveys/special/${ssId}/reset-wish`, {
        student_id: targetId,
      });
      if (res.data.status) {
        // Fetch fresh participant data without touching loading state (avoids parent re-mount)
        const freshRes = await api.get(`/api/surveys/special/${ssId}/participants`);
        const freshList = freshRes.data.participants || [];
        // Find the same student in the refreshed list
        const freshParticipant = freshList.find(
          (p) => p.participant_id === targetId && p.role === targetRole,
        ) || null;
        // Update list + restore selection in one batch, then close the confirm modal
        setParticipants(freshList);
        setSelected(freshParticipant);
        setConfirmReset(null);
        // NOTE: onChanged is intentionally NOT called here — wish resets do not change
        // participant counts, and calling it would trigger loadData() in the parent which
        // sets loading:true and unmounts this modal, losing all local state.
        showMessage({ text: res.data.message, type: 'success' });
      } else {
        showMessage({ text: res.data.message, type: 'error' });
      }
    } catch (err) {
      showMessage({ text: err.response?.data?.message || 'Fehler beim Zurücksetzen', type: 'error' });
    } finally {
      setResetting(false);
    }
  };

  return (
    <Modal
      title="Teilnehmer verwalten"
      onClose={onClose}
      size="xl"
      footer={
        <Button variant="secondary" onClick={onClose}>Schließen</Button>
      }
    >
      {message && <MessageBox message={message.text} type={message.type} />}

      {loading ? (
        <Spinner />
      ) : (
        <div className="participant-modal">
          {/* Left panel: list */}
          <div className="participant-modal__left">
            {/* Search & filter */}
            <div className="participant-modal__controls">
              <SearchInput
                placeholder="Teilnehmer suchen…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <div className="participant-modal__tabs">
                <Button
                  variant="ghost"
                  className={`participant-modal__tab ${roleFilter === 'all' ? 'participant-modal__tab--active' : ''}`}
                  onClick={() => setRoleFilter('all')}
                >
                  Alle ({participants.length})
                </Button>
                <Button
                  variant="ghost"
                  className={`participant-modal__tab ${roleFilter === 'student' ? 'participant-modal__tab--active' : ''}`}
                  onClick={() => setRoleFilter('student')}
                >
                  Schüler ({studentCount})
                </Button>
                <Button
                  variant="ghost"
                  className={`participant-modal__tab ${roleFilter === 'parent' ? 'participant-modal__tab--active' : ''}`}
                  onClick={() => setRoleFilter('parent')}
                >
                  Eltern ({parentCount})
                </Button>
              </div>
            </div>

            {/* Participant list */}
            <div className="participant-modal__list">
              {filtered.length === 0 ? (
                <div className="participant-modal__empty">Keine Teilnehmer gefunden</div>
              ) : (
                filtered.map((p) => (
                  <div
                    key={`${p.role}-${p.participant_id}`}
                    className={`participant-modal__item ${
                      selected?.participant_id === p.participant_id && selected?.role === p.role
                        ? 'participant-modal__item--selected'
                        : ''
                    }`}
                    onClick={() => setSelected(p)}
                  >
                    <div className="participant-modal__item-main">
                      <span className="participant-modal__item-name">{p.display_name}</span>
                      <span className={`participant-modal__role-badge participant-modal__role-badge--${p.role}`}>
                        {p.role === 'student' ? 'Schüler' : 'Eltern'}
                      </span>
                    </div>
                    <div className="participant-modal__item-sub">
                      {p.account}
                      {p.class_name && ` · ${p.class_name}`}
                      {!p.linked && <span className="participant-modal__unlinked" title="Benutzer noch nicht angemeldet"> ⚠</span>}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Add button */}
            <div className="participant-modal__add-bar">
              <Button variant="primary" size="sm" onClick={() => setShowAddForm(true)}>
                + Teilnehmer hinzufügen
              </Button>
            </div>
          </div>

          {/* Right panel: details */}
          <div className="participant-modal__right">
            {showAddForm ? (
              <div className="participant-modal__add-form">
                <h4 style={{ marginBottom: 'var(--space-md)' }}>Teilnehmer hinzufügen</h4>

                {/* Role */}
                <div className="participant-modal__field">
                  <label>Rolle</label>
                  <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
                    <Button
                      variant="ghost"
                      className={`participant-modal__tab ${addRole === 'student' ? 'participant-modal__tab--active' : ''}`}
                      onClick={() => setAddRole('student')}
                    >
                      Schüler/in
                    </Button>
                    <Button
                      variant="ghost"
                      className={`participant-modal__tab ${addRole === 'parent' ? 'participant-modal__tab--active' : ''}`}
                      onClick={() => { setAddRole('parent'); setAddClass(''); }}
                    >
                      Elternteil
                    </Button>
                  </div>
                </div>

                {/* User search */}
                <div className="participant-modal__field">
                  <label>Benutzer</label>
                  <TextInput
                    placeholder="Benutzername suchen…"
                    value={userSearch}
                    onChange={(e) => {
                      setUserSearch(e.target.value);
                      setAddUsername(e.target.value);
                    }}
                    fullWidth
                  />
                  {userSearch.trim() && (
                    <div className="participant-modal__user-list">
                      {filteredUsers.length === 0 ? (
                        <div className="participant-modal__empty" style={{ padding: '8px' }}>Kein Benutzer gefunden</div>
                      ) : (
                        filteredUsers.slice(0, 20).map((u) => (
                          <div
                            key={u.uuid}
                            className={`participant-modal__user-item ${addUsername === u.username ? 'participant-modal__user-item--selected' : ''}`}
                            onClick={() => {
                              setAddUsername(u.username);
                              setUserSearch(u.username);
                            }}
                          >
                            {u.username}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>

                {/* Class (student only) */}
                {addRole === 'student' && (
                  <div className="participant-modal__field">
                    <label>Klasse</label>
                    <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
                      <TextInput
                        placeholder="z.B. 7a"
                        value={addClass}
                        onChange={(e) => setAddClass(e.target.value)}
                        style={{ flex: 1 }}
                      />
                      {existingClasses.length > 0 && (
                        <SelectInput
                          value={addClass}
                          onChange={(e) => setAddClass(e.target.value)}
                          style={{ flex: 1 }}
                        >
                          <option value="">Klasse wählen…</option>
                          {existingClasses.map((c) => (
                            <option key={c} value={c}>{c}</option>
                          ))}
                        </SelectInput>
                      )}
                    </div>
                  </div>
                )}

                <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
                  <Button variant="primary" onClick={handleAdd} loading={adding}>
                    Hinzufügen
                  </Button>
                  <Button variant="secondary" onClick={resetAddForm}>
                    Abbrechen
                  </Button>
                </div>
              </div>
            ) : selected ? (
              <div className="participant-modal__detail">
                <h4 style={{ marginBottom: 'var(--space-md)' }}>{selected.display_name}</h4>

                <div className="participant-modal__detail-grid">
                  <div className="participant-modal__detail-label">Rolle</div>
                  <div>
                    <span className={`participant-modal__role-badge participant-modal__role-badge--${selected.role}`}>
                      {selected.role === 'student' ? 'Schüler/in' : 'Elternteil'}
                    </span>
                  </div>

                  <div className="participant-modal__detail-label">Benutzername</div>
                  <div>{selected.account}</div>

                  {selected.class_name && (
                    <>
                      <div className="participant-modal__detail-label">Klasse</div>
                      <div>{selected.class_name}</div>
                    </>
                  )}

                  <div className="participant-modal__detail-label">Verknüpft</div>
                  <div>{selected.linked ? '✅ Ja' : '⚠️ Nein (noch nicht angemeldet)'}</div>

                  {selected.email && (
                    <>
                      <div className="participant-modal__detail-label">E-Mail</div>
                      <div>{selected.email}</div>
                    </>
                  )}
                </div>

                {/* Student-specific info */}
                {selected.role === 'student' && (
                  <div style={{ marginTop: 'var(--space-lg)' }}>
                    <h5 style={{ marginBottom: 'var(--space-sm)', color: 'var(--color-text-secondary)' }}>Umfragedaten</h5>
                    <div className="participant-modal__detail-grid">
                      <div className="participant-modal__detail-label">Wunsch 1</div>
                      <div>{selected.wish?.wish1_name || '—'}</div>

                      <div className="participant-modal__detail-label">Wunsch 2</div>
                      <div>{selected.wish?.wish2_name || '—'}</div>

                      <div className="participant-modal__detail-label">Gewähltes Elternteil</div>
                      <div>{selected.wish?.selected_parent_name || '—'}</div>

                      <div className="participant-modal__detail-label">Eltern bestätigt</div>
                      <div>{selected.wish ? (selected.wish.parent_confirmed ? '✅ Ja' : '❌ Nein') : '—'}</div>

                      <div className="participant-modal__detail-label">Lehrerbewertung</div>
                      <div>
                        {selected.evaluation
                          ? `✅ Bewertet von ${selected.evaluation.teacher_name || 'Lehrkraft'}`
                          : '—'}
                      </div>
                    </div>

                    {/* Reset wishes button */}
                    {selected.wish && (
                      <div style={{ marginTop: 'var(--space-md)' }}>
                        <Button
                          variant="secondary"
                          onClick={() => setConfirmReset(selected)}
                        >
                          🔄 Wünsche zurücksetzen
                        </Button>
                      </div>
                    )}
                  </div>
                )}

                {/* Parent-specific info */}
                {selected.role === 'parent' && (
                  <div style={{ marginTop: 'var(--space-lg)' }}>
                    <h5 style={{ marginBottom: 'var(--space-sm)', color: 'var(--color-text-secondary)' }}>Umfragedaten</h5>
                    <div className="participant-modal__detail-grid">
                      <div className="participant-modal__detail-label">Bestätigung</div>
                      <div>{selected.confirmed ? '✅ Abgeschlossen' : '⏳ Ausstehend'}</div>

                      <div className="participant-modal__detail-label">Gewählt von</div>
                      <div>{selected.selected_by?.length > 0 ? selected.selected_by.join(', ') : '—'}</div>
                    </div>
                  </div>
                )}

                {/* Remove button */}
                <div style={{ marginTop: 'var(--space-xl)', borderTop: '1px solid var(--color-border, #e5e7eb)', paddingTop: 'var(--space-md)' }}>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => setConfirmRemove(selected)}
                  >
                    Teilnehmer entfernen
                  </Button>
                </div>
              </div>
            ) : (
              <div className="participant-modal__empty-detail">
                <div style={{ textAlign: 'center', color: 'var(--color-text-secondary)' }}>
                  <div style={{ fontSize: '2rem', marginBottom: 'var(--space-sm)' }}>👤</div>
                  <p>Wählen Sie einen Teilnehmer aus der Liste, um Details anzuzeigen.</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Confirm remove modal */}
      {confirmRemove && (
        <Modal
          title="Teilnehmer entfernen"
          onClose={() => setConfirmRemove(null)}
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmRemove(null)}>Abbrechen</Button>
              <Button variant="danger" onClick={handleRemove} loading={removing}>
                Entfernen
              </Button>
            </>
          }
        >
          <p>
            Möchten Sie <strong>{confirmRemove.display_name}</strong> ({confirmRemove.role === 'student' ? 'Schüler/in' : 'Elternteil'}) wirklich aus dieser Umfrage entfernen?
          </p>
          {confirmRemove.role === 'student' && (
            <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)', marginTop: 'var(--space-sm)' }}>
              Alle zugehörigen Wünsche und Bewertungen werden ebenfalls gelöscht.
            </p>
          )}
          {confirmRemove.role === 'parent' && (
            <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)', marginTop: 'var(--space-sm)' }}>
              Die Elternauswahl bei betroffenen Schülern wird zurückgesetzt.
            </p>
          )}
        </Modal>
      )}

      {/* Confirm reset modal */}
      {confirmReset && (
        <Modal
          title="Wünsche zurücksetzen"
          onClose={() => setConfirmReset(null)}
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmReset(null)}>Abbrechen</Button>
              <Button variant="danger" onClick={handleResetWish} loading={resetting}>
                Zurücksetzen
              </Button>
            </>
          }
        >
          <p>
            Möchten Sie die Wünsche von <strong>{confirmReset.display_name}</strong> wirklich zurücksetzen?
          </p>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)', marginTop: 'var(--space-sm)' }}>
            Die Schülerauswahl wird gelöscht. Falls ein Elternteil bereits bestätigt hat,
            wird die Bestätigung ebenfalls zurückgesetzt.
          </p>
        </Modal>
      )}
    </Modal>
  );
};

export default ParticipantEditModal;

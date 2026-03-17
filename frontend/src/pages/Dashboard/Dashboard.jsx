import { useState, useEffect, useCallback, useRef } from 'react';
import api from '../../utils/api';
import { useUser } from '../../contexts/UserContext';
import { PageContainer, Card, Spinner, Button, Modal, FormGroup, MessageBox, Tabs, TextInput, TextArea } from '../../components/shared';
import AppModal from './AppModal';
import './Dashboard.css';

/* ═══════════════════════════════════════════════════════
   SVG Icon helpers (inline to avoid extra deps)
   ═══════════════════════════════════════════════════════ */
const Icon = ({ d, size = 20, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d={d} />
  </svg>
);

const ICONS = {
  plus:  'M12 4a1 1 0 0 1 1 1v6h6a1 1 0 1 1 0 2h-6v6a1 1 0 1 1-2 0v-6H5a1 1 0 1 1 0-2h6V5a1 1 0 0 1 1-1Z',
  edit:  'M16.293 2.293a1 1 0 0 1 1.414 0l4 4a1 1 0 0 1 0 1.414l-13 13A1 1 0 0 1 8 21H4a1 1 0 0 1-1-1v-4a1 1 0 0 1 .293-.707l13-13ZM5 16.414V19h2.586l12-12L17.414 4.586l-12 12Z',
  trash: 'M7 4a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v1h4a1 1 0 1 1 0 2h-1v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7H3a1 1 0 0 1 0-2h4V4Zm2 1v0h6V4H9v1ZM6 7v13h12V7H6Zm4 3a1 1 0 0 1 1 1v6a1 1 0 1 1-2 0v-6a1 1 0 0 1 1-1Zm4 0a1 1 0 0 1 1 1v6a1 1 0 1 1-2 0v-6a1 1 0 0 1 1-1Z',
  drag:  'M8 4a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm8 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM8 10.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm8 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM8 17a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm8 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Z',
  link:  'M13.828 10.172a4 4 0 0 0-5.656 0l-4 4a4 4 0 1 0 5.656 5.656l1.102-1.101a.75.75 0 0 0-1.06-1.06l-1.102 1.1a2.5 2.5 0 1 1-3.536-3.535l4-4a2.5 2.5 0 0 1 3.536 3.536.75.75 0 0 0 1.06 1.06 4 4 0 0 0 0-5.656Zm-3.656 3.656a4 4 0 0 0 5.656 0l4-4a4 4 0 0 0-5.656-5.656l-1.1 1.1a.75.75 0 1 0 1.06 1.061l1.1-1.1a2.5 2.5 0 0 1 3.536 3.535l-4 4a2.5 2.5 0 0 1-3.536-3.535.75.75 0 0 0-1.06-1.061 4 4 0 0 0 0 5.656Z',
  close: 'M6.293 6.293a1 1 0 0 1 1.414 0L12 10.586l4.293-4.293a1 1 0 1 1 1.414 1.414L13.414 12l4.293 4.293a1 1 0 0 1-1.414 1.414L12 13.414l-4.293 4.293a1 1 0 0 1-1.414-1.414L10.586 12 6.293 7.707a1 1 0 0 1 0-1.414Z',
};

/* ═══════════════════════════════════════════════════════
   Drag & Drop hook (HTML5 native – no library needed)
   ═══════════════════════════════════════════════════════ */
function useDragAndDrop(items, onReorder) {
  const dragItem = useRef(null);
  const dragOverItem = useRef(null);

  const onDragStart = (index) => { dragItem.current = index; };
  const onDragEnter = (index) => { dragOverItem.current = index; };

  const onDragEnd = () => {
    if (dragItem.current === null || dragOverItem.current === null) return;
    if (dragItem.current === dragOverItem.current) {
      dragItem.current = null;
      dragOverItem.current = null;
      return;
    }
    const reordered = [...items];
    const [removed] = reordered.splice(dragItem.current, 1);
    reordered.splice(dragOverItem.current, 0, removed);
    dragItem.current = null;
    dragOverItem.current = null;
    onReorder(reordered);
  };

  return { onDragStart, onDragEnter, onDragEnd };
}

/* ═══════════════════════════════════════════════════════
   Main Dashboard Component
   ═══════════════════════════════════════════════════════ */
function Dashboard() {
  const { hasPermission } = useUser();
  // ── State ──
  const [pages, setPages] = useState([]);
  const [activePageId, setActivePageId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dragMode, setDragMode] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Editing controls are only visible when admin has explicitly activated Edit Mode
  const editingEnabled = hasPermission('dashboard.manage') && isEditMode;

  const toggleEditMode = () => {
    setIsEditMode(prev => {
      if (prev) setDragMode(false); // reset drag when leaving edit mode
      return !prev;
    });
  };

  // Modals
  const [pageModal, setPageModal] = useState(null);   // { mode: 'create'|'edit', page? }
  const [topicModal, setTopicModal] = useState(null); // { mode: 'create'|'edit', topic?, pageId }
  const [appModal, setAppModal] = useState(null);     // { mode: 'create'|'edit', app? }

  // ── Fetch hierarchy ──
  const fetchHierarchy = useCallback(async () => {
    try {
      const res = await api.get('/api/dashboard/hierarchy');
      const fetched = res.data.pages || [];
      setPages(fetched);
      setActivePageId(prev => {
        if (prev && fetched.some(p => p.id === prev)) return prev;
        return fetched.length ? fetched[0].id : null;
      });
    } catch (err) {
      console.error('Failed to fetch hierarchy:', err);
      if (err.response?.status !== 403) {
        setError('Fehler beim Laden der Daten.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchHierarchy(); }, [fetchHierarchy]);

  const activePage = pages.find(p => p.id === activePageId) || null;

  // ── Flash helpers ──
  const flash = msg => { setSuccess(msg); setTimeout(() => setSuccess(''), 3000); };
  const flashError = msg => { setError(msg); setTimeout(() => setError(''), 5000); };

  /* ═══════════════════════════════════════════════════
     API helpers
     ═══════════════════════════════════════════════════ */

  // ── Pages ──
  const handleCreatePage = async (name, description) => {
    try {
      await api.post('/api/dashboard/pages', { name, description });
      flash('Seite erstellt.');
      await fetchHierarchy();
    } catch (e) { flashError(e.response?.data?.message || 'Fehler beim Erstellen.'); throw e; }
  };

  const handleUpdatePage = async (id, name, description) => {
    try {
      await api.put(`/api/dashboard/pages/${id}`, { name, description });
      flash('Seite aktualisiert.');
      await fetchHierarchy();
    } catch (e) { flashError(e.response?.data?.message || 'Fehler beim Aktualisieren.'); throw e; }
  };

  const handleDeletePage = async (id) => {
    try {
      await api.delete(`/api/dashboard/pages/${id}`);
      flash('Seite gelöscht.');
      if (activePageId === id) setActivePageId(null);
      await fetchHierarchy();
    } catch (e) { flashError(e.response?.data?.message || 'Fehler beim Löschen.'); throw e; }
  };

  // ── Topics ──
  const handleCreateTopic = async (name, description, pageId) => {
    try {
      await api.post('/api/dashboard/topics', { name, description, page_id: pageId });
      flash('Rubrik erstellt.');
      await fetchHierarchy();
    } catch (e) { flashError(e.response?.data?.message || 'Fehler beim Erstellen.'); throw e; }
  };

  const handleUpdateTopic = async (id, name, description) => {
    try {
      await api.put(`/api/dashboard/topics/${id}`, { name, description });
      flash('Rubrik aktualisiert.');
      await fetchHierarchy();
    } catch (e) { flashError(e.response?.data?.message || 'Fehler beim Aktualisieren.'); throw e; }
  };

  const handleDeleteTopic = async (id) => {
    try {
      await api.delete(`/api/dashboard/topics/${id}`);
      flash('Rubrik gelöscht.');
      await fetchHierarchy();
    } catch (e) { flashError(e.response?.data?.message || 'Fehler beim Löschen.'); throw e; }
  };

  // ── Applications ──
  const handleCreateApp = async (data) => {
    try {
      await api.post('/api/dashboard/applications', data);
      flash('Anwendung erstellt.');
      await fetchHierarchy();
    } catch (e) { flashError(e.response?.data?.message || 'Fehler beim Erstellen.'); throw e; }
  };

  const handleUpdateApp = async (id, data) => {
    try {
      await api.put(`/api/dashboard/applications/${id}`, data);
      flash('Anwendung aktualisiert.');
      await fetchHierarchy();
    } catch (e) { flashError(e.response?.data?.message || 'Fehler beim Aktualisieren.'); throw e; }
  };

  const handleDeleteApp = async (id) => {
    try {
      await api.delete(`/api/dashboard/applications/${id}`);
      flash('Anwendung gelöscht.');
      await fetchHierarchy();
    } catch (e) { flashError(e.response?.data?.message || 'Fehler beim Löschen.'); throw e; }
  };

  // ── Reorder ──
  const handleReorderPages = async (reordered) => {
    setPages(reordered);
    try {
      await api.post('/api/dashboard/pages/reorder', { ordered_ids: reordered.map(p => p.id) });
    } catch { flashError('Fehler beim Speichern der Reihenfolge.'); await fetchHierarchy(); }
  };

  const handleReorderTopics = async (pageId, reorderedTopics) => {
    setPages(prev => prev.map(p => p.id === pageId ? { ...p, topics: reorderedTopics } : p));
    try {
      await api.post('/api/dashboard/topics/reorder', { page_id: pageId, ordered_ids: reorderedTopics.map(t => t.id) });
    } catch { flashError('Fehler beim Speichern der Reihenfolge.'); await fetchHierarchy(); }
  };

  const handleReorderApps = async (topicId, reorderedApps) => {
    setPages(prev => prev.map(p => ({
      ...p,
      topics: p.topics.map(t => t.id === topicId ? { ...t, applications: reorderedApps } : t),
    })));
    try {
      await api.post('/api/dashboard/applications/reorder', { topic_id: topicId, ordered_ids: reorderedApps.map(a => a.id) });
    } catch { flashError('Fehler beim Speichern der Reihenfolge.'); await fetchHierarchy(); }
  };

  /* ═══════════════════════════ RENDER ═══════════════════════════ */

  if (loading) {
    return <Spinner size="lg" text="Lade Dashboard…" fullPage />;
  }

  return (
    <PageContainer>
      {/* ─── Flash messages ─── */}
      {error && <MessageBox type="error" message={error} onDismiss={() => setError('')} />}
      {success && <MessageBox type="success" message={success} autoHide={3000} onDismiss={() => setSuccess('')} />}
      {hasPermission('dashboard.view') && (
        <>
      {/* ─── Header Card ─── */}
      <Card variant="header" title="Übersicht digitale Anwendungen">
        {editingEnabled && (
          <>
            <Button variant={dragMode ? 'primary' : 'ghost'} onClick={() => setDragMode(d => !d)} title="Drag & Drop Modus">
              <Icon d={ICONS.drag} size={14} /> {dragMode ? 'Fertig' : 'Sortieren'}
            </Button>
            <Button variant="primary" onClick={() => setAppModal({ mode: 'create' })}>
              <Icon d={ICONS.plus} size={14} /> Anwendung
            </Button>
          </>
        )}
        {hasPermission('dashboard.manage') && (
          <Button
            variant={isEditMode ? 'secondary' : 'ghost'}
            onClick={toggleEditMode}
            title={isEditMode ? 'Bearbeitungsmodus beenden' : 'Dashboard bearbeiten'}
          >
            {isEditMode ? 'Bearbeitung beenden' : 'Dashboard bearbeiten'}
          </Button>
        )}
      </Card>

      {/* ─── Page Tabs ─── */}
      <Tabs
        tabs={pages.map(p => ({ id: p.id, label: p.name }))}
        activeTab={activePageId}
        onChange={setActivePageId}
        stretch
        admin={editingEnabled}
        dragMode={dragMode}
        onAdd={() => setPageModal({ mode: 'create' })}
        onEdit={(tab) => setPageModal({ mode: 'edit', page: pages.find(p => p.id === tab.id) })}
        onReorder={(reorderedTabs) => handleReorderPages(reorderedTabs.map(t => pages.find(p => p.id === t.id)))}
      />

      {/* ─── Active page content ─── */}
      {activePage ? (
        <PageContent
          page={activePage}
          admin={editingEnabled}
          dragMode={dragMode}
          pages={pages}
          onAddTopic={() => setTopicModal({ mode: 'create', pageId: activePage.id })}
          onEditTopic={(topic) => setTopicModal({ mode: 'edit', topic, pageId: activePage.id })}
          onEditApp={(app) => setAppModal({ mode: 'edit', app })}
          onDeleteApp={handleDeleteApp}
          onReorderTopics={(reordered) => handleReorderTopics(activePage.id, reordered)}
          onReorderApps={handleReorderApps}
        />
      ) : (
        <div className="dash-empty">
          {editingEnabled ? (
            <div className="dash-empty__inner">
              <p>Noch keine Seiten vorhanden.</p>
              <Button variant="primary" onClick={() => setPageModal({ mode: 'create' })}>
                <Icon d={ICONS.plus} size={16} /> Erste Seite erstellen
              </Button>
            </div>
          ) : (
            <p>Keine Anwendungen verfügbar.</p>
          )}
        </div>
      )}

      {/* ─── Modals ─── */}
      {pageModal && (
        <PageModal
          mode={pageModal.mode}
          page={pageModal.page}
          onClose={() => setPageModal(null)}
          onCreate={handleCreatePage}
          onUpdate={handleUpdatePage}
          onDelete={handleDeletePage}
        />
      )}
      {topicModal && (
        <TopicModal
          mode={topicModal.mode}
          topic={topicModal.topic}
          pageId={topicModal.pageId}
          onClose={() => setTopicModal(null)}
          onCreate={handleCreateTopic}
          onUpdate={handleUpdateTopic}
          onDelete={handleDeleteTopic}
        />
      )}
      {appModal && (
        <AppModal
          mode={appModal.mode}
          app={appModal.app}
          pages={pages}
          onClose={() => setAppModal(null)}
          onCreate={handleCreateApp}
          onUpdate={handleUpdateApp}
          onDelete={handleDeleteApp}
        />
      )}
    </>
  )}
    
    </PageContainer>
  );
}

/* ═══════════════════════════════════════════════════════
   Page Content (Topics + Applications)
   ═══════════════════════════════════════════════════════ */
function PageContent({ page, admin, dragMode, onAddTopic, onEditTopic, onEditApp, onDeleteApp, onReorderTopics, onReorderApps }) {
  const topics = page.topics || [];
  const { onDragStart, onDragEnter, onDragEnd } = useDragAndDrop(topics, onReorderTopics);

  return (
    <div className="dash-page-content">
      {topics.map((topic, idx) => (
        <TopicSection
          key={topic.id}
          topic={topic}
          admin={admin}
          dragMode={dragMode}
          topicIndex={idx}
          onEditTopic={onEditTopic}
          onEditApp={onEditApp}
          onDeleteApp={onDeleteApp}
          onReorderApps={onReorderApps}
          onDragStart={() => onDragStart(idx)}
          onDragEnter={() => onDragEnter(idx)}
          onDragEnd={onDragEnd}
        />
      ))}

      {admin && (
        <Button className="dash-add-topic-btn" variant="ghost" onClick={onAddTopic}>
          <Icon d={ICONS.plus} size={16} /> Neue Rubrik hinzufügen
        </Button>
      )}

      {topics.length === 0 && !admin && (
        <div className="dash-empty"><p>Keine Rubriken auf dieser Seite.</p></div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Topic Section
   ═══════════════════════════════════════════════════════ */
function TopicSection({ topic, admin, dragMode, onEditTopic, onEditApp, onDeleteApp, onReorderApps, onDragStart, onDragEnter, onDragEnd }) {
  const apps = topic.applications || [];
  const appDrag = useDragAndDrop(apps, (reordered) => onReorderApps(topic.id, reordered));

  return (
    <div
      className="dash-topic"
      draggable={admin && dragMode}
      onDragStart={e => { e.stopPropagation(); onDragStart(); }}
      onDragEnter={e => { e.stopPropagation(); onDragEnter(); }}
      onDragEnd={e => { e.stopPropagation(); onDragEnd(); }}
      onDragOver={e => e.preventDefault()}
    >
      <div className="dash-topic__header">
        {admin && dragMode && <span className="dash-drag-handle"><Icon d={ICONS.drag} size={16} /></span>}
        <h3 className="dash-topic__title">{topic.name}</h3>
        {topic.description && <span className="dash-topic__desc">{topic.description}</span>}
        {admin && (
          <Button variant="ghost" size="sm" className="dash-topic__edit-btn" onClick={() => onEditTopic(topic)} title="Rubrik bearbeiten">
            <Icon d={ICONS.edit} size={14} />
          </Button>
        )}
      </div>

      <div className="dash-apps-grid">
        {apps.map((app, idx) => (
          <div
            key={app.id}
            className="dash-app-card"
            draggable={admin && dragMode}
            onDragStart={e => { e.stopPropagation(); appDrag.onDragStart(idx); }}
            onDragEnter={e => { e.stopPropagation(); appDrag.onDragEnter(idx); }}
            onDragEnd={e => { e.stopPropagation(); appDrag.onDragEnd(); }}
            onDragOver={e => e.preventDefault()}
          >
            {admin && dragMode && (
              <span className="dash-drag-handle dash-drag-handle--app">
                <Icon d={ICONS.drag} size={14} />
              </span>
            )}
            <a className="dash-app-card__link" href={app.url} target="_blank" rel="noopener noreferrer">
              {app.icon ? (
                <img src={app.icon} alt={app.name} className="dash-app-card__icon" />
              ) : (
                <div className="dash-app-card__icon-placeholder"><Icon d={ICONS.link} size={28} /></div>
              )}
              <div className="dash-app-card__name">{app.name}</div>
              {app.description && <div className="dash-app-card__desc">{app.description}</div>}
            </a>
            {admin && (
              <div className="dash-app-card__actions">
                <Button variant="ghost" size="sm" onClick={() => onEditApp(app)} title="Bearbeiten"><Icon d={ICONS.edit} size={14} /></Button>
                <Button variant="ghost" size="sm" onClick={() => { if (window.confirm(`„${app.name}“ wirklich löschen?`)) onDeleteApp(app.id); }} title="Löschen">
                  <Icon d={ICONS.trash} size={14} />
                </Button>
              </div>
            )}
          </div>
        ))}
        {apps.length === 0 && (
          <div className="dash-apps-grid__empty">Keine Anwendungen in dieser Rubrik.</div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Page Modal (Create / Edit / Delete)
   ═══════════════════════════════════════════════════════ */
function PageModal({ mode, page, onClose, onCreate, onUpdate, onDelete }) {
  const [name, setName] = useState(page?.name || '');
  const [description, setDescription] = useState(page?.description || '');
  const [saving, setSaving] = useState(false);
  const [fieldError, setFieldError] = useState('');

  const handleSave = async () => {
    if (!name.trim()) { setFieldError('Name ist erforderlich.'); return; }
    setSaving(true);
    try {
      if (mode === 'create') await onCreate(name, description);
      else await onUpdate(page.id, name, description);
      onClose();
    } catch { /* error handled upstream */ }
    finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Seite „${page.name}" und alle zugehörigen Rubriken und Anwendungen löschen?`)) return;
    setSaving(true);
    try { await onDelete(page.id); onClose(); }
    catch { /* error handled upstream */ }
    finally { setSaving(false); }
  };

  return (
    <Modal
      title={mode === 'create' ? 'Neue Seite erstellen' : 'Seite bearbeiten'}
      onClose={onClose}
      size="sm"
      footer={
        <div className="dash-modal-footer">
          {mode === 'edit' && <Button variant="danger" size="sm" onClick={handleDelete} disabled={saving}>Löschen</Button>}
          <div className="dash-modal-footer__right">
            <Button variant="ghost" size="sm" onClick={onClose}>Abbrechen</Button>
            <Button variant="primary" size="sm" onClick={handleSave} loading={saving}>
              {mode === 'create' ? 'Erstellen' : 'Speichern'}
            </Button>
          </div>
        </div>
      }
    >
      {fieldError && <MessageBox type="error" message={fieldError} autoHide={3000} onDismiss={() => setFieldError('')} />}
      <TextInput id="page-name" label="Name" required value={name} onChange={e => setName(e.target.value)} autoFocus />
      <TextArea id="page-desc" label="Beschreibung" rows={3} value={description} onChange={e => setDescription(e.target.value)} />
    </Modal>
  );
}

/* ═══════════════════════════════════════════════════════
   Topic Modal (Create / Edit / Delete)
   ═══════════════════════════════════════════════════════ */
function TopicModal({ mode, topic, pageId, onClose, onCreate, onUpdate, onDelete }) {
  const [name, setName] = useState(topic?.name || '');
  const [description, setDescription] = useState(topic?.description || '');
  const [saving, setSaving] = useState(false);
  const [fieldError, setFieldError] = useState('');

  const handleSave = async () => {
    if (!name.trim()) { setFieldError('Name ist erforderlich.'); return; }
    setSaving(true);
    try {
      if (mode === 'create') await onCreate(name, description, pageId);
      else await onUpdate(topic.id, name, description);
      onClose();
    } catch { /* error handled upstream */ }
    finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Rubrik „${topic.name}" und alle zugehörigen Anwendungen löschen?`)) return;
    setSaving(true);
    try { await onDelete(topic.id); onClose(); }
    catch { /* error handled upstream */ }
    finally { setSaving(false); }
  };

  return (
    <Modal
      title={mode === 'create' ? 'Neue Rubrik erstellen' : 'Rubrik bearbeiten'}
      onClose={onClose}
      size="sm"
      footer={
        <div className="dash-modal-footer">
          {mode === 'edit' && <Button variant="danger" size="sm" onClick={handleDelete} disabled={saving}>Löschen</Button>}
          <div className="dash-modal-footer__right">
            <Button variant="ghost" size="sm" onClick={onClose}>Abbrechen</Button>
            <Button variant="primary" size="sm" onClick={handleSave} loading={saving}>
              {mode === 'create' ? 'Erstellen' : 'Speichern'}
            </Button>
          </div>
        </div>
      }
    >
      {fieldError && <MessageBox type="error" message={fieldError} autoHide={3000} onDismiss={() => setFieldError('')} />}
      <TextInput id="topic-name" label="Name" required value={name} onChange={e => setName(e.target.value)} autoFocus />
      <TextArea id="topic-desc" label="Beschreibung" rows={3} value={description} onChange={e => setDescription(e.target.value)} />
    </Modal>
  );
}

export default Dashboard;

import { useState, useEffect, useRef } from 'react';
import api from '../../utils/api';
import { Button, Modal, FormGroup, MessageBox, TextInput, TextArea, SelectInput } from '../../components/shared';

/* ─── Tiny inline plus icon (no external dep) ─── */
const PlusIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 4a1 1 0 0 1 1 1v6h6a1 1 0 1 1 0 2h-6v6a1 1 0 1 1-2 0v-6H5a1 1 0 1 1 0-2h6V5a1 1 0 0 1 1-1Z" />
  </svg>
);

/* ═══════════════════════════════════════════════════════
   IconUpload
   ─ Click-to-upload area with live preview.
     Uploads immediately on selection; stores the returned URL.
   ═══════════════════════════════════════════════════════ */
const LINK_ICON_PATH = 'M13.828 10.172a4 4 0 0 0-5.656 0l-4 4a4 4 0 1 0 5.656 5.656l1.102-1.101a.75.75 0 0 0-1.06-1.06l-1.102 1.1a2.5 2.5 0 1 1-3.536-3.535l4-4a2.5 2.5 0 0 1 3.536 3.536.75.75 0 0 0 1.06 1.06 4 4 0 0 0 0-5.656Zm-3.656 3.656a4 4 0 0 0 5.656 0l4-4a4 4 0 0 0-5.656-5.656l-1.1 1.1a.75.75 0 1 0 1.06 1.061l1.1-1.1a2.5 2.5 0 0 1 3.536 3.535l-4 4a2.5 2.5 0 0 1-3.536-3.535.75.75 0 0 0-1.06-1.061 4 4 0 0 0 0 5.656Z';

function IconUpload({ value, onChange }) {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const handleFileChange = async e => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError('');
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post('/api/dashboard/icons', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onChange(res.data.url);
    } catch (err) {
      setUploadError(err.response?.data?.message ?? 'Upload fehlgeschlagen.');
    } finally {
      setUploading(false);
      /* Reset so the same file can be re-selected after a clear */
      e.target.value = '';
    }
  };

  return (
    <div className="dash-icon-upload">
      {/* Hidden file input */}
      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      {/* Click area / preview */}
      <Button
        variant="ghost"
        className={`dash-icon-upload__preview ${uploading ? 'dash-icon-upload__preview--loading' : ''}`}
        onClick={() => fileRef.current?.click()}
        title="Icon hochladen"
        disabled={uploading}
      >
        {value ? (
          <img src={value} alt="Icon" className="dash-icon-upload__img" />
        ) : (
          <svg width={32} height={32} viewBox="0 0 24 24" fill="currentColor" className="dash-icon-upload__placeholder">
            <path d={LINK_ICON_PATH} />
          </svg>
        )}
        {uploading && <span className="dash-icon-upload__spinner" />}
        <span className="dash-icon-upload__overlay">
          {uploading ? 'Lädt…' : value ? 'Ändern' : 'Hochladen'}
        </span>
      </Button>

      {/* Action row: filename hint + clear */}
      <div className="dash-icon-upload__row">
        <span className="dash-icon-upload__hint">
          {value ? value.split('/').pop() : 'PNG, JPG, GIF, WebP oder SVG'}
        </span>
        {value && (
          <Button
            variant="ghost"
            size="sm"
            className="dash-icon-upload__clear"
            onClick={() => onChange('')}
            title="Icon entfernen"
          >
            Entfernen
          </Button>
        )}
      </div>

      {uploadError && (
        <p className="dash-icon-upload__error">{uploadError}</p>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   TopicAutocomplete
   ─ Text field that filters existing topics and offers
     an inline "create new" option when no match is found.
   ═══════════════════════════════════════════════════════ */
function TopicAutocomplete({ pages, initialValue, onChange }) {
  const [text, setText] = useState(() => initialValue?.label ?? '');
  const [open, setOpen] = useState(false);
  const [newPageId, setNewPageId] = useState('');
  const containerRef = useRef(null);

  /* Build flat topic list: { id, name, pageId, pageName, label } */
  const allTopics = [];
  (pages || []).forEach(page => {
    (page.topics || []).forEach(topic => {
      allTopics.push({
        id: topic.id,
        name: topic.name,
        pageId: page.id,
        pageName: page.name,
        label: `${page.name} → ${topic.name}`,
      });
    });
  });

  /* Filtered suggestions */
  const q = text.trim().toLowerCase();
  const filtered = q
    ? allTopics.filter(
        t => t.name.toLowerCase().includes(q) || t.pageName.toLowerCase().includes(q)
      )
    : allTopics;

  /* True when the typed text does not match any existing topic */
  const exactMatch = allTopics.find(
    t =>
      t.label.toLowerCase() === text.trim().toLowerCase() ||
      t.name.toLowerCase() === text.trim().toLowerCase()
  );
  const isNew = text.trim() !== '' && !exactMatch;

  /* Close dropdown on outside click */
  useEffect(() => {
    const handler = e => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleInputChange = e => {
    setText(e.target.value);
    setOpen(true);
    onChange(null);
    setNewPageId('');
  };

  const handleSelect = topic => {
    setText(topic.label);
    setOpen(false);
    onChange(topic);
  };

  /* User clicked "Neue Rubrik … erstellen" in the dropdown */
  const handlePickNew = () => {
    setOpen(false);
    /* Propagate immediately; page will be chosen below */
    onChange({ isNew: true, name: text.trim(), pageId: newPageId });
  };

  const handlePageSelect = e => {
    const pid = e.target.value;
    setNewPageId(pid);
    onChange({ isNew: true, name: text.trim(), pageId: pid });
  };

  return (
    <div className="dash-tauto" ref={containerRef}>
      <TextInput
        type="text"
        placeholder="Rubrik suchen oder neu erstellen…"
        value={text}
        onChange={handleInputChange}
        onFocus={() => setOpen(true)}
        autoComplete="off"
      />

      {/* Dropdown */}
      {open && (filtered.length > 0 || isNew) && (
        <ul className="dash-tauto__list">
          {filtered.map(t => (
            <li
              key={t.id}
              className="dash-tauto__item"
              onMouseDown={() => handleSelect(t)}
            >
              <span className="dash-tauto__page">{t.pageName}</span>
              <span className="dash-tauto__sep">›</span>
              <span className="dash-tauto__name">{t.name}</span>
            </li>
          ))}
          {isNew && (
            <li className="dash-tauto__create" onMouseDown={handlePickNew}>
              <PlusIcon />
              <span>Neue Rubrik &bdquo;{text.trim()}&ldquo; erstellen</span>
            </li>
          )}
        </ul>
      )}

      {/* Page selector – shown after user picks "create new" */}
      {isNew && !open && (
        <div className="dash-tauto__newpage">
          <label className="dash-tauto__newpage-label">Neue Rubrik auf Seite hinzufügen:</label>
          <SelectInput value={newPageId} onChange={handlePageSelect}>
            <option value="">— Seite wählen —</option>
            {(pages || []).map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </SelectInput>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   AppModal  (Create / Edit / Delete)
   ═══════════════════════════════════════════════════════ */
function AppModal({ mode, app, pages, onClose, onCreate, onUpdate, onDelete }) {
  const [name, setName] = useState(app?.name ?? '');
  const [description, setDescription] = useState(app?.description ?? '');
  const [url, setUrl] = useState(app?.url ?? '');
  const [icon, setIcon] = useState(app?.icon ?? '');
  const [saving, setSaving] = useState(false);
  const [fieldError, setFieldError] = useState('');

  /* Compute initial topic for edit mode (lazy so it runs once) */
  const [topicSelection, setTopicSelection] = useState(() => {
    if (mode === 'edit' && app?.topic_id) {
      for (const page of pages || []) {
        for (const topic of page.topics || []) {
          if (topic.id === app.topic_id) {
            return {
              id: topic.id,
              name: topic.name,
              pageId: page.id,
              pageName: page.name,
              label: `${page.name} → ${topic.name}`,
            };
          }
        }
      }
    }
    return null;
  });

  const handleSave = async () => {
    if (!name.trim()) { setFieldError('Name ist erforderlich.'); return; }
    if (!url.trim()) { setFieldError('URL ist erforderlich.'); return; }
    if (!topicSelection) { setFieldError('Bitte eine Rubrik auswählen oder neu erstellen.'); return; }

    setSaving(true);
    try {
      let finalTopicId;

      if (topicSelection.isNew) {
        if (!topicSelection.pageId) {
          setFieldError('Für eine neue Rubrik bitte eine Seite auswählen.');
          setSaving(false);
          return;
        }
        /* Create the new topic first */
        const res = await api.post('/api/dashboard/topics', {
          name: topicSelection.name,
          page_id: Number(topicSelection.pageId),
        });
        finalTopicId = res.data.id;
      } else {
        finalTopicId = topicSelection.id;
      }

      const payload = { name, description, url, icon, topic_id: Number(finalTopicId) };
      if (mode === 'create') await onCreate(payload);
      else await onUpdate(app.id, payload);
      onClose();
    } catch (e) {
      setFieldError(e.response?.data?.message ?? 'Ein Fehler ist aufgetreten.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Anwendung „${app.name}" wirklich löschen?`)) return;
    setSaving(true);
    try { await onDelete(app.id); onClose(); }
    catch { /* handled upstream */ }
    finally { setSaving(false); }
  };

  const noTopicsExist = (pages || []).every(p => (p.topics || []).length === 0);

  return (
    <Modal
      title={mode === 'create' ? 'Neue Anwendung erstellen' : 'Anwendung bearbeiten'}
      onClose={onClose}
      size="md"
      footer={
        <div className="dash-modal-footer">
          {mode === 'edit' && (
            <Button variant="danger" size="sm" onClick={handleDelete} disabled={saving}>
              Löschen
            </Button>
          )}
          <div className="dash-modal-footer__right">
            <Button variant="ghost" size="sm" onClick={onClose}>Abbrechen</Button>
            <Button variant="primary" size="sm" onClick={handleSave} loading={saving}>
              {mode === 'create' ? 'Erstellen' : 'Speichern'}
            </Button>
          </div>
        </div>
      }
    >
      {fieldError && (
        <MessageBox type="error" message={fieldError} autoHide={3000} onDismiss={() => setFieldError('')} />
      )}

      <TextInput
        id="app-name"
        label="Name"
        required
        value={name}
        onChange={e => setName(e.target.value)}
        autoFocus
      />

      <TextArea
        id="app-desc"
        label="Beschreibung"
        rows={2}
        value={description}
        onChange={e => setDescription(e.target.value)}
      />

      <TextInput
        id="app-url"
        type="url"
        label="URL / Route"
        required
        placeholder="https://…"
        value={url}
        onChange={e => setUrl(e.target.value)}
      />

      <FormGroup label="Icon" htmlFor="app-icon" hint="Optional – PNG, JPG, GIF, WebP oder SVG">
        <IconUpload value={icon} onChange={setIcon} />
      </FormGroup>

      <FormGroup label="Rubrik" required>
        <TopicAutocomplete
          pages={pages}
          initialValue={topicSelection}
          onChange={setTopicSelection}
        />
      </FormGroup>

      {noTopicsExist && (
        <MessageBox
          type="info"
          message="Noch keine Rubriken vorhanden. Tippe einen Namen ins Rubrik-Feld, um direkt eine neue zu erstellen."
        />
      )}
    </Modal>
  );
}

export default AppModal;

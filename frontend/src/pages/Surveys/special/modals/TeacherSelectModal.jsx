import { useState, useMemo } from 'react';
import { Modal, Button, SearchInput, CheckboxInput } from '../../../../components/shared';
import '../../Surveys.css';

/**
 * TeacherSelectModal – a searchable, multi-select modal for choosing teachers.
 * Follows the same pattern as GroupSelectModal.
 *
 * @param {Array}    teachers       – full list of { uuid, username }
 * @param {Array}    selectedUuids  – currently selected teacher UUIDs
 * @param {Function} onConfirm      – called with the new array of selected UUIDs
 * @param {Function} onClose        – close without saving
 * @param {string}   title          – modal title (default: "Lehrkräfte auswählen")
 */
const TeacherSelectModal = ({
  teachers = [],
  selectedUuids = [],
  onConfirm,
  onClose,
  title = 'Lehrkräfte auswählen',
}) => {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(new Set(selectedUuids));

  const filtered = useMemo(() => {
    const term = search.toLowerCase().trim();
    if (!term) return teachers;
    return teachers.filter((t) => t.username.toLowerCase().includes(term));
  }, [teachers, search]);

  const toggle = (uuid) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(uuid)) next.delete(uuid);
      else next.add(uuid);
      return next;
    });
  };

  const selectAll = () => {
    setSelected(new Set(filtered.map((t) => t.uuid)));
  };

  const deselectAll = () => {
    setSelected(new Set());
  };

  return (
    <Modal
      title={title}
      onClose={onClose}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Abbrechen</Button>
          <Button variant="primary" onClick={() => onConfirm([...selected])}>
            Übernehmen ({selected.size})
          </Button>
        </>
      }
    >
      {/* Search */}
      <div className="group-modal__search">
        <SearchInput
          placeholder="Lehrkraft suchen…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoFocus
        />
      </div>

      {/* Quick actions */}
      <div className="group-modal__actions">
        <Button variant="ghost" size="sm" className="group-modal__link" onClick={selectAll}>
          Alle auswählen
        </Button>
        <Button variant="ghost" size="sm" className="group-modal__link" onClick={deselectAll}>
          Auswahl aufheben
        </Button>
        <span className="group-modal__count">{selected.size} / {teachers.length} gewählt</span>
      </div>

      {/* Teacher list */}
      <div className="group-modal__list">
        {filtered.length === 0 ? (
          <div className="group-modal__empty">Keine Lehrkräfte gefunden</div>
        ) : (
          filtered.map((t) => (
            <label key={t.uuid} className={`group-modal__item ${selected.has(t.uuid) ? 'group-modal__item--selected' : ''}`}>
              <CheckboxInput
                checked={selected.has(t.uuid)}
                onChange={() => toggle(t.uuid)}
              />
              <span className="group-modal__item-name">{t.username}</span>
            </label>
          ))
        )}
      </div>
    </Modal>
  );
};

export default TeacherSelectModal;

import { useState, useMemo } from 'react';
import { Modal, Button, SearchInput, CheckboxInput } from '../../../components/shared';
import '../Surveys.css';

/**
 * GroupSelectModal – a searchable, multi-select modal for choosing groups.
 *
 * @param {Array}    groups         – full list of { id, name }
 * @param {Array}    selectedIds    – currently selected group IDs
 * @param {Function} onConfirm      – called with the new array of selected IDs
 * @param {Function} onClose        – close without saving
 * @param {string}   title          – modal title (default: "Gruppen auswählen")
 */
const GroupSelectModal = ({
  groups = [],
  selectedIds = [],
  onConfirm,
  onClose,
  title = 'Gruppen auswählen',
}) => {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(new Set(selectedIds));

  const filtered = useMemo(() => {
    const term = search.toLowerCase().trim();
    if (!term) return groups;
    return groups.filter((g) => g.name.toLowerCase().includes(term));
  }, [groups, search]);

  const toggle = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    setSelected(new Set(filtered.map((g) => g.id)));
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
          placeholder="Gruppe suchen…"
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
        <span className="group-modal__count">{selected.size} / {groups.length} gewählt</span>
      </div>

      {/* Group list */}
      <div className="group-modal__list">
        {filtered.length === 0 ? (
          <div className="group-modal__empty">Keine Gruppen gefunden</div>
        ) : (
          filtered.map((g) => (
            <label key={g.id} className={`group-modal__item ${selected.has(g.id) ? 'group-modal__item--selected' : ''}`}>
              <CheckboxInput
                checked={selected.has(g.id)}
                onChange={() => toggle(g.id)}
              />
              <span className="group-modal__item-name">{g.name}</span>
            </label>
          ))
        )}
      </div>
    </Modal>
  );
};

export default GroupSelectModal;

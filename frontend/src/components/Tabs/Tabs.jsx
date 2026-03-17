import { useRef, useState, useEffect } from 'react';
import { Button } from '../shared';
import './Tabs.css';

/* ── SVG Icon (inline to avoid extra deps) ── */
const Icon = ({ d, size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d={d} />
  </svg>
);

const ICONS = {
  plus: 'M12 4a1 1 0 0 1 1 1v6h6a1 1 0 1 1 0 2h-6v6a1 1 0 1 1-2 0v-6H5a1 1 0 1 1 0-2h6V5a1 1 0 0 1 1-1Z',
  edit: 'M16.293 2.293a1 1 0 0 1 1.414 0l4 4a1 1 0 0 1 0 1.414l-13 13A1 1 0 0 1 8 21H4a1 1 0 0 1-1-1v-4a1 1 0 0 1 .293-.707l13-13ZM5 16.414V19h2.586l12-12L17.414 4.586l-12 12Z',
  drag: 'M8 4a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm8 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM8 10.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm8 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM8 17a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm8 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Z',
};

/* ── Internal drag-sort hook ── */
function useDragSort(items, onReorder) {
  const dragItem = useRef(null);
  const dragOverItem = useRef(null);

  const onDragStart = (index) => { dragItem.current = index; };
  const onDragEnter = (index) => { dragOverItem.current = index; };

  const onDragEnd = () => {
    if (
      dragItem.current === null ||
      dragOverItem.current === null ||
      dragItem.current === dragOverItem.current
    ) {
      dragItem.current = null;
      dragOverItem.current = null;
      return;
    }
    const newOrder = [...items];
    const [removed] = newOrder.splice(dragItem.current, 1);
    newOrder.splice(dragOverItem.current, 0, removed);
    dragItem.current = null;
    dragOverItem.current = null;
    onReorder(newOrder);
  };

  return { onDragStart, onDragEnter, onDragEnd };
}

/**
 * Shared Tabs component – use in place of any custom tab bar.
 *
 * Props:
 *   tabs        [{ id, label }]       Required. Tab definitions.
 *   activeTab   string                Required. Currently active tab id.
 *   onChange    (id) => void          Required. Called on tab click.
 *   stretch     bool = false          When true each tab takes equal width (flex: 1).
 *   sticky      bool = false          Makes the tab bar sticky, positioned below the
 *                                     header Card (mirrors the Card header variant).
 *   admin       bool = false          Enables admin controls (edit/add buttons, drag).
 *   dragMode    bool = false          When true (and admin) tabs are draggable.
 *   onReorder   (tabs) => void        Called with reordered tab array after drag.
 *   onAdd       () => void            Renders a + button at the end (admin only).
 *   onEdit      (tab) => void         Renders a pencil button per tab on hover (admin only).
 */
export default function Tabs({
  tabs = [],
  activeTab,
  onChange,
  stretch = false,
  sticky = false,
  admin = false,
  dragMode = false,
  onReorder,
  onAdd,
  onEdit,
}) {
  const draggable = admin && dragMode && typeof onReorder === 'function';
  const { onDragStart, onDragEnter, onDragEnd } = useDragSort(tabs, onReorder ?? (() => {}));
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  /* Close dropdown when clicking outside */
  useEffect(() => {
    if (!menuOpen) return;
    const handleOutsideClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [menuOpen]);

  const activeTabLabel = tabs.find((t) => t.id === activeTab)?.label ?? '';

  const handleTabClick = (id) => {
    if (typeof onChange === 'function') onChange(id);
    setMenuOpen(false);
  };

  /* ── Shared inner tab list (used by both variants) ── */
  const tabListNode = (
    <>
      {/* Mobile hamburger button */}
      <button
        className="tabs__hamburger"
        aria-expanded={menuOpen}
        aria-haspopup="listbox"
        onClick={() => setMenuOpen((o) => !o)}
      >
        <span className="tabs__hamburger-label">{activeTabLabel}</span>
        <span className={`tabs__hamburger-icon${menuOpen ? ' tabs__hamburger-icon--open' : ''}`} aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z" />
          </svg>
        </span>
      </button>

      {/* Tab list (desktop horizontal / mobile dropdown) */}
      <div className={`tabs__list${menuOpen ? ' tabs__list--open' : ''}`}>
        {tabs.map((tab, idx) => (
          <div
            key={tab.id}
            className={[
              'tabs__tab',
              tab.id === activeTab ? 'tabs__tab--active' : '',
              stretch ? 'tabs__tab--stretch' : '',
            ].filter(Boolean).join(' ')}
            role="tab"
            aria-selected={tab.id === activeTab}
            tabIndex={0}
            onClick={() => handleTabClick(tab.id)}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && handleTabClick(tab.id)}
            draggable={draggable}
            onDragStart={draggable ? () => onDragStart(idx) : undefined}
            onDragEnter={draggable ? () => onDragEnter(idx) : undefined}
            onDragEnd={draggable ? onDragEnd : undefined}
            onDragOver={draggable ? (e) => e.preventDefault() : undefined}
          >
            {draggable && (
              <span className="tabs__drag-handle">
                <Icon d={ICONS.drag} size={14} />
              </span>
            )}
            <span className="tabs__label">{tab.label}</span>
            {admin && typeof onEdit === 'function' && (
              <Button
                variant="ghost"
                className="tabs__edit-btn"
                onClick={(e) => { e.stopPropagation(); onEdit(tab); }}
                title="Bearbeiten"
                aria-label={`Tab "${tab.label}" bearbeiten`}
              >
                <Icon d={ICONS.edit} size={14} />
              </Button>
            )}
          </div>
        ))}
        {admin && typeof onAdd === 'function' && (
          <Button variant="secondary" size="sm" onClick={onAdd} className="tabs__add-btn" title="Neuen Tab hinzufügen" aria-label="Neuen Tab hinzufügen">
            <Icon d={ICONS.plus} size={16} />
          </Button>
        )}
      </div>
    </>
  );

  /* ── Sticky header variant (mirrors Card variant="header") ── */
  if (sticky) {
    return (
      <div className="tabs tabs--sticky" ref={menuRef}>
        <div className="tabs__sticky-content">
          {tabListNode}
        </div>
        <div className="tabs-sticky-spacer" />
      </div>
    );
  }

  /* ── Default variant ── */
  return (
    <div className="tabs" ref={menuRef}>
      {tabListNode}
    </div>
  );
}

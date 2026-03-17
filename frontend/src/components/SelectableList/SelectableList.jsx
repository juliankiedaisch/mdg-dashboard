import './SelectableList.css';

/**
 * SelectableList – Reusable selectable list component
 *
 * Used for module lists, profile lists, and user lists throughout
 * the application. Supports active item highlighting, badges,
 * state indicators, and configurable font size.
 *
 * @param {Array}    items        – [{ key, label, badge, state }]
 * @param {string}   activeKey    – Key of the currently active item
 * @param {function} onSelect     – Callback when an item is clicked (receives key)
 * @param {string}   emptyMessage – Message when list is empty
 * @param {string}   ariaLabel    – Accessible label for the list
 * @param {'sm'|'md'|'lg'} size   – Font size variant
 * @param {string}   className    – Additional CSS classes
 */
function SelectableList({
  items = [],
  activeKey,
  onSelect,
  emptyMessage = 'Keine Einträge',
  ariaLabel = 'Liste',
  size = 'sm',
  className = '',
}) {
  if (items.length === 0) {
    return <p className="shared-selectable-list__empty">{emptyMessage}</p>;
  }

  const listClasses = [
    'shared-selectable-list',
    `shared-selectable-list--${size}`,
    className,
  ].filter(Boolean).join(' ');

  return (
    <ul className={listClasses} role="listbox" aria-label={ariaLabel}>
      {items.map(item => {
        const isActive = item.key === activeKey;
        const itemClasses = [
          'shared-selectable-list__item',
          isActive ? 'is-active' : '',
          item.state === 'full' ? 'is-full' : '',
          item.state === 'partial' ? 'is-partial' : '',
        ].filter(Boolean).join(' ');

        return (
          <li
            key={item.key}
            className={itemClasses}
            role="option"
            aria-selected={isActive}
            tabIndex={0}
            onClick={() => onSelect?.(item.key)}
            onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onSelect?.(item.key)}
          >
            <span className="shared-selectable-list__label">{item.label}</span>
            {item.badge != null && (
              <span className="shared-selectable-list__badge">{item.badge}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default SelectableList;

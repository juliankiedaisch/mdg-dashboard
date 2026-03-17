import { forwardRef } from 'react';
import './SearchInput.css';

/**
 * SearchInput – Einheitliches Suchfeld mit optionalem Icon
 *
 * @param {string}  id          – HTML id
 * @param {string}  value       – Aktueller Wert
 * @param {function} onChange   – Change-Handler
 * @param {string}  placeholder – Platzhaltertext
 * @param {'sm'|'md'|'lg'} size – Größe
 * @param {boolean} fullWidth   – 100 % Breite
 * @param {boolean} disabled    – Deaktiviert
 * @param {string}  className   – Zusätzliche CSS-Klassen
 * @param {string}  ariaLabel   – Zugänglicher Name
 */
const SearchInput = forwardRef(function SearchInput(
  {
    id,
    value,
    onChange,
    placeholder = 'Suchen…',
    size = 'md',
    fullWidth = true,
    disabled = false,
    className = '',
    ariaLabel,
    ...props
  },
  ref
) {
  const wrapperClasses = [
    'shared-search',
    `shared-search--${size}`,
    fullWidth ? 'shared-search--full' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={wrapperClasses}>
      <svg
        className="shared-search__icon"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        ref={ref}
        id={id}
        type="search"
        className="shared-search__input"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        aria-label={ariaLabel || placeholder}
        {...props}
      />
    </div>
  );
});

export default SearchInput;

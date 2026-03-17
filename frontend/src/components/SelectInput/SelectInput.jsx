import { forwardRef } from 'react';
import '../shared/shared.css';
import './SelectInput.css';

/**
 * SelectInput – Einheitliches Auswahlfeld (Dropdown)
 *
 * @param {string}  id          – HTML id
 * @param {string}  label       – Optionales Label
 * @param {string}  value       – Aktueller Wert
 * @param {function} onChange   – Change-Handler
 * @param {string}  error       – Fehlermeldung
 * @param {string}  helperText  – Hilfetext
 * @param {'sm'|'md'|'lg'} size – Größe
 * @param {boolean} fullWidth   – 100% Breite
 * @param {boolean} disabled    – Deaktiviert
 * @param {boolean} required    – Pflichtfeld
 * @param {string}  className   – Zusätzliche CSS-Klassen
 * @param {React.ReactNode} children – <option> Elemente
 */
const SelectInput = forwardRef(function SelectInput(
  {
    id,
    label,
    value,
    onChange,
    error,
    helperText,
    size = 'md',
    fullWidth = true,
    disabled = false,
    required = false,
    className = '',
    children,
    ...props
  },
  ref
) {
  const selectClasses = [
    'shared-input',
    'shared-input--select',
    `shared-input--${size}`,
    fullWidth ? 'shared-input--full' : '',
    error ? 'shared-input--error' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const select = (
    <select
      ref={ref}
      id={id}
      className={selectClasses}
      value={value}
      onChange={onChange}
      disabled={disabled}
      required={required}
      {...props}
    >
      {children}
    </select>
  );

  if (!label && !error && !helperText) return select;

  return (
    <div className="shared-form-group">
      {label && (
        <label className="shared-form-group__label" htmlFor={id}>
          {label}
          {required && <span className="shared-form-group__required"> *</span>}
        </label>
      )}
      {select}
      {error && <span className="shared-input__error">{error}</span>}
      {!error && helperText && <span className="shared-input__helper">{helperText}</span>}
    </div>
  );
});

export default SelectInput;

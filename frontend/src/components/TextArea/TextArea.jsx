import { forwardRef } from 'react';
import '../shared/shared.css';
import './TextArea.css';

/**
 * TextArea – Einheitliches mehrzeiliges Textfeld
 *
 * @param {string}  id          – HTML id
 * @param {string}  label       – Optionales Label
 * @param {string}  value       – Aktueller Wert
 * @param {function} onChange   – Change-Handler
 * @param {string}  placeholder – Platzhaltertext
 * @param {string}  error       – Fehlermeldung
 * @param {string}  helperText  – Hilfetext
 * @param {number}  rows        – Zeilenanzahl (default: 3)
 * @param {'sm'|'md'|'lg'} size – Größe
 * @param {boolean} fullWidth   – 100% Breite
 * @param {boolean} disabled    – Deaktiviert
 * @param {boolean} required    – Pflichtfeld
 * @param {string}  className   – Zusätzliche CSS-Klassen
 */
const TextArea = forwardRef(function TextArea(
  {
    id,
    label,
    value,
    onChange,
    placeholder,
    error,
    helperText,
    rows = 3,
    size = 'md',
    fullWidth = true,
    disabled = false,
    required = false,
    className = '',
    ...props
  },
  ref
) {
  const textareaClasses = [
    'shared-input',
    'shared-input--textarea',
    `shared-input--${size}`,
    fullWidth ? 'shared-input--full' : '',
    error ? 'shared-input--error' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const textarea = (
    <textarea
      ref={ref}
      id={id}
      className={textareaClasses}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      disabled={disabled}
      required={required}
      rows={rows}
      {...props}
    />
  );

  if (!label && !error && !helperText) return textarea;

  return (
    <div className="shared-form-group">
      {label && (
        <label className="shared-form-group__label" htmlFor={id}>
          {label}
          {required && <span className="shared-form-group__required"> *</span>}
        </label>
      )}
      {textarea}
      {error && <span className="shared-input__error">{error}</span>}
      {!error && helperText && <span className="shared-input__helper">{helperText}</span>}
    </div>
  );
});

export default TextArea;

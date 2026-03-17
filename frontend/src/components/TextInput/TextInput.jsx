import { forwardRef } from 'react';
import '../shared/shared.css';
import './TextInput.css';

/**
 * TextInput – Einheitliches Text-Eingabefeld
 *
 * @param {string}  id          – HTML id
 * @param {string}  type        – input type (text, email, password, url, number, date, time, search, color)
 * @param {string}  label       – Optionales Label (wird über dem Input gerendert)
 * @param {string}  value       – Aktueller Wert
 * @param {function} onChange   – Change-Handler
 * @param {string}  placeholder – Platzhaltertext
 * @param {string}  error       – Fehlermeldung (unter dem Input)
 * @param {string}  helperText  – Hilfetext (unter dem Input)
 * @param {'sm'|'md'|'lg'} size – Größe
 * @param {boolean} fullWidth   – 100% Breite
 * @param {boolean} disabled    – Deaktiviert
 * @param {boolean} required    – Pflichtfeld
 * @param {boolean} autoFocus   – Autofokus
 * @param {string}  className   – Zusätzliche CSS-Klassen
 */
const TextInput = forwardRef(function TextInput(
  {
    id,
    type = 'text',
    label,
    value,
    onChange,
    placeholder,
    error,
    helperText,
    size = 'md',
    fullWidth = true,
    disabled = false,
    required = false,
    autoFocus = false,
    className = '',
    ...props
  },
  ref
) {
  const inputClasses = [
    'shared-input',
    `shared-input--${size}`,
    fullWidth ? 'shared-input--full' : '',
    error ? 'shared-input--error' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const input = (
    <input
      ref={ref}
      id={id}
      type={type}
      className={inputClasses}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      disabled={disabled}
      required={required}
      autoFocus={autoFocus}
      {...props}
    />
  );

  if (!label && !error && !helperText) return input;

  return (
    <div className="shared-form-group">
      {label && (
        <label className="shared-form-group__label" htmlFor={id}>
          {label}
          {required && <span className="shared-form-group__required"> *</span>}
        </label>
      )}
      {input}
      {error && <span className="shared-input__error">{error}</span>}
      {!error && helperText && <span className="shared-input__helper">{helperText}</span>}
    </div>
  );
});

export default TextInput;

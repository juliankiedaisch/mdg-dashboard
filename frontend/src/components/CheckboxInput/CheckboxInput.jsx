import { forwardRef } from 'react';
import './CheckboxInput.css';

/**
 * CheckboxInput – Einheitliche Checkbox
 *
 * @param {string}  id          – HTML id
 * @param {string|React.ReactNode} label – Label neben der Checkbox
 * @param {boolean} checked     – Checked-Zustand
 * @param {function} onChange   – Change-Handler
 * @param {boolean} indeterminate – Indeterminate-Zustand (für Select-All)
 * @param {boolean} disabled    – Deaktiviert
 * @param {string}  className   – Zusätzliche CSS-Klassen für den Wrapper
 */
const CheckboxInput = forwardRef(function CheckboxInput(
  {
    id,
    label,
    checked = false,
    onChange,
    indeterminate = false,
    disabled = false,
    className = '',
    ...props
  },
  ref
) {
  const setRef = (el) => {
    if (el) el.indeterminate = indeterminate;
    if (typeof ref === 'function') ref(el);
    else if (ref) ref.current = el;
  };

  return (
    <label className={`shared-checkbox ${disabled ? 'shared-checkbox--disabled' : ''} ${className}`}>
      <input
        ref={setRef}
        id={id}
        type="checkbox"
        className="shared-checkbox__input"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        {...props}
      />
      {label && <span className="shared-checkbox__label">{label}</span>}
    </label>
  );
});

export default CheckboxInput;

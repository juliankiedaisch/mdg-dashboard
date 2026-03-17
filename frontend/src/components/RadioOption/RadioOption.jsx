import './RadioOption.css';

/**
 * RadioOption – Einzelne Radio-Option (wird intern von RadioGroup verwendet,
 *  kann aber auch standalone eingesetzt werden)
 *
 * @param {string}  name      – Radio-Gruppenname
 * @param {*}       value     – Wert dieser Option
 * @param {boolean} checked   – Ob diese Option ausgewählt ist
 * @param {function} onChange – Change-Handler
 * @param {string|React.ReactNode} label – Label-Text
 * @param {boolean} disabled  – Deaktiviert
 * @param {string}  className – Zusätzliche CSS-Klassen
 */
function RadioOption({
  name,
  value,
  checked = false,
  onChange,
  label,
  disabled = false,
  className = '',
  ...props
}) {
  const handleClick = () => {
    if (!disabled && onChange) {
      onChange(value);
    }
  };

  return (
    <label
      className={`shared-radio-option ${checked ? 'shared-radio-option--selected' : ''} ${disabled ? 'shared-radio-option--disabled' : ''} ${className}`}
      onClick={handleClick}
    >
      <input
        type="radio"
        className="shared-radio-option__input"
        name={name}
        value={value}
        checked={checked}
        onChange={() => onChange && onChange(value)}
        disabled={disabled}
        {...props}
      />
      {label && <span className="shared-radio-option__label">{label}</span>}
    </label>
  );
}

export default RadioOption;

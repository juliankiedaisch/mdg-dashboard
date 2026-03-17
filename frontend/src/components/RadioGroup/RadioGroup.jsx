import RadioOption from '../RadioOption/RadioOption';
import './RadioGroup.css';

/**
 * RadioGroup – Gruppe von Radio-Buttons
 *
 * @param {Array}   options   – Array von { value, label } Objekten
 * @param {*}       value     – Aktuell ausgewählter Wert
 * @param {function} onChange – Callback mit dem neuen Wert: onChange(value)
 * @param {string}  name      – HTML name-Attribut für die Radiogruppe
 * @param {string}  label     – Optionales Gruppen-Label
 * @param {boolean} disabled  – Alle Optionen deaktivieren
 * @param {string}  layout    – 'vertical' (default) oder 'horizontal'
 * @param {string}  className – Zusätzliche CSS-Klassen
 */
function RadioGroup({
  options = [],
  value,
  onChange,
  name,
  label,
  disabled = false,
  layout = 'vertical',
  className = '',
  ...props
}) {
  return (
    <div
      className={`shared-radio-group shared-radio-group--${layout} ${className}`}
      role="radiogroup"
      aria-label={label}
      {...props}
    >
      {label && <span className="shared-radio-group__label">{label}</span>}
      {options.map((opt) => (
        <RadioOption
          key={opt.value}
          name={name}
          value={opt.value}
          checked={value === opt.value}
          onChange={onChange}
          label={opt.label}
          disabled={disabled || opt.disabled}
        />
      ))}
    </div>
  );
}

export default RadioGroup;

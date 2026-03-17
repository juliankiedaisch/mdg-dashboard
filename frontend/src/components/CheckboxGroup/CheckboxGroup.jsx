import CheckboxInput from '../CheckboxInput/CheckboxInput';
import './CheckboxGroup.css';

/**
 * CheckboxGroup – Gruppe von Checkboxen
 *
 * @param {Array}   options        – Array von { value, label } Objekten
 * @param {Array}   selectedValues – Array der ausgewählten Werte
 * @param {function} onChange      – Callback mit neuem Array: onChange(newValues)
 * @param {string}  label          – Optionales Gruppen-Label
 * @param {boolean} disabled       – Alle Checkboxen deaktivieren
 * @param {string}  layout         – 'vertical' (default) oder 'horizontal'
 * @param {string}  className      – Zusätzliche CSS-Klassen
 */
function CheckboxGroup({
  options = [],
  selectedValues = [],
  onChange,
  label,
  disabled = false,
  layout = 'vertical',
  className = '',
  ...props
}) {
  const handleToggle = (value) => {
    if (!onChange) return;
    const next = selectedValues.includes(value)
      ? selectedValues.filter((v) => v !== value)
      : [...selectedValues, value];
    onChange(next);
  };

  return (
    <div
      className={`shared-checkbox-group shared-checkbox-group--${layout} ${className}`}
      role="group"
      aria-label={label}
      {...props}
    >
      {label && <span className="shared-checkbox-group__label">{label}</span>}
      {options.map((opt) => (
        <CheckboxInput
          key={opt.value}
          checked={selectedValues.includes(opt.value)}
          onChange={() => handleToggle(opt.value)}
          label={opt.label}
          disabled={disabled || opt.disabled}
        />
      ))}
    </div>
  );
}

export default CheckboxGroup;

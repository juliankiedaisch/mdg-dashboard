import '../shared/shared.css';
import './FormGroup.css';

/**
 * FormGroup - Einheitliche Formulargruppe mit Label und Input
 * 
 * @param {string} label - Feldbezeichnung
 * @param {string} htmlFor - ID des Eingabefeldes (für Label)
 * @param {boolean} required - Pflichtfeld-Markierung
 * @param {string} hint - Optionaler Hinweistext
 * @param {React.ReactNode} children - Eingabefeld(er)
 * @param {string} className - Zusätzliche CSS-Klassen
 */
function FormGroup({ label, htmlFor, required = false, hint, children, className = '' }) {
  return (
    <div className={`shared-form-group ${className}`}>
      {label && (
        <label className="shared-form-group__label" htmlFor={htmlFor}>
          {label}{required && <span className="shared-form-group__required"> *</span>}
        </label>
      )}
      {hint && <span className="shared-form-group__hint">{hint}</span>}
      {children}
    </div>
  );
}

export default FormGroup;

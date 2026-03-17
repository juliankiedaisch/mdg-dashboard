import '../shared/shared.css';
import './Spinner.css';

/**
 * Spinner - Einheitlicher Lade-Indikator
 * 
 * @param {'sm'|'md'|'lg'} size - Spinner-Größe
 * @param {string} text - Optionaler Ladetext
 * @param {boolean} fullPage - Zentriert auf kompletter Seite
 * @param {string} className - Zusätzliche CSS-Klassen
 */
function Spinner({ size = 'md', text, fullPage = false, className = '' }) {
  const content = (
    <div className={`shared-spinner-wrapper ${className}`}>
      <div className={`shared-spinner shared-spinner--${size}`} />
      {text && <span className="shared-spinner__text">{text}</span>}
    </div>
  );

  if (fullPage) {
    return <div className="shared-spinner-fullpage">{content}</div>;
  }

  return content;
}

export default Spinner;

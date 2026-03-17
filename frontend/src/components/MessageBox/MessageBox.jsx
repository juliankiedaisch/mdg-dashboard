import { useEffect, useState } from 'react';
import '../shared/shared.css';
import './MessageBox.css';

/**
 * MessageBox - Einheitliche Erfolgs-/Fehler-/Info-Meldung
 * 
 * @param {string} message - Nachrichtentext
 * @param {'success'|'error'|'warning'|'info'} type - Nachrichtentyp
 * @param {number} autoHide - Automatisch ausblenden nach X ms (0 = nie)
 * @param {function} onDismiss - Callback beim Schließen
 * @param {React.ReactNode} children - Zusätzlicher Inhalt (z.B. Links)
 * @param {string} className - Zusätzliche CSS-Klassen
 */
function MessageBox({ message, type = 'info', autoHide = 0, onDismiss, children, className = '' }) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (autoHide > 0) {
      const timer = setTimeout(() => {
        setVisible(false);
        onDismiss?.();
      }, autoHide);
      return () => clearTimeout(timer);
    }
  }, [autoHide, onDismiss]);

  if (!visible || !message) return null;

  return (
    <div className={`shared-message shared-message--${type} ${className}`}>
      <span className="shared-message__text">{message}</span>
      {children}
      {onDismiss && (
        <button 
          className="shared-message__dismiss" 
          onClick={() => { setVisible(false); onDismiss(); }}
          aria-label="Schließen"
        >
          ×
        </button>
      )}
    </div>
  );
}

export default MessageBox;

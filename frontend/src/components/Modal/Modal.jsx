import '../shared/shared.css';
import './Modal.css';

/**
 * Modal - Einheitlicher Modal-Dialog
 * 
 * @param {string} title - Modal-Titel
 * @param {React.ReactNode} children - Modal-Inhalt (Body)
 * @param {React.ReactNode} footer - Modal-Footer-Inhalt (Buttons)
 * @param {function} onClose - Schließen-Handler
 * @param {'sm'|'md'|'lg'|'xl'} size - Modal-Größe
 * @param {string} className - Zusätzliche CSS-Klassen
 * @param {boolean} closeOnOverlay - Schließen beim Klick auf Overlay
 */
function Modal({ 
  title, 
  children, 
  footer, 
  onClose, 
  size = 'md', 
  className = '',
  closeOnOverlay = true 
}) {
  const handleOverlayClick = (e) => {
    if (closeOnOverlay && e.target === e.currentTarget) {
      onClose?.();
    }
  };

  return (
    <div className="shared-modal-overlay" onClick={handleOverlayClick}>
      <div className={`shared-modal shared-modal--${size} ${className}`} onClick={(e) => e.stopPropagation()}>
        <div className="shared-modal__header">
          <h2 className="shared-modal__title">{title}</h2>
          <button className="shared-modal__close" onClick={onClose} aria-label="Schließen">
            ×
          </button>
        </div>
        <div className="shared-modal__body">
          {children}
        </div>
        {footer && (
          <div className="shared-modal__footer">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

export default Modal;

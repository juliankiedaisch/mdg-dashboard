import '../shared/shared.css';
import './Button.css';

/**
 * Button - Einheitlicher Button
 * 
 * @param {React.ReactNode} children - Button-Text/Inhalt
 * @param {'primary'|'secondary'|'danger'|'success'|'ghost'} variant - Button-Variante
 * @param {'sm'|'md'|'lg'} size - Button-Größe
 * @param {boolean} disabled - Deaktiviert
 * @param {boolean} loading - Ladezustand anzeigen
 * @param {string} className - Zusätzliche CSS-Klassen
 * @param {string} type - button | submit | reset
 * @param {function} onClick - Click-Handler
 */
function Button({ 
  children, 
  variant = 'primary', 
  size = 'md', 
  disabled = false, 
  loading = false, 
  className = '', 
  type = 'button',
  onClick,
  ...props 
}) {
  const classes = [
    'shared-btn',
    `shared-btn--${variant}`,
    `shared-btn--${size}`,
    loading ? 'shared-btn--loading' : '',
    className
  ].filter(Boolean).join(' ');

  return (
    <button 
      className={classes} 
      disabled={disabled || loading} 
      type={type}
      onClick={onClick}
      {...props}
    >
      {loading && <span className="shared-btn__spinner" />}
      <span className={loading ? 'shared-btn__text--loading' : ''}>{children}</span>
    </button>
  );
}

export default Button;

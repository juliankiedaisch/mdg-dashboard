import './StatCard.css';

/**
 * StatCard - Statistik-Karte für Übersichten
 * 
 * @param {string|number} value - Zahlenwert
 * @param {string} label - Beschriftung
 * @param {'default'|'success'|'danger'|'info'|'warning'} variant - Farbvariante
 * @param {'normal'|'small'} size - Größenvariante
 * @param {string} className - Zusätzliche CSS-Klassen
 * @param {function} onClick - Click-Handler
 * @param {boolean} darkbackground - Ob die Karte auf dunklem Hintergrund verwendet wird
 */
function StatCard({ value, label, variant = 'default', size = 'normal', className = '', onClick, hoverable = false, darkbackground = false }) {
  return (
    <div 
      className={`shared-stat-card shared-stat-card-${size || 'normal'} ${hoverable ? 'shared-stat-card--hoverable' : ''} ${darkbackground ? 'shared-stat-card-bg-page' : ''} ${onClick ? 'shared-stat-card--clickable' : ''} ${className}`}
      onClick={onClick}
    >
      <div className={`shared-stat-card__value shared-stat-card__value--${variant}`}>
        {value}
      </div>
      <div className="shared-stat-card__label">{label}</div>
    </div>
  );
}

export default StatCard;

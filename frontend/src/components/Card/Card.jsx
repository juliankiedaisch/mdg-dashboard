import { useRef, useEffect } from 'react';
import './Card.css';

/**
 * Card - Wiederverwendbare Karte für Inhaltsblöcke
 * 
 * @param {string} title - Optionaler Kartentitel
 * @param {React.ReactNode} children - Karteninhalt
 * @param {string} className - Zusätzliche CSS-Klassen
 * @param {boolean} hoverable - Hover-Effekt aktivieren
 * @param {function} onClick - Click-Handler
 * @param {string} variant - 'default' | 'section' (grauer Hintergrund) | 'header' (sticky Seitenkopf)
 */
function Card({ title, children, className = '', hoverable = false, onClick, variant = 'default' }) {
  const headerRef = useRef(null);

  /* Track header card height so sticky Tabs know where to anchor */
  useEffect(() => {
    if (variant !== 'header' || !headerRef.current) return;

    const update = () => {
      const h = headerRef.current?.getBoundingClientRect().height ?? 0;
      document.documentElement.style.setProperty('--page-header-height', `${h}px`);
    };

    update();
    const ro = new ResizeObserver(update);
    ro.observe(headerRef.current);
    return () => ro.disconnect();
  }, [variant]);

  const classes = [
    'shared-card',
    variant === 'section' ? 'shared-card--section' : '',
    variant === 'header' ? 'shared-card--header' : '',
    hoverable ? 'shared-card--hoverable' : '',
    onClick ? 'shared-card--clickable' : '',
    className
  ].filter(Boolean).join(' ');

  if (variant === 'header') {
    return (
      <>
      <div className={classes} onClick={onClick} ref={headerRef}>
        <div className="shared-card__header_content">
        {title && <h1 className="shared-card__title-header">{title}</h1>}
        {children && <div className="shared-card__header-actions">{children}</div>}
        </div>
        <div className="shared-card-header-spacer">&nbsp;</div>
      </div>
      
      </>
    );
  }

  return (
    <div className={classes} onClick={onClick}>
      {title && <h2 className="shared-card__title">{title}</h2>}
      {children}
    </div>
  );
}

export default Card;

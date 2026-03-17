import './PageContainer.css';

/**
 * PageContainer - Einheitlicher Seiten-Container
 * Verwendung: Wrapper für jede Seite (Module) im Dashboard
 * Titel werden nicht mehr von PageContainer gerendert – jede Seite
 * muss ihren eigenen Header via <Card variant="header"> implementieren.
 * 
 * @param {React.ReactNode} children - Seiteninhalt
 * @param {string} className - Zusätzliche CSS-Klassen
 */
function PageContainer({ children, className = '' }) {
  return (
    <div className={`page-container ${className}`}>
      <div className="page-content">
        {children}
      </div>
    </div>
  );
}

export default PageContainer;

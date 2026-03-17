// Assistant Module - Source References Component
import './SourceReferences.css';

function SourceReferences({ sources }) {
  if (!sources || sources.length === 0) return null;

  const renderBreadcrumb = (src) => {
    const parts = [];
    if (src.book_name) parts.push(src.book_name);
    if (src.chapter_name) parts.push(src.chapter_name);
    if (src.title && src.title !== src.book_name) parts.push(src.title);
    if (parts.length === 0 && src.source) parts.push(src.source, src.title || '');
    return parts.filter(Boolean).join(' › ');
  };

  return (
    <div className="source-references">
      <div className="source-references__label">
        📚 Verwendete Quellen
      </div>
      {sources.map((src, i) => (
        <div key={i} className="source-references__item">
          {src.url ? (
            <a
              href={src.url}
              target="_blank"
              rel="noopener noreferrer"
              className="source-references__link"
            >
              <span className="source-references__icon">📄</span>
              <span className="source-references__breadcrumb">{renderBreadcrumb(src)}</span>
            </a>
          ) : (
            <span className="source-references__text">
              <span className="source-references__icon">📄</span>
              <span className="source-references__breadcrumb">{renderBreadcrumb(src)}</span>
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

export default SourceReferences;

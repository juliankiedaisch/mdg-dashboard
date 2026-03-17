// Assistant Module - Message Bubble Component
import './MessageBubble.css';

// ── Inline Markdown Parser ────────────────────────────────────────
// Handles **bold**, [Quelle: ...] citations, bullet lists (* / -),
// and plain paragraphs. Works incrementally so streaming looks good.

function parseInline(text, keyPrefix) {
  // Tokenise: **bold**, links and [Quelle: ...]
  const tokens = [];
  const re = /\*\*(.+?)\*\*|\[Quelle:\s*([^\]]+)\]|\[([^\]]+)\]\(([^)]+)\)/g;

  let last = 0;
  let m;

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      tokens.push({ t: 'text', v: text.slice(last, m.index) });
    }

    if (m[1] !== undefined) {
      tokens.push({ t: 'bold', v: m[1] });
    } 
    else if (m[2] !== undefined) {
      tokens.push({ t: 'source', v: m[2] });
    } 
    else if (m[3] !== undefined) {
      tokens.push({ t: 'link', name: m[3], url: m[4] });
    }

    last = re.lastIndex;
  }

  if (last < text.length) {
    tokens.push({ t: 'text', v: text.slice(last) });
  }

  return tokens.map((tok, i) => {
    const k = `${keyPrefix}-${i}`;

    if (tok.t === 'bold')
      return <strong key={k}>{tok.v}</strong>;

    if (tok.t === 'source')
      return (
        <span key={k} className="message-bubble__inline-source">
          [Quelle: {tok.v}]
        </span>
      );

    if (tok.t === 'link')
      return (
        <a key={k} href={tok.url} target="_blank" rel="noopener noreferrer">
          {tok.name}
        </a>
      );

    return <span key={k}>{tok.v}</span>;
  });
}

function renderMarkdown(text) {
  if (!text) return null;
  const lines = text.split('\n');
  const out = [];
  let bullets = [];
  let key = 0;

  const flushBullets = () => {
    if (!bullets.length) return;
    out.push(
      <ul key={`ul-${key++}`} className="message-bubble__list">
        {bullets.map((item, i) => (
          <li key={i} className="message-bubble__list-item">
            {parseInline(item, `li-${key}-${i}`)}
          </li>
        ))}
      </ul>
    );
    bullets = [];
  };

  for (const line of lines) {
    const bm = line.match(/^[*\-]\s+(.*)$/);
    if (bm) {
      bullets.push(bm[1]);
    } else {
      flushBullets();
      if (line.trim() === '') {
        // skip blank lines between blocks (CSS margin handles spacing)
      } else {
        out.push(
          <p key={`p-${key++}`} className="message-bubble__paragraph">
            {parseInline(line, `p-${key}`)}
          </p>
        );
      }
    }
  }
  flushBullets();
  return out;
}

// ─────────────────────────────────────────────────────────────────

function MessageBubble({ message }) {
  const isUser = message.role === 'user';

  const formatTime = (isoStr) => {
    if (!isoStr) return '';
    const d = new Date(isoStr);
    return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  };

  const renderSourceLabel = (src) => {
    if (src.book_name && src.chapter_name) {
      return `${src.book_name} › ${src.chapter_name} › ${src.title}`;
    }
    if (src.book_name) {
      return `${src.book_name} › ${src.title}`;
    }
    if (src.source && src.source !== src.title) {
      return `${src.source} › ${src.title}`;
    }
    return src.title;
  };

  return (
    <div className={`message-bubble${isUser ? ' message-bubble--user' : ' message-bubble--assistant'}`}>
      <div className={`message-bubble__content${isUser ? ' message-bubble__content--user' : ' message-bubble__content--assistant'}`}>
        <div className={`message-bubble__text${isUser ? '' : ' message-bubble__text--markdown'}`}>
          {isUser
            ? message.message
            : renderMarkdown(message.message)
          }
          {message._streaming && (
            <span className="message-bubble__cursor" aria-hidden="true" />
          )}
        </div>

        {/* Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="message-bubble__sources message-bubble__sources--assistant">
            <div className="message-bubble__sources-label">Quellen:</div>
            {message.sources.map((src, i) => (
              <div key={i} className="message-bubble__source-item">
                {src.url ? (
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="message-bubble__source-link"
                  >
                    <span className="message-bubble__source-icon">📄</span>
                    <span className="message-bubble__source-label">{renderSourceLabel(src)}</span>
                  </a>
                ) : (
                  <span className="message-bubble__source-text">
                    <span className="message-bubble__source-icon">📄</span>
                    <span className="message-bubble__source-label">{renderSourceLabel(src)}</span>
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Timestamp */}
        <div className="message-bubble__footer">
          <span className="message-bubble__time">{formatTime(message.created_at)}</span>
        </div>
      </div>
    </div>
  );
}

export default MessageBubble;

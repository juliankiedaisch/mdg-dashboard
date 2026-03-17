import { useState, useEffect } from 'react';

/**
 * Hook that manages a self-dismissing message.
 * Error messages are NOT auto-dismissed – only 'success' and 'info'.
 *
 * @param {number} duration – auto-dismiss after ms (default 4000)
 * @returns {[object|null, Function]} – [message, setMessage]
 *   message shape: { text: string, type: 'success'|'error'|'info' } | null
 */
export default function useAutoMessage(duration = 4000) {
  const [message, setMessage] = useState(null);

  useEffect(() => {
    if (message && message.type !== 'error') {
      const timer = setTimeout(() => setMessage(null), duration);
      return () => clearTimeout(timer);
    }
  }, [message, duration]);

  return [message, setMessage];
}

import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Modal, Button, Spinner, MessageBox, FormGroup, TextInput } from '../../components/shared';

// Calculate duration string between two date strings
function calcDuration(start, end) {
  const parseDE = (s) => {
    // format: dd.mm.yyyy HH:MM:SS
    const [datePart, timePart] = s.split(' ');
    const [d, m, y] = datePart.split('.');
    return new Date(`${y}-${m}-${d}T${timePart}`);
  };
  const diff = parseDE(end) - parseDE(start);
  if (isNaN(diff) || diff < 0) return '–';
  const totalSec = Math.floor(diff / 1000);
  const h = Math.floor(totalSec / 3600);
  const min = Math.floor((totalSec % 3600) / 60);
  const sec = totalSec % 60;
  if (h > 0) return `${h}h ${min}m`;
  if (min > 0) return `${min}m ${sec}s`;
  return `${sec}s`;
}

function parseDeToDate(s) {
  if (!s) return null;
  const [datePart, timePart] = s.split(' ');
  const [d, m, y] = datePart.split('.');
  return new Date(`${y}-${m}-${d}T${timePart}`);
}

function UnifyDeviceModal({ deviceId, onClose, apiUrl }) {
  const [deviceData, setDeviceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [apSearch, setApSearch] = useState('');
  const [apInput, setApInput] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filterError, setFilterError] = useState('');
  const suggestionsRef = useRef(null);
  const apInputRef = useRef(null);

  useEffect(() => {
    loadDeviceData();
  }, [deviceId]);

  // Close suggestions on outside click
  useEffect(() => {
    const handler = (e) => {
      if (
        suggestionsRef.current && !suggestionsRef.current.contains(e.target) &&
        apInputRef.current && !apInputRef.current.contains(e.target)
      ) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const loadDeviceData = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${apiUrl}/api/unify/device/${deviceId}`, {
        credentials: 'include'
      });
      if (!response.ok) throw new Error('Fehler beim Laden des Geräts');
      const data = await response.json();
      setDeviceData(data);
      setError(null);
    } catch (err) {
      console.error('Error loading device:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Unique AP names for autocomplete
  const apSuggestions = useMemo(() => {
    if (!deviceData) return [];
    const names = [...new Set(deviceData.locations.map((l) => l.ap))];
    return names.sort();
  }, [deviceData]);

  // Filtered suggestions based on current input
  const filteredSuggestions = useMemo(() => {
    if (!apInput.trim()) return apSuggestions;
    const lower = apInput.toLowerCase();
    return apSuggestions.filter((ap) => ap.toLowerCase().includes(lower));
  }, [apInput, apSuggestions]);

  // Combined filtered locations
  const filteredLocations = useMemo(() => {
    if (!deviceData) return [];
    return deviceData.locations.filter((loc) => {
      // AP filter
      if (apSearch && !loc.ap.toLowerCase().includes(apSearch.toLowerCase())) return false;

      // Date range filter – compare against start of the entry
      if (dateFrom || dateTo) {
        const locStart = parseDeToDate(loc.start);
        const locEnd = parseDeToDate(loc.end);
        if (dateFrom) {
          const from = new Date(dateFrom + 'T00:00:00');
          if (locEnd && locEnd < from) return false;
        }
        if (dateTo) {
          const to = new Date(dateTo + 'T23:59:59');
          if (locStart && locStart > to) return false;
        }
      }
      return true;
    });
  }, [deviceData, apSearch, dateFrom, dateTo]);

  const handleDateFrom = useCallback((e) => {
    const val = e.target.value;
    setDateFrom(val);
    if (dateTo && val && val > dateTo) {
      setFilterError('Startdatum darf nicht nach dem Enddatum liegen.');
    } else {
      setFilterError('');
    }
  }, [dateTo]);

  const handleDateTo = useCallback((e) => {
    const val = e.target.value;
    setDateTo(val);
    if (dateFrom && val && val < dateFrom) {
      setFilterError('Enddatum darf nicht vor dem Startdatum liegen.');
    } else {
      setFilterError('');
    }
  }, [dateFrom]);

  const handleApInputChange = (e) => {
    setApInput(e.target.value);
    setApSearch('');    // clear committed search while typing
    setShowSuggestions(true);
  };

  const commitApSearch = (value) => {
    setApInput(value);
    setApSearch(value);
    setShowSuggestions(false);
  };

  const handleApInputKeyDown = (e) => {
    if (e.key === 'Enter') {
      commitApSearch(apInput);
    }
  };

  const handleApInputBlur = () => {
    // Small delay so click on suggestion registers first
    setTimeout(() => {
      setShowSuggestions(false);
      setApSearch(apInput);
    }, 150);
  };

  const handleReset = () => {
    setDateFrom('');
    setDateTo('');
    setApSearch('');
    setApInput('');
    setFilterError('');
  };

  const hasActiveFilter = dateFrom || dateTo || apSearch;

  return (
    <Modal
      title={
        deviceData
          ? `${deviceData.name} — ${deviceData.mac}`
          : 'Gerät laden…'
      }
      onClose={onClose}
      size="xl"
    >
      {loading && <Spinner text="Gerätedaten werden geladen…" />}
      {error && <MessageBox message={error} type="error" />}

      {deviceData && (
        <>
          {/* Filter toolbar */}
          <div className="udm-filter-bar">
            <FormGroup label="Von" htmlFor="udm-date-from" className="udm-filter-group">
              <TextInput
                id="udm-date-from"
                type="date"
                value={dateFrom}
                onChange={handleDateFrom}
                max={dateTo || undefined}
              />
            </FormGroup>
            <FormGroup label="Bis" htmlFor="udm-date-to" className="udm-filter-group">
              <TextInput
                id="udm-date-to"
                type="date"
                value={dateTo}
                onChange={handleDateTo}
                min={dateFrom || undefined}
              />
            </FormGroup>
            <FormGroup label="Access Point" htmlFor="udm-ap-search" className="udm-filter-group udm-filter-ap">
              <div className="udm-autocomplete-wrapper">
                <TextInput
                  id="udm-ap-search"
                  ref={apInputRef}
                  value={apInput}
                  onChange={handleApInputChange}
                  onKeyDown={handleApInputKeyDown}
                  onBlur={handleApInputBlur}
                  onFocus={() => setShowSuggestions(true)}
                  placeholder="AP filtern…"
                  autoComplete="off"
                />
                {showSuggestions && filteredSuggestions.length > 0 && (
                  <ul className="udm-suggestions" ref={suggestionsRef}>
                    {filteredSuggestions.map((ap) => (
                      <li
                        key={ap}
                        className="udm-suggestion-item"
                        onMouseDown={() => commitApSearch(ap)}
                      >
                        {ap}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </FormGroup>
            {hasActiveFilter && (
              <div className="udm-filter-reset">
                <Button variant="secondary" size="sm" onClick={handleReset}>
                  Filter zurücksetzen
                </Button>
              </div>
            )}
          </div>

          {filterError && (
            <MessageBox message={filterError} type="error" />
          )}

          {/* History table */}
          <div className="udm-history-wrapper">
            {filteredLocations.length === 0 ? (
              <p className="udm-empty">
                {hasActiveFilter
                  ? 'Keine Einträge für die gewählten Filter.'
                  : 'Keine Standortdaten verfügbar.'}
              </p>
            ) : (
              <table className="udm-history-table">
                <thead>
                  <tr>
                    <th>Access Point</th>
                    <th>Von</th>
                    <th>Bis</th>
                    <th>Dauer</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLocations.map((loc, i) => (
                    <tr key={i}>
                      <td className="udm-ap-name">{loc.ap}</td>
                      <td className="udm-ts">{loc.start}</td>
                      <td className="udm-ts">{loc.end}</td>
                      <td className="udm-duration">{calcDuration(loc.start, loc.end)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <p className="udm-count">
            {filteredLocations.length} von {deviceData.locations.length} Einträgen
          </p>
        </>
      )}
    </Modal>
  );
}

export default UnifyDeviceModal;


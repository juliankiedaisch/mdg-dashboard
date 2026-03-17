import { useState, useEffect, useMemo } from 'react';
import { Card, StatCard, Spinner, MessageBox } from '../../components/shared';

function UnifyOverview({ apiUrl }) {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortConfig, setSortConfig] = useState({ column: null, direction: 'none' });

  useEffect(() => {
    loadOverview();
    // Refresh every 60 seconds
    const interval = setInterval(loadOverview, 60000);
    return () => clearInterval(interval);
  }, []);

  const loadOverview = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${apiUrl}/api/unify/overview`, {
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error('Fehler beim Laden der Übersicht');
      }
      
      const data = await response.json();
      setOverview(data);
      setError(null);
    } catch (err) {
      console.error('Error loading overview:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (columnIndex) => {
    setSortConfig((prev) => ({
      column: columnIndex,
      direction: prev.column === columnIndex && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  const getSortIcon = (columnIndex) => {
    if (sortConfig.column !== columnIndex) return '⇅';
    return sortConfig.direction === 'asc' ? '🔼' : '🔽';
  };

  const sortedOfflineDevices = useMemo(() => {
    if (!overview?.offline_devices) return [];
    if (sortConfig.column === null) return overview.offline_devices;

    return [...overview.offline_devices].sort((a, b) => {
      let aValue, bValue;
      switch (sortConfig.column) {
        case 0: aValue = a.name;           bValue = b.name;           break;
        case 1: aValue = a.group;          bValue = b.group;          break;
        case 2: aValue = a.last_location;  bValue = b.last_location;  break;
        case 3: aValue = a.last_seen;      bValue = b.last_seen;      break;
        case 4: aValue = a.offline_since;  bValue = b.offline_since;  break;
        default: return 0;
      }
      const cmp = (aValue ?? '').localeCompare(bValue ?? '', undefined, { numeric: true });
      return sortConfig.direction === 'asc' ? cmp : -cmp;
    });
  }, [overview, sortConfig]);

  if (loading && !overview) {
    return (
      <Card variant="section">
        <Spinner text="Lade Übersicht..." fullPage />
      </Card>
    );
  }

  if (error) {
    return (
      <Card variant="section">
        <MessageBox message={`Fehler: ${error}`} type="error" />
      </Card>
    );
  }

  if (!overview) {
    return null;
  }

  return (
    <Card variant="section" className="unify-overview">
      <div className="overview-stats">
        <StatCard value={overview.total_devices} label="Geräte gesamt" />
        <StatCard value={overview.online_count} label="Online" variant="success" />
        <StatCard value={overview.offline_count} label="Offline" variant="danger" />
      </div>

      {overview.offline_devices && overview.offline_devices.length > 0 && (
        <div className="offline-devices-section">
          <div className="offline-devices-table">
            <table>
              <thead>
                <tr>
                  <th>
                    Name
                    <span className="unify-sort-icon" onClick={() => handleSort(0)}>
                      {getSortIcon(0)}
                    </span>
                  </th>
                  <th>
                    Gruppe
                    <span className="unify-sort-icon" onClick={() => handleSort(1)}>
                      {getSortIcon(1)}
                    </span>
                  </th>
                  <th>
                    Letzter Standort
                    <span className="unify-sort-icon" onClick={() => handleSort(2)}>
                      {getSortIcon(2)}
                    </span>
                  </th>
                  <th>
                    Zuletzt gesehen
                    <span className="unify-sort-icon" onClick={() => handleSort(3)}>
                      {getSortIcon(3)}
                    </span>
                  </th>
                  <th>
                    Offline seit
                    <span className="unify-sort-icon" onClick={() => handleSort(4)}>
                      {getSortIcon(4)}
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedOfflineDevices.map((device) => (
                  <tr key={device.id}>
                    <td>
                      <strong>{device.name}</strong>
                      <br />
                      <span className="device-mac">{device.mac}</span>
                    </td>
                    <td>{device.group}</td>
                    <td>{device.last_location}</td>
                    <td>{device.last_seen}</td>
                    <td>
                      <span className="offline-duration">{device.offline_since}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {overview.offline_devices && overview.offline_devices.length === 0 && (
        <MessageBox message="✅ Alle Geräte sind online!" type="success" />
      )}
    </Card>
  );
}

export default UnifyOverview;


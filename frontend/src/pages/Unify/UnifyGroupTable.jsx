import { useState } from 'react';
import RenameGroupModal from './RenameGroupModal';
import { Card, Button } from '../../components/shared';

function UnifyGroupTable({ groupData, onDeleteDevice, onOpenDevice, isAdmin, apiUrl, onGroupUpdate, showTitle = true }) {
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [sortConfig, setSortConfig] = useState({ column: null, direction: 'none' });

  const handleSort = (columnIndex) => {
    const newDirection = sortConfig.column === columnIndex && sortConfig.direction === 'asc' 
      ? 'desc' 
      : 'asc';
    setSortConfig({ column: columnIndex, direction: newDirection });
  };

  const getSortIcon = (columnIndex) => {
    if (sortConfig.column !== columnIndex) return '⇅';
    return sortConfig.direction === 'asc' ? '🔼' : '🔽';
  };

  const sortedDevices = [...groupData.devices].sort((a, b) => {
    if (sortConfig.column === null) return 0;

    let aValue, bValue;
    switch (sortConfig.column) {
      case 0: // Name
        aValue = a.name;
        bValue = b.name;
        break;
      case 1: // MAC
        aValue = a.mac;
        bValue = b.mac;
        break;
      case 2: // IP
        aValue = a.ip;
        bValue = b.ip;
        break;
      case 3: // Location
        aValue = a.location.ap_name;
        bValue = b.location.ap_name;
        break;
      case 4: // Last contact
        aValue = a.location.timestamp;
        bValue = b.location.timestamp;
        break;
      default:
        return 0;
    }

    if (sortConfig.direction === 'asc') {
      return aValue.localeCompare(bValue, undefined, { numeric: true });
    } else {
      return bValue.localeCompare(aValue, undefined, { numeric: true });
    }
  });

  const handleRenameSuccess = (action) => {
    setShowRenameModal(false);
    if (onGroupUpdate) {
      onGroupUpdate(action);
    }
  };

  return (
    <>
    <Card variant="section" className="unify-overview">
      {showTitle && (
        <>
          <h2 className="shared-card__title">{groupData.group.name}</h2>
          {isAdmin && (
            <Button 
              variant="ghost"
              className="rename-icon-btn" 
              onClick={() => setShowRenameModal(true)}
              title="Gruppe umbenennen"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 16 16">
                <path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168l10-10zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207 11.207 2.5zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293l6.5-6.5zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325z"/>
              </svg>
            </Button>
          )}
        </>
      )}

      <div className="unify-table-container">
        <table id="unify-group-table">
          <thead>
            <tr>
              <th>
                Name
                <span className="unify-sort-icon" onClick={() => handleSort(0)}>
                  {getSortIcon(0)}
                </span>
              </th>
              <th>
                MAC-Adresse
                <span className="unify-sort-icon" onClick={() => handleSort(1)}>
                  {getSortIcon(1)}
                </span>
              </th>
              <th>
                IP-Adresse
                <span className="unify-sort-icon" onClick={() => handleSort(2)}>
                  {getSortIcon(2)}
                </span>
              </th>
              <th>
                Standort
                <span className="unify-sort-icon" onClick={() => handleSort(3)}>
                  {getSortIcon(3)}
                </span>
              </th>
              <th>
                Letzter Kontakt
                <span className="unify-sort-icon" onClick={() => handleSort(4)}>
                  {getSortIcon(4)}
                </span>
              </th>
              {isAdmin && (
                <th>Aktion</th>
              )}
            </tr>
          </thead>
          <tbody>
            {sortedDevices.map((device) => (
              <tr key={device.id} className={!device.is_online ? 'device-offline' : ''}>
                <td>
                  <a href="#" onClick={(e) => { e.preventDefault(); onOpenDevice(device.id); }}>
                    {device.name}
                  </a>
                </td>
                <td>{device.mac}</td>
                <td>{device.ip}</td>
                <td>
                  {device.location.ap_name}
                </td>
                <td>
                  {device.location.timestamp}
                </td>
                {isAdmin && (
                  <td>
                    <span
                      onClick={() => onDeleteDevice(device.id)}
                      title="Löschen"
                      style={{ cursor: 'pointer' }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="#dc3545" viewBox="0 0 16 16">
                        <path d="M5.5 5.5a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0v-6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 1 1 0v6a.5.5 0 0 1-1 0v-6z"/>
                        <path fillRule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4H2.5a1 1 0 0 1 0-2H5h6h2.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 2a.5.5 0 0 0 0 1H4h8h1.5a.5.5 0 0 0 0-1H12H4H2.5z"/>
                      </svg>
                    </span>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
      {showRenameModal && (
        <RenameGroupModal
          group={groupData.group}
          apiUrl={apiUrl}
          onClose={() => setShowRenameModal(false)}
          onSuccess={handleRenameSuccess}
        />
      )}
    </>
  );
}

export default UnifyGroupTable;

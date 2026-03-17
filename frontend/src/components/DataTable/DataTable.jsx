import { useState } from 'react';
import './DataTable.css';

/**
 * DataTable - Einheitliche Tabelle mit optionaler Sortierung
 * 
 * @param {Array<{key: string, label: string, sortable?: boolean}>} columns - Spaltendefinitionen
 * @param {Array<Object>} data - Tabellendaten
 * @param {function} renderRow - Funktion zum Rendern einer Zeile: (item, index) => <tr>...</tr>
 * @param {string} emptyMessage - Nachricht bei leeren Daten
 * @param {string} className - Zusätzliche CSS-Klassen
 * @param {function} onSort - Sortier-Callback: (columnKey, direction) => void
 * @param {function} rowClassName - Funktion für Zeilen-CSS-Klasse: (item) => string
 */
function DataTable({ 
  columns, 
  data, 
  renderRow, 
  emptyMessage = 'Keine Daten vorhanden',
  className = '',
  onSort,
  rowClassName
}) {
  const [sortColumn, setSortColumn] = useState(null);
  const [sortDirection, setSortDirection] = useState('asc');

  const handleSort = (column) => {
    if (!column.sortable) return;
    
    const newDirection = sortColumn === column.key && sortDirection === 'asc' ? 'desc' : 'asc';
    setSortColumn(column.key);
    setSortDirection(newDirection);
    
    if (onSort) {
      onSort(column.key, newDirection);
    }
  };

  return (
    <div className={`shared-table-container ${className}`}>
      <table className="shared-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th 
                key={col.key} 
                onClick={() => handleSort(col)}
                className={col.sortable ? 'shared-table__th--sortable' : ''}
              >
                {col.label}
                {col.sortable && (
                  <span className="shared-table__sort-icon">
                    {sortColumn === col.key ? (sortDirection === 'asc' ? '▲' : '▼') : '⇅'}
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="shared-table__empty">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((item, index) => renderRow(item, index))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default DataTable;

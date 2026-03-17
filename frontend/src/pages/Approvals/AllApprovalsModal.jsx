import React, { useState, useEffect } from 'react';
import api from '../../utils/api';
import { Modal, Spinner } from '../../components/shared';
import './Approvals.css';

const AllApprovalsModal = ({ appId, appName, onClose, onDeleteApproval }) => {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAllApprovals();
  }, [appId]);

  const loadAllApprovals = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/api/approvals/applications/${appId}/all-approvals`);
      setApprovals(response.data.approvals || []);
    } catch (error) {
      console.error('Error loading all approvals:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (approvalId) => {
    await onDeleteApproval(approvalId);
    loadAllApprovals();
  };

  const sortTable = (columnIndex) => {
    const sorted = [...approvals].sort((a, b) => {
      const keys = ['approved_users', 'approved_groups', 'start', 'end', 'given_by'];
      const key = keys[columnIndex];
      return (a[key] || '').toString().localeCompare((b[key] || '').toString());
    });
    setApprovals(sorted);
  };

  return (
    <Modal title={`${appName} - Alle Freigaben`} onClose={onClose} size="xl">
          {loading ? (
            <Spinner text="Lade Freigaben..." fullPage />
          ) : (
            <div className="approval-table-container">
              <table className="approval-table">
                <thead>
                  <tr>
                    <th onClick={() => sortTable(0)}>
                      Benutzer <span className="sort-icon">⇅</span>
                    </th>
                    <th onClick={() => sortTable(1)}>
                      Gruppen <span className="sort-icon">⇅</span>
                    </th>
                    <th onClick={() => sortTable(2)}>
                      Start <span className="sort-icon">⇅</span>
                    </th>
                    <th onClick={() => sortTable(3)}>
                      Ende <span className="sort-icon">⇅</span>
                    </th>
                    <th onClick={() => sortTable(4)}>
                      gebucht von <span className="sort-icon">⇅</span>
                    </th>
                    <th>Aktion</th>
                  </tr>
                </thead>
                <tbody>
                  {approvals.length === 0 ? (
                    <tr>
                      <td colSpan="6" style={{ textAlign: 'center' }}>
                        Keine Freigaben vorhanden
                      </td>
                    </tr>
                  ) : (
                    approvals.map((approval) => (
                      <tr key={approval.approval_id}>
                        <td>{approval.approved_users}</td>
                        <td>{approval.approved_groups}</td>
                        <td>{approval.start}</td>
                        <td>{approval.end || '-'}</td>
                        <td>{approval.given_by}</td>
                        <td>
                          <span
                            onClick={() => handleDelete(approval.approval_id)}
                            title="Löschen"
                            style={{ cursor: 'pointer' }}
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="18"
                              height="18"
                              fill="#dc3545"
                              viewBox="0 0 16 16"
                            >
                              <path d="M5.5 5.5a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0v-6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 1 1 0v6a.5.5 0 0 1-1 0v-6z" />
                              <path fillRule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4H2.5a1 1 0 0 1 0-2H5h6h2.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 2a.5.5 0 0 0 0 1H4h8h1.5a.5.5 0 0 0 0-1H12H4H2.5z" />
                            </svg>
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
    </Modal>
  );
};

export default AllApprovalsModal;

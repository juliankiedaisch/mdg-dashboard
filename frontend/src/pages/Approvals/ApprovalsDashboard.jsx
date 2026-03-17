import React, { useState, useEffect } from 'react';
import { io } from 'socket.io-client';
import { useUser } from '../../contexts/UserContext';
import api from '../../utils/api';
import { PageContainer, Card, Button, DataTable, MessageBox, StatCard, Spinner } from '../../components/shared';
import NewApplicationModal from './NewApplicationModal';
import ConfirmModal from './ConfirmModal';
import './Approvals.css';

const ApprovalsDashboard = () => {
  const [approvals, setApprovals] = useState([]);
  const [overview, setOverview] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [showNewAppModal, setShowNewAppModal] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const { hasPermission } = useUser();

  useEffect(() => {
    loadApprovals();
    if (hasPermission('approvals.manage')) {
      loadOverview();
    }
    
    // SocketIO listeners
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';
    const approvalsSocket = io(`${apiUrl}/approvals`, {
      withCredentials: true
    });
    
    approvalsSocket.on('new_application_success', (msg) => {
      setMessage({ text: msg, type: 'success' });
      // Reload overview when new application is created
      if (hasPermission('approvals.manage')) {
        loadOverview();
      }
    });

    approvalsSocket.on('new_application_error', (msg) => {
      setMessage({ text: msg, type: 'error' });
    });

    return () => {
      approvalsSocket.disconnect();
    };
  }, []);

  const loadApprovals = async () => {
    try {
      setLoading(true);
      const response = await api.get('/api/approvals/my-approvals');
      setApprovals(response.data.approvals || []);
    } catch (error) {
      console.error('Error loading approvals:', error);
      setMessage({ text: 'Fehler beim Laden der Freigaben', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const loadOverview = async () => {
    try {
      const response = await api.get('/api/approvals/overview');
      setOverview(response.data.overview || []);
    } catch (error) {
      console.error('Error loading overview:', error);
      setMessage({ text: 'Fehler beim Laden der Übersicht', type: 'error' });
    }
  };

  const handleDeleteApproval = (approvalId) => {
    setConfirmDelete(approvalId);
  };

  const confirmDeleteApproval = async () => {
    const approvalId = confirmDelete;
    setConfirmDelete(null);

    try {
      const response = await api.delete(`/api/approvals/approvals/${approvalId}`);
      setMessage({ text: response.data.message, type: response.data.status ? 'success' : 'error' });
      loadApprovals();
    } catch (error) {
      console.error('Error deleting approval:', error);
      setMessage({ text: 'Fehler beim Löschen der Freigabe', type: 'error' });
    }
  };

  const sortTable = (columnIndex) => {
    const sorted = [...approvals].sort((a, b) => {
      const keys = ['application_name', 'approved_users', 'approved_groups', 'start', 'end'];
      const key = keys[columnIndex];
      return (a[key] || '').toString().localeCompare((b[key] || '').toString());
    });
    setApprovals(sorted);
  };

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  if (loading) {
    return <Spinner size="lg" text="Lade Freigaben..." fullPage />;
  }

  return (
    <PageContainer>
      <Card variant="header" title="Freigabenverwaltung">
        {hasPermission('approvals.manage') && (
          <Button onClick={() => setShowNewAppModal(true)}>
            Neue Anwendung hinzufügen
          </Button>
        )}
      </Card>
      <Card>
        {message && (
          <MessageBox message={message.text} type={message.type} />
        )}



        {hasPermission('approvals.manage') && overview.length > 0 && (
          <Card variant="section">
            <h2 className="shared-card__title">Freigaben-Übersicht</h2>
            <div className="approval-overview-grid">
              {overview.map((item) => (
                <div key={item.id} className="approval-card">
                  <div className="approval-card-name">{item.name}</div>
                  <div className="approval-card-stats">
                    <div className="approval-card-stat">
                      <StatCard value={item.current_count} size="small" label="Aktuelle" variant="success" />
                    </div>
                    <div className="approval-card-stat">
                      <StatCard value={item.planned_count} size="small" label="Geplante" variant="info" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Card variant="section">
          <h2 className="shared-card__title">Deine Freigaben</h2>
          <div className="approval-table-container">
            <table className="approval-table">
              <thead>
                <tr>
                  <th onClick={() => sortTable(0)}>
                    Anwendung <span className="sort-icon">⇅</span>
                  </th>
                  <th onClick={() => sortTable(1)}>
                    Benutzer <span className="sort-icon">⇅</span>
                  </th>
                  <th onClick={() => sortTable(2)}>
                    Gruppen <span className="sort-icon">⇅</span>
                  </th>
                  <th onClick={() => sortTable(3)}>
                    Start <span className="sort-icon">⇅</span>
                  </th>
                  <th onClick={() => sortTable(4)}>
                    Ende <span className="sort-icon">⇅</span>
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
                      <td>{approval.application_name}</td>
                      <td>{approval.approved_users}</td>
                      <td>{approval.approved_groups}</td>
                      <td>{approval.start}</td>
                      <td>{approval.end || '-'}</td>
                      <td>
                        <span
                          onClick={() => handleDeleteApproval(approval.approval_id)}
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
        </Card>
      </Card>

      {showNewAppModal && (
        <NewApplicationModal
          onClose={() => setShowNewAppModal(false)}
          onSuccess={() => {
            loadApprovals();
            if (hasPermission('approvals.manage')) {
              loadOverview();
            }
          }}
        />
      )}

      {confirmDelete && (
        <ConfirmModal
          message="Möchten Sie diese Freigabe wirklich löschen?"
          onConfirm={confirmDeleteApproval}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </PageContainer>
  );
};

export default ApprovalsDashboard;

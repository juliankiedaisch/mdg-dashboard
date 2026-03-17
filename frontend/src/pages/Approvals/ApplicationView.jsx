import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { io } from 'socket.io-client';
import { useUser } from '../../contexts/UserContext';
import api from '../../utils/api';
import { PageContainer, Card, Button, MessageBox, Spinner } from '../../components/shared';
import NewApprovalModal from './NewApprovalModal';
import UpdateApplicationModal from './UpdateApplicationModal';
import AllApprovalsModal from './AllApprovalsModal';
import ConfirmModal from './ConfirmModal';
import './Approvals.css';

const ApplicationView = () => {
  const { appId } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useUser();
  const [app, setApp] = useState(null);
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [showNewApprovalModal, setShowNewApprovalModal] = useState(false);
  const [showUpdateModal, setShowUpdateModal] = useState(false);
  const [showAllApprovalsModal, setShowAllApprovalsModal] = useState(false);
  const [confirmDeleteApp, setConfirmDeleteApp] = useState(false);
  const [confirmDeleteApproval, setConfirmDeleteApproval] = useState(null);

  useEffect(() => {
    loadApplication();
  }, [appId]);

  const loadApplication = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/api/approvals/applications/${appId}`);
      setApp(response.data.app);
      setApprovals(response.data.approvals || []);
    } catch (error) {
      console.error('Error loading application:', error);
      setMessage({ text: 'Fehler beim Laden der Anwendung', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteApp = () => {
    setConfirmDeleteApp(true);
  };

  const confirmDeleteApplication = async () => {
    setConfirmDeleteApp(false);

    try {
      const response = await api.delete(`/api/approvals/applications/${appId}`);
      setMessage({ text: response.data.message, type: response.data.status ? 'success' : 'error' });
      setTimeout(() => navigate('/approvals'), 1000);
    } catch (error) {
      console.error('Error deleting application:', error);
      setMessage({ text: 'Fehler beim Löschen der Anwendung', type: 'error' });
    }
  };

  const handleDeleteApproval = (approvalId) => {
    setConfirmDeleteApproval(approvalId);
  };

  const confirmDeleteApprovalAction = async () => {
    const approvalId = confirmDeleteApproval;
    setConfirmDeleteApproval(null);

    try {
      const response = await api.delete(`/api/approvals/approvals/${approvalId}`);
      setMessage({ text: response.data.message, type: response.data.status ? 'success' : 'error' });
      loadApplication();
    } catch (error) {
      console.error('Error deleting approval:', error);
      setMessage({ text: 'Fehler beim Löschen der Freigabe', type: 'error' });
    }
  };

  const sortTable = (columnIndex) => {
    const sorted = [...approvals].sort((a, b) => {
      const keys = ['approved_users', 'approved_groups', 'start', 'end', 'given_by'];
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
    return <Spinner size="lg" text="Lade Anwendung..." fullPage />;
  }

  if (!app) {
    return <div className="error">Anwendung nicht gefunden</div>;
  }

  return (
    <PageContainer>
      <Card variant="header" title="Übersicht">
        <Button variant="secondary" onClick={() => navigate('/approvals')}>← Zurück</Button>
      </Card>
      <Card>
        {message && (
          <MessageBox message={message.text} type={message.type} autoHide={3000} onDismiss={() => setMessage(null)} />
        )}

        <div className="box-content" style={{ position: 'relative' }}>
          {hasPermission('approvals.manage') && (
            <>
              <Button
                variant="ghost"
                className="btn-icon"
                style={{ position: 'absolute', top: '-8px', right: '8px' }}
                onClick={() => setShowUpdateModal(true)}
                title="Bearbeiten"
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path fillRule="evenodd" clipRule="evenodd" d="M13.2929 4.29291C15.0641 2.52167 17.9359 2.52167 19.7071 4.2929C21.4784 6.06414 21.4784 8.93588 19.7071 10.7071L18.7073 11.7069L11.6135 18.8007C10.8766 19.5376 9.92793 20.0258 8.89999 20.1971L4.16441 20.9864C3.84585 21.0395 3.52127 20.9355 3.29291 20.7071C3.06454 20.4788 2.96053 20.1542 3.01362 19.8356L3.80288 15.1C3.9742 14.0721 4.46243 13.1234 5.19932 12.3865L13.2929 4.29291ZM13 7.41422L6.61353 13.8007C6.1714 14.2428 5.87846 14.8121 5.77567 15.4288L5.21656 18.7835L8.57119 18.2244C9.18795 18.1216 9.75719 17.8286 10.1993 17.3865L16.5858 11L13 7.41422ZM18 9.5858L14.4142 6.00001L14.7071 5.70712C15.6973 4.71693 17.3027 4.71693 18.2929 5.70712C19.2831 6.69731 19.2831 8.30272 18.2929 9.29291L18 9.5858Z" fill="currentColor"/>
                </svg>
              </Button>
              <Button
                variant="ghost"
                className="btn-icon"
                style={{ position: 'absolute', top: '-8px', right: '50px' }}
                onClick={() => setShowAllApprovalsModal(true)}
                title="Alle Freigaben anzeigen"
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path fillRule="evenodd" clipRule="evenodd" d="M3 4H21V20H3V4ZM5 6V18H19V6H5ZM7 8H9V10H7V8ZM11 8H13V10H11V8ZM15 8H17V10H15V8ZM7 12H9V14H7V12ZM11 12H13V14H11V12ZM15 12H17V14H15V12ZM7 16H9V18H7V16ZM11 16H13V18H11V16ZM15 16H17V18H15V16Z" fill="currentColor"/>
                </svg>
              </Button>
              <Button
                variant="ghost"
                className="btn-icon btn-danger"
                style={{ position: 'absolute', top: '-8px', right: '92px' }}
                onClick={handleDeleteApp}
                title="Anwendung löschen"
              >
                <svg width="24" height="24" viewBox="0 0 16 16" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                  <path d="M5.5 5.5a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0v-6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 1 1 0v6a.5.5 0 0 1-1 0v-6z"/>
                  <path fillRule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4H2.5a1 1 0 0 1 0-2H5h6h2.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 2a.5.5 0 0 0 0 1H4h8h1.5a.5.5 0 0 0 0-1H12H4H2.5z"/>
                </svg>
              </Button>
            </>
          )}
          <p style={{ fontSize: '1.5rem', margin: '-10px -10px 0 0', fontWeight: 'bold' }}>
            {app.name}
          </p>
          {app.description && <p>{app.description}</p>}
          <p style={{ marginBottom: '-10px' }}>
            <a href={app.url} target="_blank" rel="noopener noreferrer">
              {app.url}
            </a>
          </p>
        </div>

        <Button onClick={() => setShowNewApprovalModal(true)}>
          Neue Freigabe hinzufügen
        </Button>

        <h2 style={{ marginTop: '2rem' }}>Gebuchte Freigaben</h2>
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
                {hasPermission('approvals.manage') && <th>Aktion</th>}
              </tr>
            </thead>
            <tbody>
              {approvals.length === 0 ? (
                <tr>
                  <td colSpan={hasPermission('approvals.manage') ? "6" : "5"} style={{ textAlign: 'center' }}>
                    Keine aktiven Freigaben vorhanden
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
                    {hasPermission('approvals.manage') && (
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
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {showNewApprovalModal && (
        <NewApprovalModal
          appId={appId}
          onClose={() => setShowNewApprovalModal(false)}
          onSuccess={() => {
            console.log('Approval success callback triggered');
            setMessage({ text: 'Freigabe erfolgreich erstellt', type: 'success' });
            loadApplication();
            setShowNewApprovalModal(false);
          }}
        />
      )}

      {showUpdateModal && (
        <UpdateApplicationModal
          app={app}
          onClose={() => setShowUpdateModal(false)}
          onSuccess={() => {
            setMessage({ text: 'Anwendung erfolgreich aktualisiert', type: 'success' });
            loadApplication();
            setShowUpdateModal(false);
          }}
        />
      )}

      {showAllApprovalsModal && (
        <AllApprovalsModal
          appId={appId}
          appName={app.name}
          onClose={() => setShowAllApprovalsModal(false)}
          onDeleteApproval={handleDeleteApproval}
        />
      )}

      {confirmDeleteApp && (
        <ConfirmModal
          message={`Möchten Sie die Anwendung "${app?.name}" wirklich löschen? Alle zugehörigen Freigaben werden ebenfalls gelöscht.`}
          onConfirm={confirmDeleteApplication}
          onCancel={() => setConfirmDeleteApp(false)}
        />
      )}

      {confirmDeleteApproval && (
        <ConfirmModal
          message="Möchten Sie diese Freigabe wirklich löschen?"
          onConfirm={confirmDeleteApprovalAction}
          onCancel={() => setConfirmDeleteApproval(null)}
        />
      )}
    </PageContainer>
  );
};

export default ApplicationView;

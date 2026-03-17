import { useState, useEffect } from 'react';
import { io } from 'socket.io-client';
import { useUser } from '../../contexts/UserContext';
import { PageContainer, Card, Button } from '../../components/shared';
import UnifyOverview from './UnifyOverview';
import DeviceGroupImportModal from './DeviceGroupImportModal';
import './Unify.css';

function UnifyDashboard() {
  const { hasPermission } = useUser();
  const [socket, setSocket] = useState(null);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';

  useEffect(() => {
    // Initialize SocketIO connection
    const socketUrl = `${apiUrl}/unify`;
    const newSocket = io(socketUrl, {
      withCredentials: true
    });

    newSocket.on('connect', () => {
      console.log('Connected to Unify socket');
    });

    newSocket.on('load_menu', () => {
      // Backend emits this event to refresh the sidebar menu via Layout
    });

    setSocket(newSocket);

    return () => {
      newSocket.disconnect();
    };
  }, [apiUrl]);

  return (
    <PageContainer>
      <Card variant="header" title="Gerätemanager - Übersicht">
        {hasPermission('unify.manage') && (
          <Button variant="primary" onClick={() => setImportModalOpen(true)}>
            Gruppen importieren
          </Button>
        )}
      </Card>

      <UnifyOverview apiUrl={apiUrl} refreshKey={refreshKey} />

      {importModalOpen && (
        <DeviceGroupImportModal
          socket={socket}
          onClose={() => setImportModalOpen(false)}
          onSuccess={() => {
            setImportModalOpen(false);
            setRefreshKey((k) => k + 1);
          }}
        />
      )}
    </PageContainer>
  );
}

export default UnifyDashboard;

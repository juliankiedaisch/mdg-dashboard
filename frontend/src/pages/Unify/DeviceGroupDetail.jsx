import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import { PageContainer, Card, Button, Spinner, MessageBox, Modal } from '../../components/shared';
import UnifyGroupTable from './UnifyGroupTable';
import UnifyDeviceModal from './UnifyDeviceModal';
import RenameGroupModal from './RenameGroupModal';
import './Unify.css';

function DeviceGroupDetail() {
  const { groupId } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useUser();
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';

  const [groupData, setGroupData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [deviceModalOpen, setDeviceModalOpen] = useState(false);
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  useEffect(() => {
    loadGroupData();
  }, [groupId]);

  const loadGroupData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/api/unify/groups/${groupId}`, {
        credentials: 'include'
      });
      if (!response.ok) {
        throw new Error('Gruppe konnte nicht geladen werden.');
      }
      const data = await response.json();
      setGroupData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDevice = async (deviceId) => {
    if (!window.confirm('Möchten Sie dieses Gerät wirklich löschen?')) {
      return;
    }
    try {
      const response = await fetch(`${apiUrl}/api/unify/device/${deviceId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      const data = await response.json();
      if (data.status) {
        loadGroupData();
      }
    } catch (err) {
      console.error('Error deleting device:', err);
    }
  };

  const handleDeleteGroup = async () => {
    setDeleteLoading(true);
    setDeleteError('');
    try {
      const response = await fetch(`${apiUrl}/api/unify/groups/${groupId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      const data = await response.json();
      if (data.status) {
        navigate('/unify');
      } else {
        setDeleteError(data.message || 'Fehler beim Löschen der Gruppe.');
      }
    } catch (err) {
      setDeleteError('Fehler beim Löschen der Gruppe.');
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleOpenDevice = (deviceId) => {
    setSelectedDevice(deviceId);
    setDeviceModalOpen(true);
  };

  const handleCloseDeviceModal = () => {
    setDeviceModalOpen(false);
    setSelectedDevice(null);
  };

  const handleGroupUpdate = (action) => {
    if (action === 'delete') {
      navigate('/unify');
    } else if (action === 'rename') {
      setRenameModalOpen(false);
      loadGroupData();
    }
  };

  const pageTitle = groupData
    ? `Gerätemanager - ${groupData.group.name}`
    : 'Gerätemanager';

  return (
    <PageContainer>
      <Card variant="header" title={pageTitle}>
        <Button variant="secondary" onClick={() => navigate('/unify')}>
          Zurück
        </Button>
        {hasPermission('unify.manage') && (
          <>
            <Button variant="primary" onClick={() => setRenameModalOpen(true)}>
              Umbenennen
            </Button>
            <Button variant="danger" onClick={() => setDeleteConfirmOpen(true)}>
              Gruppe löschen
            </Button>
          </>
        )}
      </Card>

      {loading && <Spinner />}
      {error && <MessageBox type="error">{error}</MessageBox>}

      {!loading && !error && groupData && (
        <UnifyGroupTable
          groupData={groupData}
          onDeleteDevice={handleDeleteDevice}
          onOpenDevice={handleOpenDevice}
          isAdmin={hasPermission('unify.manage')}
          apiUrl={apiUrl}
          onGroupUpdate={handleGroupUpdate}
          showTitle={false}
        />
      )}

      {deviceModalOpen && selectedDevice && (
        <UnifyDeviceModal
          deviceId={selectedDevice}
          apiUrl={apiUrl}
          onClose={handleCloseDeviceModal}
        />
      )}

      {renameModalOpen && groupData && (
        <RenameGroupModal
          group={groupData.group}
          apiUrl={apiUrl}
          onClose={() => setRenameModalOpen(false)}
          onSuccess={handleGroupUpdate}
        />
      )}

      {deleteConfirmOpen && groupData && (
        <Modal
          title="Gruppe löschen?"
          onClose={() => setDeleteConfirmOpen(false)}
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setDeleteConfirmOpen(false)} disabled={deleteLoading}>
                Abbrechen
              </Button>
              <Button variant="danger" onClick={handleDeleteGroup} loading={deleteLoading}>
                {deleteLoading ? 'Lösche...' : 'Gruppe löschen'}
              </Button>
            </>
          }
        >
          <p className="delete-warning">
            Möchten Sie die Gruppe <strong>"{groupData.group.name}"</strong> wirklich löschen?
          </p>
          <p className="delete-warning-text">
            Alle Geräte und Daten dieser Gruppe werden unwiderruflich gelöscht!
          </p>
          {deleteError && <MessageBox message={deleteError} type="error" />}
        </Modal>
      )}
    </PageContainer>
  );
}

export default DeviceGroupDetail;

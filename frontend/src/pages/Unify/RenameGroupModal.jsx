import { useState } from 'react';
import axios from 'axios';
import { Modal, Button, FormGroup, MessageBox, TextInput, Form } from '../../components/shared';

function RenameGroupModal({ group, apiUrl, onClose, onSuccess }) {
  const [newName, setNewName] = useState(group.name);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleRename = async (e) => {
    e.preventDefault();
    if (!newName.trim()) {
      setError('Gruppenname darf nicht leer sein.');
      return;
    }

    if (newName.trim() === group.name) {
      setError('Neuer Name ist identisch mit dem alten Namen.');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const response = await axios.put(
        `${apiUrl}/api/unify/groups/${group.id}`,
        { new_name: newName.trim() },
        { withCredentials: true }
      );

      if (response.data.status) {
        onSuccess('rename');
      } else {
        setError(response.data.message || 'Fehler beim Umbenennen der Gruppe.');
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Fehler beim Umbenennen der Gruppe.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    setIsLoading(true);
    setError('');

    try {
      const response = await axios.delete(
        `${apiUrl}/api/unify/groups/${group.id}`,
        { withCredentials: true }
      );

      if (response.data.status) {
        onSuccess('delete');
      } else {
        setError(response.data.message || 'Fehler beim Löschen der Gruppe.');
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Fehler beim Löschen der Gruppe.');
    } finally {
      setIsLoading(false);
    }
  };

  if (showDeleteConfirm) {
    return (
      <Modal
        title="Gruppe löschen?"
        onClose={onClose}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowDeleteConfirm(false)} disabled={isLoading}>Abbrechen</Button>
            <Button variant="danger" onClick={handleDelete} loading={isLoading}>
              {isLoading ? 'Lösche...' : 'Gruppe löschen'}
            </Button>
          </>
        }
      >
            <p className="delete-warning">
              Möchten Sie die Gruppe <strong>"{group.name}"</strong> wirklich löschen?
            </p>
            <p className="delete-warning-text">
              Alle Geräte und Daten dieser Gruppe werden unwiderruflich gelöscht!
            </p>
            {error && <MessageBox message={error} type="error" />}
      </Modal>
    );
  }

  return (
    <Modal
      title="Gruppe umbenennen"
      onClose={onClose}
      size="md"
      footer={
        <>
          <Button variant="danger" onClick={() => setShowDeleteConfirm(true)} disabled={isLoading}>
            Gruppe löschen
          </Button>
          <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
            <Button variant="secondary" onClick={onClose} disabled={isLoading}>Abbrechen</Button>
            <Button onClick={handleRename} loading={isLoading}>
              {isLoading ? 'Speichere...' : 'Umbenennen'}
            </Button>
          </div>
        </>
      }
    >
        <Form onSubmit={handleRename}>
          <FormGroup label="Gruppenname:" htmlFor="groupName">
            <TextInput
              id="groupName"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              disabled={isLoading}
              autoFocus
              fullWidth
            />
          </FormGroup>
          {error && <MessageBox message={error} type="error" />}
        </Form>
    </Modal>
  );
}

export default RenameGroupModal;

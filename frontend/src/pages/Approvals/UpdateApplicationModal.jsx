import React, { useState } from 'react';
import api from '../../utils/api';
import { Modal, Button, FormGroup, TextInput, Form } from '../../components/shared';
import AlertModal from './AlertModal';
import './Approvals.css';

const UpdateApplicationModal = ({ app, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    name: app.name || '',
    description: app.description || '',
    url: app.url || ''
  });
  const [loading, setLoading] = useState(false);
  const [alertMessage, setAlertMessage] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.name.trim() || !formData.url.trim()) {
      setAlertMessage('Name und URL sind Pflichtfelder');
      return;
    }

    try {
      setLoading(true);
      await api.put(`/api/approvals/applications/${app.id}`, {
        new_name: formData.name,
        new_description: formData.description,
        new_url: formData.url
      });
      onSuccess();
    } catch (error) {
      console.error('Error updating application:', error);
      setAlertMessage('Fehler beim Aktualisieren der Anwendung');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
    <Modal
      title="Anwendung bearbeiten"
      onClose={onClose}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>Abbrechen</Button>
          <Button loading={loading} onClick={handleSubmit}>
            {loading ? 'Speichere...' : 'Speichern'}
          </Button>
        </>
      }
    >
      <Form onSubmit={handleSubmit}>
        <FormGroup label="Name" htmlFor="name-update" required>
          <TextInput
            id="name-update"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
            disabled={loading}
            fullWidth
          />
        </FormGroup>
        <FormGroup label="Beschreibung" htmlFor="description-update">
          <TextInput
            id="description-update"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            disabled={loading}
            fullWidth
          />
        </FormGroup>
        <FormGroup label="URL Website" htmlFor="url-update" required>
          <TextInput
            id="url-update"
            value={formData.url}
            onChange={(e) => setFormData({ ...formData, url: e.target.value })}
            required
            disabled={loading}
            fullWidth
          />
        </FormGroup>
      </Form>
    </Modal>

      {alertMessage && (
        <AlertModal
          message={alertMessage}
          onClose={() => setAlertMessage(null)}
        />
      )}
    </>
  );
};

export default UpdateApplicationModal;

import React, { useState } from 'react';
import { io } from 'socket.io-client';
import { Modal, Button, FormGroup, TextInput, Form } from '../../components/shared';
import AlertModal from './AlertModal';
import './Approvals.css';

const NewApplicationModal = ({ onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    url: ''
  });
  const [loading, setLoading] = useState(false);
  const [alertMessage, setAlertMessage] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!formData.name.trim() || !formData.url.trim()) {
      setAlertMessage('Name und URL sind Pflichtfelder');
      return;
    }

    console.log('[NewApplicationModal] Submitting:', formData);
    setLoading(true);
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';
    const approvalsSocket = io(`${apiUrl}/approvals`, {
      withCredentials: true
    });

    approvalsSocket.on('connect', () => {
      console.log('[NewApplicationModal] Socket connected, emitting new_application');
      approvalsSocket.emit('new_application', formData);
    });

    // Listen for success/error
    approvalsSocket.on('new_application_success', (msg) => {
      console.log('[NewApplicationModal] Success:', msg);
      setLoading(false);
      approvalsSocket.disconnect();
      onSuccess();
      onClose();
    });

    approvalsSocket.on('new_application_error', (msg) => {
      console.log('[NewApplicationModal] Error:', msg);
      setAlertMessage(msg);
      setLoading(false);
      approvalsSocket.disconnect();
    });
  };

  return (
    <>
    <Modal 
      title="Neue Anwendung erstellen" 
      onClose={onClose}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>Abbrechen</Button>
          <Button type="submit" loading={loading} onClick={handleSubmit}>
            {loading ? 'Erstelle...' : 'Anwendung erstellen'}
          </Button>
        </>
      }
    >
      <Form onSubmit={handleSubmit}>
        <FormGroup label="Name" htmlFor="name" required>
          <TextInput
            id="name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
            disabled={loading}
            fullWidth
          />
        </FormGroup>
        <FormGroup label="Beschreibung" htmlFor="description">
          <TextInput
            id="description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            disabled={loading}
            fullWidth
          />
        </FormGroup>
        <FormGroup label="URL Website" htmlFor="url" required>
          <TextInput
            id="url"
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

export default NewApplicationModal;

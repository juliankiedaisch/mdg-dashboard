import React from 'react';
import { Modal, Button } from '../../components/shared';
import './Approvals.css';

const AlertModal = ({ message, onClose, type = 'error' }) => {
  return (
    <Modal
      title={type === 'error' ? 'Fehler' : 'Hinweis'}
      onClose={onClose}
      size="sm"
      footer={<Button onClick={onClose}>OK</Button>}
    >
      <p>{message}</p>
    </Modal>
  );
};

export default AlertModal;

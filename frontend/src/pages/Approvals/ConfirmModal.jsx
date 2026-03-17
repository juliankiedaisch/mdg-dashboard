import React from 'react';
import { Modal, Button } from '../../components/shared';
import './Approvals.css';

const ConfirmModal = ({ message, onConfirm, onCancel }) => {
  return (
    <Modal 
      title="Bestätigung" 
      onClose={onCancel} 
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>Abbrechen</Button>
          <Button variant="danger" onClick={onConfirm}>Löschen</Button>
        </>
      }
    >
      <p>{message}</p>
    </Modal>
  );
};

export default ConfirmModal;

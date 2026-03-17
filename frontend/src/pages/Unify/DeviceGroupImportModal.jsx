import { useState, useRef } from 'react';
import { Modal, Button, FormGroup, MessageBox } from '../../components/shared';

/**
 * DeviceGroupImportModal
 * Handles CSV upload for importing device groups.
 * Communicates via SocketIO (passed as prop) to keep the same
 * connection that UnifyDashboard already manages.
 *
 * @param {object}   socket      - Active SocketIO socket instance
 * @param {function} onClose     - Called to close the modal
 * @param {function} onSuccess   - Called after a successful import
 */
function DeviceGroupImportModal({ socket, onClose, onSuccess }) {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0] || null;
    setFile(selected);
    setMessage(null);
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!file) {
      setMessage({ type: 'error', text: 'Bitte eine CSV-Datei auswählen.' });
      return;
    }

    if (!file.name.toLowerCase().endsWith('.csv')) {
      setMessage({ type: 'error', text: 'Nur CSV-Dateien werden unterstützt.' });
      return;
    }

    if (!socket) {
      setMessage({ type: 'error', text: 'Keine Verbindung zum Server. Bitte Seite neu laden.' });
      return;
    }

    setIsUploading(true);
    setMessage(null);

    const reader = new FileReader();

    reader.onload = () => {
      // Register one-time response listeners before emitting
      socket.once('upload_success', (msg) => {
        setIsUploading(false);
        setMessage({ type: 'success', text: msg });
        setFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        onSuccess?.();
      });

      socket.once('upload_error', (msg) => {
        setIsUploading(false);
        setMessage({ type: 'error', text: msg || 'Fehler beim Importieren.' });
      });

      socket.emit('upload_csv', {
        filename: file.name,
        data: reader.result,
      });
    };

    reader.onerror = () => {
      setIsUploading(false);
      setMessage({ type: 'error', text: 'Fehler beim Lesen der Datei.' });
    };

    reader.readAsArrayBuffer(file);
  };

  return (
    <Modal
      title="Gerätegruppen importieren"
      onClose={!isUploading ? onClose : undefined}
      closeOnOverlay={!isUploading}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isUploading}>
            Abbrechen
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={!file || isUploading}
            loading={isUploading}
          >
            {isUploading ? 'Importiere…' : 'Import starten'}
          </Button>
        </>
      }
    >
      {message && (
        <MessageBox message={message.text} type={message.type} />
      )}

      <FormGroup
        label="CSV-Datei auswählen"
        hint="Exportieren Sie in IServ unter Geräte die gewünschten Gruppen als CSV und laden Sie die Datei hier hoch."
        htmlFor="import-csv-file"
      >
        <input
          ref={fileInputRef}
          id="import-csv-file"
          type="file"
          accept=".csv"
          className="shared-input"
          onChange={handleFileChange}
          disabled={isUploading}
        />
        {file && (
          <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginTop: '4px', display: 'block' }}>
            Ausgewählte Datei: <strong>{file.name}</strong>
          </span>
        )}
      </FormGroup>
    </Modal>
  );
}

export default DeviceGroupImportModal;

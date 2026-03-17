import { useState, useEffect } from 'react';
import { io } from 'socket.io-client';
import { useUser } from '../../contexts/UserContext';
import { PageContainer, Card, Button, MessageBox, FormGroup, TextInput, Form, InputFile } from '../../components/shared';
import './CSVGenerator.css';

function CSVGeneratorDashboard() {
  const { hasPermission } = useUser();
  const [socket, setSocket] = useState(null);
  const [generators, setGenerators] = useState({
    iservbuecherei: { file: null, terms: '', message: null, isProcessing: false },
    moodle: { file: null, terms: '', message: null, isProcessing: false },
    anmeldedaten: { file: null, message: null, isProcessing: false }
  });

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';

  useEffect(() => {
    // Load saved terms from backend
    loadSavedTerms();

    // Initialize SocketIO connection
    const socketUrl = `${apiUrl}/csvgenerator`;
    const newSocket = io(socketUrl, {
      withCredentials: true
    });

    newSocket.on('connect', () => {
      console.log('Connected to CSVGenerator socket');
    });

    newSocket.on('csv_ready', (data) => {
      setGenerators(prev => ({
        ...prev,
        [data.type]: {
          ...prev[data.type],
          message: { type: 'success', text: data.message, link: data.link },
          isProcessing: false,
          file: null
        }
      }));
      setTimeout(() => {
        setGenerators(prev => ({
          ...prev,
          [data.type]: { ...prev[data.type], message: null }
        }));
      }, 10000);
    });

    newSocket.on('csv_error', (data) => {
      setGenerators(prev => ({
        ...prev,
        [data.type]: {
          ...prev[data.type],
          message: { type: 'error', text: data.error || 'Es ist ein Fehler aufgetreten.' },
          isProcessing: false
        }
      }));
      setTimeout(() => {
        setGenerators(prev => ({
          ...prev,
          [data.type]: { ...prev[data.type], message: null }
        }));
      }, 10000);
    });

    setSocket(newSocket);

    return () => {
      newSocket.disconnect();
    };
  }, [apiUrl]);

  const loadSavedTerms = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/csvgenerator/terms`, {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setGenerators(prev => ({
          ...prev,
          iservbuecherei: { ...prev.iservbuecherei, terms: data.terms_buecherei || '' },
          moodle: { ...prev.moodle, terms: data.terms_moodle || '' }
        }));
      }
    } catch (error) {
      console.error('Failed to load saved terms:', error);
    }
  };

  const handleFileChange = (type, file) => {
    setGenerators(prev => ({
      ...prev,
      [type]: { ...prev[type], file, message: null }
    }));
  };

  const handleTermsChange = (type, terms) => {
    setGenerators(prev => ({
      ...prev,
      [type]: { ...prev[type], terms }
    }));
  };

  const handleSubmit = (type, socketEvent) => {
    const generator = generators[type];
    
    if (!generator.file) {
      setGenerators(prev => ({
        ...prev,
        [type]: {
          ...prev[type],
          message: { type: 'error', text: 'Bitte eine Datei auswählen.' }
        }
      }));
      return;
    }

    if (!socket) {
      setGenerators(prev => ({
        ...prev,
        [type]: {
          ...prev[type],
          message: { type: 'error', text: 'Keine Verbindung zum Server.' }
        }
      }));
      return;
    }

    setGenerators(prev => ({
      ...prev,
      [type]: { ...prev[type], isProcessing: true, message: null }
    }));

    const reader = new FileReader();
    
    reader.onload = () => {
      const eventData = {
        filename: generator.file.name,
        type: type
      };

      if (type === 'anmeldedaten') {
        eventData.content = reader.result.split(',')[1]; // strip base64 header
        eventData.terms = '';
      } else {
        eventData.content = reader.result;
        eventData.terms = generator.terms;
      }

      socket.emit(socketEvent, eventData);
    };

    reader.onerror = () => {
      setGenerators(prev => ({
        ...prev,
        [type]: {
          ...prev[type],
          message: { type: 'error', text: 'Fehler beim Lesen der Datei.' },
          isProcessing: false
        }
      }));
    };

    if (type === 'anmeldedaten') {
      reader.readAsDataURL(generator.file);
    } else {
      reader.readAsText(generator.file);
    }
  };

  // Check if user has required roles
  if (!hasPermission('csvgenerator.use')) {
    return (
      <PageContainer title="CSV / Excel Dateien erstellen">
        <MessageBox message="Sie haben keine Berechtigung, auf dieses Modul zuzugreifen." type="error" />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="CSV / Excel Dateien erstellen">
      <Card variant="header" title="CSV / Excel Dateien erstellen">
      </Card>
      <div className="grid-lg">
        {/* Lehrerimport Schulbücher-Modul */}
        <Card variant="section">
            
              <h2>Lehrerimport Schulbücher-Modul</h2>
            <div className="tool-header"></div>
          {generators.iservbuecherei.message && (
            <MessageBox
              message={generators.iservbuecherei.message.text}
              type={generators.iservbuecherei.message.type}
            >
              {generators.iservbuecherei.message.link && (
                <a href={`${apiUrl}${generators.iservbuecherei.message.link}`} download>
                  Datei herunterladen
                </a>
              )}
            </MessageBox>
          )}
          <Form
            onSubmit={() => handleSubmit('iservbuecherei', 'generate_iserv_csv')}
            className="csvgen-form"
          >
            <Card variant="section">
              <FormGroup hint="Einträge mit folgenden Begriffen automatisch entfernen:">
                <TextInput
                  placeholder="Begriffe mit Komma getrennt eingeben"
                  value={generators.iservbuecherei.terms}
                  onChange={(e) => handleTermsChange('iservbuecherei', e.target.value)}
                  disabled={generators.iservbuecherei.isProcessing}
                  fullWidth
                />
              </FormGroup>
              <FormGroup>
                <InputFile
                  allowedFormats={[".csv"]}
                  onChange={(e) => handleFileChange('iservbuecherei', e.target.files[0])}
                  disabled={generators.iservbuecherei.isProcessing}
                />
              </FormGroup>
            </Card>
            <div className="csvgen-form-footer">
              <Button
                type="submit"
                size="lg"
                loading={generators.iservbuecherei.isProcessing}
                disabled={generators.iservbuecherei.isProcessing}
              >
                {generators.iservbuecherei.isProcessing ? 'Verarbeite...' : 'CSV erstellen'}
              </Button>
            </div>
          </Form>
        </Card>

      {/* Moodle Importdatei erstellen */}
      <Card variant="section">
          <h2>Moodle Importdatei erstellen</h2>
          <div className="tool-header"/>
        {generators.moodle.message && (
          <MessageBox
            message={generators.moodle.message.text}
            type={generators.moodle.message.type}
          >
            {generators.moodle.message.link && (
              <a href={`${apiUrl}${generators.moodle.message.link}`} download>
                Datei herunterladen
              </a>
            )}
          </MessageBox>
        )}
        <Form
          onSubmit={() => handleSubmit('moodle', 'generate_moodle_csv')}
          className="csvgen-form"
        >
          <Card variant="section">
            <FormGroup hint="Einträge mit folgenden Begriffen automatisch entfernen:">
              <TextInput
                placeholder="Begriffe mit Komma getrennt eingeben"
                value={generators.moodle.terms}
                onChange={(e) => handleTermsChange('moodle', e.target.value)}
                disabled={generators.moodle.isProcessing}
                fullWidth
              />
            </FormGroup>
            <FormGroup>
              <InputFile
                allowedFormats={[".csv"]}
                onChange={(e) => handleFileChange('moodle', e.target.files[0])}
                disabled={generators.moodle.isProcessing}
              />
            </FormGroup>
          </Card>
          <div className="csvgen-form-footer">
            <Button
              type="submit"
              size="lg"
              loading={generators.moodle.isProcessing}
              disabled={generators.moodle.isProcessing}
            >
              {generators.moodle.isProcessing ? 'Verarbeite...' : 'CSV erstellen'}
            </Button>
          </div>
        </Form>
      </Card>

      {/* 5. Klassen Anmeldedaten */}
      <Card variant="section">
          
        <h2>5. Klassen Anmeldedaten</h2>
        <div className="tool-header"/>
        {generators.anmeldedaten.message && (
          <MessageBox
            message={generators.anmeldedaten.message.text}
            type={generators.anmeldedaten.message.type}
          >
            {generators.anmeldedaten.message.link && (
              <a href={`${apiUrl}${generators.anmeldedaten.message.link}`} download>
                Datei herunterladen
              </a>
            )}
          </MessageBox>
        )}
        <Form
          onSubmit={() => handleSubmit('anmeldedaten', 'generate_anmeldedaten_csv')}
          className="csvgen-form"
        >
          <Card variant="section">
            <FormGroup>
              <InputFile
                allowedFormats={[".xlsx", ".xls"]}
                onChange={(e) => handleFileChange('anmeldedaten', e.target.files[0])}
                disabled={generators.anmeldedaten.isProcessing}
              />
            </FormGroup>
          </Card>
          <div className="csvgen-form-footer">
            <Button
              type="submit"
              size="lg"
              loading={generators.anmeldedaten.isProcessing}
              disabled={generators.anmeldedaten.isProcessing}
            >
              {generators.anmeldedaten.isProcessing ? 'Verarbeite...' : 'Excel erstellen'}
            </Button>
          </div>
        </Form>
      </Card>
      </div>
    </PageContainer>
  );
}

export default CSVGeneratorDashboard;

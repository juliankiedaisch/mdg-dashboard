import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import QRCodeStyling from 'qr-code-styling';
import api from '../../utils/api';
import { PageContainer, Card, Button, TextInput, Form, StatCard } from '../../components/shared';
import './TeacherTools.css';

function TeacherTools() {
  const navigate = useNavigate();
  const { hasPermission } = useUser();
  const [qrUrl, setQrUrl] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [qrCode, setQrCode] = useState(null);
  const [currentColor, setCurrentColor] = useState('#001d1d');
  const [hasImage, setHasImage] = useState(false);
  const [wcCount, setWcCount] = useState(null);
  const qrRef = useRef(null);

  useEffect(() => {
    if (hasPermission('teachertools.wordcloud')) {
      api.get('/api/teachertools/wordcloud/count')
        .then(res => setWcCount(res.data))
        .catch(() => {});
    }
  }, [hasPermission]);

  const presetColors = [
    { name: 'black', value: '#001d1d' },
    { name: 'blue', value: '#00ced1' },
    { name: 'red', value: '#ff2d55' },
    { name: 'green', value: '#47ba7a' }
  ];

  const handleGenerateQR = (e) => {
    e?.preventDefault();
    
    const trimmedUrl = qrUrl.trim();
    if (trimmedUrl === '') return;

    // Create new QR code instance
    const qrOptions = {
      width: 1000,
      height: 1000,
      type: 'svg',
      data: trimmedUrl,
      image: '',
      dotsOptions: {
        color: currentColor,
        type: 'rounded'
      },
      backgroundOptions: {
        color: '#ffffff',
      },
      imageOptions: {
        crossOrigin: 'anonymous',
        margin: 20
      }
    };

    const qr = new QRCodeStyling(qrOptions);
    setQrCode(qr);
    setShowModal(true);
  };

  useEffect(() => {
    if (qrCode && qrRef.current && showModal) {
      // Clear previous QR code
      qrRef.current.innerHTML = '';
      qrCode.append(qrRef.current);
      
      // Set viewBox for proper scaling
      const svg = qrRef.current.querySelector('svg');
      if (svg) {
        svg.setAttribute('viewBox', '0 0 1000 1000');
        svg.setAttribute('preserveAspectRatio', 'xMinYMin meet');
      }
    }
  }, [qrCode, showModal]);

  const handleColorChange = (color) => {
    setCurrentColor(color);
    if (qrCode) {
      qrCode.update({
        dotsOptions: {
          color: color,
          type: 'rounded'
        }
      });
      
      // Update viewBox after color change
      const svg = qrRef.current?.querySelector('svg');
      if (svg) {
        svg.setAttribute('viewBox', '0 0 1000 1000');
        svg.setAttribute('preserveAspectRatio', 'xMinYMin meet');
      }
    }
  };

  const handleCustomColorChange = (e) => {
    handleColorChange(e.target.value);
  };

  const handleImageUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onloadend = (event) => {
      const img = new Image();
      img.src = event.target.result;
      img.onload = () => {
        let imageData = event.target.result;
        
        // Resize image if too large
        if (img.width > 500) {
          const canvas = document.createElement('canvas');
          const ratio = img.width / img.height;
          const width = 500;
          const height = 500 / ratio;
          canvas.width = width;
          canvas.height = height;
          canvas.getContext('2d').drawImage(img, 0, 0, width, height);
          imageData = canvas.toDataURL('image/png');
        }

        if (qrCode) {
          qrCode.update({ image: imageData });
          setHasImage(true);
          
          // Update viewBox after image change
          const svg = qrRef.current?.querySelector('svg');
          if (svg) {
            svg.setAttribute('viewBox', '0 0 1000 1000');
            svg.setAttribute('preserveAspectRatio', 'xMinYMin meet');
          }
        }
      };
    };
    reader.readAsDataURL(file);
    e.target.value = ''; // Reset file input
  };

  const handleRemoveImage = () => {
    if (qrCode) {
      qrCode.update({ image: '' });
      setHasImage(false);
      
      // Update viewBox after image removal
      const svg = qrRef.current?.querySelector('svg');
      if (svg) {
        svg.setAttribute('viewBox', '0 0 1000 1000');
        svg.setAttribute('preserveAspectRatio', 'xMinYMin meet');
      }
    }
  };

  const handleDownload = () => {
    if (qrCode) {
      qrCode.download({ name: 'code-qr', extension: 'png' });
    }
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setHasImage(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleGenerateQR(e);
    }
  };

  return (
    <PageContainer>
      <Card variant="header" title="Tools für den Unterricht" />

        <div className="grid-lg">
          { hasPermission('teachertools.qr-code') && (
            <Card>
              <h2>QR-Code erstellen</h2>
            <div className="tool-header">
            </div>
            <Form onSubmit={handleGenerateQR} className="teachertools-form">
              <p className="anmerkung">Url für den QR-Code:</p>
              <TextInput
                id="teachertools_qr_url"
                value={qrUrl}
                onChange={(e) => setQrUrl(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="https://example.com"
                fullWidth
              />
              <Button type="submit" id="teachertools_qr_submit" className="teachertools-button" >
                QR Code erstellen
              </Button>
            </Form>
        </Card>
          )}

          { hasPermission('teachertools.wordcloud') && (
        <Card>
          
          <h2>Wortwolke</h2>
          <div className="tool-header"></div>
          <Form className="teachertools-form">
            <div className="teachertools-wc-stats">
              <StatCard
                value={wcCount?.active_count ?? '–'}
                label="Aktive Wortwolken"
                variant="info"
                darkbackground={true}
              />
              <StatCard
                value={wcCount?.count ?? '–'}
                label="Gesamt erstellt"
                variant="default"
                darkbackground={true}
              />
            </div>
          <Button
            variant="primary"
            className="teachertools-button"
            onClick={() => navigate('/teachertools/wordcloud')}
          >
            Wortwolken verwalten
          </Button>
          </Form>
        </Card>
        )}
      </div>
          
      {showModal && hasPermission('teachertools.qr-code') && (
        <div
          id="teachertools-qr-modal"
          className="teachertools-qr-modal show"
          tabIndex="-1"
        >
          <div
            id="teachertools-qr-modal-content"
            className="teachertools-qr-modal-content"
            role="dialog"
          >
            <header>
              <span className="teachertools-qr-title">QR Code</span>
              <span
                id="teachertools-qr-close"
                className="teachertools-qr-close"
                role="button"
                tabIndex="-1"
                onClick={handleCloseModal}
                onKeyDown={(e) => e.key === 'Enter' && handleCloseModal()}
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="black" width="24px" height="24px">
                  <path d="M0 0h24v24H0z" fill="none"/>
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
              </span>
            </header>

            <div className="teachertools-qr-modal-background">
              <div className="teachertools-qr-modal-inner-content">
                <div id="teachertools-qr-code" ref={qrRef}></div>
                <div className="teachertools-qr-colors">
                  {presetColors.map((color) => (
                    <span
                      key={color.name}
                      className={`teachertools-qr-color ${color.name}`}
                      role="button"
                      tabIndex="-1"
                      data-color={color.value}
                      onClick={() => handleColorChange(color.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleColorChange(color.value)}
                    />
                  ))}
                  <span
                    id="teachertools-qr-color-selection"
                    role="button"
                    tabIndex="-1"
                    title="Farbe auswählen"
                  >
                    <label htmlFor="teachertools-qr-color">
                      <svg xmlns="http://www.w3.org/2000/svg" height="36px" viewBox="0 0 24 24" width="36px" fill="#000000">
                        <path d="M0 0h24v24H0z" fill="none"/>
                        <path d="M20.71 5.63l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-3.12 3.12-1.93-1.91-1.41 1.41 1.42 1.42L3 16.25V21h4.75l8.92-8.92 1.42 1.42 1.41-1.41-1.92-1.92 3.12-3.12c.4-.4.4-1.03.01-1.42zM6.92 19L5 17.08l8.06-8.06 1.92 1.92L6.92 19z"/>
                      </svg>
                    </label>
                    <input
                      type="color"
                      id="teachertools-qr-color"
                      value={currentColor}
                      onChange={handleCustomColorChange}
                    />
                  </span>
                  <span
                    id="teachertools-qr-image-selection"
                    role="button"
                    tabIndex="-1"
                    title="Bild in der Mitte auswählen"
                  >
                    <label htmlFor="teachertools-qr-image">
                      <svg xmlns="http://www.w3.org/2000/svg" height="36px" viewBox="0 0 24 24" width="36px" fill="#000000">
                        <path d="M0 0h24v24H0z" fill="none"/>
                        <path d="M19 7v2.99s-1.99.01-2 0V7h-3s.01-1.99 0-2h3V2h2v3h3v2h-3zm-3 4V8h-3V5H5c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-8h-3zM5 19l3-4 2 3 3-4 4 5H5z"/>
                      </svg>
                    </label>
                    <input
                      type="file"
                      id="teachertools-qr-image"
                      accept=".png, .jpeg, .jpg, .gif"
                      onChange={handleImageUpload}
                    />
                  </span>
                  <span
                    id="teachertools-qr-image-remove"
                    className={hasImage ? 'visible' : ''}
                    role="button"
                    tabIndex="-1"
                    title="Bild entfernen"
                    onClick={handleRemoveImage}
                    onKeyDown={(e) => e.key === 'Enter' && handleRemoveImage()}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" height="36px" viewBox="0 0 24 24" width="36px" fill="#ff6259">
                      <path d="M0 0h24v24H0z" fill="none"/>
                      <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                  </span>
                </div>
                <div className="teachertools-qr-actions">
                  <Button
                    id="teachertools-qr-download-submit"
                    tabIndex="-1"
                    onClick={handleDownload}
                    onKeyDown={(e) => e.key === 'Enter' && handleDownload()}
                  >
                    Download
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
}

export default TeacherTools;

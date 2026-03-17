import { useNavigate } from 'react-router-dom';
import { Button } from '../components/shared';

function NotAllowed() {
  const navigate = useNavigate();

  return (
    <div className="modal-overlay" style={{ display: 'flex' }}>
      <div className="modal-content">
        <h2>Zugriff verweigert</h2>
        <p>Sie haben keinen Zugriff auf diesen Bereich oder sind nicht angemeldet.</p>
        <p>Gehen Sie zurück zur Hauptseite, um sich anzumelden.</p>
        <Button variant="secondary" onClick={() => navigate('/')}>
          Zur Hauptseite zurückkehren
        </Button>
      </div>
    </div>
  );
}

export default NotAllowed;

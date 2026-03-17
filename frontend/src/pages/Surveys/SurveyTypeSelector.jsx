// SurveyTypeSelector
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import { PageContainer, Card, Button, MessageBox } from '../../components/shared';
import './Surveys.css';

/**
 * Survey type selection page — permission-gated per type.
 * Only shows survey types the user is allowed to manage.
 */
const SurveyTypeSelector = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { hasPermission } = useUser();
  const isTemplate = searchParams.get('template') === '1';

  const canManageNormal = hasPermission(['surveys.manage.all', 'surveys.normal.manage']);
  const canManageSpecial = hasPermission(['surveys.manage.all', 'surveys.special.manage']);

  if (!canManageNormal && !canManageSpecial) {
    return (
      <PageContainer>
        <Card variant="header" title="Keine Berechtigung">
          <Button variant="secondary" onClick={() => navigate('/surveys')}>← Zurück</Button>
        </Card>
        <MessageBox text="Sie haben keine Berechtigung, Umfragen zu erstellen." type="error" />
      </PageContainer>
    );
  }

  if (isTemplate) {
    // Template creation: let user choose between normal and evaluation template
    return (
      <PageContainer>
        <Card variant="header" title="Neue Vorlage erstellen">
          <Button variant="secondary" onClick={() => navigate('/surveys')}>
            ← Zurück
          </Button>
        </Card>

        <div className="survey-type-grid">
          {canManageNormal && (
            <Card hoverable onClick={() => navigate('/surveys/new/normal?template=1')} className="survey-type-card">
              <div className="survey-type-card__icon">📋</div>
              <h2 className="survey-type-card__title">Umfragevorlage</h2>
              <p className="survey-type-card__desc">
                Erstellen Sie eine Vorlage für normale Umfragen. Diese kann später
                als Basis für neue Umfragen verwendet werden.
              </p>
              <Button variant="primary" style={{ marginTop: 'auto' }}>
                Umfragevorlage erstellen →
              </Button>
            </Card>
          )}

          {canManageSpecial && (
            <Card hoverable onClick={() => navigate('/surveys/new/evaluation-template')} className="survey-type-card">
              <div className="survey-type-card__icon">🎓</div>
              <h2 className="survey-type-card__title">Bewertungsvorlage</h2>
              <p className="survey-type-card__desc">
                Erstellen Sie eine Bewertungsvorlage für Spezialumfragen (Lehrerbewertung).
                Inkl. Excel-Export-Konfiguration pro Frage.
              </p>
              <Button variant="primary" style={{ marginTop: 'auto' }}>
                Bewertungsvorlage erstellen →
              </Button>
            </Card>
          )}
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <Card variant="header" title="Neue Umfrage erstellen">
        <Button variant="secondary" onClick={() => navigate('/surveys')}>
          ← Zurück
        </Button>
      </Card>

      <div className="survey-type-grid">
        {canManageNormal && (
          <Card hoverable onClick={() => navigate('/surveys/new/normal')} className="survey-type-card">
            <div className="survey-type-card__icon">📋</div>
            <h2 className="survey-type-card__title">Normale Umfrage</h2>
            <p className="survey-type-card__desc">
              Erstellen Sie eine standardmäßige Umfrage mit verschiedenen Fragetypen.
              Teilnehmer beantworten die Fragen einzeln.
            </p>
            <Button variant="primary" style={{ marginTop: 'auto' }}>
              Umfrage erstellen →
            </Button>
          </Card>
        )}

        {canManageSpecial && (
          <Card hoverable onClick={() => navigate('/surveys/new/special')} className="survey-type-card">
          <div className="survey-type-card__icon">🏫</div>
          <h2 className="survey-type-card__title">Klassenzusammensetzung</h2>
          <p className="survey-type-card__desc">
            Neue Klassenzusammensetzung: 3-Phasen-Workflow mit Schülerwünschen,
            Elternbestätigung und Lehrkraftbewertung. Erfordert CSV-Upload.
          </p>
          <Button variant="primary" style={{ marginTop: 'auto' }}>
            Umfrage erstellen →
          </Button>
          </Card>
        )}
      </div>
    </PageContainer>
  );
};

export default SurveyTypeSelector;

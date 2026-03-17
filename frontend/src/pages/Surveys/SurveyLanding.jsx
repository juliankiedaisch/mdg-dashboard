import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import api from '../../utils/api';
import {
  PageContainer, Card, Button, MessageBox, Spinner, Tabs,
} from '../../components/shared';
import ShareModal from './components/ShareModal';
import { STATUS_LABELS, STATUS_LABELS_SPECIAL } from './surveyConstants';
import useAutoMessage from './useAutoMessage';
import './Surveys.css';

/**
 * Tab-based Survey landing page.
 *
 * Top-level tabs:
 *   1. Teilnehmen     – active surveys the user can participate in
 *   2. Meine Umfragen – surveys the user created (active / draft / closed)
 *   3. Vorlagen       – survey templates (normal + evaluation)
 *   4. Archiviert     – archived surveys
 *   5. Papierkorb     – soft-deleted surveys (only with surveys.delete.permanently)
 *
 * Creation buttons shown based on type-specific permissions.
 */

const SurveyLanding = () => {
  const { hasPermission } = useUser();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // ── Active tab ──
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'participate');

  // ── Permission flags ──
  const canManage = hasPermission([
    'surveys.manage.all',
    'surveys.normal.manage',
    'surveys.special.manage',
  ]);
  const canManageNormal = hasPermission(['surveys.manage.all', 'surveys.normal.manage']);
  const canManageSpecial = hasPermission(['surveys.manage.all', 'surveys.special.manage']);
  const canDeletePermanently = hasPermission(['surveys.delete.permanently', 'surveys.admin']);

  // ── Build tabs list (permission-gated) ──
  const tabs = useMemo(() => {
    const list = [{ id: 'participate', label: 'Teilnehmen' }];
    if (canManage) {
      list.push({ id: 'my-surveys', label: 'Meine Umfragen' });
      list.push({ id: 'templates', label: 'Vorlagen' });
      list.push({ id: 'archived', label: 'Archiviert' });
    }
    if (canDeletePermanently) {
      list.push({ id: 'trash', label: 'Papierkorb' });
    }
    return list;
  }, [canManage, canDeletePermanently]);

  // ── Participation state ──
  const [activeSurveys, setActiveSurveys] = useState([]);
  const [specialSurveys, setSpecialSurveys] = useState([]);
  const [loadingParticipation, setLoadingParticipation] = useState(true);

  // ── Management state (My Surveys / Templates / Archived) ──
  const [managedSurveys, setManagedSurveys] = useState([]);
  const [managedEvalTemplates, setManagedEvalTemplates] = useState([]);
  const [managedSpecial, setManagedSpecial] = useState([]);
  const [loadingManagement, setLoadingManagement] = useState(false);

  // ── Trash state ──
  const [trashSurveys, setTrashSurveys] = useState([]);
  const [loadingTrash, setLoadingTrash] = useState(false);

  // ── Shared UI state ──
  const [message, setMessage] = useAutoMessage();
  const [shareTarget, setShareTarget] = useState(null);

  // ── Tab change handler ──
  const handleTabChange = useCallback((tabId) => {
    setActiveTab(tabId);
    setSearchParams({ tab: tabId }, { replace: true });
  }, [setSearchParams]);

  // ── Data loading ──
  useEffect(() => {
    if (activeTab === 'participate') {
      loadParticipation();
    } else if (activeTab === 'my-surveys' || activeTab === 'templates' || activeTab === 'archived') {
      loadManagement();
    } else if (activeTab === 'trash') {
      loadTrash();
    }
  }, [activeTab]);

  const loadParticipation = async () => {
    try {
      setLoadingParticipation(true);
      const [surveysRes, specialRes] = await Promise.all([
        api.get('/api/surveys/active'),
        api.get('/api/surveys/special/active'),
      ]);
      setActiveSurveys(surveysRes.data.surveys || []);
      setSpecialSurveys(specialRes.data.surveys || []);
    } catch (error) {
      console.error('Error loading participation surveys:', error);
      setMessage({ text: 'Fehler beim Laden der Umfragen', type: 'error' });
    } finally {
      setLoadingParticipation(false);
    }
  };

  const loadManagement = async () => {
    // Map tab id → API tab param
    const tabMap = { 'my-surveys': 'active', templates: 'templates', archived: 'archived' };
    const apiTab = tabMap[activeTab] || 'active';
    try {
      setLoadingManagement(true);
      const loadSpecial = apiTab === 'active' || apiTab === 'archived';
      const isTemplateTab = apiTab === 'templates';
      const [surveyRes, evalTplRes, specialRes] = await Promise.all([
        api.get(`/api/surveys?tab=${apiTab}${isTemplateTab ? '&template_type=normal' : ''}`),
        isTemplateTab
          ? api.get('/api/surveys?tab=templates&template_type=teacher_evaluation')
          : Promise.resolve({ data: { surveys: [] } }),
        loadSpecial
          ? api.get(`/api/surveys/special?tab=${apiTab}`)
          : Promise.resolve({ data: { special_surveys: [] } }),
      ]);
      setManagedSurveys(surveyRes.data.surveys || []);
      setManagedEvalTemplates(isTemplateTab ? (evalTplRes.data.surveys || []) : []);
      setManagedSpecial(loadSpecial ? (specialRes.data.special_surveys || []) : []);
    } catch (error) {
      console.error('Error loading managed surveys:', error);
      setMessage({ text: 'Fehler beim Laden der verwalteten Umfragen', type: 'error' });
    } finally {
      setLoadingManagement(false);
    }
  };

  const loadTrash = async () => {
    try {
      setLoadingTrash(true);
      const res = await api.get('/api/surveys/trash');
      setTrashSurveys(res.data.surveys || []);
    } catch (error) {
      console.error('Error loading trash:', error);
      setMessage({ text: 'Fehler beim Laden des Papierkorbs', type: 'error' });
    } finally {
      setLoadingTrash(false);
    }
  };

  // ── Trash actions ──
  const handleRestore = async (survey) => {
    try {
      await api.post(`/api/surveys/admin/deleted/${survey.id}/restore?type=${survey.survey_type === 'special' ? 'special' : 'normal'}`);
      setMessage({ text: 'Umfrage wiederhergestellt', type: 'success' });
      loadTrash();
    } catch {
      setMessage({ text: 'Fehler beim Wiederherstellen', type: 'error' });
    }
  };

  const handlePermanentDelete = async (survey) => {
    if (!window.confirm('Diese Umfrage wird endgültig gelöscht. Fortfahren?')) return;
    try {
      await api.delete(`/api/surveys/admin/deleted/${survey.id}/permanent?type=${survey.survey_type === 'special' ? 'special' : 'normal'}`);
      setMessage({ text: 'Umfrage endgültig gelöscht', type: 'success' });
      loadTrash();
    } catch {
      setMessage({ text: 'Fehler beim endgültigen Löschen', type: 'error' });
    }
  };

  // ── Helpers ──

  const formatDate = (isoString) => {
    if (!isoString) return null;
    return new Date(isoString).toLocaleDateString('de-DE', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  const getCardState = (survey) => {
    if (survey.already_responded && !survey.allow_edit_response && !survey.edit_granted) return 'responded';
    if (survey.already_responded && (survey.allow_edit_response || survey.edit_granted)) return 'editable';
    if (survey.is_expired) return 'expired';
    if (survey.not_yet_started) return 'upcoming';
    return 'open';
  };

  const handleCardClick = (survey) => {
    const state = getCardState(survey);
    if (state === 'open' || state === 'editable') {
      navigate(`/surveys/${survey.id}/participate`);
    }
  };

  // ── Participation card (normal survey) ──
  const renderParticipationCard = (survey) => {
    const state = getCardState(survey);
    return (
      <div
        key={survey.id}
        className={`survey-card survey-card--${state}`}
        onClick={() => handleCardClick(survey)}
      >
        <div className="survey-card__title">{survey.title}</div>
        {survey.description && (
          <div className="survey-card__description">{survey.description}</div>
        )}
        {(survey.starts_at || survey.ends_at) && (
          <div className="survey-card__time">
            {survey.starts_at && (
              <span className="survey-card__time-item">📅 Start: {formatDate(survey.starts_at)}</span>
            )}
            {survey.ends_at && (
              <span className="survey-card__time-item">⏰ Ende: {formatDate(survey.ends_at)}</span>
            )}
          </div>
        )}
        <div className="survey-card__meta">
          {state === 'responded' && (
            <span className="survey-card__status survey-card__status--closed">✓ Bereits teilgenommen</span>
          )}
          {state === 'editable' && (
            <span className="survey-card__status survey-card__status--active">✏️ Antwort bearbeiten</span>
          )}
          {state === 'expired' && (
            <span className="survey-card__status survey-card__status--closed">Abgelaufen</span>
          )}
          {state === 'upcoming' && (
            <span className="survey-card__status survey-card__status--draft">Noch nicht gestartet</span>
          )}
          {state === 'open' && (
            <span className="survey-card__status survey-card__status--active">Jetzt teilnehmen →</span>
          )}
        </div>
      </div>
    );
  };

  // ── Participation card (special survey) ──
  const renderSpecialParticipationCard = (ss) => {
    const roleLabels = { student: 'Schülerwünsche', parent: 'Elternbestätigung', teacher: 'Lehrerbewertung' };
    const roleLabelsShort = { student: 'Schüler/in', parent: 'Elternteil', teacher: 'Lehrkraft' };
    const phaseRoutes = { student: 'phase1', parent: 'phase2', teacher: 'phase3' };
    const isLocked = ss.locked;
    const isDone = ss.already_responded;
    const state = isLocked ? 'responded' : isDone ? 'editable' : 'open';
    return (
      <div
        key={`special-${ss.id}-${ss.role}`}
        className={`survey-card survey-card--${state}`}
        onClick={() => {
          if (!isLocked) navigate(`/surveys/special/${ss.id}/${phaseRoutes[ss.role]}`);
        }}
      >
        <div className="survey-card__title">{ss.title}</div>
        <div className="survey-card__description">{ss.description}</div>
        <div className="survey-card__meta">
          <span className="question-card__type-badge">{roleLabels[ss.role]}</span>
          <span className="question-card__type-badge">Rolle: {roleLabelsShort[ss.role]}</span>
          {ss.progress && (
            <span className="question-card__type-badge">Fortschritt: {ss.progress}</span>
          )}
          {isLocked && (
            <span className="survey-card__status survey-card__status--closed">🔒 Gesperrt</span>
          )}
          {isDone && !isLocked && (
            <span className="survey-card__status survey-card__status--active">✏️ Bearbeiten</span>
          )}
          {!isDone && !isLocked && (
            <span className="survey-card__status survey-card__status--active">Jetzt teilnehmen →</span>
          )}
        </div>
      </div>
    );
  };

  // ── Management card (normal survey / template) ──
  const renderManagedCard = (survey) => {
    const isTemplate = survey.is_template;
    const isOwner = survey.is_owner !== undefined ? survey.is_owner : true;
    const isEvalTemplate = isTemplate && survey.template_type === 'teacher_evaluation';

    return (
      <div
        key={survey.id}
        className={`survey-card ${isTemplate ? 'survey-card--template' : ''}`}
        onClick={() => {
          if (isTemplate && !isOwner) return;
          if (isEvalTemplate) {
            navigate(`/surveys/evaluation-template/${survey.id}`);
          } else {
            navigate(`/surveys/${survey.id}`);
          }
        }}
        style={isTemplate && !isOwner ? { cursor: 'default' } : undefined}
      >
        <div className="survey-card__title">
          {survey.title}
          {isTemplate && !isOwner && (
            <span className="survey-card__shared-badge">Geteilt</span>
          )}
          {isEvalTemplate && (
            <span className="survey-card__shared-badge" style={{ background: '#7c3aed', color: '#fff' }}>
              Bewertung
            </span>
          )}
        </div>
        {survey.description && (
          <div className="survey-card__description">{survey.description}</div>
        )}
        <div className="survey-card__meta">
          {isTemplate ? (
            <span className="survey-card__status survey-card__status--template">
              Vorlage · {survey.questions?.length || 0} Fragen
            </span>
          ) : (
            <>
              <span className={`survey-card__status survey-card__status--${survey.status}`}>
                {STATUS_LABELS[survey.status] || survey.status}
              </span>
              <span className="survey-card__responses">
                {survey.response_count} Antwort{survey.response_count !== 1 ? 'en' : ''}
              </span>
            </>
          )}
        </div>

        {isTemplate && !isOwner && survey.creator_name && (
          <div className="survey-card__creator">Von: {survey.creator_name}</div>
        )}

        {!isTemplate && survey.groups && survey.groups.length > 0 && (
          <div className="survey-card__groups">
            {survey.groups.map((g) => (
              <span key={g.id} className="survey-card__group-tag">{g.name}</span>
            ))}
          </div>
        )}

        {/* Template actions */}
        {isTemplate && (
          <div className="survey-card__template-actions" onClick={(e) => e.stopPropagation()}>
            {!isEvalTemplate && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate('/surveys/new/normal', { state: { fromTemplate: survey } })}
              >
                Umfrage erstellen
              </Button>
            )}
            {isEvalTemplate && isOwner && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate(`/surveys/evaluation-template/${survey.id}`)}
              >
                Bearbeiten
              </Button>
            )}
            {isOwner && (
              <Button variant="secondary" size="sm" onClick={() => setShareTarget(survey)}>
                Teilen
              </Button>
            )}
          </div>
        )}

        {/* Edit button for non-active, non-archived, non-template surveys */}
        {!isTemplate && survey.status !== 'active' && survey.status !== 'archived' && (
          <div className="survey-card__template-actions" onClick={(e) => e.stopPropagation()}>
            <Button variant="secondary" size="sm" onClick={() => navigate(`/surveys/${survey.id}/edit`)}>
              Bearbeiten
            </Button>
          </div>
        )}
      </div>
    );
  };

  // ── Management card (special survey) ──
  const renderManagedSpecialCard = (ss) => (
    <div
      key={`special-${ss.id}`}
      className="survey-card survey-card--special"
      onClick={() => navigate(`/surveys/special/${ss.id}`)}
    >
      <div className="survey-card__title">
        {ss.title}
        <span className="survey-card__shared-badge" style={{ background: '#6366f1', color: '#fff' }}>
          Spezial
        </span>
      </div>
      {ss.description && (
        <div className="survey-card__description">{ss.description}</div>
      )}
      <div className="survey-card__meta">
        <span className={`survey-card__status survey-card__status--${ss.status === 'archived' ? 'archived' : ss.status === 'completed' ? 'closed' : ss.status === 'setup' ? 'draft' : 'active'}`}>
          {STATUS_LABELS_SPECIAL[ss.status] || ss.status}
        </span>
        {ss.grade_level && (
          <span className="survey-card__responses">Stufe {ss.grade_level}</span>
        )}
      </div>
      <div className="survey-card__groups">
        {ss.student_count != null && (
          <span className="survey-card__group-tag">{ss.student_count} Schüler</span>
        )}
      </div>
    </div>
  );

  // ── Trash card ──
  const renderTrashCard = (survey) => {
    const typeLabels = { normal: 'Umfrage', template: 'Vorlage', special: 'Spezialumfrage' };
    return (
      <div key={`trash-${survey.survey_type}-${survey.id}`} className="survey-card survey-card--trash">
        <p className="question-card__type-badge">{typeLabels[survey.survey_type] || survey.survey_type}</p>
        <div className="survey-card__title">
          {survey.title}
          
        </div>
        
        {survey.description && (
          <div className="survey-card__description">{survey.description}</div>
        )}
        <div className="survey-card__meta">
          {survey.deleted_at && (
            <span className="survey-card__responses">Gelöscht: {formatDate(survey.deleted_at)}</span>
          )}
        </div>
        <div className="survey-card__template-actions" onClick={(e) => e.stopPropagation()}>
          <Button variant="primary" size="sm" onClick={() => handleRestore(survey)}>
            Wiederherstellen
          </Button>
          <Button variant="danger" size="sm" onClick={() => handlePermanentDelete(survey)}>
           Löschen
          </Button>
        </div>
      </div>
    );
  };

  // ── Tab content renderers ──

  const renderParticipateTab = () => (
    <>
      {loadingParticipation ? (
        <Spinner />
      ) : activeSurveys.length === 0 && specialSurveys.length === 0 ? (
        <div className="surveys-empty">
          <div className="surveys-empty__icon">✅</div>
          <div className="surveys-empty__text">Keine Umfragen verfügbar</div>
        </div>
      ) : (
        <>
          {specialSurveys.length > 0 && (
            <div className="surveys-grid">
              {specialSurveys.map(renderSpecialParticipationCard)}
            </div>
          )}
          {activeSurveys.length > 0 && (
            <div className="surveys-grid" style={{ marginTop: specialSurveys.length > 0 ? 'var(--space-lg)' : 0 }}>
              {activeSurveys.map(renderParticipationCard)}
            </div>
          )}
        </>
      )}
    </>
  );

  const renderManagementTab = () => {
    const isTemplateTab = activeTab === 'templates';
    const isArchivedTab = activeTab === 'archived';

    return loadingManagement ? (
      <Spinner />
    ) : (
      <>
        {/* Special surveys section (on my-surveys and archived tabs) */}
        {(activeTab === 'my-surveys' || isArchivedTab) && managedSpecial.length > 0 && canManageSpecial && (
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: '16px', fontWeight: 600 }}>
              Klassenzusammensetzung
            </h3>
            <div className="surveys-grid">
              {managedSpecial.map(renderManagedSpecialCard)}
            </div>
          </div>
        )}

        {/* Normal managed surveys */}
        {managedSurveys.length === 0 && managedSpecial.length === 0 && managedEvalTemplates.length === 0 ? (
          <div className="surveys-empty">
            <div className="surveys-empty__icon">
              {isTemplateTab ? '📄' : isArchivedTab ? '📦' : '📋'}
            </div>
            <div className="surveys-empty__text">
              {isTemplateTab
                ? 'Keine Vorlagen vorhanden'
                : isArchivedTab
                ? 'Keine archivierten Umfragen'
                : 'Noch keine Umfragen erstellt'}
            </div>
            {activeTab === 'my-surveys' && canManageNormal && (
              <Button variant="primary" onClick={() => navigate('/surveys/new')}>
                Erste Umfrage erstellen
              </Button>
            )}
            {isTemplateTab && canManageNormal && (
              <Button variant="secondary" onClick={() => navigate('/surveys/new/normal?template=1')}>
                Erste Vorlage erstellen
              </Button>
            )}
          </div>
        ) : managedSurveys.length > 0 || managedEvalTemplates.length > 0 ? (
          <>
            {!isTemplateTab && managedSpecial.length > 0 && (
              <h3 style={{ margin: '0 0 12px', fontSize: '16px', fontWeight: 600 }}>
                Normale Umfragen
              </h3>
            )}
            {managedSurveys.length > 0 && (
              <>
                {isTemplateTab && managedEvalTemplates.length > 0 && (
                  <h3 style={{ margin: '0 0 12px', fontSize: '16px', fontWeight: 600 }}>
                    📋 Umfragevorlagen
                  </h3>
                )}
                <div className="surveys-grid">
                  {managedSurveys.map(renderManagedCard)}
                </div>
              </>
            )}
            {/* Evaluation templates section (templates tab only) */}
            {isTemplateTab && managedEvalTemplates.length > 0 && (
              <div style={{ marginTop: managedSurveys.length > 0 ? '24px' : 0 }}>
                <h3 style={{ margin: '0 0 12px', fontSize: '16px', fontWeight: 600 }}>
                  🎓 Bewertungsvorlagen (Klassenzusammensetzung)
                </h3>
                <div className="surveys-grid">
                  {managedEvalTemplates.map(renderManagedCard)}
                </div>
              </div>
            )}
          </>
        ) : null}
      </>
    );
  };

  const renderTrashTab = () => (
    loadingTrash ? (
      <Spinner />
    ) : trashSurveys.length === 0 ? (
      <div className="surveys-empty">
        <div className="surveys-empty__icon">🗑️</div>
        <div className="surveys-empty__text">Papierkorb ist leer</div>
      </div>
    ) : (
      <div className="surveys-grid">
        {trashSurveys.map(renderTrashCard)}
      </div>
    )
  );

  // ── Render ──
  return (
    <PageContainer>
      {/* Header with permission-gated action buttons */}
      <Card variant="header" title="Umfragen">
        {canManage && (
          <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
            {canManageNormal && (
              <>
                <Button variant="primary" onClick={() => navigate('/surveys/new')}>
                  + Neue Umfrage
                </Button>
                <Button variant="secondary" onClick={() => navigate('/surveys/new/normal?template=1')}>
                  + Vorlage
                </Button>
              </>
            )}
          </div>
        )}
      </Card>

      {message && <MessageBox text={message.text} type={message.type} />}

      {/* ── Top-level tab bar ── */}
      {canManage && (
      <Tabs
        tabs={tabs}
        activeTab={activeTab}
        onChange={handleTabChange}
        stretch={true}
        sticky
      />
      )}

      {/* ── Tab content ── */}
      <div style={{ marginTop: 'var(--space-md)' }}>
        {activeTab === 'participate' && renderParticipateTab()}
        {(activeTab === 'my-surveys' || activeTab === 'templates' || activeTab === 'archived') && renderManagementTab()}
        {activeTab === 'trash' && renderTrashTab()}
      </div>

      {/* ── Modals ── */}
      {shareTarget && (
        <ShareModal
          survey={shareTarget}
          onClose={() => setShareTarget(null)}
          onSaved={() => {
            setShareTarget(null);
            setMessage({ text: 'Freigabe aktualisiert', type: 'success' });
            loadManagement();
          }}
        />
      )}

    </PageContainer>
  );
};

export default SurveyLanding;

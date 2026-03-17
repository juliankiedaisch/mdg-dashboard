// Assistant Module - Admin Page
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import SocketService from '../../utils/socket';
import {
  PageContainer, Card, Button, Tabs, StatCard, MessageBox, Spinner,
  TextInput, SelectInput, FormGroup, Modal,
} from '../../components/shared';
import {
  getAdminStatus,
  getAdminSources,
  createAdminSource,
  updateAdminSource,
  deleteAdminSource,
  testAdminSource,
  syncAdminSource,
  getAdminModels,
  pullAdminModel,
  removeAdminModel,
  testAdminModel,
  getAdminConfig,
  setAdminConfig,
  rebuildIndex,
  purgeEmbeddings,
  getPipelineQueue,
  getAdminLogs,
  getAdminLogEventTypes,
  getAdminTags,
  createAdminTag,
  updateAdminTag,
  deleteAdminTag,
  setSourceTags,
  getVectorStats,
  getQdrantDebug,
  getQdrantDocuments,
  reconcileDocumentCounts,
  cancelAllTasks,
  cancelSingleTask,
  getPipelineEvents,
  clearPipelineEvents,
  getAdminRetrievalConfig,
  updateAdminRetrievalConfig,
  rebuildBm25Index,
  getBm25Status,
  testRetrieval,
  getScheduledSyncs,
  createScheduledSync,
  updateScheduledSync,
  deleteScheduledSync,
} from './services/assistantApi';
import './AssistantAdminPage.css';

const TABS = [
  { id: 'status', label: 'Dashboard' },
  { id: 'sources', label: 'Quellen' },
  { id: 'tags', label: 'Tags' },
  { id: 'models', label: 'Modelle' },
  { id: 'config', label: 'Konfiguration' },
  { id: 'retrieval', label: 'Retrieval' },
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'vectordb', label: 'Vector DB' },
  { id: 'logs', label: 'Logs' },
];

function AssistantAdminPage() {
  const { hasPermission } = useUser();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('status');
  const [status, setStatus] = useState(null);
  const [sources, setSources] = useState([]);
  const [models, setModels] = useState([]);
  const [config, setConfig] = useState([]);
  const [logs, setLogs] = useState([]);
  const [logPage, setLogPage] = useState(1);
  const [logTotal, setLogTotal] = useState(0);
  const [logTotalPages, setLogTotalPages] = useState(1);
  const [logHasNext, setLogHasNext] = useState(false);
  const [logHasPrev, setLogHasPrev] = useState(false);
  const [logEventTypeFilter, setLogEventTypeFilter] = useState('');
  const [logSourceFilter, setLogSourceFilter] = useState('');
  const [logEventTypes, setLogEventTypes] = useState([]);
  const [pipelineQueue, setPipelineQueue] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null); // { text, type }
  const [tags, setTags] = useState([]);

  // Retrieval config
  const [retrievalConfig, setRetrievalConfig] = useState(null);
  const [retrievalForm, setRetrievalForm] = useState({
    tag_weights: {},
    top_k: 20,
    top_k_distribution: {},
    summarization_enabled: false,
    summarization_model: '',
    pipeline_config: {
      reranker_enabled: true,
      reranker_model: '',
      initial_retrieval_k: 75,
      final_context_k: 10,
      hybrid_enabled: true,
      vector_weight: 0.7,
      keyword_weight: 0.3,
      parent_child_enabled: false,
      dedup_enabled: true,
      dedup_threshold: 0.92,
    },
  });
  const [newWeightKey, setNewWeightKey] = useState('');
  const [newDistKey, setNewDistKey] = useState('');

  // Diagnostics
  const [diagQuery, setDiagQuery] = useState('');
  const [diagResults, setDiagResults] = useState(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [bm25Status, setBm25Status] = useState(null);
  const [bm25Rebuilding, setBm25Rebuilding] = useState(false);

  // Tag form
  const [tagForm, setTagForm] = useState({ name: '', description: '' });
  const [editingTagId, setEditingTagId] = useState(null);
  const [newTagModal, setNewTagModal] = useState({ open: false, title: '', onConfirm: null});
  const showNewTagModal = (title = 'Tag hinzufügen', onConfirm) =>
  setNewTagModal({ open: true, title, onConfirm});
  const closeNewTagModal = () => setNewTagModal(s => ({ ...s, open: false, onConfirm: null }));

  // Source form
  const [showSourceForm, setShowSourceForm] = useState(false);
  const [sourceForm, setSourceForm] = useState({
    name: '', source_type: 'bookstack', enabled: true,
    config: { base_url: '', token_id: '', token_secret: '', directory: '', recursive: true },
  });
  const [editingSourceId, setEditingSourceId] = useState(null);

  // Model pull
  const [pullModelName, setPullModelName] = useState('');

  // Config form
  const [configForm, setConfigForm] = useState({ key: '', value: '', description: '' });

  // Vector DB debug
  const [vectorStats, setVectorStats] = useState(null);
  const [qdrantDebug, setQdrantDebug] = useState(null);
  const [vectorDbLoading, setVectorDbLoading] = useState(false);

  // Vector DB document browser
  const [qdrantDocs, setQdrantDocs] = useState([]);
  const [qdrantDocsTotal, setQdrantDocsTotal] = useState(0);
  const [qdrantDocsOffset, setQdrantDocsOffset] = useState(null);
  const [qdrantDocsNextOffset, setQdrantDocsNextOffset] = useState(null);
  const [qdrantDocsOffsetHistory, setQdrantDocsOffsetHistory] = useState([]);
  const [qdrantDocsPageSize, setQdrantDocsPageSize] = useState(50);
  const [qdrantDocsFilter, setQdrantDocsFilter] = useState({ source_id: '', tag: '', search: '' });
  const [qdrantDocsLoading, setQdrantDocsLoading] = useState(false);
  const [expandedDocId, setExpandedDocId] = useState(null);

  // Confirm modal (replaces all native confirm() dialogs)
  const [confirmModal, setConfirmModal] = useState({ open: false, title: '', message: '', onConfirm: null, danger: true });
  const showConfirm = (message, onConfirm, title = 'Bestätigung') =>
    setConfirmModal({ open: true, title, message, onConfirm, danger: true });
  const closeConfirm = () => setConfirmModal(s => ({ ...s, open: false, onConfirm: null }));

  // Scheduled syncs
  const [scheduledSyncs, setScheduledSyncs] = useState([]);
  const [showScheduleForm, setShowScheduleForm] = useState(false);
  const [scheduleForm, setScheduleForm] = useState({
    source_id: '', frequency: 'daily', time_of_day: '06:00', day_of_week: 0,
  });

  // Pipeline live activity feed (WebSocket + persisted history)
  const [pipelineEvents, setPipelineEvents] = useState([]);
  const [pipelineConnected, setPipelineConnected] = useState(false);
  const [pipelineHistoryLoaded, setPipelineHistoryLoaded] = useState(false);
  const pipelineFeedRef = useRef(null);
  // Track seen event ids (DB pk) to avoid duplicates between history and live stream
  const seenEventIds = useRef(new Set());

  // Load persisted history from the DB once on mount
  useEffect(() => {
    if (!hasPermission('assistant.manage')) return;
    getPipelineEvents({ limit: 500 })
      .then((res) => {
        const events = res.data?.events ?? [];
        seenEventIds.current = new Set(events.map((e) => e.id));
        // Show newest events first
        setPipelineEvents(events.map((e) => ({ ...e, _id: e.id ?? `h-${e.timestamp}` })).reverse());
        setPipelineHistoryLoaded(true);
      })
      .catch(() => {
        // history load failure is non-fatal; live feed still works
        setPipelineHistoryLoaded(true);
      });
  }, []);

  useEffect(() => {
    if (!hasPermission('assistant.manage')) return;
    loadTab(activeTab);
  }, [activeTab]);

  // Reload logs when page changes
  useEffect(() => {
    if (!hasPermission('assistant.manage')) return;
    if (activeTab === 'logs') loadTab('logs');
  }, [logPage]);

  // WebSocket listener for pipeline progress events
  useEffect(() => {
    if (!hasPermission('assistant.manage')) return;

    const socket = SocketService.connect('/main');
    setPipelineConnected(SocketService.isConnected);

    const handleProgress = (data) => {
      setPipelineEvents((prev) => {
        // Deduplicate: if the event has a DB id and we've already seen it, skip
        if (data.id != null && seenEventIds.current.has(data.id)) {
          return prev;
        }
        if (data.id != null) {
          seenEventIds.current.add(data.id);
        }
        // Prepend newest events at the top
        const next = [{ ...data, _id: data.id ?? Date.now() + Math.random() }, ...prev];
        // Keep last 500 events in memory
        return next.length > 500 ? next.slice(0, 500) : next;
      });
    };

    const handleConnect = () => setPipelineConnected(true);
    const handleDisconnect = () => setPipelineConnected(false);

    SocketService.on('assistant_progress', handleProgress);
    SocketService.on('connect', handleConnect);
    SocketService.on('disconnect', handleDisconnect);

    return () => {
      SocketService.off('assistant_progress', handleProgress);
      SocketService.off('connect', handleConnect);
      SocketService.off('disconnect', handleDisconnect);
    };
  }, []);

  // No auto-scroll needed — newest events are already at the top

  // ── Permission guard ─────────────────────────────────────────────
  if (!hasPermission('assistant.manage')) {
    return (
      <PageContainer>
        <Card variant="header" title="MDG Assistent Verwaltung">
          <Button variant="secondary" onClick={() => navigate('/assistant')}>Zurück</Button>
        </Card>
        <MessageBox
          message="Sie haben keine Berechtigung für die Assistenten-Verwaltung."
          type="error"
        />
      </PageContainer>
    );
  }

  // ── Vector DB document browser helpers ───────────────────────────
  const loadQdrantDocuments = async (offset = null, resetHistory = false) => {
    setQdrantDocsLoading(true);
    try {
      const params = {
        limit: qdrantDocsPageSize,
        offset: offset ?? undefined,
        source_id: qdrantDocsFilter.source_id || undefined,
        tag: qdrantDocsFilter.tag || undefined,
        search: qdrantDocsFilter.search || undefined,
      };
      const res = await getQdrantDocuments(params);
      setQdrantDocs(res.data.documents || []);
      setQdrantDocsTotal(res.data.total ?? 0);
      setQdrantDocsNextOffset(res.data.next_offset ?? null);
      setQdrantDocsOffset(offset);
      if (resetHistory) {
        setQdrantDocsOffsetHistory([]);
      }
    } catch (err) {
      console.error('Failed to load Qdrant documents:', err);
    }
    setQdrantDocsLoading(false);
  };

  const handleDocsNextPage = () => {
    if (qdrantDocsNextOffset == null) return;
    setQdrantDocsOffsetHistory((prev) => [...prev, qdrantDocsOffset]);
    loadQdrantDocuments(qdrantDocsNextOffset);
  };

  const handleDocsPrevPage = () => {
    if (qdrantDocsOffsetHistory.length === 0) return;
    const prev = [...qdrantDocsOffsetHistory];
    const prevOffset = prev.pop();
    setQdrantDocsOffsetHistory(prev);
    loadQdrantDocuments(prevOffset);
  };

  const handleDocsFilterApply = () => {
    loadQdrantDocuments(null, true);
  };

  const handleDocsFilterReset = () => {
    setQdrantDocsFilter({ source_id: '', tag: '', search: '' });
    // Trigger load after reset – use empty filters
    setQdrantDocsLoading(true);
    getQdrantDocuments({ limit: qdrantDocsPageSize })
      .then((res) => {
        setQdrantDocs(res.data.documents || []);
        setQdrantDocsTotal(res.data.total ?? 0);
        setQdrantDocsNextOffset(res.data.next_offset ?? null);
        setQdrantDocsOffset(null);
        setQdrantDocsOffsetHistory([]);
      })
      .catch(console.error)
      .finally(() => setQdrantDocsLoading(false));
  };

  const loadTab = async (tab) => {
    setLoading(true);
    try {
      if (tab === 'status') {
        const [statusRes, queueRes] = await Promise.all([getAdminStatus(), getPipelineQueue()]);
        setStatus(statusRes.data);
        setPipelineQueue(queueRes.data);
      } else if (tab === 'sources') {
        const [srcRes, tagRes] = await Promise.all([getAdminSources(), getAdminTags()]);
        setSources(srcRes.data.sources || []);
        setTags(tagRes.data.tags || []);
      } else if (tab === 'tags') {
        const res = await getAdminTags();
        setTags(res.data.tags || []);
      } else if (tab === 'models') {
        const res = await getAdminModels();
        setModels(res.data.models || []);
      } else if (tab === 'config') {
        const res = await getAdminConfig();
        setConfig(res.data.config || []);
      } else if (tab === 'retrieval') {
        const [res, bm25Res] = await Promise.all([
          getAdminRetrievalConfig(),
          getBm25Status().catch(() => ({ data: { is_built: false, document_count: 0 } })),
        ]);
        const cfg = res.data.config || {};
        setRetrievalConfig(cfg);
        setRetrievalForm({
          tag_weights: cfg.tag_weights || {},
          top_k: cfg.top_k || 20,
          top_k_distribution: cfg.top_k_distribution || {},
          summarization_enabled: cfg.summarization_enabled || false,
          summarization_model: cfg.summarization_model || '',
          pipeline_config: {
            reranker_enabled: true,
            reranker_model: '',
            initial_retrieval_k: 75,
            final_context_k: 10,
            hybrid_enabled: true,
            vector_weight: 0.7,
            keyword_weight: 0.3,
            parent_child_enabled: false,
            dedup_enabled: true,
            dedup_threshold: 0.92,
            ...(cfg.pipeline_config || {}),
          },
        });
        setBm25Status(bm25Res.data);
      } else if (tab === 'vectordb') {
        const [statsRes, debugRes] = await Promise.all([getVectorStats(), getQdrantDebug(20)]);
        setVectorStats(statsRes.data);
        setQdrantDebug(debugRes.data);
        // Also load the first page of documents
        loadQdrantDocuments(null, true);
      } else if (tab === 'logs') {
        const [logRes, typesRes] = await Promise.all([
          getAdminLogs(50, logPage, logEventTypeFilter || null, logSourceFilter || null),
          getAdminLogEventTypes(),
        ]);
        setLogs(logRes.data.logs || []);
        setLogTotal(logRes.data.total || 0);
        setLogTotalPages(logRes.data.total_pages || 1);
        setLogHasNext(logRes.data.has_next || false);
        setLogHasPrev(logRes.data.has_prev || false);
        setLogPage(logRes.data.page || 1);
        setLogEventTypes(typesRes.data.event_types || []);
      }
    } catch (err) {
      console.error(`Failed to load ${tab}:`, err);
    }
    setLoading(false);
  };

  const showMsg = (text, type = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  // ── Source Handlers ──────────────────────────────────────────────

  const handleSaveSource = async () => {
    const data = {
      name: sourceForm.name,
      source_type: sourceForm.source_type,
      enabled: sourceForm.enabled,
      config: sourceForm.source_type === 'bookstack'
        ? {
            base_url: sourceForm.config.base_url,
            token_id: sourceForm.config.token_id,
            token_secret: sourceForm.config.token_secret,
            webhook_enabled: sourceForm.config.webhook_enabled || false,
            index_attachments: sourceForm.config.index_attachments !== false,
            max_attachment_size_mb: Number(sourceForm.config.max_attachment_size_mb) || 0,
          }
        : { directory: sourceForm.config.directory, recursive: sourceForm.config.recursive },
    };
    try {
      if (editingSourceId) {
        await updateAdminSource(editingSourceId, data);
        showMsg('Quelle aktualisiert');
      } else {
        await createAdminSource(data);
        showMsg('Quelle erstellt');
      }
      setShowSourceForm(false);
      setEditingSourceId(null);
      loadTab('sources');
    } catch (err) {
      showMsg(err.response?.data?.message || 'Fehler', 'error');
    }
  };

  const handleEditSource = (source) => {
    setSourceForm({
      name: source.name,
      source_type: source.source_type,
      enabled: source.enabled,
      config: source.config || {},
    });
    setEditingSourceId(source.id);
    setShowSourceForm(true);
  };

  const handleDeleteSource = (id) => {
    showConfirm('Quelle wirklich löschen?', async () => {
      closeConfirm();
      try {
        await deleteAdminSource(id);
        showMsg('Quelle gelöscht');
        loadTab('sources');
      } catch (err) {
        showMsg('Fehler beim Löschen', 'error');
      }
    });
  };

  const handleTestSource = async (id) => {
    try {
      const res = await testAdminSource(id);
      showMsg(res.data.message || 'Test abgeschlossen', res.data.success ? 'success' : 'error');
    } catch (err) {
      showMsg('Test fehlgeschlagen', 'error');
    }
  };

  const handleSyncSource = async (id) => {
    try {
      await syncAdminSource(id);
      showMsg('Sync gestartet');
    } catch (err) {
      showMsg('Sync fehlgeschlagen', 'error');
    }
  };

  // ── Model Handlers ───────────────────────────────────────────────

  const handlePullModel = async () => {
    if (!pullModelName.trim()) return;
    showMsg('Modell wird heruntergeladen...');
    try {
      const res = await pullAdminModel(pullModelName.trim());
      showMsg(res.data.message || 'Modell heruntergeladen');
      setPullModelName('');
      loadTab('models');
    } catch (err) {
      showMsg('Download fehlgeschlagen', 'error');
    }
  };

  const handleRemoveModel = (name) => {
    showConfirm(`Modell "${name}" wirklich entfernen?`, async () => {
      closeConfirm();
      try {
        await removeAdminModel(name);
        showMsg('Modell entfernt');
        loadTab('models');
      } catch (err) {
        showMsg('Fehler beim Entfernen', 'error');
      }
    });
  };

  const handleTestModel = async (name) => {
    showMsg('Modell wird getestet...');
    try {
      const res = await testAdminModel(name);
      if (res.data.success) {
        showMsg(`Antwort: "${res.data.response?.substring(0, 100) || ''}"`);
      } else {
        showMsg(res.data.message || 'Test fehlgeschlagen', 'error');
      }
    } catch (err) {
      showMsg('Test fehlgeschlagen', 'error');
    }
  };

  // ── Config Handler ───────────────────────────────────────────────

  const handleSaveConfig = async () => {
    if (!configForm.key || !configForm.value) return;
    try {
      await setAdminConfig(configForm.key, configForm.value, configForm.description);
      showMsg('Konfiguration gespeichert');
      setConfigForm({ key: '', value: '', description: '' });
      loadTab('config');
    } catch (err) {
      showMsg('Fehler beim Speichern', 'error');
    }
  };

  // ── Retrieval Config Handler ─────────────────────────────────────

  const handleSaveRetrievalConfig = async () => {
    try {
      await updateAdminRetrievalConfig(retrievalForm);
      showMsg('Retrieval-Konfiguration gespeichert');
      loadTab('retrieval');
    } catch (err) {
      showMsg('Fehler beim Speichern der Retrieval-Konfiguration', 'error');
    }
  };

  // ── Pipeline Handlers ────────────────────────────────────────────

  const handleRebuild = () => {
    showConfirm('Gesamten Index neu aufbauen? Dies kann einige Zeit dauern.', async () => {
      closeConfirm();
      try {
        await rebuildIndex();
        showMsg('Rebuild gestartet');
        loadTab('status');
      } catch (err) {
        showMsg('Rebuild fehlgeschlagen', 'error');
      }
    });
  };

  const handlePurge = () => {
    showConfirm('Alle Embeddings löschen? Dies entfernt den gesamten Suchindex.', async () => {
      closeConfirm();
      try {
        await purgeEmbeddings();
        showMsg('Embeddings gelöscht');
        loadTab('status');
      } catch (err) {
        showMsg('Fehler beim Löschen', 'error');
      }
    });
  };

  const handleCancelTasks = () => {
    showConfirm('Alle laufenden und wartenden Jobs abbrechen und aus der Datenbank entfernen?', async () => {
      closeConfirm();
      try {
        const res = await cancelAllTasks();
        showMsg(res.data?.message || 'Alle Jobs abgebrochen');
        loadTab('status');
      } catch (err) {
        showMsg('Fehler beim Abbrechen', 'error');
      }
    });
  };

  const handleCancelSingleTask = (taskId) => {
    showConfirm(`Task #${taskId} abbrechen?`, async () => {
      closeConfirm();
      try {
        const res = await cancelSingleTask(taskId);
        showMsg(res.data?.message || `Task ${taskId} abgebrochen`);
        loadTab('status');
      } catch (err) {
        showMsg('Fehler beim Abbrechen', 'error');
      }
    });
  };

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const handleTabChange = (id) => {
    setActiveTab(id);
    if (id === 'pipeline') {
      loadTab('status');
      // Load scheduled syncs and sources for the pipeline tab
      loadScheduledSyncs();
      getAdminSources().then(res => setSources(res.data.sources || [])).catch(() => {});
    }
  };

  // ── Scheduled Sync Handlers ──────────────────────────────────────

  const loadScheduledSyncs = async () => {
    try {
      const res = await getScheduledSyncs();
      setScheduledSyncs(res.data.schedules || []);
    } catch (err) {
      console.error('Failed to load scheduled syncs:', err);
    }
  };

  const handleCreateSchedule = async () => {
    try {
      const payload = {
        source_id: Number(scheduleForm.source_id),
        frequency: scheduleForm.frequency,
        time_of_day: scheduleForm.time_of_day,
      };
      if (scheduleForm.frequency === 'weekly') {
        payload.day_of_week = Number(scheduleForm.day_of_week);
      }
      await createScheduledSync(payload);
      showMsg('Automatischer Sync erstellt');
      setShowScheduleForm(false);
      setScheduleForm({ source_id: '', frequency: 'daily', time_of_day: '06:00', day_of_week: 0 });
      loadScheduledSyncs();
    } catch (err) {
      showMsg(err.response?.data?.message || 'Fehler beim Erstellen', 'error');
    }
  };

  const handleToggleSchedule = async (scheduleId, active) => {
    try {
      await updateScheduledSync(scheduleId, { active: !active });
      loadScheduledSyncs();
    } catch (err) {
      showMsg('Fehler beim Ändern', 'error');
    }
  };

  const handleDeleteSchedule = (scheduleId) => {
    showConfirm('Diesen automatischen Sync wirklich löschen?', async () => {
      closeConfirm();
      try {
        await deleteScheduledSync(scheduleId);
        showMsg('Automatischer Sync gelöscht');
        loadScheduledSyncs();
      } catch (err) {
        showMsg('Fehler beim Löschen', 'error');
      }
    });
  };

  // ── Tag Handlers ─────────────────────────────────────────────────

  const handleSaveTag = async () => {
    if (!tagForm.name.trim()) {
      showMsg('Bitte geben Sie einen Namen für den Tag ein', 'error');
      return;
    }
    try {
      if (editingTagId) {
        await updateAdminTag(editingTagId, tagForm);
        showMsg('Tag aktualisiert');
      } else {
        await createAdminTag(tagForm);
        showMsg('Tag erstellt');
      }
      setEditingTagId(null);
      closeNewTagModal();
      setTagForm({ name: '', description: '' });
      loadTab('tags');
    } catch (err) {
      showMsg(err.response?.data?.message || 'Fehler', 'error');
    }
  };

   const handleEditTag = (tag) => {
    if (tag) {
    setTagForm({ name: tag.name, description: tag.description || '' });
    showNewTagModal('Tag bearbeiten', async () => {
      setEditingTagId(tag.id);
      
      await handleSaveTag();
    });
    
    } else {
      setTagForm({ name: '', description: '' });
      showNewTagModal('Tag hinzufügen', async () => {
      setEditingTagId(null);
      await handleSaveTag();
    });
    }
    
  };


  const handleDeleteTag = (id) => {
    showConfirm('Tag wirklich löschen? Die zugehörige Berechtigung wird ebenfalls entfernt.', async () => {
      closeConfirm();
      try {
        await deleteAdminTag(id);
        showMsg('Tag gelöscht');
        loadTab('tags');
      } catch (err) {
        showMsg('Fehler beim Löschen', 'error');
      }
    });
  };

  const handleSourceTagToggle = async (sourceId, tagId, currentTags) => {
    const currentTagIds = currentTags.map(t => t.id);
    const newTagIds = currentTagIds.includes(tagId)
      ? currentTagIds.filter(id => id !== tagId)
      : [...currentTagIds, tagId];
    try {
      await setSourceTags(sourceId, newTagIds);
      loadTab('sources');
    } catch (err) {
      showMsg('Fehler beim Aktualisieren der Tags', 'error');
    }
  };

  return (
    <>
    <PageContainer>
      <Card variant="header" title="MDG Assistent - Verwaltung">
        {activeTab === 'retrieval' && !loading && (
          <>
          <Button variant="primary" onClick={handleSaveRetrievalConfig}>Speichern</Button>
          <Button variant="white" onClick={() => loadTab('retrieval')}>Zurücksetzen</Button>
          </>
        )}
        {activeTab === 'vectordb' && !loading && (
          <>
            <Button variant="white"  onClick={() => loadTab('vectordb')}>Aktualisieren</Button>
            <Button variant="primary"  onClick={async () => {
                try {
                  await reconcileDocumentCounts();
                  showMsg('Dokument-Zähler abgeglichen');
                  loadTab('vectordb');
                } catch (err) {
                  showMsg('Fehler beim Abgleichen', 'error');
                }
              }}>Zähler abgleichen</Button>
          </>
        )}
        {activeTab === 'sources' && !loading && (
          <>
            <Button
              variant="primary"
              onClick={() => {
                setSourceForm({ name: '', source_type: 'bookstack', enabled: true, config: {} });
                setEditingSourceId(null);
                setShowSourceForm(true);
              }}
            >
              + Quelle hinzufügen
            </Button>
          </>
        )}
        {activeTab === 'tags' && !loading && (
          <>
            <Button
              variant="primary"
              onClick={() => {
                handleEditTag(null);
              }}
            >
              + Tag hinzufügen
            </Button>
          </>
        )}
        <Button variant="secondary" onClick={() => navigate('/assistant')}>Zurück</Button>
      </Card>

      {message && (
        <MessageBox
          message={message.text}
          type={message.type}
          onDismiss={() => setMessage(null)}
        />
      )}

      <Tabs tabs={TABS} activeTab={activeTab} onChange={handleTabChange} stretch={true} sticky/>

      {loading && <Spinner text="Laden..." />}

      {/* ── Status Tab ──────────────────────────────────────── */}
      {activeTab === 'status' && !loading && status && (
        <div>
          <div className="assistant-admin__stat-row">
            <StatCard
              value={status.ollama?.available ? 'Online' : 'Offline'}
              label="Ollama LLM"
              variant={status.ollama?.available ? 'success' : 'danger'}
            />
            <StatCard
              value={status.vector_db?.available ? 'Online' : 'Offline'}
              label="Vector DB"
              variant={status.vector_db?.available ? 'success' : 'danger'}
            />
            <StatCard
              value={status.sources?.total_documents || 0}
              label="Indexierte Dokumente"
              variant="info"
            />
            <StatCard
              value={`${status.sources?.active || 0} / ${status.sources?.total || 0}`}
              label="Aktive Quellen"
              variant="default"
            />
            <StatCard
              value={status.metrics?.total_sessions || 0}
              label="Sessions"
              variant="default"
            />
          </div>

          <div className="assistant-admin__detail-row">
            <Card title="Ollama LLM">
              <p className="assistant-admin__text-sm">LLM-Modell: <strong>{status.models?.llm_model || '—'}</strong></p>
              <p className="assistant-admin__text-sm">Modelle verfügbar: {status.ollama?.model_count || 0}</p>
            </Card>
            <Card title="Nutzung">
              <p className="assistant-admin__text-sm">Anfragen (letzte Std.): {status.metrics?.queries_last_hour || 0}</p>
              <p className="assistant-admin__text-sm">Nachrichten gesamt: {status.metrics?.total_messages || 0}</p>
            </Card>
          </div>
        </div>
      )}

      {/* ── Sources Tab ─────────────────────────────────────── */}
      {activeTab === 'sources' && !loading && (
        <div>
          <div className="assistant-admin__section-header">
            <h2 className="assistant-admin__section-title">Wissensquellen</h2>
          </div>

          {/* Source Form */}
          {showSourceForm && (
            <Card className="assistant-admin__form-card">
              <h3 className="assistant-admin__form-title">
                {editingSourceId ? 'Quelle bearbeiten' : 'Neue Quelle'}
              </h3>
              <FormGroup label="Name" htmlFor="source-name">
                <TextInput
                  id="source-name"
                  placeholder="Quellenname"
                  value={sourceForm.name}
                  onChange={(e) => setSourceForm({ ...sourceForm, name: e.target.value })}
                />
              </FormGroup>
              <FormGroup label="Quelltyp" htmlFor="source-type">
                <SelectInput
                  id="source-type"
                  value={sourceForm.source_type}
                  onChange={(e) => setSourceForm({ ...sourceForm, source_type: e.target.value, config: {} })}
                >
                  <option value="bookstack">BookStack</option>
                  <option value="filesystem">Dateisystem</option>
                </SelectInput>
              </FormGroup>

              {sourceForm.source_type === 'bookstack' && (
                <>
                  <FormGroup label="BookStack URL" htmlFor="source-url">
                    <TextInput
                      id="source-url"
                      placeholder="https://wiki.example.com"
                      value={sourceForm.config.base_url || ''}
                      onChange={(e) => setSourceForm({ ...sourceForm, config: { ...sourceForm.config, base_url: e.target.value } })}
                    />
                  </FormGroup>
                  <FormGroup label="API Token ID" htmlFor="source-token-id">
                    <TextInput
                      id="source-token-id"
                      placeholder="Token ID"
                      value={sourceForm.config.token_id || ''}
                      onChange={(e) => setSourceForm({ ...sourceForm, config: { ...sourceForm.config, token_id: e.target.value } })}
                    />
                  </FormGroup>
                  <FormGroup label="API Token Secret" htmlFor="source-token-secret">
                    <TextInput
                      id="source-token-secret"
                      type="password"
                      placeholder="Token Secret"
                      value={sourceForm.config.token_secret || ''}
                      onChange={(e) => setSourceForm({ ...sourceForm, config: { ...sourceForm.config, token_secret: e.target.value } })}
                    />
                  </FormGroup>
                  <label className="assistant-admin__label-checkbox">
                    <input
                      type="checkbox"
                      checked={sourceForm.config.webhook_enabled || false}
                      onChange={(e) => setSourceForm({ ...sourceForm, config: { ...sourceForm.config, webhook_enabled: e.target.checked } })}
                    />
                    Webhook-Synchronisation aktivieren
                  </label>
                  <p className="assistant-admin__text-sm" style={{ marginLeft: '1.5rem', marginTop: '-0.5rem', color: '#666' }}>
                    Wenn aktiviert, verarbeitet das System eingehende BookStack-Webhooks für inkrementelle Aktualisierungen.
                  </p>
                  <label className="assistant-admin__label-checkbox">
                    <input
                      type="checkbox"
                      checked={sourceForm.config.index_attachments !== false}
                      onChange={(e) => setSourceForm({ ...sourceForm, config: { ...sourceForm.config, index_attachments: e.target.checked } })}
                    />
                    Anhänge synchronisieren
                  </label>
                  <p className="assistant-admin__text-sm" style={{ marginLeft: '1.5rem', marginTop: '-0.5rem', color: '#666' }}>
                    Wenn aktiviert, werden Dateianhänge (PDF, DOCX, etc.) heruntergeladen und indexiert.
                  </p>
                  <FormGroup label="Max. Anhang-Größe (MB)" htmlFor="source-max-att-size">
                    <TextInput
                      id="source-max-att-size"
                      type="number"
                      min="0"
                      step="1"
                      placeholder="0"
                      value={sourceForm.config.max_attachment_size_mb ?? ''}
                      onChange={(e) => {
                        const val = e.target.value === '' ? '' : Number(e.target.value);
                        setSourceForm({ ...sourceForm, config: { ...sourceForm.config, max_attachment_size_mb: val } });
                      }}
                    />
                  </FormGroup>
                  <p className="assistant-admin__text-sm" style={{ marginTop: '-0.5rem', color: '#666' }}>
                    Anhänge größer als dieser Wert werden übersprungen und im Log erfasst. 0 = kein Limit.
                  </p>
                </>
              )}

              {sourceForm.source_type === 'filesystem' && (
                <>
                  <FormGroup label="Verzeichnispfad" htmlFor="source-dir">
                    <TextInput
                      id="source-dir"
                      placeholder="/pfad/zum/verzeichnis"
                      value={sourceForm.config.directory || ''}
                      onChange={(e) => setSourceForm({ ...sourceForm, config: { ...sourceForm.config, directory: e.target.value } })}
                    />
                  </FormGroup>
                  <label className="assistant-admin__label-checkbox">
                    <input
                      type="checkbox"
                      checked={sourceForm.config.recursive !== false}
                      onChange={(e) => setSourceForm({ ...sourceForm, config: { ...sourceForm.config, recursive: e.target.checked } })}
                    />
                    Rekursiv durchsuchen
                  </label>
                </>
              )}

              <div className="assistant-admin__form-actions">
                <Button variant="primary" size="sm" onClick={handleSaveSource}>Speichern</Button>
                <Button variant="secondary" size="sm" onClick={() => { setShowSourceForm(false); setEditingSourceId(null); }}>Abbrechen</Button>
              </div>
            </Card>
          )}

          {/* Source List */}
          {sources.map((source) => (
            <Card key={source.id}>
              <div className="assistant-admin__item-header">
                <div>
                  <h3 className="assistant-admin__item-name">
                    {source.name}
                    <span className={`assistant-admin__badge assistant-admin__badge--${source.enabled ? 'active' : 'inactive'}`}>
                      {source.enabled ? 'Aktiv' : 'Deaktiviert'}
                    </span>
                  </h3>
                  <p className="assistant-admin__item-meta">
                    Typ: {source.source_type} | Dokumente: {source.document_count || 0}
                    {source.last_sync_at && ` | Letzter Sync: ${new Date(source.last_sync_at).toLocaleString('de-DE')}`}
                    {source.last_sync_status && (
                      <span className={`assistant-admin__status-text--${source.last_sync_status === 'success' ? 'success' : 'error'}`}>
                        {' '}({source.last_sync_status})
                      </span>
                    )}
                    {source.source_type === 'bookstack' && (
                      <>
                        {source.config?.webhook_enabled && (
                          <span className="assistant-admin__badge assistant-admin__badge--active" style={{ marginLeft: '0.5rem', fontSize: '0.7rem' }}>
                            Webhook
                          </span>
                        )}
                        {source.config?.index_attachments === false && (
                          <span className="assistant-admin__badge assistant-admin__badge--inactive" style={{ marginLeft: '0.5rem', fontSize: '0.7rem' }}>
                            Anhänge deaktiviert
                          </span>
                        )}
                      </>
                    )}
                  </p>
                  {/* Source Tags (read-only display — manage via Permission Management) */}
                  <div className="assistant-admin__source-tags">
                    {(source.tags || []).length > 0 ? (
                      (source.tags || []).map((tag) => (
                        <span
                          key={tag.id}
                          className="assistant-admin__tag-chip assistant-admin__tag-chip--active assistant-admin__tag-chip--readonly"
                          title={`Tag "${tag.name}" — Verwaltung über Berechtigungen`}
                        >
                          {tag.name}
                        </span>
                      ))
                    ) : (
                      <span className="assistant-admin__text-sm">Keine Tags zugewiesen</span>
                    )}
                  </div>
                </div>
                <div className="assistant-admin__item-actions">
                  <Button variant="primary" size="sm" onClick={() => handleSyncSource(source.id)}>Sync</Button>
                  <Button variant="secondary" size="sm" onClick={() => handleTestSource(source.id)}>Test</Button>
                  <Button variant="secondary" size="sm" onClick={() => handleEditSource(source)}>Bearbeiten</Button>
                  <Button variant="danger" size="sm" onClick={() => handleDeleteSource(source.id)}>Löschen</Button>
                </div>
              </div>
            </Card>
          ))}
          {sources.length === 0 && (
            <Card><p className="assistant-admin__empty">Keine Quellen konfiguriert.</p></Card>
          )}
        </div>
      )}

      {/* ── Tags Tab ────────────────────────────────────────── */}
      {activeTab === 'tags' && !loading && (
        <div>
          <div className="assistant-admin__section-header">
            <h2 className="assistant-admin__section-title">Zugriffssteuerung-Tags</h2>
          </div>

          <Card className="assistant-admin__info-card">
            <p className="assistant-admin__text-sm">
              Tags steuern den Zugriff auf Wissensquellen. Für jeden Tag wird automatisch eine Berechtigung erstellt
              (z.B. <code>ASSISTANT_TAG_ENGINEERING_WIKI</code>), die über die Berechtigungsverwaltung Rollen zugewiesen werden kann.
            </p>
          </Card>

          {/* Tag Form */}
          {newTagModal.open && (
            <Modal
              title={newTagModal.title}
              size="sm"
              onClose={closeNewTagModal}
              footer={
                <>
                  <Button variant="secondary" onClick={closeNewTagModal}>Abbrechen</Button>
                  <Button variant="primary" onClick={newTagModal.onConfirm}>Bestätigen</Button>
                </>
              }
            >
              <FormGroup label="Name" htmlFor="tag-name">
                <TextInput
                  id="tag-name"
                  placeholder="z.B. engineering_wiki"
                  value={tagForm.name}
                  onChange={(e) => setTagForm({ ...tagForm, name: e.target.value })}
                />
              </FormGroup>
              <FormGroup label="Beschreibung" htmlFor="tag-desc">
                <TextInput
                  id="tag-desc"
                  placeholder="Beschreibung (optional)"
                  value={tagForm.description}
                  onChange={(e) => setTagForm({ ...tagForm, description: e.target.value })}
                />
              </FormGroup>
            </Modal>
          )}

          {/* Tag List */}
          {tags.map((tag) => (
            <Card key={tag.id}>
              <div className="assistant-admin__item-header">
                <div>
                  <h3 className="assistant-admin__item-name">
                    {tag.name}
                    <span className="assistant-admin__badge assistant-admin__badge--active">
                      {tag.permission_id}
                    </span>
                  </h3>
                  {tag.description && (
                    <p className="assistant-admin__item-meta">{tag.description}</p>
                  )}
                  <p className="assistant-admin__item-meta">
                    Quellen: {tag.source_count || 0}
                    {tag.created_at && ` | Erstellt: ${new Date(tag.created_at).toLocaleString('de-DE')}`}
                  </p>
                </div>
                <div className="assistant-admin__item-actions">
                  <Button variant="secondary" size="sm" onClick={() => handleEditTag(tag)}>Bearbeiten</Button>
                  <Button variant="danger" size="sm" onClick={() => handleDeleteTag(tag.id)}>Löschen</Button>
                </div>
              </div>
            </Card>
          ))}
          {tags.length === 0 && (
            <Card><p className="assistant-admin__empty">Keine Tags vorhanden. Erstellen Sie einen neuen Tag.</p></Card>
          )}
        </div>
      )}

      {/* ── Models Tab ──────────────────────────────────────── */}
      {activeTab === 'models' && !loading && (
        <div>
          <h2 className="assistant-admin__section-title">Ollama Modelle</h2>

          <Card>
            <FormGroup label="Modell herunterladen" htmlFor="pull-model">
              <div className="assistant-admin__inline-row">
                <TextInput
                  id="pull-model"
                  placeholder="Modellname (z.B. llama3, nomic-embed-text)"
                  value={pullModelName}
                  onChange={(e) => setPullModelName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handlePullModel()}
                />
                <Button variant="primary" onClick={handlePullModel}>Herunterladen</Button>
              </div>
            </FormGroup>
          </Card>

          {models.map((model) => (
            <Card key={model.name}>
              <div className="assistant-admin__item-header">
                <div>
                  <h3 className="assistant-admin__item-name">{model.name}</h3>
                  <p className="assistant-admin__item-meta">
                    Größe: {formatBytes(model.size)}
                    {model.details?.family && ` | Familie: ${model.details.family}`}
                    {model.details?.parameter_size && ` | Parameter: ${model.details.parameter_size}`}
                  </p>
                </div>
                <div className="assistant-admin__item-actions">
                  <Button variant="primary" onClick={() => handleTestModel(model.name)}>Test</Button>
                  <Button variant="danger" onClick={() => handleRemoveModel(model.name)}>Entfernen</Button>
                </div>
              </div>
            </Card>
          ))}
          {models.length === 0 && (
            <Card><p className="assistant-admin__empty">Keine Modelle installiert.</p></Card>
          )}
        </div>
      )}

      {/* ── Config Tab ──────────────────────────────────────── */}
      {activeTab === 'config' && !loading && (
        <div>
          <h2 className="assistant-admin__section-title">Konfiguration</h2>

          <Card>
            <h3 className="assistant-admin__form-title">Einstellung setzen</h3>
            <div className="assistant-admin__config-grid">
              <FormGroup label="Schlüssel" htmlFor="config-key">
                <SelectInput
                  id="config-key"
                  value={configForm.key}
                  onChange={(e) => setConfigForm({ ...configForm, key: e.target.value })}
                >
                  <option value="">Schlüssel wählen...</option>
                  <option value="llm_model">LLM Model</option>
                  <option value="embedding_model">Embedding Model</option>
                  <option value="ollama_url">Ollama URL</option>
                  <option value="qdrant_url">Qdrant URL</option>
                  <option value="debug_mode">Debug Mode</option>
                </SelectInput>
              </FormGroup>
              <FormGroup label="Wert" htmlFor="config-value">
                <TextInput
                  id="config-value"
                  placeholder="Wert"
                  value={configForm.value}
                  onChange={(e) => setConfigForm({ ...configForm, value: e.target.value })}
                />
              </FormGroup>
              <FormGroup label="Beschreibung" htmlFor="config-desc">
                <div className="assistant-admin__inline-row">
                  <TextInput
                    id="config-desc"
                    placeholder="Beschreibung (optional)"
                    value={configForm.description}
                    onChange={(e) => setConfigForm({ ...configForm, description: e.target.value })}
                  />
                  <Button variant="primary" onClick={handleSaveConfig}>Speichern</Button>
                </div>
              </FormGroup>
            </div>
          </Card>

          <div className="shared-table-container">
            <table className="shared-table">
              <thead>
                <tr>
                  <th>Schlüssel</th>
                  <th>Wert</th>
                  <th>Beschreibung</th>
                  <th>Aktualisiert</th>
                </tr>
              </thead>
              <tbody>
                {config.map((c) => (
                  <tr key={c.id}>
                    <td><strong>{c.key}</strong></td>
                    <td><code>{c.value}</code></td>
                    <td>{c.description || '—'}</td>
                    <td>{c.updated_at ? new Date(c.updated_at).toLocaleString('de-DE') : '—'}</td>
                  </tr>
                ))}
                {config.length === 0 && (
                  <tr><td colSpan={4} className="shared-table__empty">Keine Konfigurationseinträge.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Retrieval Tab ───────────────────────────────────── */}
      {activeTab === 'retrieval' && !loading && (
        <div>
          <div className="assistant-admin__section-header">
            <h2 className="assistant-admin__section-title">Retrieval-Konfiguration</h2>
          </div>

          {/* A) Tag Weighting */}
          <div className="grid-lg">
          <Card title="Tag-Gewichtung">
            <p className="assistant-admin__text-sm" style={{ marginBottom: '0.75rem' }}>
              Gewichtung pro Quelltyp. Der finale Score wird berechnet als: <code>similarity_score × tag_weight</code>
            </p>
            <table className="shared-table" style={{ marginBottom: '1rem' }}>
              <thead>
                <tr>
                  <th>Quelltyp</th>
                  <th>Gewichtung</th>
                  <th style={{ width: '60px' }}></th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(retrievalForm.tag_weights || {}).map(([key, val]) => (
                  <tr key={key}>
                    <td><code>{key}</code></td>
                    <td>
                      <TextInput
                        type="number"
                        step="0.1"
                        min="0"
                        value={val}
                        onChange={(e) => setRetrievalForm(prev => ({
                          ...prev,
                          tag_weights: { ...prev.tag_weights, [key]: parseFloat(e.target.value) || 0 },
                        }))}
                        style={{ width: '100px' }}
                      />
                    </td>
                    <td>
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => setRetrievalForm(prev => {
                          const w = { ...prev.tag_weights };
                          delete w[key];
                          return { ...prev, tag_weights: w };
                        })}
                      >
                        ✕
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <SelectInput
                value={newWeightKey}
                onChange={(e) => setNewWeightKey(e.target.value)}
                style={{ width: '200px' }}
              >
                <option value="">Quelltyp wählen…</option>
                {['page', 'attachment', 'external_document'].filter(
                  st => !retrievalForm.tag_weights?.hasOwnProperty(st)
                ).map(st => (
                  <option key={st} value={st}>{st}</option>
                ))}
              </SelectInput>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  if (newWeightKey.trim()) {
                    setRetrievalForm(prev => ({
                      ...prev,
                      tag_weights: { ...prev.tag_weights, [newWeightKey.trim()]: 1.0 },
                    }));
                    setNewWeightKey('');
                  }
                }}
              >
                + Hinzufügen
              </Button>
            </div>
          </Card>

          {/* B) Intelligent Top_K */}
          <Card title="Intelligente Top_K-Verteilung">
            <FormGroup label="Gesamtzahl abgerufener Chunks (Top_K)" htmlFor="top-k">
              <TextInput
                id="top-k"
                type="number"
                min="1"
                value={retrievalForm.top_k}
                onChange={(e) => setRetrievalForm(prev => ({ ...prev, top_k: parseInt(e.target.value) || 1 }))}
                style={{ width: '120px' }}
              />
            </FormGroup>
            <p className="assistant-admin__text-sm" style={{ marginBottom: '0.75rem' }}>
              Prozentuale Verteilung der Ergebnisse pro Quelltyp. Soll in Summe 100% ergeben.
            </p>
            <table className="shared-table" style={{ marginBottom: '1rem' }}>
              <thead>
                <tr>
                  <th>Quelltyp</th>
                  <th>Anteil (%)</th>
                  <th>Ergibt Chunks</th>
                  <th style={{ width: '60px' }}></th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(retrievalForm.top_k_distribution || {}).map(([key, pct]) => {
                  const totalPct = Object.values(retrievalForm.top_k_distribution || {}).reduce((a, b) => a + b, 0) || 100;
                  const chunks = Math.floor(retrievalForm.top_k * (pct / totalPct));
                  return (
                    <tr key={key}>
                      <td><code>{key}</code></td>
                      <td>
                        <TextInput
                          type="number"
                          min="0"
                          max="100"
                          value={pct}
                          onChange={(e) => setRetrievalForm(prev => ({
                            ...prev,
                            top_k_distribution: { ...prev.top_k_distribution, [key]: parseInt(e.target.value) || 0 },
                          }))}
                          style={{ width: '100px' }}
                        />
                      </td>
                      <td>{chunks}</td>
                      <td>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => setRetrievalForm(prev => {
                            const d = { ...prev.top_k_distribution };
                            delete d[key];
                            return { ...prev, top_k_distribution: d };
                          })}
                        >
                          ✕
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <SelectInput
                value={newDistKey}
                onChange={(e) => setNewDistKey(e.target.value)}
                style={{ width: '200px' }}
              >
                <option value="">Quelltyp wählen…</option>
                {['page', 'attachment', 'external_document'].filter(
                  st => !retrievalForm.top_k_distribution?.hasOwnProperty(st)
                ).map(st => (
                  <option key={st} value={st}>{st}</option>
                ))}
              </SelectInput>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  if (newDistKey.trim()) {
                    setRetrievalForm(prev => ({
                      ...prev,
                      top_k_distribution: { ...prev.top_k_distribution, [newDistKey.trim()]: 0 },
                    }));
                    setNewDistKey('');
                  }
                }}
              >
                + Hinzufügen
              </Button>
            </div>
          </Card>
          </div>
          <div className='grid-lg-2to1'>

          {/* D) Pipeline Configuration */}
          <Card title="Pipeline-Konfiguration (Fortgeschritten)">
            <p className="assistant-admin__text-sm" style={{ marginBottom: '0.75rem' }}>
              Erweiterte Retrieval-Pipeline-Einstellungen: Reranking, Hybrid-Suche, Parent-Child-Chunking und Deduplizierung.
            </p>

            {/* Reranker */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <FormGroup label="Cross-Encoder Reranking" htmlFor="reranker-enabled">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    id="reranker-enabled"
                    type="checkbox"
                    checked={retrievalForm.pipeline_config?.reranker_enabled ?? true}
                    onChange={(e) => setRetrievalForm(prev => ({
                      ...prev,
                      pipeline_config: { ...prev.pipeline_config, reranker_enabled: e.target.checked },
                    }))}
                  />
                  Aktiviert
                </label>
              </FormGroup>
              {retrievalForm.pipeline_config?.reranker_enabled && (
                <FormGroup label="Reranker-Modell (leer = Standard)" htmlFor="reranker-model">
                  <TextInput
                    id="reranker-model"
                    placeholder="z.B. nomic-embed-text"
                    value={retrievalForm.pipeline_config?.reranker_model || ''}
                    onChange={(e) => setRetrievalForm(prev => ({
                      ...prev,
                      pipeline_config: { ...prev.pipeline_config, reranker_model: e.target.value },
                    }))}
                  />
                </FormGroup>
              )}
            </div>

            {/* Hybrid Search */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <FormGroup label="Hybrid-Suche (Vektor + BM25)" htmlFor="hybrid-enabled">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    id="hybrid-enabled"
                    type="checkbox"
                    checked={retrievalForm.pipeline_config?.hybrid_enabled ?? true}
                    onChange={(e) => setRetrievalForm(prev => ({
                      ...prev,
                      pipeline_config: { ...prev.pipeline_config, hybrid_enabled: e.target.checked },
                    }))}
                  />
                  Aktiviert
                </label>
                {bm25Status && (
                  <span className="assistant-admin__text-sm" style={{ marginTop: '0.25rem', color: bm25Status.is_built ? '#16a34a' : '#dc2626' }}>
                    BM25: {bm25Status.is_built ? `${bm25Status.document_count} Dokumente` : 'nicht aufgebaut'}
                  </span>
                )}
              </FormGroup>
              {retrievalForm.pipeline_config?.hybrid_enabled && (
                <>
                  <FormGroup label="Vektor-Gewicht" htmlFor="vector-weight">
                    <TextInput
                      id="vector-weight"
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={retrievalForm.pipeline_config?.vector_weight ?? 0.7}
                      onChange={(e) => setRetrievalForm(prev => ({
                        ...prev,
                        pipeline_config: { ...prev.pipeline_config, vector_weight: parseFloat(e.target.value) || 0 },
                      }))}
                      style={{ width: '100px' }}
                    />
                  </FormGroup>
                  <FormGroup label="Keyword-Gewicht" htmlFor="keyword-weight">
                    <TextInput
                      id="keyword-weight"
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={retrievalForm.pipeline_config?.keyword_weight ?? 0.3}
                      onChange={(e) => setRetrievalForm(prev => ({
                        ...prev,
                        pipeline_config: { ...prev.pipeline_config, keyword_weight: parseFloat(e.target.value) || 0 },
                      }))}
                      style={{ width: '100px' }}
                    />
                  </FormGroup>
                </>
              )}
            </div>
{/* BM25 Rebuild */}
            {retrievalForm.pipeline_config?.hybrid_enabled && (
              <div style={{ marginBottom: '1rem' }}>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={bm25Rebuilding}
                  onClick={async () => {
                    setBm25Rebuilding(true);
                    try {
                      const res = await rebuildBm25Index();
                      showMsg(`BM25-Index aufgebaut: ${res.data.document_count} Dokumente`);
                      setBm25Status({ is_built: true, document_count: res.data.document_count });
                    } catch (err) {
                      showMsg('BM25-Index Aufbau fehlgeschlagen', 'error');
                    }
                    setBm25Rebuilding(false);
                  }}
                >
                  {bm25Rebuilding ? 'Wird aufgebaut…' : 'BM25-Index neu aufbauen'}
                </Button>
              </div>
            )}

            {/* Retrieval K values */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <FormGroup label="Initial Retrieval K (Kandidaten)" htmlFor="initial-retrieval-k">
                <TextInput
                  id="initial-retrieval-k"
                  type="number"
                  min="10"
                  max="500"
                  value={retrievalForm.pipeline_config?.initial_retrieval_k ?? 75}
                  onChange={(e) => setRetrievalForm(prev => ({
                    ...prev,
                    pipeline_config: { ...prev.pipeline_config, initial_retrieval_k: parseInt(e.target.value) || 75 },
                  }))}
                  style={{ width: '120px' }}
                />
              </FormGroup>
              <FormGroup label="Final Context K (an LLM)" htmlFor="final-context-k">
                <TextInput
                  id="final-context-k"
                  type="number"
                  min="1"
                  max="100"
                  value={retrievalForm.pipeline_config?.final_context_k ?? 10}
                  onChange={(e) => setRetrievalForm(prev => ({
                    ...prev,
                    pipeline_config: { ...prev.pipeline_config, final_context_k: parseInt(e.target.value) || 10 },
                  }))}
                  style={{ width: '120px' }}
                />
              </FormGroup>
            </div>

            {/* Deduplication */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <FormGroup label="Semantische Deduplizierung" htmlFor="dedup-enabled">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    id="dedup-enabled"
                    type="checkbox"
                    checked={retrievalForm.pipeline_config?.dedup_enabled ?? true}
                    onChange={(e) => setRetrievalForm(prev => ({
                      ...prev,
                      pipeline_config: { ...prev.pipeline_config, dedup_enabled: e.target.checked },
                    }))}
                  />
                  Aktiviert
                </label>
              </FormGroup>
              {retrievalForm.pipeline_config?.dedup_enabled && (
                <FormGroup label="Ähnlichkeits-Schwellwert" htmlFor="dedup-threshold">
                  <TextInput
                    id="dedup-threshold"
                    type="number"
                    step="0.01"
                    min="0.5"
                    max="1"
                    value={retrievalForm.pipeline_config?.dedup_threshold ?? 0.92}
                    onChange={(e) => setRetrievalForm(prev => ({
                      ...prev,
                      pipeline_config: { ...prev.pipeline_config, dedup_threshold: parseFloat(e.target.value) || 0.92 },
                    }))}
                    style={{ width: '120px' }}
                  />
                </FormGroup>
              )}
            </div>

            {/* Parent-Child Chunking */}
            <FormGroup label="Parent-Child Chunking" htmlFor="parent-child-enabled">
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  id="parent-child-enabled"
                  type="checkbox"
                  checked={retrievalForm.pipeline_config?.parent_child_enabled ?? false}
                  onChange={(e) => setRetrievalForm(prev => ({
                    ...prev,
                    pipeline_config: { ...prev.pipeline_config, parent_child_enabled: e.target.checked },
                  }))}
                />
                Aktiviert
              </label>
              <p className="assistant-admin__text-sm" style={{ marginTop: '0.25rem', color: '#6b7280' }}>
                Erzeugt bei der Ingestion Parent- und Child-Chunks. Child-Chunks werden für die Suche verwendet, Parent-Chunks für den LLM-Kontext.
                <strong> Erfordert einen Rebuild nach Aktivierung.</strong>
              </p>
            </FormGroup>
          </Card>
          {/* C) Summarization */}
          <Card title="Quellen-Zusammenfassung (Pre-Answer)">
            <p className="assistant-admin__text-sm" style={{ marginBottom: '0.75rem' }}>
              Wenn aktiviert, werden abgerufene Quellen zuerst zusammengefasst, bevor der finale Antwort-Prompt erstellt wird.
              Dies kann die Antwortpräzision bei vielen Chunks verbessern.
            </p>
            <FormGroup label="Zusammenfassung aktivieren" htmlFor="summarization-enabled">
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  id="summarization-enabled"
                  type="checkbox"
                  checked={retrievalForm.summarization_enabled}
                  onChange={(e) => setRetrievalForm(prev => ({ ...prev, summarization_enabled: e.target.checked }))}
                />
                Aktiviert
              </label>
            </FormGroup>
            {retrievalForm.summarization_enabled && (
              <FormGroup label="Zusammenfassungs-Modell" htmlFor="summarization-model">
                <TextInput
                  id="summarization-model"
                  placeholder="z.B. gemma3:4b (leer = Standard-LLM)"
                  value={retrievalForm.summarization_model}
                  onChange={(e) => setRetrievalForm(prev => ({ ...prev, summarization_model: e.target.value }))}
                />
              </FormGroup>
            )}
          </Card>

          </div>
          {/* E) Retrieval Diagnostics */}
          <Card title="Retrieval-Diagnose">
            <p className="assistant-admin__text-sm" style={{ marginBottom: '0.75rem' }}>
              Test-Abfrage ausführen (ohne LLM-Aufruf) um die Retrieval-Pipeline zu analysieren.
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end', marginBottom: '1rem' }}>
              <FormGroup label="Test-Abfrage" htmlFor="diag-query" style={{ flex: 1 }}>
                <TextInput
                  id="diag-query"
                  placeholder="z.B. Wie funktioniert die Moodle-Anmeldung?"
                  value={diagQuery}
                  onChange={(e) => setDiagQuery(e.target.value)}
                />
              </FormGroup>
              <Button
                variant="primary"
                disabled={diagLoading || !diagQuery.trim()}
                onClick={async () => {
                  setDiagLoading(true);
                  try {
                    const res = await testRetrieval(diagQuery.trim());
                    setDiagResults(res.data);
                  } catch (err) {
                    showMsg('Retrieval-Test fehlgeschlagen', 'error');
                  }
                  setDiagLoading(false);
                }}
              >
                {diagLoading ? 'Läuft…' : 'Testen'}
              </Button>
            </div>

            {diagResults && (
              <div>
                <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
                  <StatCard label="Ergebnisse" value={diagResults.result_count ?? 0} />
                  <StatCard label="Gesamtdauer" value={`${diagResults.diagnostics?.total_duration_ms ?? 0}ms`} />
                  {diagResults.diagnostics?.stages?.vector_search && (
                    <StatCard label="Vektor-Suche" value={`${diagResults.diagnostics.stages.vector_search.count} / ${diagResults.diagnostics.stages.vector_search.duration_ms}ms`} />
                  )}
                  {diagResults.diagnostics?.stages?.keyword_search && (
                    <StatCard label="BM25-Suche" value={`${diagResults.diagnostics.stages.keyword_search.count} / ${diagResults.diagnostics.stages.keyword_search.duration_ms}ms`} />
                  )}
                  {diagResults.diagnostics?.stages?.reranking && (
                    <StatCard label="Reranking" value={`${diagResults.diagnostics.stages.reranking.output_count} / ${diagResults.diagnostics.stages.reranking.duration_ms}ms`} />
                  )}
                  {diagResults.diagnostics?.stages?.deduplication && (
                    <StatCard label="Dedupliziert" value={`${diagResults.diagnostics.stages.deduplication.removed} entfernt`} />
                  )}
                </div>

                {/* Stage details */}
                {diagResults.diagnostics?.stages && (
                  <details style={{ marginBottom: '0.75rem' }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 600, marginBottom: '0.5rem' }}>Pipeline-Stages (Detail)</summary>
                    <pre style={{ background: '#f5f5f5', padding: '0.75rem', borderRadius: '4px', fontSize: '0.8rem', overflow: 'auto', maxHeight: '300px' }}>
                      {JSON.stringify(diagResults.diagnostics.stages, null, 2)}
                    </pre>
                  </details>
                )}

                {/* Final results table */}
                <h4 style={{ marginBottom: '0.5rem' }}>Ergebnisse</h4>
                <div style={{ overflow: 'auto', maxHeight: '400px' }}>
                  <table className="shared-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Title</th>
                        <th>Source</th>
                        <th>Type</th>
                        <th>Score</th>
                        <th>Vector</th>
                        <th>Keyword</th>
                        <th>Reranker</th>
                        <th>Preview</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(diagResults.diagnostics?.final_results || []).map((r, i) => (
                        <tr key={i}>
                          <td>{i + 1}</td>
                          <td title={r.title} style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.title}</td>
                          <td>{r.source}</td>
                          <td><code>{r.source_type}</code></td>
                          <td>{r.score}</td>
                          <td>{r.vector_score}</td>
                          <td>{r.keyword_score}</td>
                          <td>{r.reranker_score}</td>
                          <td title={r.chunk_text_preview} style={{ maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.75rem' }}>{r.chunk_text_preview}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </Card>

        </div>
      )}

      {/* ── Pipeline Tab ────────────────────────────────────── */}
      {activeTab === 'pipeline' && !loading && (
        <div>
          <h2 className="assistant-admin__section-title">Pipeline-Verwaltung</h2>

          <div className="assistant-admin__pipeline-actions">
            <Button variant="primary" onClick={handleRebuild}>Index neu aufbauen</Button>
            <Button variant="danger" onClick={handlePurge}>Alle Embeddings löschen</Button>
            <Button variant="danger" onClick={handleCancelTasks}>Alle Jobs abbrechen</Button>
            <Button variant="secondary" onClick={async () => {
              try {
                await clearPipelineEvents();
                setPipelineEvents([]);
                seenEventIds.current = new Set();
              } catch (err) {
                console.error('Failed to clear pipeline events:', err);
              }
            }}>Feed leeren</Button>
            <span className={`assistant-admin__ws-status ${pipelineConnected ? 'assistant-admin__ws-status--ok' : 'assistant-admin__ws-status--off'}`}>
              {pipelineConnected ? 'WebSocket verbunden' : 'WebSocket getrennt'}
            </span>
          </div>

          <Card title="Aufgabenwarteschlange">
            {pipelineQueue ? (
              <>
                <p className="assistant-admin__text-sm">Warten: {pipelineQueue.pending_tasks || 0} Aufgaben</p>
                {pipelineQueue.current_task && (
                  <p className="assistant-admin__text-sm assistant-admin__text-sm--info">
                    Aktuell: {pipelineQueue.current_task.task_type} (Source {pipelineQueue.current_task.source_id}) — {pipelineQueue.current_task.status}
                    {' '}
                    <Button variant="danger" style={{ marginLeft: '0.5rem', padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
                      onClick={() => handleCancelSingleTask(pipelineQueue.current_task.id)}>Abbrechen</Button>
                  </p>
                )}
                {pipelineQueue.tasks?.map((t, i) => (
                  <p key={i} className="assistant-admin__text-sm">
                    • {t.task_type} Source {t.source_id} — {t.status}
                    {(t.status === 'pending' || t.status === 'running') && (
                      <Button variant="danger" style={{ marginLeft: '0.5rem', padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
                        onClick={() => handleCancelSingleTask(t.id)}>Abbrechen</Button>
                    )}
                  </p>
                ))}
              </>
            ) : (
              <p className="assistant-admin__empty">Keine Daten</p>
            )}
          </Card>

          <Card title="Aktivitätsfeed">
            {!pipelineHistoryLoaded ? (
              <p className="assistant-admin__empty">Lade Ereignisverlauf…</p>
            ) : pipelineEvents.length === 0 ? (
              <p className="assistant-admin__empty">
                Noch keine Ereignisse. Starten Sie einen Rebuild oder Sync, um die Aktivität hier zu sehen.
              </p>
            ) : (
              <>
                {/* Progress bar for current sub-step */}
                {(() => {
                  const last = pipelineEvents.find(e => e.progress != null);
                  if (!last) return null;
                  const pct = Math.round(last.progress * 100);
                  return (
                    <div className="assistant-admin__progress-bar-wrap">
                      <div className="assistant-admin__progress-bar">
                        <div
                          className="assistant-admin__progress-bar-fill"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="assistant-admin__progress-bar-label">{pct}% — {last.stage}</span>
                    </div>
                  );
                })()}

                <div className="assistant-admin__pipeline-feed" ref={pipelineFeedRef}>
                  {pipelineEvents.map((evt) => (
                    <div
                      key={evt._id}
                      className={`assistant-admin__pipeline-event assistant-admin__pipeline-event--${evt.level || 'info'}`}
                    >
                      <span className="assistant-admin__pipeline-event-time">
                        {new Date(evt.timestamp * 1000).toLocaleTimeString('de-DE')}
                      </span>
                      <span className={`assistant-admin__pipeline-event-badge assistant-admin__pipeline-event-badge--${evt.stage || 'info'}`}>
                        {evt.stage}
                      </span>
                      {evt.source_name && (
                        <span className="assistant-admin__pipeline-event-source">[{evt.source_name}]</span>
                      )}
                      <span className="assistant-admin__pipeline-event-msg">{evt.message}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </Card>

          {/* ── Scheduled Syncs ──────────────────────────────── */}
          <Card title="Automatische Syncs">
            <div style={{ marginBottom: '0.75rem' }}>
              <Button variant="primary" onClick={() => setShowScheduleForm(s => !s)}>
                {showScheduleForm ? 'Abbrechen' : 'Neuen automatischen Sync anlegen'}
              </Button>
            </div>

            {showScheduleForm && (
              <div className="assistant-admin__form" style={{ marginBottom: '1rem', padding: '0.75rem', background: '#f9f9f9', borderRadius: '6px' }}>
                <FormGroup label="Quelle">
                  <SelectInput value={scheduleForm.source_id}
                    onChange={e => setScheduleForm(f => ({ ...f, source_id: e.target.value }))}>
                    <option value="">— Quelle wählen —</option>
                    {sources.map(s => (
                      <option key={s.id} value={s.id}>{s.name} ({s.source_type})</option>
                    ))}
                  </SelectInput>
                </FormGroup>
                <FormGroup label="Häufigkeit">
                  <SelectInput value={scheduleForm.frequency}
                    onChange={e => setScheduleForm(f => ({ ...f, frequency: e.target.value }))}>
                    <option value="daily">Täglich</option>
                    <option value="weekly">Wöchentlich</option>
                  </SelectInput>
                </FormGroup>
                <FormGroup label="Uhrzeit (UTC)">
                  <TextInput type="time" value={scheduleForm.time_of_day}
                    onChange={e => setScheduleForm(f => ({ ...f, time_of_day: e.target.value }))} />
                </FormGroup>
                {scheduleForm.frequency === 'weekly' && (
                  <FormGroup label="Wochentag">
                    <SelectInput value={scheduleForm.day_of_week}
                      onChange={e => setScheduleForm(f => ({ ...f, day_of_week: Number(e.target.value) }))}>
                      <option value={0}>Montag</option>
                      <option value={1}>Dienstag</option>
                      <option value={2}>Mittwoch</option>
                      <option value={3}>Donnerstag</option>
                      <option value={4}>Freitag</option>
                      <option value={5}>Samstag</option>
                      <option value={6}>Sonntag</option>
                    </SelectInput>
                  </FormGroup>
                )}
                <Button variant="primary" onClick={handleCreateSchedule}
                  disabled={!scheduleForm.source_id}>Speichern</Button>
              </div>
            )}

            {scheduledSyncs.length === 0 ? (
              <p className="assistant-admin__empty">Keine automatischen Syncs konfiguriert.</p>
            ) : (
              <table className="shared-table">
                <thead>
                  <tr>
                    <th>Quelle</th>
                    <th>Häufigkeit</th>
                    <th>Zeit (UTC)</th>
                    <th>Tag</th>
                    <th>Status</th>
                    <th>Nächster Lauf</th>
                    <th>Letzter Lauf</th>
                    <th>Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {scheduledSyncs.map(sch => {
                    const src = sources.find(s => s.id === sch.source_id);
                    const dayNames = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
                    return (
                      <tr key={sch.id}>
                        <td>{src ? src.name : `Source ${sch.source_id}`}</td>
                        <td>{sch.frequency === 'daily' ? 'Täglich' : 'Wöchentlich'}</td>
                        <td>{sch.time_of_day}</td>
                        <td>{sch.frequency === 'weekly' && sch.day_of_week != null ? dayNames[sch.day_of_week] : '—'}</td>
                        <td>
                          <span style={{
                            padding: '0.15rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem',
                            background: sch.active ? '#e6f4ea' : '#fce8e6',
                            color: sch.active ? '#1e7e34' : '#c62828',
                          }}>
                            {sch.active ? 'Aktiv' : 'Inaktiv'}
                          </span>
                        </td>
                        <td style={{ fontSize: '0.8rem' }}>
                          {sch.next_run_at ? new Date(sch.next_run_at).toLocaleString('de-DE') : '—'}
                        </td>
                        <td style={{ fontSize: '0.8rem' }}>
                          {sch.last_run_at ? new Date(sch.last_run_at).toLocaleString('de-DE') : '—'}
                          {sch.last_run_status && (
                            <span style={{ marginLeft: '0.3rem', fontSize: '0.7rem', opacity: 0.7 }}>
                              ({sch.last_run_status})
                            </span>
                          )}
                        </td>
                        <td>
                          <Button variant="secondary" style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem', marginRight: '0.3rem' }}
                            onClick={() => handleToggleSchedule(sch.id, sch.active)}>
                            {sch.active ? 'Deaktivieren' : 'Aktivieren'}
                          </Button>
                          <Button variant="danger" style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
                            onClick={() => handleDeleteSchedule(sch.id)}>Löschen</Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </Card>
        </div>
      )}

      {/* ── Logs Tab ────────────────────────────────────────── */}
      {activeTab === 'logs' && !loading && (
        <div>
          <div className="assistant-admin__section-header">
            <h2 className="assistant-admin__section-title">Logs</h2>
            <Button variant="secondary" onClick={() => loadTab('logs')}>Aktualisieren</Button>
          </div>

          {/* Filters */}
          <div className="assistant-admin__log-filters">
            <div className="assistant-admin__log-filter-group">
              <label className="assistant-admin__log-filter-label">Typ</label>
              <SelectInput
                value={logEventTypeFilter}
                onChange={(e) => {
                  setLogEventTypeFilter(e.target.value);
                  setLogPage(1);
                }}
              >
                <option value="">Alle</option>
                {logEventTypes.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </SelectInput>
            </div>
            <div className="assistant-admin__log-filter-group">
              <label className="assistant-admin__log-filter-label">Quelle</label>
              <TextInput
                placeholder="Suche in Nachrichten..."
                value={logSourceFilter}
                onChange={(e) => {
                  setLogSourceFilter(e.target.value);
                  setLogPage(1);
                }}
              />
            </div>
            <Button
              variant="primary"
              onClick={() => loadTab('logs')}
            >
              Filtern
            </Button>
          </div>

          <Card>
            <div className="assistant-admin__logs-container">
              {logs.map((log) => (
                <div key={log.id} className="assistant-admin__log-entry">
                  <span className={`assistant-admin__log-badge assistant-admin__log-badge--${log.event_type === 'error' ? 'error' : 'success'}`}>
                    {log.event_type}
                  </span>
                  <span className="assistant-admin__log-message">{log.message}</span>
                  <span className="assistant-admin__log-time">
                    {log.created_at ? new Date(log.created_at).toLocaleString('de-DE') : ''}
                  </span>
                </div>
              ))}
              {logs.length === 0 && (
                <p className="assistant-admin__empty">Keine Logs vorhanden.</p>
              )}
            </div>

            {/* Pagination controls */}
            {logTotal > 0 && (
              <div className="assistant-admin__log-pagination">
                <Button
                  variant="secondary" size="sm"
                  disabled={!logHasPrev}
                  onClick={() => { setLogPage((p) => p - 1); }}
                >
                  ← Zurück
                </Button>
                <span className="assistant-admin__log-pagination-info">
                  Seite {logPage} von {logTotalPages} ({logTotal} Einträge)
                </span>
                <Button
                  variant="secondary" size="sm"
                  disabled={!logHasNext}
                  onClick={() => { setLogPage((p) => p + 1); }}
                >
                  Weiter →
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ── Vector DB Tab ───────────────────────────────────── */}
      {activeTab === 'vectordb' && !loading && (
        <div>
          <div className="assistant-admin__section-header">
            <h2 className="assistant-admin__section-title">Vector Database Status</h2>
          </div>

          {/* Count mismatch warning */}
          {vectorStats?.count_mismatch && (
            <MessageBox
              type="warning"
              message="Die Datenbank zeigt 0 Dokumente, aber Qdrant enthält Vektoren. Klicken Sie auf 'Zähler abgleichen', um die Zähler zu korrigieren."
            />
          )}

          {/* Stats Overview */}
          {vectorStats && (
            <>
              <div className="assistant-admin__stat-row">
                <StatCard
                  value={vectorStats.vector_count || 0}
                  label="Vektoren gespeichert"
                  variant="info"
                />
                <StatCard
                  value={vectorStats.documents_indexed || 0}
                  label="Dokumente indexiert"
                  variant="info"
                />
                <StatCard
                  value={vectorStats.chunks_indexed || 0}
                  label="Chunks"
                  variant="info"
                />
                <StatCard
                  value={vectorStats.vector_dimension ?? '—'}
                  label="Modell-Dimension"
                  variant={vectorStats.dimension_mismatch ? 'danger' : 'default'}
                />
                <StatCard
                  value={vectorStats.embedding_available ? 'Online' : 'Offline'}
                  label="Embedding Service"
                  variant={vectorStats.embedding_available ? 'success' : 'danger'}
                />
              </div>

              <div className="assistant-admin__detail-row">
                <Card title="Qdrant Collection">
                  <p className="assistant-admin__text-sm">Collection: <strong>{vectorStats.collection}</strong></p>
                  <p className="assistant-admin__text-sm">Status: <strong>{vectorStats.collection_status}</strong></p>
                  <p className="assistant-admin__text-sm">URL: <code>{vectorStats.qdrant_url}</code></p>
                  <p className="assistant-admin__text-sm">
                    Gespeicherte Vektordimension: {vectorStats.collection_stored_dimension ?? '—'}
                  </p>
                  {vectorStats.dimension_mismatch && (
                    <p className="assistant-admin__text-sm" style={{ color: 'var(--color-danger, #dc2626)', fontWeight: 600 }}>
                      ⚠ Dimension mismatch! Collection hat dim={vectorStats.collection_stored_dimension},
                      Embedding-Modell liefert dim={vectorStats.vector_dimension}.
                      Bitte Index neu aufbauen (Pipeline → Index neu aufbauen).
                    </p>
                  )}
                </Card>
                <Card title="Embedding-Modell">
                  <p className="assistant-admin__text-sm">Modell: <strong>{vectorStats.embedding_model}</strong></p>
                  <p className="assistant-admin__text-sm">Ollama URL: <code>{vectorStats.ollama_url}</code></p>
                  <p className="assistant-admin__text-sm">Live-Dimension: {vectorStats.vector_dimension || '—'}</p>
                  <p className="assistant-admin__text-sm">
                    Status:{' '}
                    <span className={`assistant-admin__status-text--${vectorStats.embedding_available ? 'success' : 'error'}`}>
                      {vectorStats.embedding_available ? 'Erreichbar' : 'Nicht erreichbar'}
                    </span>
                  </p>
                </Card>
              </div>

              {/* Per-Source Breakdown */}
              {vectorStats.sources && vectorStats.sources.length > 0 && (
                <Card title="Quellen-Übersicht">
                  <div className="shared-table-container">
                    <table className="shared-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Name</th>
                          <th>Typ</th>
                          <th>Dokumente</th>
                          <th>Status</th>
                          <th>Letzter Sync</th>
                        </tr>
                      </thead>
                      <tbody>
                        {vectorStats.sources.map((s) => (
                          <tr key={s.id}>
                            <td>{s.id}</td>
                            <td><strong>{s.name}</strong></td>
                            <td>{s.source_type}</td>
                            <td>{s.document_count}</td>
                            <td>
                              <span className={`assistant-admin__status-text--${s.last_sync_status === 'success' ? 'success' : 'error'}`}>
                                {s.last_sync_status || '—'}
                              </span>
                            </td>
                            <td>{s.last_sync_at ? new Date(s.last_sync_at).toLocaleString('de-DE') : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}
            </>
          )}

          {/* Qdrant Debug: Metadata Issues */}
          {qdrantDebug && qdrantDebug.metadata_issues_count > 0 && (
            <Card title={`Metadaten-Prüfung (${qdrantDebug.sample_count} geprüft)`}>
              <div className="assistant-admin__debug-issues">
                <p className="assistant-admin__text-sm assistant-admin__text-sm--warning">
                  ⚠ {qdrantDebug.metadata_issues_count} Metadaten-Probleme gefunden:
                </p>
                <ul className="assistant-admin__issue-list">
                  {qdrantDebug.metadata_issues.slice(0, 10).map((issue, i) => (
                    <li key={i} className="assistant-admin__text-sm">{issue}</li>
                  ))}
                  {qdrantDebug.metadata_issues.length > 10 && (
                    <li className="assistant-admin__text-sm">... und {qdrantDebug.metadata_issues.length - 10} weitere</li>
                  )}
                </ul>
              </div>
            </Card>
          )}
          {qdrantDebug && qdrantDebug.metadata_issues_count === 0 && qdrantDebug.sample_count > 0 && (
            <Card title="Metadaten-Prüfung">
              <p className="assistant-admin__text-sm" style={{ color: 'var(--color-success, #16a34a)' }}>
                ✓ Keine Metadaten-Probleme in der Stichprobe ({qdrantDebug.sample_count} Einträge) gefunden.
              </p>
            </Card>
          )}

          {/* ── Document Browser with Pagination ── */}
          <Card title="Dokument-Browser">
            {/* Filters */}
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem', alignItems: 'flex-end' }}>
              <div style={{ minWidth: '160px' }}>
                <label className="assistant-admin__text-sm" style={{ display: 'block', marginBottom: '0.25rem' }}>Quelle</label>
                <SelectInput
                  value={qdrantDocsFilter.source_id}
                  onChange={(e) => setQdrantDocsFilter((f) => ({ ...f, source_id: e.target.value }))}
                >
                  <option value="">Alle Quellen</option>
                  {(vectorStats?.sources || []).map((s) => (
                    <option key={s.id} value={s.id}>{s.name} ({s.source_type})</option>
                  ))}
                </SelectInput>
              </div>
              <div style={{ minWidth: '140px' }}>
                <label className="assistant-admin__text-sm" style={{ display: 'block', marginBottom: '0.25rem' }}>Tag</label>
                <TextInput
                  placeholder="Tag filtern..."
                  value={qdrantDocsFilter.tag}
                  onChange={(e) => setQdrantDocsFilter((f) => ({ ...f, tag: e.target.value }))}
                />
              </div>
              <div style={{ minWidth: '180px', flex: 1 }}>
                <label className="assistant-admin__text-sm" style={{ display: 'block', marginBottom: '0.25rem' }}>Titelsuche</label>
                <TextInput
                  placeholder="Im Titel suchen..."
                  value={qdrantDocsFilter.search}
                  onChange={(e) => setQdrantDocsFilter((f) => ({ ...f, search: e.target.value }))}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleDocsFilterApply(); }}
                />
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <Button variant="primary" onClick={handleDocsFilterApply}>Filtern</Button>
                <Button variant="secondary" onClick={handleDocsFilterReset}>Zurücksetzen</Button>
              </div>
            </div>

            {/* Pagination top */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span className="assistant-admin__text-sm">
                {qdrantDocsTotal > 0
                  ? `${qdrantDocs.length} von ~${qdrantDocsTotal} Einträgen`
                  : 'Keine Einträge'}
                {(qdrantDocsFilter.source_id || qdrantDocsFilter.tag || qdrantDocsFilter.search) && ' (gefiltert)'}
              </span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <Button
                  variant="secondary" size="sm"
                  disabled={qdrantDocsOffsetHistory.length === 0 || qdrantDocsLoading}
                  onClick={handleDocsPrevPage}
                >
                  ← Zurück
                </Button>
                <span className="assistant-admin__text-sm" style={{ lineHeight: '2rem' }}>
                  Seite {qdrantDocsOffsetHistory.length + 1}
                </span>
                <Button
                  variant="secondary" size="sm"
                  disabled={qdrantDocsNextOffset == null || qdrantDocsLoading}
                  onClick={handleDocsNextPage}
                >
                  Weiter →
                </Button>
              </div>
            </div>

            {/* Loading spinner */}
            {qdrantDocsLoading && (
              <div style={{ textAlign: 'center', padding: '1rem' }}>
                <Spinner size="sm" /> Lade Dokumente...
              </div>
            )}

            {/* Documents table */}
            {!qdrantDocsLoading && qdrantDocs.length > 0 && (
              <div className="shared-table-container">
                <table className="shared-table">
                  <thead>
                    <tr>
                      <th style={{ width: '30px' }}></th>
                      <th>Quelle</th>
                      <th>Titel</th>
                      <th>Chunk</th>
                      <th>Länge</th>
                      <th>Tags</th>
                      <th>URL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {qdrantDocs.map((doc) => (
                      <>
                        <tr
                          key={doc.id}
                          style={{ cursor: 'pointer' }}
                          onClick={() => setExpandedDocId(expandedDocId === doc.id ? null : doc.id)}
                        >
                          <td style={{ textAlign: 'center', fontSize: '0.75rem' }}>
                            {expandedDocId === doc.id ? '▼' : '▶'}
                          </td>
                          <td>{doc.source || '—'}</td>
                          <td><strong>{doc.title || '—'}</strong></td>
                          <td>{doc.chunk_position ?? '—'}</td>
                          <td>{doc.chunk_length != null ? `${doc.chunk_length} Z.` : '—'}</td>
                          <td>
                            {doc.permission_tags && doc.permission_tags.length > 0
                              ? doc.permission_tags.join(', ')
                              : <span style={{ color: 'var(--color-text-secondary)' }}>keine</span>
                            }
                          </td>
                          <td>
                            {doc.document_url ? (
                              <a
                                href={doc.document_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="assistant-admin__link"
                                onClick={(e) => e.stopPropagation()}
                              >
                                Link
                              </a>
                            ) : '—'}
                          </td>
                        </tr>
                        {expandedDocId === doc.id && (
                          <tr key={`${doc.id}-detail`}>
                            <td colSpan={7} style={{ padding: '0.75rem 1rem', background: 'var(--color-bg-secondary, #f9fafb)' }}>
                              <div style={{ marginBottom: '0.5rem' }}>
                                <strong>ID:</strong> <code style={{ fontSize: '0.75rem' }}>{doc.id}</code>
                                {doc.source_id && <> &nbsp;|&nbsp; <strong>Source ID:</strong> {doc.source_id}</>}
                              </div>
                              {doc.chunk_text ? (
                                <pre style={{
                                  whiteSpace: 'pre-wrap',
                                  wordBreak: 'break-word',
                                  fontSize: '0.8rem',
                                  maxHeight: '300px',
                                  overflow: 'auto',
                                  background: 'var(--color-bg-tertiary, #f3f4f6)',
                                  padding: '0.5rem',
                                  borderRadius: '4px',
                                  margin: 0,
                                }}>
                                  {doc.chunk_text}
                                </pre>
                              ) : (
                                <p className="assistant-admin__text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                                  Kein Chunk-Text verfügbar.
                                </p>
                              )}
                            </td>
                          </tr>
                        )}
                      </>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {!qdrantDocsLoading && qdrantDocs.length === 0 && (
              <p className="assistant-admin__empty">Keine Dokumente gefunden.</p>
            )}
          </Card>

          {!vectorStats && !qdrantDebug && (
            <Card><p className="assistant-admin__empty">Keine Daten verfügbar.</p></Card>
          )}
        </div>
      )}
    </PageContainer>

    {confirmModal.open && (
      <Modal
        title={confirmModal.title}
        size="sm"
        onClose={closeConfirm}
        footer={
          <>
            <Button variant="secondary" onClick={closeConfirm}>Abbrechen</Button>
            <Button variant="danger" onClick={confirmModal.onConfirm}>Bestätigen</Button>
          </>
        }
      >
        <p>{confirmModal.message}</p>
      </Modal>
    )}
    </>
  );
}

export default AssistantAdminPage;
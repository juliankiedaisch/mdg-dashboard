// Assistant Module - Frontend API Service
import api from '../../../utils/api';

const BASE = '/api/assistant';
const ADMIN = '/api/assistant/admin';

// ── Chat Sessions ──────────────────────────────────────────────────

export const getSessions = (archived = false) =>
  api.get(`${BASE}/sessions`, { params: { archived } });

export const createSession = (title = 'New Chat') =>
  api.post(`${BASE}/sessions`, { title });

export const getSession = (sessionUuid) =>
  api.get(`${BASE}/sessions/${sessionUuid}`);

export const updateSession = (sessionUuid, title) =>
  api.put(`${BASE}/sessions/${sessionUuid}`, { title });

export const deleteSession = (sessionUuid) =>
  api.delete(`${BASE}/sessions/${sessionUuid}`);

export const archiveSession = (sessionUuid) =>
  api.post(`${BASE}/sessions/${sessionUuid}/archive`);

// ── Chat ───────────────────────────────────────────────────────────

export const sendMessage = (message, sessionUuid = '') =>
  api.post(`${BASE}/chat`, { message, session_uuid: sessionUuid });

export const sendMessageStream = async (message, sessionUuid, onChunk, onSources, onDone, onError, onDebug, onDiagnostics) => {
  try {
    const response = await fetch(
      `${api.defaults.baseURL}${BASE}/chat/stream`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ message, session_uuid: sessionUuid }),
      }
    );

    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Stream failed' }));
      onError?.(err.error || 'Stream failed');
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === 'chunk') onChunk?.(data.data);
          else if (data.type === 'sources') onSources?.(data.data);
          else if (data.type === 'done') onDone?.(data.session_uuid);
          else if (data.type === 'error') onError?.(data.data);
          else if (data.type === 'debug') onDebug?.(data.data);
          else if (data.type === 'diagnostics') onDiagnostics?.(data.data);
        } catch {
          // skip malformed lines
        }
      }
    }
  } catch (err) {
    onError?.(err.message);
  }
};

// ── Feedback ───────────────────────────────────────────────────────

export const setMessageFeedback = (messageId, feedback) =>
  api.post(`${BASE}/messages/${messageId}/feedback`, { feedback });

// ── Admin: Status ──────────────────────────────────────────────────

export const getAdminStatus = () =>
  api.get(`${ADMIN}/status`);

export const getAdminLogs = (limit = 50, page = 1, eventType = null, source = null) =>
  api.get(`${ADMIN}/logs`, {
    params: {
      limit,
      page,
      event_type: eventType || undefined,
      source: source || undefined,
    },
  });

export const getAdminLogEventTypes = () =>
  api.get(`${ADMIN}/logs/event-types`);

// ── Admin: Sources ─────────────────────────────────────────────────

export const getAdminSources = () =>
  api.get(`${ADMIN}/sources`);

export const createAdminSource = (data) =>
  api.post(`${ADMIN}/sources`, data);

export const getAdminSource = (sourceId) =>
  api.get(`${ADMIN}/sources/${sourceId}`);

export const updateAdminSource = (sourceId, data) =>
  api.put(`${ADMIN}/sources/${sourceId}`, data);

export const deleteAdminSource = (sourceId) =>
  api.delete(`${ADMIN}/sources/${sourceId}`);

export const testAdminSource = (sourceId) =>
  api.post(`${ADMIN}/sources/${sourceId}/test`);

export const syncAdminSource = (sourceId) =>
  api.post(`${ADMIN}/sources/${sourceId}/sync`);

export const getSourceSyncStatus = () =>
  api.get(`${ADMIN}/sources/sync-status`);

// ── Admin: Models ──────────────────────────────────────────────────

export const getAdminModels = () =>
  api.get(`${ADMIN}/models`);

export const pullAdminModel = (name) =>
  api.post(`${ADMIN}/models/pull`, { name });

export const removeAdminModel = (name) =>
  api.post(`${ADMIN}/models/remove`, { name });

export const testAdminModel = (name) =>
  api.post(`${ADMIN}/models/test`, { name });

export const getModelStatus = () =>
  api.get(`${ADMIN}/models/status`);

// ── Admin: Config ──────────────────────────────────────────────────

export const getAdminConfig = () =>
  api.get(`${ADMIN}/config`);

export const setAdminConfig = (key, value, description = '') =>
  api.post(`${ADMIN}/config`, { key, value, description });

// ── Admin: Pipeline ────────────────────────────────────────────────

export const rebuildIndex = () =>
  api.post(`${ADMIN}/pipeline/rebuild`);

export const getPipelineQueue = () =>
  api.get(`${ADMIN}/pipeline/queue`);

export const purgeEmbeddings = () =>
  api.post(`${ADMIN}/pipeline/purge`);

export const cancelAllTasks = () =>
  api.post(`${ADMIN}/pipeline/cancel`);

export const cancelSingleTask = (taskId) =>
  api.post(`${ADMIN}/pipeline/cancel/${taskId}`);

export const getPipelineEvents = (params = {}) =>
  api.get(`${ADMIN}/pipeline/events`, { params });

export const clearPipelineEvents = () =>
  api.delete(`${ADMIN}/pipeline/events`);

// ── Admin: Vector DB Debug ─────────────────────────────────────────

export const getVectorStats = () =>
  api.get(`${ADMIN}/vector-stats`);

export const getQdrantDebug = (limit = 20) =>
  api.get(`${ADMIN}/qdrant-debug`, { params: { limit } });

export const getQdrantDocuments = ({ limit = 50, offset, source_id, source, tag, search } = {}) =>
  api.get(`${ADMIN}/qdrant-documents`, {
    params: { limit, offset, source_id, source, tag, search },
  });

export const reconcileDocumentCounts = () =>
  api.post(`${ADMIN}/reconcile-counts`);

// ── Admin: Tags ────────────────────────────────────────────────────

export const getAdminTags = () =>
  api.get(`${ADMIN}/tags`);

export const createAdminTag = (data) =>
  api.post(`${ADMIN}/tags`, data);

export const getAdminTag = (tagId) =>
  api.get(`${ADMIN}/tags/${tagId}`);

export const updateAdminTag = (tagId, data) =>
  api.put(`${ADMIN}/tags/${tagId}`, data);

export const deleteAdminTag = (tagId) =>
  api.delete(`${ADMIN}/tags/${tagId}`);

// ── Admin: Source Tags ─────────────────────────────────────────────

export const getSourceTags = (sourceId) =>
  api.get(`${ADMIN}/sources/${sourceId}/tags`);

export const setSourceTags = (sourceId, tagIds) =>
  api.put(`${ADMIN}/sources/${sourceId}/tags`, { tag_ids: tagIds });

// ── Admin: Retrieval Configuration ─────────────────────────────────

export const getAdminRetrievalConfig = () =>
  api.get(`${ADMIN}/retrieval-config`);

export const updateAdminRetrievalConfig = (data) =>
  api.put(`${ADMIN}/retrieval-config`, data);

// ── Admin: BM25 Index ──────────────────────────────────────────────

export const rebuildBm25Index = () =>
  api.post(`${ADMIN}/bm25/rebuild`);

export const getBm25Status = () =>
  api.get(`${ADMIN}/bm25/status`);

// ── Admin: Retrieval Test (Diagnostics) ────────────────────────────

export const testRetrieval = (query, topK = 10) =>
  api.post(`${ADMIN}/retrieval-test`, { query, top_k: topK });

// ── User: Retrieval Configuration ──────────────────────────────────

export const getUserRetrievalConfig = () =>
  api.get(`${BASE}/retrieval-config`);

export const updateUserRetrievalConfig = (data) =>
  api.put(`${BASE}/retrieval-config`, data);

export const resetUserRetrievalConfig = () =>
  api.delete(`${BASE}/retrieval-config`);

// ── Admin: Scheduled Syncs ─────────────────────────────────────────

export const getScheduledSyncs = () =>
  api.get(`${ADMIN}/scheduled-syncs`);

export const createScheduledSync = (data) =>
  api.post(`${ADMIN}/scheduled-syncs`, data);

export const updateScheduledSync = (scheduleId, data) =>
  api.put(`${ADMIN}/scheduled-syncs/${scheduleId}`, data);

export const deleteScheduledSync = (scheduleId) =>
  api.delete(`${ADMIN}/scheduled-syncs/${scheduleId}`);

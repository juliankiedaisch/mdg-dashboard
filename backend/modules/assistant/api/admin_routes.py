# Assistant Module - API: Admin Routes
"""
Routes for admin management (sources, models, pipeline, dashboard).
Requires: assistant.manage permission.
"""
import logging
from flask import Blueprint, request, jsonify, session

from src.decorators import login_required, permission_required

logger = logging.getLogger(__name__)
from modules.assistant.services import source_service
from modules.assistant.services import tag_service
from modules.assistant.services.model_service import (
    get_model_service, get_config_value, set_config_value, get_all_config,
)
from modules.assistant.dashboard.metrics_service import (
    get_assistant_status, get_source_sync_status, get_recent_logs,
    get_log_event_types,
)
from modules.assistant.tasks.ingestion_worker import (
    enqueue_ingestion, get_queue_status, cancel_all_tasks, cancel_single_task,
)
from src.utils import utc_isoformat


def register_admin_routes(bp, oauth):
    """Register admin API routes on the given Blueprint."""
    url = '/api/assistant/admin'

    # ── Dashboard / Status ──────────────────────────────────────────

    @bp.route(f"{url}/status", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def admin_status():
        status = get_assistant_status()
        return jsonify(status)

    @bp.route(f"{url}/logs", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def admin_logs():
        limit = request.args.get('limit', 50, type=int)
        page = request.args.get('page', 1, type=int)
        event_type = request.args.get('event_type', None)
        level = request.args.get('level', None)
        source = request.args.get('source', None)
        result = get_recent_logs(
            limit=limit, event_type=event_type,
            page=page, level=level, source=source,
        )
        return jsonify(result)

    @bp.route(f"{url}/logs/event-types", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def admin_log_event_types():
        types = get_log_event_types()
        return jsonify({"event_types": types})

    # ── Sources ─────────────────────────────────────────────────────

    @bp.route(f"{url}/sources", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def list_sources():
        sources = source_service.get_all_sources()
        return jsonify({"sources": sources})

    @bp.route(f"{url}/sources", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def create_source():
        data = request.get_json(silent=True) or {}
        result, err = source_service.create_source(
            name=data.get('name', ''),
            source_type=data.get('source_type', ''),
            config=data.get('config', {}),
            enabled=data.get('enabled', True),
        )
        if err:
            return jsonify({"status": False, "message": err}), 400
        return jsonify({"status": True, "source": result}), 201

    @bp.route(f"{url}/sources/<int:source_id>", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def get_source(source_id):
        source = source_service.get_source(source_id)
        if not source:
            return jsonify({"error": "Source not found."}), 404
        return jsonify({"source": source})

    @bp.route(f"{url}/sources/<int:source_id>", methods=["PUT"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def update_source(source_id):
        data = request.get_json(silent=True) or {}
        result, err = source_service.update_source(
            source_id,
            name=data.get('name'),
            enabled=data.get('enabled'),
            config=data.get('config'),
        )
        if err:
            return jsonify({"status": False, "message": err}), 400
        return jsonify({"status": True, "source": result})

    @bp.route(f"{url}/sources/<int:source_id>", methods=["DELETE"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def delete_source(source_id):
        # Also delete vectors for this source
        from modules.assistant.rag.vector_store import get_vector_store
        get_vector_store().delete_by_source(source_id)

        result, err = source_service.delete_source(source_id)
        if err:
            return jsonify({"status": False, "message": err}), 404
        return jsonify(result)

    @bp.route(f"{url}/sources/<int:source_id>/test", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def test_source(source_id):
        result = source_service.test_source_connection(source_id)
        return jsonify(result)

    @bp.route(f"{url}/sources/<int:source_id>/sync", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def sync_source(source_id):
        source = source_service.get_source(source_id)
        if not source:
            return jsonify({"error": "Source not found."}), 404
        task = enqueue_ingestion(source_id, task_type='sync', source_config=source)
        return jsonify({"status": True, "task": task})

    @bp.route(f"{url}/sources/sync-status", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def sync_status():
        status = get_source_sync_status()
        return jsonify({"sources": status})

    # ── Models ──────────────────────────────────────────────────────

    @bp.route(f"{url}/models", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def list_models():
        model_service = get_model_service()
        models = model_service.list_models()
        return jsonify({"models": models})

    @bp.route(f"{url}/models/pull", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def pull_model():
        data = request.get_json(silent=True) or {}
        model_name = data.get('name', '')
        if not model_name:
            return jsonify({"error": "Model name is required."}), 400
        model_service = get_model_service()
        result = model_service.pull_model(model_name)
        return jsonify(result)

    @bp.route(f"{url}/models/remove", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def remove_model():
        data = request.get_json(silent=True) or {}
        model_name = data.get('name', '')
        if not model_name:
            return jsonify({"error": "Model name is required."}), 400
        model_service = get_model_service()
        result = model_service.remove_model(model_name)
        return jsonify(result)

    @bp.route(f"{url}/models/test", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def test_model():
        data = request.get_json(silent=True) or {}
        model_name = data.get('name', '')
        if not model_name:
            return jsonify({"error": "Model name is required."}), 400
        model_service = get_model_service()
        result = model_service.test_model(model_name)
        return jsonify(result)

    @bp.route(f"{url}/models/status", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def model_status():
        model_service = get_model_service()
        return jsonify(model_service.get_status())

    # ── Config ──────────────────────────────────────────────────────

    @bp.route(f"{url}/config", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def get_config():
        config = get_all_config()
        return jsonify({"config": config})

    @bp.route(f"{url}/config", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def set_config():
        data = request.get_json(silent=True) or {}
        key = data.get('key', '')
        value = data.get('value', '')
        description = data.get('description', '')
        if not key or not value:
            return jsonify({"error": "Key and value are required."}), 400
        result = set_config_value(key, value, description)
        return jsonify({"config": result})

    # ── Pipeline ────────────────────────────────────────────────────

    @bp.route(f"{url}/pipeline/rebuild", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def rebuild_index():
        """Full rebuild of the vector index."""
        task = enqueue_ingestion(0, task_type='full_rebuild')
        return jsonify({"status": True, "task": task, "message": "Full rebuild enqueued."})

    @bp.route(f"{url}/pipeline/queue", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def pipeline_queue():
        return jsonify(get_queue_status())

    @bp.route(f"{url}/pipeline/cancel", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def cancel_pipeline():
        """Abort the running job and delete all pending/running tasks."""
        from flask import current_app
        result = cancel_all_tasks(current_app._get_current_object())
        return jsonify({
            "status": True,
            "cancelled": result['cancelled'],
            "message": f"{result['cancelled']} Aufgabe(n) abgebrochen und gelöscht.",
        })
    @bp.route(f"{url}/pipeline/cancel/<int:task_id>", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def cancel_single_pipeline_task(task_id):
        """Cancel a single task by its ID."""
        from flask import current_app
        result = cancel_single_task(current_app._get_current_object(), task_id)
        status_code = 200 if result.get('cancelled') else 404
        return jsonify({
            "status": result.get('cancelled', False),
            "message": result.get('message', ''),
            "task_id": task_id,
        }), status_code
    @bp.route(f"{url}/pipeline/extraction-health", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def extraction_health():
        """Check health of external document extraction services (Docling & Tika)."""
        from modules.assistant.services.extraction_service import check_service_health
        return jsonify(check_service_health())

    @bp.route(f"{url}/pipeline/purge", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def purge_embeddings():
        """Delete all embeddings (purge vector store)."""
        from modules.assistant.rag.vector_store import get_vector_store
        vs = get_vector_store()
        success = vs.delete_collection()
        if success:
            vs.ensure_collection()
            return jsonify({"status": True, "message": "All embeddings purged."})
        return jsonify({"status": False, "message": "Failed to purge embeddings."}), 500

    @bp.route(f"{url}/pipeline/events", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def pipeline_events():
        """Return persisted pipeline activity events for history display.

        Query parameters
        ----------------
        limit   : int   Maximum rows to return (default 500, max 1000).
        offset  : int   Pagination offset (default 0).
        task_id : int   Filter by sync task id.
        stage   : str   Filter by stage name.
        level   : str   Filter by level (info/warning/error/success).
        since   : float Unix timestamp lower bound (inclusive).
        before  : float Unix timestamp upper bound (exclusive).
        """
        from modules.assistant.models.pipeline_event import PipelineEvent

        limit = min(request.args.get('limit', 500, type=int), 1000)
        offset = request.args.get('offset', 0, type=int)
        task_id = request.args.get('task_id', None, type=int)
        stage = request.args.get('stage', None)
        level = request.args.get('level', None)
        since = request.args.get('since', None, type=float)
        before = request.args.get('before', None, type=float)

        q = PipelineEvent.query
        if task_id is not None:
            q = q.filter(PipelineEvent.task_id == task_id)
        if stage:
            q = q.filter(PipelineEvent.stage == stage)
        if level:
            q = q.filter(PipelineEvent.level == level)
        if since is not None:
            q = q.filter(PipelineEvent.ts >= since)
        if before is not None:
            q = q.filter(PipelineEvent.ts < before)

        total = q.count()
        events = (
            q.order_by(PipelineEvent.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return jsonify({
            "events": [e.to_dict() for e in events],
            "total": total,
            "has_more": (offset + limit) < total,
        })

    @bp.route(f"{url}/pipeline/events", methods=["DELETE"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def clear_pipeline_events():
        """Delete all persisted pipeline activity events.

        Clears the ``assistant_pipeline_events`` table so the activity feed
        starts from a clean state.  This is the backend counterpart to the
        \"Feed leeren\" button in the admin UI.
        """
        from modules.assistant.models.pipeline_event import PipelineEvent
        from src.db import db

        try:
            count = PipelineEvent.query.delete()
            db.session.commit()
            logger.info("[Admin] Cleared %d pipeline events", count)
            return jsonify({
                "status": True,
                "deleted": count,
                "message": f"{count} Ereignisse gel\u00f6scht.",
            })
        except Exception as e:
            db.session.rollback()
            logger.error("[Admin] Failed to clear pipeline events: %s", e)
            return jsonify({"status": False, "message": str(e)}), 500

    # ── Tags ────────────────────────────────────────────────────────

    @bp.route(f"{url}/tags", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def list_tags():
        """List all assistant tags."""
        tags = tag_service.get_all_tags()
        return jsonify({"tags": tags})

    @bp.route(f"{url}/tags", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def create_tag():
        """Create a new tag (and its corresponding permission)."""
        data = request.get_json(silent=True) or {}
        result, err = tag_service.create_tag(
            name=data.get('name', ''),
            description=data.get('description', ''),
        )
        if err:
            return jsonify({"status": False, "message": err}), 400
        return jsonify({"status": True, "tag": result}), 201

    @bp.route(f"{url}/tags/<int:tag_id>", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def get_tag(tag_id):
        """Get a single tag."""
        tag = tag_service.get_tag(tag_id)
        if not tag:
            return jsonify({"error": "Tag not found."}), 404
        return jsonify({"tag": tag})

    @bp.route(f"{url}/tags/<int:tag_id>", methods=["PUT"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def update_tag(tag_id):
        """Update a tag."""
        data = request.get_json(silent=True) or {}
        result, err = tag_service.update_tag(
            tag_id,
            name=data.get('name'),
            description=data.get('description'),
        )
        if err:
            return jsonify({"status": False, "message": err}), 400
        return jsonify({"status": True, "tag": result})

    @bp.route(f"{url}/tags/<int:tag_id>", methods=["DELETE"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def delete_tag(tag_id):
        """Delete a tag (and its corresponding permission)."""
        result, err = tag_service.delete_tag(tag_id)
        if err:
            return jsonify({"status": False, "message": err}), 404
        return jsonify(result)

    # ── Source Tag Assignment ───────────────────────────────────────

    @bp.route(f"{url}/sources/<int:source_id>/tags", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def get_source_tags(source_id):
        """Get tags assigned to a source."""
        tags = tag_service.get_source_tags(source_id)
        return jsonify({"tags": tags})

    @bp.route(f"{url}/sources/<int:source_id>/tags", methods=["PUT"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def set_source_tags(source_id):
        """Set tags for a source. Body: {"tag_ids": [1, 2, 3]}"""
        data = request.get_json(silent=True) or {}
        tag_ids = data.get('tag_ids', [])
        result, err = tag_service.set_source_tags(source_id, tag_ids)
        if err:
            return jsonify({"status": False, "message": err}), 400
        return jsonify({"status": True, "source": result})

    # ── Debug / diagnostics ─────────────────────────────────────────

    @bp.route(f"{url}/reconcile-counts", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def reconcile_counts():
        """Reconcile DB document counts with actual Qdrant point counts."""
        result = source_service.reconcile_document_counts()
        return jsonify({"status": True, **result})

    @bp.route(f"{url}/vector-stats", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def vector_stats():
        """Return vector DB statistics in the format expected by the admin UI."""
        from modules.assistant.rag.vector_store import get_vector_store
        from modules.assistant.rag.embeddings import get_embedding_service
        from modules.assistant.models.source_config import SourceConfig

        vs = get_vector_store()
        es = get_embedding_service()
        collection_info = vs.get_collection_info()

        # Total documents and chunks from DB
        sources = SourceConfig.query.all()
        documents_indexed_db = sum(s.document_count for s in sources)

        # Vector count from Qdrant
        vector_count = 0
        collection_stored_dim = None
        collection_status = 'unknown'
        if collection_info:
            vector_count = collection_info.get('points_count', 0)
            collection_status = collection_info.get('status', 'unknown')
            collection_stored_dim = collection_info.get('vector_size')

        # If DB says 0 but Qdrant has vectors, flag the mismatch so the
        # admin UI can prompt a reconcile.
        count_mismatch = (
            documents_indexed_db == 0
            and vector_count > 0
        )

        # Live embedding dimension test
        embed_ok = False
        live_dimension = None
        try:
            test_vec = es.embed_text("dimension probe")
            if test_vec:
                live_dimension = len(test_vec)
                embed_ok = True
        except Exception:
            pass

        # Warn if there's a dimension mismatch between collection and model
        dim_mismatch = (
            collection_stored_dim is not None
            and live_dimension is not None
            and collection_stored_dim != live_dimension
        )

        return jsonify({
            "collection": vs.collection_name,
            "collection_status": collection_status,
            "documents_indexed": documents_indexed_db,
            "documents_indexed_db": documents_indexed_db,
            "chunks_indexed": vector_count,
            "vector_count": vector_count,
            "vector_dimension": live_dimension,
            "collection_stored_dimension": collection_stored_dim,
            "dimension_mismatch": dim_mismatch,
            "count_mismatch": count_mismatch,
            "embedding_model": es.model,
            "embedding_available": embed_ok,
            "qdrant_url": vs.qdrant_url,
            "ollama_url": es.ollama_url,
            "sources": [
                {
                    "id": s.id,
                    "name": s.name,
                    "source_type": s.source_type,
                    "document_count": s.document_count,
                    "enabled": s.enabled,
                    "last_sync_status": s.last_sync_status,
                    "last_sync_at": utc_isoformat(s.last_sync_at),
                }
                for s in sources
            ],
        })

    @bp.route(f"{url}/qdrant-debug", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def qdrant_debug():
        """Return sample vectors and metadata from Qdrant for debugging."""
        from modules.assistant.rag.vector_store import get_vector_store

        vs = get_vector_store()
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 100)  # cap

        samples = vs.scroll_sample(limit=limit)

        sample_vectors = []
        for s in samples:
            payload = s.get('payload', {})
            sample_vectors.append({
                "id": s['id'],
                "source": payload.get('source', ''),
                "source_id": payload.get('source_id', ''),
                "title": payload.get('title', ''),
                "chunk_position": payload.get('chunk_position', 0),
                "chunk_length": len(payload.get('chunk_text', '')),
                "document_url": payload.get('document_url', ''),
                "permission_tags": payload.get('permission_tags', []),
                "has_chunk_text": bool(payload.get('chunk_text')),
            })

        # Metadata consistency check
        issues = []
        for sv in sample_vectors:
            if not sv['source']:
                issues.append(f"Point {sv['id']}: missing 'source' metadata")
            if not sv['title']:
                issues.append(f"Point {sv['id']}: missing 'title' metadata")
            if not sv['has_chunk_text']:
                issues.append(f"Point {sv['id']}: missing 'chunk_text' metadata")
            if not sv['permission_tags']:
                issues.append(f"Point {sv['id']}: empty 'permission_tags' (only accessible to super_admin)")

        return jsonify({
            "sample_count": len(sample_vectors),
            "sample_vectors": sample_vectors,
            "metadata_issues": issues,
            "metadata_issues_count": len(issues),
        })

    @bp.route(f"{url}/qdrant-documents", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def qdrant_documents():
        """Paginated, filterable document browser for the Vector DB inspection UI.

        Query params:
            limit      – page size (default 50, max 200)
            offset     – Qdrant scroll offset (opaque string from previous page)
            source_id  – filter by source ID (int)
            source     – filter by source name (string, e.g. 'bookstack')
            tag        – filter by permission tag name
            search     – substring search in title / chunk_text
        """
        from modules.assistant.rag.vector_store import get_vector_store

        vs = get_vector_store()
        limit = min(request.args.get('limit', 50, type=int), 200)
        offset = request.args.get('offset', None, type=str)
        source_id = request.args.get('source_id', None, type=int)
        source = request.args.get('source', None, type=str)
        tag = request.args.get('tag', None, type=str)
        search = request.args.get('search', None, type=str)

        result = vs.scroll_documents(
            limit=limit,
            offset=offset if offset else None,
            source_id=source_id,
            source=source,
            tag=tag,
            title_search=search,
        )

        documents = []
        for r in result['records']:
            payload = r.get('payload', {})
            documents.append({
                "id": r['id'],
                "source": payload.get('source', ''),
                "source_id": payload.get('source_id', ''),
                "title": payload.get('title', ''),
                "chunk_position": payload.get('chunk_position', 0),
                "chunk_length": len(payload.get('chunk_text', '')),
                "chunk_text_preview": (payload.get('chunk_text') or '')[:200],
                "document_url": payload.get('document_url', ''),
                "permission_tags": payload.get('permission_tags', []),
            })

        return jsonify({
            "documents": documents,
            "next_offset": result['next_offset'],
            "total": result['total'],
            "page_size": limit,
        })

    # ── Retrieval Configuration ─────────────────────────────────────

    @bp.route(f"{url}/retrieval-config", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def get_retrieval_config():
        """Return admin retrieval configuration."""
        from modules.assistant.models.retrieval_config import get_admin_retrieval_config
        config = get_admin_retrieval_config()
        return jsonify({"config": config})

    @bp.route(f"{url}/retrieval-config", methods=["PUT"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def update_retrieval_config():
        """Update admin retrieval configuration."""
        from modules.assistant.models.retrieval_config import save_admin_retrieval_config
        data = request.get_json(silent=True) or {}
        config = save_admin_retrieval_config(data)
        return jsonify({"status": True, "config": config})

    # ── BM25 Index Management ───────────────────────────────────────

    @bp.route(f"{url}/bm25/rebuild", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def rebuild_bm25_index():
        """Rebuild the BM25 keyword search index from the vector store."""
        from modules.assistant.rag.bm25_index import get_bm25_index
        try:
            bm25_idx = get_bm25_index()
            count = bm25_idx.build_from_vector_store()
            bm25_idx.save()
            return jsonify({
                "status": True,
                "message": f"BM25 index rebuilt with {count} documents.",
                "document_count": count,
            })
        except Exception as e:
            return jsonify({"status": False, "message": str(e)}), 500

    @bp.route(f"{url}/bm25/status", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def bm25_status():
        """Return BM25 index status."""
        from modules.assistant.rag.bm25_index import get_bm25_index
        bm25_idx = get_bm25_index()
        return jsonify({
            "is_built": bm25_idx.is_built,
            "document_count": bm25_idx.N,
        })

    # ── Retrieval Test (diagnostics) ────────────────────────────────

    @bp.route(f"{url}/retrieval-test", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def retrieval_test():
        """Run retrieval pipeline without LLM call — returns diagnostics.

        Body: {"query": "...", "top_k": 10}
        """
        from modules.assistant.rag.retriever import get_retriever
        from modules.assistant.models.retrieval_config import get_admin_retrieval_config

        data = request.get_json(silent=True) or {}
        query = data.get('query', '').strip()
        if not query:
            return jsonify({"error": "query is required."}), 400

        retrieval_cfg = get_admin_retrieval_config()
        retriever = get_retriever()

        results, diagnostics = retriever.retrieve(
            query=query,
            permission_tags=None,   # admin bypass
            retrieval_config=retrieval_cfg,
        )

        return jsonify({
            "status": True,
            "result_count": len(results),
            "diagnostics": diagnostics,
        })

    # ── Scheduled Syncs ─────────────────────────────────────────────

    @bp.route(f"{url}/scheduled-syncs", methods=["GET"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def list_scheduled_syncs():
        """List all scheduled sync jobs."""
        from modules.assistant.models.scheduled_sync import ScheduledSync
        schedules = ScheduledSync.query.order_by(ScheduledSync.id).all()
        return jsonify({"schedules": [s.to_dict() for s in schedules]})

    @bp.route(f"{url}/scheduled-syncs", methods=["POST"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def create_scheduled_sync():
        """Create a new scheduled sync job.

        Body: {source_id, frequency, time_of_day, day_of_week?, active?}
        """
        from modules.assistant.models.scheduled_sync import ScheduledSync
        from modules.assistant.tasks.scheduler import compute_next_run
        from modules.assistant.dashboard.metrics_service import add_log
        from src.db import db
        import re

        data = request.get_json(silent=True) or {}
        source_id = data.get('source_id')
        frequency = data.get('frequency', '')
        time_of_day = data.get('time_of_day', '')
        day_of_week = data.get('day_of_week')
        active = data.get('active', True)

        # Validate
        if not source_id:
            return jsonify({"status": False, "message": "source_id is required."}), 400
        if frequency not in ('daily', 'weekly'):
            return jsonify({"status": False, "message": "frequency must be 'daily' or 'weekly'."}), 400
        if not re.match(r'^\d{2}:\d{2}$', time_of_day):
            return jsonify({"status": False, "message": "time_of_day must be 'HH:MM'."}), 400
        if frequency == 'weekly':
            if day_of_week is None or not isinstance(day_of_week, int) or day_of_week < 0 or day_of_week > 6:
                return jsonify({"status": False, "message": "day_of_week must be 0-6 for weekly."}), 400

        # Verify source exists
        source = source_service.get_source(source_id)
        if not source:
            return jsonify({"status": False, "message": "Source not found."}), 404

        schedule = ScheduledSync(
            source_id=source_id,
            frequency=frequency,
            time_of_day=time_of_day,
            day_of_week=day_of_week if frequency == 'weekly' else None,
            active=active,
        )
        schedule.next_run_at = compute_next_run(
            frequency, time_of_day,
            day_of_week if frequency == 'weekly' else None)

        db.session.add(schedule)
        db.session.commit()

        add_log('scheduled_sync_created',
                f"Scheduled sync created: source {source.get('name', '?')} "
                f"({frequency} {time_of_day})",
                {'schedule_id': schedule.id, 'source_id': source_id,
                 'frequency': frequency, 'time_of_day': time_of_day,
                 'day_of_week': day_of_week})

        logger.info("[Admin] Created scheduled sync id=%d for source %d (%s %s)",
                    schedule.id, source_id, frequency, time_of_day)
        return jsonify({"status": True, "schedule": schedule.to_dict()}), 201

    @bp.route(f"{url}/scheduled-syncs/<int:schedule_id>", methods=["PUT"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def update_scheduled_sync(schedule_id):
        """Update a scheduled sync job (active, frequency, time, day)."""
        from modules.assistant.models.scheduled_sync import ScheduledSync
        from modules.assistant.tasks.scheduler import compute_next_run
        from src.db import db
        import re

        schedule = ScheduledSync.query.get(schedule_id)
        if not schedule:
            return jsonify({"status": False, "message": "Schedule not found."}), 404

        data = request.get_json(silent=True) or {}

        if 'active' in data:
            schedule.active = bool(data['active'])

        if 'frequency' in data:
            if data['frequency'] not in ('daily', 'weekly'):
                return jsonify({"status": False, "message": "frequency must be 'daily' or 'weekly'."}), 400
            schedule.frequency = data['frequency']

        if 'time_of_day' in data:
            if not re.match(r'^\d{2}:\d{2}$', data['time_of_day']):
                return jsonify({"status": False, "message": "time_of_day must be 'HH:MM'."}), 400
            schedule.time_of_day = data['time_of_day']

        if 'day_of_week' in data:
            dow = data['day_of_week']
            if dow is not None and (not isinstance(dow, int) or dow < 0 or dow > 6):
                return jsonify({"status": False, "message": "day_of_week must be 0-6 or null."}), 400
            schedule.day_of_week = dow

        # Recompute next run
        schedule.next_run_at = compute_next_run(
            schedule.frequency, schedule.time_of_day,
            schedule.day_of_week if schedule.frequency == 'weekly' else None)

        db.session.commit()

        logger.info("[Admin] Updated scheduled sync id=%d", schedule_id)
        return jsonify({"status": True, "schedule": schedule.to_dict()})

    @bp.route(f"{url}/scheduled-syncs/<int:schedule_id>", methods=["DELETE"])
    @login_required(oauth)
    @permission_required("assistant.manage")
    def delete_scheduled_sync(schedule_id):
        """Delete a scheduled sync job."""
        from modules.assistant.models.scheduled_sync import ScheduledSync
        from modules.assistant.dashboard.metrics_service import add_log
        from src.db import db

        schedule = ScheduledSync.query.get(schedule_id)
        if not schedule:
            return jsonify({"status": False, "message": "Schedule not found."}), 404

        sid = schedule.source_id
        db.session.delete(schedule)
        db.session.commit()

        add_log('scheduled_sync_deleted',
                f"Scheduled sync {schedule_id} deleted (source {sid})",
                {'schedule_id': schedule_id, 'source_id': sid})

        logger.info("[Admin] Deleted scheduled sync id=%d", schedule_id)
        return jsonify({"status": True, "message": f"Schedule {schedule_id} deleted."})

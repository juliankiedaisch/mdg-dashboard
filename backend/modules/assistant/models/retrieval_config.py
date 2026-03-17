# Assistant Module - Database Models: Retrieval Configuration
"""
Stores admin-level and user-level retrieval tuning settings:
  - Tag weights for score boosting
  - Intelligent Top_K distribution percentages
  - Optional summarization configuration
  - Advanced pipeline configuration (reranking, hybrid search,
    parent-child chunking, semantic deduplication)

Admin settings are the system-wide defaults.
User settings override admin defaults per-user.
"""
import json
from src.db import db
from datetime import datetime, timezone
from src.utils import utc_isoformat


# ── Default configuration values ────────────────────────────────────

DEFAULT_TAG_WEIGHTS = {
    'page': 1.0,
    'attachment': 1.0,
    'external_document': 1.0,
}

DEFAULT_TOP_K = 20

DEFAULT_TOP_K_DISTRIBUTION = {
    'page': 60,
    'attachment': 40,
}

DEFAULT_SUMMARIZATION_ENABLED = False
DEFAULT_SUMMARIZATION_MODEL = ''

# Pipeline feature defaults (new)
DEFAULT_PIPELINE_CONFIG = {
    # Reranking
    'reranker_enabled': True,
    'reranker_model': '',          # empty = use default embedding model
    'initial_retrieval_k': 75,     # candidates fetched from vector search
    'final_context_k': 10,         # chunks sent to LLM after reranking

    # Hybrid search (vector + keyword BM25)
    'hybrid_enabled': True,
    'vector_weight': 0.7,
    'keyword_weight': 0.3,

    # Parent-child chunking (requires re-ingestion to take effect)
    'parent_child_enabled': False,

    # Semantic deduplication
    'dedup_enabled': True,
    'dedup_threshold': 0.92,
}


class RetrievalConfig(db.Model):
    """Admin-level retrieval configuration (system-wide defaults).

    Stores a single row of configuration that controls how the RAG
    pipeline weights, distributes, and optionally summarises results.
    """
    __tablename__ = 'assistant_retrieval_config'

    id = db.Column(db.Integer, primary_key=True)

    # JSON dict: {"page": 2.0, "attachment": 1.0, "external_document": 1.5}
    tag_weights_json = db.Column(db.Text, nullable=False,
                                 default=lambda: json.dumps(DEFAULT_TAG_WEIGHTS))

    # Total number of chunks to retrieve
    top_k = db.Column(db.Integer, nullable=False, default=DEFAULT_TOP_K)

    # JSON dict: {"page": 60, "attachment": 40}  (percentages, should sum ≤ 100)
    top_k_distribution_json = db.Column(db.Text, nullable=False,
                                        default=lambda: json.dumps(DEFAULT_TOP_K_DISTRIBUTION))

    # Summarisation settings
    summarization_enabled = db.Column(db.Boolean, nullable=False, default=DEFAULT_SUMMARIZATION_ENABLED)
    summarization_model = db.Column(db.String(200), nullable=False, default=DEFAULT_SUMMARIZATION_MODEL)

    # Advanced pipeline configuration (JSON)
    pipeline_config_json = db.Column(db.Text, nullable=False,
                                     default=lambda: json.dumps(DEFAULT_PIPELINE_CONFIG))

    updated_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # ── Helpers ─────────────────────────────────────────────────────

    @property
    def tag_weights(self) -> dict:
        try:
            return json.loads(self.tag_weights_json) if self.tag_weights_json else dict(DEFAULT_TAG_WEIGHTS)
        except (json.JSONDecodeError, TypeError):
            return dict(DEFAULT_TAG_WEIGHTS)

    @tag_weights.setter
    def tag_weights(self, value: dict):
        self.tag_weights_json = json.dumps(value)

    @property
    def top_k_distribution(self) -> dict:
        try:
            return json.loads(self.top_k_distribution_json) if self.top_k_distribution_json else dict(DEFAULT_TOP_K_DISTRIBUTION)
        except (json.JSONDecodeError, TypeError):
            return dict(DEFAULT_TOP_K_DISTRIBUTION)

    @top_k_distribution.setter
    def top_k_distribution(self, value: dict):
        self.top_k_distribution_json = json.dumps(value)

    @property
    def pipeline_config(self) -> dict:
        try:
            stored = json.loads(self.pipeline_config_json) if self.pipeline_config_json else {}
        except (json.JSONDecodeError, TypeError):
            stored = {}
        # Merge with defaults so new keys are always present
        merged = dict(DEFAULT_PIPELINE_CONFIG)
        merged.update(stored)
        return merged

    @pipeline_config.setter
    def pipeline_config(self, value: dict):
        self.pipeline_config_json = json.dumps(value)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'tag_weights': self.tag_weights,
            'top_k': self.top_k,
            'top_k_distribution': self.top_k_distribution,
            'summarization_enabled': self.summarization_enabled,
            'summarization_model': self.summarization_model,
            'pipeline_config': self.pipeline_config,
            'updated_at': utc_isoformat(self.updated_at),
        }


class UserRetrievalConfig(db.Model):
    """Per-user retrieval configuration overrides.

    When a user has not customised settings, the admin defaults
    from ``RetrievalConfig`` are used.  A user may override any or
    all settings.  A ``None`` / null JSON field means "use admin default".
    """
    __tablename__ = 'assistant_user_retrieval_config'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(200), unique=True, nullable=False, index=True)

    # Overrides — null means "inherit from admin config"
    tag_weights_json = db.Column(db.Text, nullable=True)
    top_k = db.Column(db.Integer, nullable=True)
    top_k_distribution_json = db.Column(db.Text, nullable=True)
    summarization_enabled = db.Column(db.Boolean, nullable=True)
    summarization_model = db.Column(db.String(200), nullable=True)
    pipeline_config_json = db.Column(db.Text, nullable=True)

    updated_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # ── Helpers ─────────────────────────────────────────────────────

    @property
    def tag_weights(self):
        if self.tag_weights_json is None:
            return None
        try:
            return json.loads(self.tag_weights_json)
        except (json.JSONDecodeError, TypeError):
            return None

    @tag_weights.setter
    def tag_weights(self, value):
        self.tag_weights_json = json.dumps(value) if value is not None else None

    @property
    def top_k_distribution(self):
        if self.top_k_distribution_json is None:
            return None
        try:
            return json.loads(self.top_k_distribution_json)
        except (json.JSONDecodeError, TypeError):
            return None

    @top_k_distribution.setter
    def top_k_distribution(self, value):
        self.top_k_distribution_json = json.dumps(value) if value is not None else None

    @property
    def pipeline_config(self):
        if self.pipeline_config_json is None:
            return None
        try:
            return json.loads(self.pipeline_config_json)
        except (json.JSONDecodeError, TypeError):
            return None

    @pipeline_config.setter
    def pipeline_config(self, value):
        self.pipeline_config_json = json.dumps(value) if value is not None else None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'tag_weights': self.tag_weights,
            'top_k': self.top_k,
            'top_k_distribution': self.top_k_distribution,
            'summarization_enabled': self.summarization_enabled,
            'summarization_model': self.summarization_model,
            'pipeline_config': self.pipeline_config,
            'updated_at': utc_isoformat(self.updated_at),
        }


def get_admin_retrieval_config() -> dict:
    """Return the admin retrieval config as a dict, creating defaults if needed."""
    cfg = RetrievalConfig.query.first()
    if cfg is None:
        cfg = RetrievalConfig()
        db.session.add(cfg)
        db.session.commit()
    return cfg.to_dict()


def save_admin_retrieval_config(data: dict) -> dict:
    """Update (or create) the admin retrieval config from a dict."""
    cfg = RetrievalConfig.query.first()
    if cfg is None:
        cfg = RetrievalConfig()
        db.session.add(cfg)

    if 'tag_weights' in data and isinstance(data['tag_weights'], dict):
        cfg.tag_weights = data['tag_weights']
    if 'top_k' in data and isinstance(data['top_k'], int):
        cfg.top_k = max(1, data['top_k'])
    if 'top_k_distribution' in data and isinstance(data['top_k_distribution'], dict):
        cfg.top_k_distribution = data['top_k_distribution']
    if 'summarization_enabled' in data:
        cfg.summarization_enabled = bool(data['summarization_enabled'])
    if 'summarization_model' in data:
        cfg.summarization_model = str(data.get('summarization_model') or '')
    if 'pipeline_config' in data and isinstance(data['pipeline_config'], dict):
        # Merge with existing to preserve defaults for missing keys
        current = cfg.pipeline_config
        current.update(data['pipeline_config'])
        cfg.pipeline_config = current

    db.session.commit()
    return cfg.to_dict()


def get_user_retrieval_config(user_id: str) -> dict:
    """Return the user's overrides (or empty dict if none)."""
    ucfg = UserRetrievalConfig.query.filter_by(user_id=user_id).first()
    return ucfg.to_dict() if ucfg else {}


def save_user_retrieval_config(user_id: str, data: dict) -> dict:
    """Update (or create) user retrieval overrides."""
    ucfg = UserRetrievalConfig.query.filter_by(user_id=user_id).first()
    if ucfg is None:
        ucfg = UserRetrievalConfig(user_id=user_id)
        db.session.add(ucfg)

    if 'tag_weights' in data:
        ucfg.tag_weights = data['tag_weights'] if isinstance(data['tag_weights'], dict) else None
    if 'top_k' in data:
        ucfg.top_k = int(data['top_k']) if data['top_k'] is not None else None
    if 'top_k_distribution' in data:
        ucfg.top_k_distribution = data['top_k_distribution'] if isinstance(data['top_k_distribution'], dict) else None
    if 'summarization_enabled' in data:
        ucfg.summarization_enabled = data['summarization_enabled'] if data['summarization_enabled'] is not None else None
    if 'summarization_model' in data:
        ucfg.summarization_model = data['summarization_model'] if data['summarization_model'] else None
    if 'pipeline_config' in data:
        ucfg.pipeline_config = data['pipeline_config'] if isinstance(data['pipeline_config'], dict) else None

    db.session.commit()
    return ucfg.to_dict()


def delete_user_retrieval_config(user_id: str) -> bool:
    """Reset user overrides (delete the row)."""
    ucfg = UserRetrievalConfig.query.filter_by(user_id=user_id).first()
    if ucfg:
        db.session.delete(ucfg)
        db.session.commit()
        return True
    return False


def get_effective_retrieval_config(user_id: str = None) -> dict:
    """Return the effective retrieval config for a user.

    Merges admin defaults with user overrides.
    If user_id is None or the user has no overrides, returns admin defaults.
    """
    admin = get_admin_retrieval_config()

    if not user_id:
        return admin

    ucfg = UserRetrievalConfig.query.filter_by(user_id=user_id).first()
    if not ucfg:
        return admin

    # Merge: user overrides take precedence over admin defaults
    effective = dict(admin)
    if ucfg.tag_weights is not None:
        effective['tag_weights'] = ucfg.tag_weights
    if ucfg.top_k is not None:
        effective['top_k'] = ucfg.top_k
    if ucfg.top_k_distribution is not None:
        effective['top_k_distribution'] = ucfg.top_k_distribution
    if ucfg.summarization_enabled is not None:
        effective['summarization_enabled'] = ucfg.summarization_enabled
    if ucfg.summarization_model is not None:
        effective['summarization_model'] = ucfg.summarization_model
    if ucfg.pipeline_config is not None:
        # Deep-merge: user's pipeline_config keys override admin's
        admin_pipeline = effective.get('pipeline_config', dict(DEFAULT_PIPELINE_CONFIG))
        user_pipeline = ucfg.pipeline_config
        merged_pipeline = dict(admin_pipeline)
        merged_pipeline.update(user_pipeline)
        effective['pipeline_config'] = merged_pipeline

    effective['_user_overrides'] = True
    return effective

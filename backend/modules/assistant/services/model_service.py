# Assistant Module - Services: Model Service
"""
Manages Ollama models (list, pull, remove, test).
"""
import requests
import logging
from typing import Dict, Any, List, Optional

from src.db import db
from src.globals import OLLAMA_API_URL
from modules.assistant.models.assistant_model import AssistantModel

logger = logging.getLogger(__name__)


class ModelService:
    """Interface for managing Ollama models."""

    def __init__(self, ollama_url: str = None):
        self.ollama_url = ollama_url or OLLAMA_API_URL

    def list_models(self) -> List[Dict[str, Any]]:
        """List all installed Ollama models."""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            response.raise_for_status()
            data = response.json()
            models = data.get('models', [])
            return [
                {
                    'name': m.get('name', ''),
                    'size': m.get('size', 0),
                    'modified_at': m.get('modified_at', ''),
                    'digest': m.get('digest', ''),
                    'details': m.get('details', {}),
                }
                for m in models
            ]
        except requests.RequestException as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def pull_model(self, model_name: str) -> Dict[str, Any]:
        """Pull (download) a model from Ollama registry."""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=600,  # Some models are large
            )
            response.raise_for_status()
            return {'success': True, 'message': f'Model {model_name} pulled successfully.'}
        except requests.RequestException as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            return {'success': False, 'message': f'Failed to pull model: {str(e)}'}

    def remove_model(self, model_name: str) -> Dict[str, Any]:
        """Remove an installed model."""
        try:
            response = requests.delete(
                f"{self.ollama_url}/api/delete",
                json={"name": model_name},
                timeout=30,
            )
            response.raise_for_status()
            return {'success': True, 'message': f'Model {model_name} removed.'}
        except requests.RequestException as e:
            logger.error(f"Failed to remove model {model_name}: {e}")
            return {'success': False, 'message': f'Failed to remove model: {str(e)}'}

    def test_model(self, model_name: str) -> Dict[str, Any]:
        """Test a model.

        Embedding models (names containing 'embed') are tested via the
        ``/api/embeddings`` endpoint.  All other models use ``/api/generate``.
        """
        # Heuristic: if the model name contains "embed", treat it as an
        # embedding model that must be called via /api/embeddings.
        is_embedding = 'embed' in model_name.lower()

        if is_embedding:
            try:
                logger.info("[ModelService] Testing embedding model '%s' via /api/embeddings",
                            model_name)
                response = requests.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": model_name, "prompt": "Hello, embedding test."},
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
                embedding = data.get('embedding', [])
                dim = len(embedding) if embedding else 0
                logger.info("[ModelService] Embedding model '%s' OK — dim=%d", model_name, dim)
                return {
                    'success': True,
                    'response': f'Embedding model working. Dimension: {dim}',
                    'model': model_name,
                    'embedding_dimension': dim,
                }
            except requests.RequestException as e:
                logger.error("[ModelService] Embedding model test failed for '%s': %s",
                             model_name, e)
                return {'success': False, 'message': f'Embedding model test failed: {str(e)}'}

        # Chat / generate model
        try:
            logger.info("[ModelService] Testing generate model '%s' via /api/generate", model_name)
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": "Say 'Hello, I am working!' in one sentence.",
                    "stream": False,
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return {
                'success': True,
                'response': data.get('response', ''),
                'model': model_name,
            }
        except requests.RequestException as e:
            logger.error("[ModelService] Generate model test failed for '%s': %s", model_name, e)
            return {'success': False, 'message': f'Model test failed: {str(e)}'}

    def get_status(self) -> Dict[str, Any]:
        """Get Ollama service status (short timeout to avoid freezing)."""
        import time
        t0 = time.monotonic()
        try:
            logger.debug("[Ollama] get_status: probing %s ...", self.ollama_url)
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=(2, 3))
            models = response.json().get('models', [])
            logger.info("[Ollama] get_status: available (%d models) in %.3fs",
                        len(models), time.monotonic() - t0)
            return {
                'available': True,
                'model_count': len(models),
                'url': self.ollama_url,
            }
        except requests.RequestException as e:
            logger.warning("[Ollama] get_status: unavailable (%.3fs) — %s",
                           time.monotonic() - t0, e)
            return {
                'available': False,
                'model_count': 0,
                'url': self.ollama_url,
            }


# ── Config helpers ──────────────────────────────────────────────────

def get_config_value(key: str, default: str = '') -> str:
    """Get a configuration value from the database."""
    config = AssistantModel.query.filter_by(key=key).first()
    return config.value if config else default


def set_config_value(key: str, value: str, description: str = '') -> Dict:
    """Set a configuration value in the database."""
    config = AssistantModel.query.filter_by(key=key).first()
    if config:
        config.value = value
        if description:
            config.description = description
    else:
        config = AssistantModel(key=key, value=value, description=description)
        db.session.add(config)
    db.session.commit()
    return config.to_dict()


def get_all_config() -> List[Dict]:
    """Get all configuration entries."""
    configs = AssistantModel.query.all()
    return [c.to_dict() for c in configs]


def get_model_service(ollama_url: str = None) -> ModelService:
    """Create a ModelService instance."""
    return ModelService(ollama_url=ollama_url)

import os
from dotenv import load_dotenv

# Load .env from project root (one level up from backend/)
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(root_dir, ".env")
load_dotenv(env_path)

OIDC_CLIENT_ID=os.getenv("OIDC_CLIENT_ID")
OIDC_CLIENT_SECRET=os.getenv("OIDC_CLIENT_SECRET")
OIDC_USER_ENDPOINT=os.getenv("OIDC_USER_ENDPOINT")
OIDC_AUTHORIZE_URL=os.getenv("OIDC_AUTHORIZE_URL")
OIDC_JWK_URL=os.getenv("OIDC_JWK_URL")
OIDC_ACCESS_TOKEN_URL=os.getenv("OIDC_ACCESS_TOKEN_URL")
OIDC_REDIRECT_URL=os.getenv("OIDC_REDIRECT_URL")
OIDC_ADMIN_CLAIM=os.getenv("OIDC_ADMIN_CLAIM", 'admins')
OIDC_TEACHER_CLAIM=os.getenv("OIDC_TEACHER_CLAIM", "lehrende")
OIDC_STUDENT_CLAIM=os.getenv("OIDC_STUDENT_CLAIM", "schuelerinnen")
OIDC_OFFICE_CLAIM=os.getenv("OIDC_OFFICE_CLAIM", "sekretariat")
SQLALCHEMY_DATABASE_URI=os.getenv("SQLALCHEMY_DATABASE_URI")
SQLALCHEMY_TRACK_MODIFICATIONS=bool(os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS", 0))

# Backend configuration
BACKEND_HOST=os.getenv("BACKEND_HOST", "localhost")
BACKEND_PORT=int(os.getenv("BACKEND_PORT", 5000))

# Frontend configuration
FRONTEND_HOST=os.getenv("FRONTEND_HOST", "localhost")
FRONTEND_PORT=int(os.getenv("FRONTEND_PORT", 3000))

# Legacy support
HOST_NAME=os.getenv("HOST_NAME", BACKEND_HOST)
HOST_PORT=int(os.getenv("HOST_PORT", BACKEND_PORT))

def _env_bool(key: str, default: bool) -> bool:
    """Parse a boolean from an env var robustly.

    Treats the strings 'false', '0', 'no', '' as False;
    everything else (including 'true', '1', 'yes') as True.
    Falls back to *default* when the variable is not set.
    """
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() not in ('false', '0', 'no', '')

DEBUG = _env_bool('DEBUG', True)
USE_RELOADER = _env_bool('USE_RELOADER', False)
PRODUCTION=os.getenv("PRODUCTION", "False").lower() in ("true", "1", "yes")
APP_SECRET_KEY=os.getenv("APP_SECRET_KEY", '9Hn8Nw2MvqKUL7o4JbSFOyzpgI_suZ81av0P5J1bbzg')
SESSION_COOKIE_DOMAIN=os.getenv("SESSION_COOKIE_DOMAIN", '.hub.mdg-hamburg.de')
DEV_ALWAYS_LOGIN=bool(os.getenv("DEV_ALWAYS_LOGIN", 0))

TIMEDELTA = int(os.getenv("TIMEDELTA", 2))

SUPER_ADMIN_USERNAME = os.getenv("SUPER_ADMIN_USERNAME", "")

# ── Assistant Module Config 
OLLAMA_API_URL=os.getenv("OLLAMA_API_URL", "http://localhost:11434")
VECTOR_DB_URL=os.getenv("VECTOR_DB_URL", "http://localhost:6333")
ASSISTANT_MODEL=os.getenv("ASSISTANT_MODEL", "gemma3:12b")

# Embeddings configuration
EMBEDDING_MODEL=os.getenv("EMBEDDING_MODEL", "bge-m3:latest")
EMBED_BATCH_SIZE = int(os.getenv('EMBEDDING_BATCH_SIZE', '64'))
# Number of retries for each embedding request
EMBED_MAX_RETRIES = int(os.getenv('EMBEDDING_MAX_RETRIES', '3'))
EMBED_RETRY_BACKOFF = float(os.getenv('EMBEDDING_RETRY_BACKOFF', '1.0'))
EMBED_TIMEOUT = int(os.getenv('EMBEDDING_TIMEOUT', '120'))

# Document extraction services (docker-compose.dev.yml)
TIKA_URL=os.getenv("TIKA_URL", "")
TIKA_TIMEOUT=int(os.getenv("TIKA_TIMEOUT", '300'))       # 

# DOCLING
DOCLING_URL=os.getenv("DOCLING_URL", "")
DOCLING_TIMEOUT = int(os.getenv('DOCLING_TIMEOUT', '300'))       # seconds per request
DOCLING_MAX_RETRIES = int(os.getenv('DOCLING_MAX_RETRIES', '3'))
DOCLING_RETRY_BACKOFF = float(os.getenv('DOCLING_RETRY_BACKOFF', '2.0'))
DOCLING_POOL_SIZE = int(os.getenv('DOCLING_POOL_SIZE', '8'))     # concurrent requests
DOCLING_USE_CHUNKING = os.getenv('DOCLING_USE_CHUNKING', 'true').lower() in ('true', '1', 'yes')

# Circuit breaker: after this many consecutive failures, pause for COOLDOWN seconds
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv('DOCLING_CB_THRESHOLD', '5'))
CIRCUIT_BREAKER_COOLDOWN = int(os.getenv('DOCLING_CB_COOLDOWN', '60'))

class TASK_MODUS:
    TASK_CHANGED = 0
    TASK_CREATE = 1
    TASK_DELETE = 2
    TASK_CLICKED = 3
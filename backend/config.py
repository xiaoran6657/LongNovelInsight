from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "longnovelinsight.sqlite"

UPLOAD_MAX_BYTES = 200 * 1024 * 1024  # 200 MB

# v0.3 optional feature: embedding-based semantic rerank. Disabled by default
# because it requires a configured embedding provider. When disabled, the
# /retrieve endpoint returns a warning if "semantic_rerank" is requested.
ENABLE_SEMANTIC_RERANK = False

DATA_DIR.mkdir(parents=True, exist_ok=True)

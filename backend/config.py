from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "longnovelinsight.sqlite"

UPLOAD_MAX_BYTES = 200 * 1024 * 1024  # 200 MB

DATA_DIR.mkdir(parents=True, exist_ok=True)

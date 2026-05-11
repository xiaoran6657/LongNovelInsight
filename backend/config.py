from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "longnovelinsight.sqlite"

DATA_DIR.mkdir(parents=True, exist_ok=True)

"""Remove expired pytest/ruff cache files. Safe to run anytime."""
import shutil
import time
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"
MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 days


def clean():
    if not CACHE_DIR.exists():
        return
    now = time.time()
    removed = 0
    for child in CACHE_DIR.iterdir():
        if child.is_dir():
            mtime = child.stat().st_mtime
            if now - mtime > MAX_AGE_SECONDS:
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
    if removed:
        print(f"Cleaned {removed} expired cache dir(s) from {CACHE_DIR}")


if __name__ == "__main__":
    clean()

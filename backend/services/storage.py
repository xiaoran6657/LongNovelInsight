from pathlib import Path

import config


def _data_dir() -> Path:
    return config.DATA_DIR.resolve()


def _is_safe(path: Path) -> None:
    """Raise if `path` is outside the data directory."""
    try:
        path.resolve().relative_to(_data_dir())
    except ValueError:
        raise ValueError("Path traversal detected")


def get_topic_dir(topic_id: str) -> Path:
    p = (_data_dir() / "topics" / topic_id).resolve()
    _is_safe(p)
    return p


def get_source_dir(topic_id: str) -> Path:
    return get_topic_dir(topic_id) / "source"


def get_original_txt_path(topic_id: str) -> Path:
    return get_source_dir(topic_id) / "original.txt"


def get_source_file_path(topic_id: str, stored_filename: str) -> Path:
    """Return the path to the stored source file for a given filename.

    Prefer this over get_original_txt_path for format-aware code paths.
    """
    return get_source_dir(topic_id) / stored_filename


def ensure_topic_dirs(topic_id: str) -> Path:
    source_dir = get_source_dir(topic_id)
    source_dir.mkdir(parents=True, exist_ok=True)
    return source_dir


def compute_file_size(path: Path) -> int:
    if path.exists() and path.is_file():
        return path.stat().st_size
    return 0


def compute_dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def compute_data_dir_size() -> int:
    if not _data_dir().exists():
        return 0
    return sum(f.stat().st_size for f in _data_dir().rglob("*") if f.is_file())


def safe_delete_file(path: Path) -> bool:
    target = path.resolve()
    _is_safe(target)
    if target.exists() and target.is_file():
        target.unlink()
        return True
    return False


def safe_delete_empty_dirs(path: Path) -> None:
    target = path.resolve()
    _is_safe(target)
    if target.exists() and target.is_dir() and not any(target.iterdir()):
        target.rmdir()
        parent = target.parent
        if parent != _data_dir() and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()

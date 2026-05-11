from pathlib import Path

import config


def _data_dir() -> Path:
    return config.DATA_DIR


def get_topic_dir(topic_id: str) -> Path:
    p = (_data_dir() / "topics" / topic_id).resolve()
    if not str(p).startswith(str(_data_dir().resolve())):
        raise ValueError("Path traversal detected")
    return p


def get_source_dir(topic_id: str) -> Path:
    return get_topic_dir(topic_id) / "source"


def get_original_txt_path(topic_id: str) -> Path:
    return get_source_dir(topic_id) / "original.txt"


def ensure_topic_dirs(topic_id: str) -> Path:
    source_dir = get_source_dir(topic_id)
    source_dir.mkdir(parents=True, exist_ok=True)
    return source_dir


def compute_file_size(path: Path) -> int:
    if path.exists() and path.is_file():
        return path.stat().st_size
    return 0


def compute_data_dir_size() -> int:
    if not _data_dir().exists():
        return 0
    return sum(f.stat().st_size for f in _data_dir().rglob("*") if f.is_file())


def safe_delete_file(path: Path) -> bool:
    target = path.resolve()
    if not str(target).startswith(str(_data_dir().resolve())):
        raise ValueError("Path traversal detected")
    if target.exists() and target.is_file():
        target.unlink()
        return True
    return False


def safe_delete_empty_dirs(path: Path) -> None:
    target = path.resolve()
    if not str(target).startswith(str(_data_dir().resolve())):
        raise ValueError("Path traversal detected")
    if target.exists() and target.is_dir() and not any(target.iterdir()):
        target.rmdir()
        parent = target.parent
        if parent != _data_dir().resolve() and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()

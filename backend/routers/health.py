from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from config import DATA_DIR
from db import get_session
from models.topic import Topic

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    topic_count = session.exec(select(func.count()).select_from(Topic)).one()

    total_disk_usage_bytes = 0
    if DATA_DIR.exists():
        total_disk_usage_bytes = sum(f.stat().st_size for f in DATA_DIR.rglob("*") if f.is_file())

    return {
        "status": "ok",
        "version": "0.2.0-dev",
        "topic_count": topic_count,
        "total_disk_usage_bytes": total_disk_usage_bytes,
    }

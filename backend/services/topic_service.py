from sqlmodel import Session, select

from models.analysis_output import AnalysisOutput
from models.analysis_run import AnalysisRun
from models.chapter import Chapter
from models.chat import ChatMessage, ChatSession
from models.chunk import Chunk
from models.document import Document
from models.extracted_atom import ExtractedAtom
from models.job import Job
from models.job_item import JobItem
from models.local_extraction import LocalExtraction
from models.topic import Topic
from services import storage


def _delete_topic_dir(topic_id: str) -> int:
    topic_dir = storage.get_topic_dir(topic_id)
    freed = storage.compute_dir_size(topic_dir)
    if topic_dir.exists():
        for f in topic_dir.rglob("*"):
            if f.is_file():
                f.unlink()
        for d in sorted(topic_dir.rglob("*"), reverse=True):
            if d.is_dir():
                try:
                    d.rmdir()
                except OSError:
                    pass
        try:
            topic_dir.rmdir()
        except OSError:
            pass
    return freed


def delete_topic(topic_id: str, session: Session) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        return {"deleted": False, "freed_bytes": 0}

    # Delete chat messages -> sessions
    sessions = session.exec(select(ChatSession).where(ChatSession.topic_id == topic_id)).all()
    for s in sessions:
        messages = session.exec(select(ChatMessage).where(ChatMessage.session_id == s.id)).all()
        for m in messages:
            session.delete(m)
        session.delete(s)

    # Delete v2 analysis artifacts: atoms → extractions → runs → outputs
    atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.topic_id == topic_id)).all()
    for a in atoms:
        session.delete(a)
    extractions = session.exec(
        select(LocalExtraction).where(LocalExtraction.topic_id == topic_id)
    ).all()
    for e in extractions:
        session.delete(e)
    runs = session.exec(select(AnalysisRun).where(AnalysisRun.topic_id == topic_id)).all()
    for r in runs:
        session.delete(r)

    # Delete analysis outputs
    outputs = session.exec(select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)).all()
    for o in outputs:
        session.delete(o)

    # Delete jobs -> job_items
    jobs = session.exec(select(Job).where(Job.topic_id == topic_id)).all()
    for j in jobs:
        items = session.exec(select(JobItem).where(JobItem.job_id == j.id)).all()
        for ji in items:
            session.delete(ji)
        session.delete(j)

    # Delete chunks -> chapters
    chunks = session.exec(select(Chunk).where(Chunk.topic_id == topic_id)).all()
    for c in chunks:
        session.delete(c)
    chapters = session.exec(select(Chapter).where(Chapter.topic_id == topic_id)).all()
    for ch in chapters:
        session.delete(ch)

    # Delete document
    doc = session.exec(select(Document).where(Document.topic_id == topic_id)).first()
    if doc:
        session.delete(doc)

    # Delete Topic
    freed_db = topic.storage_bytes
    session.delete(topic)
    session.commit()

    # Delete topic directory
    freed_disk = _delete_topic_dir(topic_id)

    return {"deleted": True, "freed_bytes": freed_db + freed_disk}


def get_topic_document_summary(doc: Document | None) -> dict | None:
    if doc is None:
        return None
    return {
        "id": doc.id,
        "original_filename": doc.original_filename,
        "status": doc.status,
        "file_size_bytes": doc.file_size_bytes,
        "char_count": doc.char_count,
    }


def get_topic_analysis_summary(topic_id: str, session: Session) -> dict:
    outputs = session.exec(select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)).all()
    if not outputs:
        return {}
    summary: dict = {}
    for o in outputs:
        if o.output_type.startswith("merge_"):
            continue
        summary[o.output_type] = "completed"
    return summary

from sqlmodel import Session, select

from models.analysis_output import AnalysisOutput
from models.analysis_run import AnalysisRun
from models.chapter import Chapter
from models.chat import ChatMessage, ChatSession
from models.chunk import Chunk
from models.cross_work_run import CrossWorkRun
from models.document import Document
from models.embedding_cache import EmbeddingCache
from models.entity_mention import EntityMention
from models.extracted_atom import ExtractedAtom
from models.global_entity import GlobalEntity
from models.graph_snapshot import GraphSnapshot
from models.job import Job
from models.job_item import JobItem
from models.local_extraction import LocalExtraction
from models.retrieval_trace import RetrievalTrace
from models.timeline_item import TimelineItem
from models.topic import Topic
from models.topic_provider_config import TopicProviderConfig
from models.work import Work
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

    # Delete retrieval traces before their optional chat message/session references.
    traces = session.exec(select(RetrievalTrace).where(RetrievalTrace.topic_id == topic_id)).all()
    for trace in traces:
        session.delete(trace)

    # Delete chat messages -> sessions
    sessions = session.exec(select(ChatSession).where(ChatSession.topic_id == topic_id)).all()
    for s in sessions:
        messages = session.exec(select(ChatMessage).where(ChatMessage.session_id == s.id)).all()
        for m in messages:
            session.delete(m)
        session.delete(s)

    # Delete analysis artifacts
    from services.artifact_storage_service import delete_artifacts_for_topic

    delete_artifacts_for_topic(session, topic_id)

    # Delete analysis outputs first (FK to analysis_run)
    outputs = session.exec(select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)).all()
    for o in outputs:
        session.delete(o)

    # Delete v2 analysis artifacts: atoms → extractions → runs
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

    # Delete jobs -> job_items
    jobs = session.exec(select(Job).where(Job.topic_id == topic_id)).all()
    for j in jobs:
        items = session.exec(select(JobItem).where(JobItem.job_id == j.id)).all()
        for ji in items:
            session.delete(ji)
        session.delete(j)

    # Delete topic provider config
    tpc = session.exec(
        select(TopicProviderConfig).where(TopicProviderConfig.topic_id == topic_id)
    ).first()
    if tpc:
        session.delete(tpc)

    # Delete cross-work derived data before Works and the Topic.
    mentions = session.exec(select(EntityMention).where(EntityMention.topic_id == topic_id)).all()
    for mention in mentions:
        session.delete(mention)
    entities = session.exec(select(GlobalEntity).where(GlobalEntity.topic_id == topic_id)).all()
    for entity in entities:
        session.delete(entity)
    graphs = session.exec(select(GraphSnapshot).where(GraphSnapshot.topic_id == topic_id)).all()
    for graph in graphs:
        session.delete(graph)
    timeline_items = session.exec(
        select(TimelineItem).where(TimelineItem.topic_id == topic_id)
    ).all()
    for item in timeline_items:
        session.delete(item)
    cross_work_runs = session.exec(
        select(CrossWorkRun).where(CrossWorkRun.topic_id == topic_id)
    ).all()
    for run in cross_work_runs:
        session.delete(run)
    embedding_rows = session.exec(
        select(EmbeddingCache).where(EmbeddingCache.topic_id == topic_id)
    ).all()
    for row in embedding_rows:
        session.delete(row)

    # Delete chunks -> chapters
    chunks = session.exec(select(Chunk).where(Chunk.topic_id == topic_id)).all()
    for c in chunks:
        session.delete(c)
    chapters = session.exec(select(Chapter).where(Chapter.topic_id == topic_id)).all()
    for ch in chapters:
        session.delete(ch)

    # FTS cleanup (virtual table, no FK cascade)
    from services.fts_service import delete_topic_chunk_fts

    delete_topic_chunk_fts(topic_id, session)

    # Delete all Work-scoped documents.
    documents = session.exec(select(Document).where(Document.topic_id == topic_id)).all()
    for document in documents:
        session.delete(document)

    works = session.exec(select(Work).where(Work.topic_id == topic_id)).all()
    for work in works:
        session.delete(work)

    # Delete Topic
    freed_db = topic.storage_bytes
    session.flush()
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

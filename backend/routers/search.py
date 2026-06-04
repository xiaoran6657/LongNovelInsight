import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from db import get_session
from models.chunk import Chunk
from services.fts_service import (
    search_chunks_fts,
    search_chunks_keyword_fallback,
)

router = APIRouter(prefix="/topics/{topic_id}", tags=["search"])

VALID_METHODS = {"fts", "keyword_fallback"}
MAX_QUERY_LENGTH = 500
MIN_LIMIT = 1
MAX_LIMIT = 100
DEFAULT_LIMIT = 20
LOCATOR_EXCERPT_CHARS = 200


# ── Schemas ──


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    limit: int = Field(DEFAULT_LIMIT, ge=MIN_LIMIT, le=MAX_LIMIT)
    include_snippets: bool = True
    methods: list[str] = Field(default_factory=lambda: ["fts", "keyword_fallback"])
    work_ids: list[str] | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("query must not be empty or whitespace-only")
        return v

    @field_validator("limit", mode="before")
    @classmethod
    def limit_must_be_int(cls, v: object) -> object:
        if isinstance(v, bool):
            raise ValueError("limit must be an integer, not a boolean")
        return v


class SearchResult(BaseModel):
    chunk_id: str
    topic_id: str
    chapter_index: int | None
    chunk_index: int
    title: str
    snippet: str
    score: float
    method: str
    work_id: str | None = None
    work_title: str | None = None
    series_index: int | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    trace_id: None = None


class LocatorResponse(BaseModel):
    chunk_id: str
    topic_id: str
    chapter_index: int | None
    chunk_index: int
    locator: dict
    excerpt: str


# ── Endpoints ──


@router.post("/search", response_model=SearchResponse)
def search_topic_chunks(
    topic_id: str,
    body: SearchRequest,
    session: Session = Depends(get_session),
) -> SearchResponse:
    # Validate methods
    if not body.methods:
        raise HTTPException(status_code=422, detail="methods must be a non-empty list")
    unknown = set(body.methods) - VALID_METHODS
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"invalid methods: {sorted(unknown)}. Valid: {sorted(VALID_METHODS)}",
        )

    # Check topic exists
    from models.topic import Topic

    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Run requested primitives directly, deduplicating by chunk_id
    seen: set[str] = set()
    results: list[dict] = []

    # Overfetch when work_ids filter is active to avoid limit-before-filter
    fetch_limit = max(body.limit * 3, body.limit + 50) if body.work_ids else body.limit

    if "fts" in body.methods:
        for r in search_chunks_fts(topic_id, body.query, session, fetch_limit):
            if r["chunk_id"] not in seen:
                seen.add(r["chunk_id"])
                results.append(r)

    if "keyword_fallback" in body.methods:
        for r in search_chunks_keyword_fallback(topic_id, body.query, session, fetch_limit):
            if r["chunk_id"] not in seen:
                seen.add(r["chunk_id"])
                results.append(r)

    # Filter by work_ids if specified
    if body.work_ids:
        from models.document import Document

        filtered = []
        for r in results:
            chunk = session.get(Chunk, r["chunk_id"])
            if chunk is not None:
                doc = session.get(Document, chunk.document_id)
                if doc is not None and doc.work_id in body.work_ids:
                    filtered.append(r)
        results = filtered

    # Annotate with work metadata
    _annotate_work_meta(results, session)

    # Sort by score descending, then limit
    results.sort(key=lambda r: r["score"], reverse=True)
    results = results[: body.limit]

    if not body.include_snippets:
        for r in results:
            r["snippet"] = ""

    return SearchResponse(
        query=body.query,
        results=[SearchResult(**r) for r in results],
    )


@router.get("/chunks/{chunk_id}/locator", response_model=LocatorResponse)
def get_chunk_locator(
    topic_id: str,
    chunk_id: str,
    session: Session = Depends(get_session),
) -> LocatorResponse:
    chunk = session.get(Chunk, chunk_id)
    if chunk is None or chunk.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Chunk not found")

    locator: dict = {}
    if chunk.source_locator_json:
        try:
            locator = json.loads(chunk.source_locator_json)
        except json.JSONDecodeError:
            pass

    return LocatorResponse(
        chunk_id=chunk.id,
        topic_id=chunk.topic_id,
        chapter_index=chunk.chapter_index,
        chunk_index=chunk.chunk_index,
        locator=locator,
        excerpt=(chunk.text or "")[:LOCATOR_EXCERPT_CHARS],
    )


def _annotate_work_meta(results: list[dict], session: Session) -> None:
    """Annotate search results with work_id and work_title from chunk → document → work."""
    from models.document import Document
    from models.work import Work as WorkModel

    for r in results:
        chunk = session.get(Chunk, r.get("chunk_id"))
        if chunk is None:
            continue
        doc = session.get(Document, chunk.document_id)
        if doc is not None and doc.work_id:
            r["work_id"] = doc.work_id
            work = session.get(WorkModel, doc.work_id)
            if work is not None:
                r["work_title"] = work.title
                r["series_index"] = work.series_index

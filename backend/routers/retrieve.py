"""v0.3 Step 7 — Hybrid retrieval endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from db import get_session
from models.topic import Topic
from services.embedding_service import semantic_rerank
from services.retrieval_service import (
    VALID_RETRIEVE_METHODS,
    hybrid_retrieve,
    save_retrieval_trace,
)

router = APIRouter(prefix="/topics/{topic_id}", tags=["retrieve"])

MAX_QUERY_LENGTH = 500
MIN_TOP_K = 1
MAX_TOP_K = 50
DEFAULT_TOP_K = 8


# ── Schemas ──


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    top_k: int = Field(DEFAULT_TOP_K, ge=MIN_TOP_K, le=MAX_TOP_K)
    methods: list[str] = Field(
        default_factory=lambda: ["fts", "keyword_fallback", "structured", "analysis_output"]
    )
    persist_trace: bool = False
    work_ids: list[str] | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("query must not be empty or whitespace-only")
        return v

    @field_validator("top_k", mode="before")
    @classmethod
    def top_k_must_be_int(cls, v: object) -> object:
        if isinstance(v, bool):
            raise ValueError("top_k must be an integer, not a boolean")
        return v


class CandidateResult(BaseModel):
    source_type: str
    source_id: str
    chunk_id: str | None = None
    chapter_index: int | None = None
    chunk_index: int | None = None
    title: str
    snippet: str
    score: float
    method: str
    matched_terms: list[str]
    source_locator: dict | None = None
    work_id: str | None = None
    work_title: str | None = None
    series_index: int | None = None


class RetrieveResponse(BaseModel):
    query: str
    results: list[CandidateResult]
    trace_id: str | None = None
    warning: str | None = None


# ── Endpoint ──


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_evidence(
    topic_id: str,
    body: RetrieveRequest,
    session: Session = Depends(get_session),
) -> RetrieveResponse:
    # Validate methods
    if not body.methods:
        raise HTTPException(status_code=422, detail="methods must be a non-empty list")
    unknown = set(body.methods) - VALID_RETRIEVE_METHODS
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"invalid methods: {sorted(unknown)}. Valid: {sorted(VALID_RETRIEVE_METHODS)}",
        )

    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Separate semantic_rerank from other methods — it's a post-processing step
    retrieval_methods = [m for m in body.methods if m != "semantic_rerank"]
    use_semantic = "semantic_rerank" in body.methods

    if not retrieval_methods:
        raise HTTPException(
            status_code=422,
            detail="At least one retrieval method is required alongside semantic_rerank",
        )

    results = hybrid_retrieve(
        topic_id=topic_id,
        query=body.query.strip(),
        session=session,
        top_k=body.top_k,
        methods=retrieval_methods,
    )

    # Filter by work_ids if specified
    if body.work_ids:
        from models.chunk import Chunk
        from models.document import Document

        filtered = []
        for r in results:
            cid = r.get("chunk_id")
            if cid:
                chunk = session.get(Chunk, cid)
                if chunk is not None:
                    doc = session.get(Document, chunk.document_id)
                    if doc is not None and doc.work_id in body.work_ids:
                        filtered.append(r)
            else:
                filtered.append(r)
        results = filtered

    # Annotate with work metadata
    from routers.search import _annotate_work_meta
    _annotate_work_meta(results, session)

    warning: str | None = None
    if use_semantic:
        results, warning = semantic_rerank(results, body.query.strip(), topic_id)

    trace_id: str | None = None
    if body.persist_trace:
        trace_id = save_retrieval_trace(
            topic_id=topic_id,
            query=body.query.strip(),
            results=results,
            session=session,
            method="hybrid",
        )

    return RetrieveResponse(
        query=body.query.strip(),
        results=[CandidateResult(**r) for r in results],
        trace_id=trace_id,
        warning=warning,
    )

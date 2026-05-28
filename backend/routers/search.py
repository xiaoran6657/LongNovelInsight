import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from db import get_session
from models.chunk import Chunk
from services.fts_service import search_chunks

router = APIRouter(prefix="/topics/{topic_id}", tags=["search"])

VALID_METHODS = {"fts", "keyword_fallback"}
MAX_QUERY_LENGTH = 500
MIN_LIMIT = 1
MAX_LIMIT = 100
DEFAULT_LIMIT = 20
LOCATOR_EXCERPT_CHARS = 200


@router.post("/search")
def search_topic_chunks(
    topic_id: str,
    body: dict,
    session: Session = Depends(get_session),
) -> dict:
    query = body.get("query")
    if not query or not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=422, detail="query must be a non-empty string")
    if len(query) > MAX_QUERY_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"query must be at most {MAX_QUERY_LENGTH} characters",
        )

    limit = body.get("limit", DEFAULT_LIMIT)
    if not isinstance(limit, int) or limit < MIN_LIMIT or limit > MAX_LIMIT:
        raise HTTPException(
            status_code=422,
            detail=f"limit must be an integer between {MIN_LIMIT} and {MAX_LIMIT}",
        )

    methods = body.get("methods", ["fts", "keyword_fallback"])
    if not isinstance(methods, list) or not methods:
        raise HTTPException(status_code=422, detail="methods must be a non-empty list")

    unknown = set(methods) - VALID_METHODS
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"invalid methods: {sorted(unknown)}. Valid: {sorted(VALID_METHODS)}",
        )

    include_snippets = body.get("include_snippets", True)

    # Check topic exists
    from models.topic import Topic

    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    results = search_chunks(topic_id, query, session, limit)

    # Filter by requested methods
    results = [r for r in results if r["method"] in methods]

    if not include_snippets:
        for r in results:
            r["snippet"] = ""

    return {
        "query": query,
        "results": results,
        "trace_id": None,
    }


@router.get("/chunks/{chunk_id}/locator")
def get_chunk_locator(
    topic_id: str,
    chunk_id: str,
    session: Session = Depends(get_session),
) -> dict:
    chunk = session.get(Chunk, chunk_id)
    if chunk is None or chunk.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Chunk not found")

    locator: dict = {}
    if chunk.source_locator_json:
        try:
            locator = json.loads(chunk.source_locator_json)
        except json.JSONDecodeError:
            pass

    text = chunk.text or ""
    excerpt = text[:LOCATOR_EXCERPT_CHARS]

    return {
        "chunk_id": chunk.id,
        "topic_id": chunk.topic_id,
        "chapter_index": chunk.chapter_index,
        "chunk_index": chunk.chunk_index,
        "locator": locator,
        "excerpt": excerpt,
    }

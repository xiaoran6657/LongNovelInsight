"""v0.3 Step 9 — Entity Evidence + Similar Scenes APIs."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session
from models.analysis_output import AnalysisOutput, resolve_content_json
from models.chunk import Chunk
from models.extracted_atom import ExtractedAtom
from models.topic import Topic
from services.retrieval_service import hybrid_retrieve

router = APIRouter(prefix="/topics/{topic_id}", tags=["entities"])

EXCERPT_MAX_CHARS = 300
DEFAULT_EVIDENCE_LIMIT = 20
MAX_EVIDENCE_LIMIT = 50
DEFAULT_SIMILAR_LIMIT = 10
MAX_SIMILAR_LIMIT = 30


# ── Schemas ──


class AtomItem(BaseModel):
    id: str
    atom_type: str
    stable_id: str
    canonical_name: str | None = None
    title: str | None = None
    summary: str | None = None
    confidence: float
    evidence_quotes: list[str] | None = None
    chapter_index: int | None = None
    chunk_index: int | None = None


class ChunkItem(BaseModel):
    id: str
    chapter_index: int | None
    chunk_index: int
    excerpt: str
    locator: dict | None = None


class OutputItem(BaseModel):
    id: str
    output_type: str
    title: str
    excerpt: str


class EntityEvidenceResponse(BaseModel):
    entity_id: str
    canonical_name: str | None
    atoms: list[AtomItem]
    chunks: list[ChunkItem]
    outputs: list[OutputItem]


class SimilarSceneItem(BaseModel):
    chunk_id: str
    chapter_index: int | None
    chunk_index: int
    title: str
    snippet: str
    score: float
    locator: dict | None = None


class SimilarScenesResponse(BaseModel):
    results: list[SimilarSceneItem]


# ── Helpers ──


def _parse_json_list(value: str) -> list:
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _load_chunk_locator(chunk_id: str, session: Session) -> dict | None:
    chunk = session.get(Chunk, chunk_id)
    if chunk is None or not chunk.source_locator_json:
        return None
    try:
        return json.loads(chunk.source_locator_json)
    except (json.JSONDecodeError, TypeError):
        return None


# ── Entity Evidence ──


@router.get("/entities/{entity_id}/evidence", response_model=EntityEvidenceResponse)
def get_entity_evidence(
    topic_id: str,
    entity_id: str,
    limit: int = Query(DEFAULT_EVIDENCE_LIMIT, ge=1, le=MAX_EVIDENCE_LIMIT),
    session: Session = Depends(get_session),
) -> EntityEvidenceResponse:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Match atoms by stable_id or canonical_name that contains entity_id
    atoms = session.exec(
        select(ExtractedAtom)
        .where(ExtractedAtom.topic_id == topic_id)
        .where((ExtractedAtom.stable_id == entity_id) | (ExtractedAtom.canonical_name == entity_id))
        .order_by(ExtractedAtom.confidence.desc())
        .limit(limit)
    ).all()

    if not atoms:
        # Try substring match as fallback
        atoms = session.exec(
            select(ExtractedAtom)
            .where(ExtractedAtom.topic_id == topic_id)
            .where(
                ExtractedAtom.stable_id.contains(entity_id)  # type: ignore[arg-type]
                | ExtractedAtom.canonical_name.contains(entity_id)  # type: ignore[arg-type]
            )
            .order_by(ExtractedAtom.confidence.desc())
            .limit(limit)
        ).all()

    # Collect unique source chunk IDs from all matching atoms
    chunk_ids: set[str] = set()
    atom_items: list[AtomItem] = []
    canonical_name: str | None = None

    for atom in atoms:
        if canonical_name is None and atom.canonical_name:
            canonical_name = atom.canonical_name
        for cid in _parse_json_list(atom.source_chunk_ids):
            chunk_ids.add(cid)
        atom_items.append(
            AtomItem(
                id=atom.id,
                atom_type=atom.atom_type,
                stable_id=atom.stable_id,
                canonical_name=atom.canonical_name,
                title=atom.title,
                summary=atom.summary,
                confidence=atom.confidence,
                evidence_quotes=_parse_json_list(atom.evidence_quotes),
                chapter_index=atom.chapter_index,
                chunk_index=atom.chunk_index,
            )
        )

    # Load source chunks
    chunk_items: list[ChunkItem] = []
    for cid in chunk_ids:
        chunk = session.get(Chunk, cid)
        if chunk is None:
            continue
        chunk_items.append(
            ChunkItem(
                id=chunk.id,
                chapter_index=chunk.chapter_index,
                chunk_index=chunk.chunk_index,
                excerpt=(chunk.text or "")[:EXCERPT_MAX_CHARS],
                locator=_load_chunk_locator(chunk.id, session),
            )
        )

    # Find analysis outputs whose source_chunk_ids overlap
    all_outputs = session.exec(
        select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)
    ).all()
    output_items: list[OutputItem] = []
    for o in all_outputs:
        o_chunks = _parse_json_list(o.source_chunk_ids)
        if chunk_ids.intersection(o_chunks):
            resolved = resolve_content_json(session, o.content_json)
            output_items.append(
                OutputItem(
                    id=o.id,
                    output_type=o.output_type,
                    title=o.title,
                    excerpt=resolved[:EXCERPT_MAX_CHARS],
                )
            )
    output_items = output_items[:limit]

    return EntityEvidenceResponse(
        entity_id=entity_id,
        canonical_name=canonical_name,
        atoms=atom_items,
        chunks=chunk_items,
        outputs=output_items,
    )


# ── Similar Scenes ──


@router.get("/similar-scenes", response_model=SimilarScenesResponse)
def get_similar_scenes(
    topic_id: str,
    chunk_id: str | None = Query(None),
    query: str | None = Query(None, min_length=1, max_length=500),
    limit: int = Query(DEFAULT_SIMILAR_LIMIT, ge=1, le=MAX_SIMILAR_LIMIT),
    session: Session = Depends(get_session),
) -> SimilarScenesResponse:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    if not chunk_id and not query:
        raise HTTPException(
            status_code=422,
            detail="Either chunk_id or query must be provided",
        )

    seed_chunk_id: str | None = None
    search_query: str

    if chunk_id:
        seed = session.get(Chunk, chunk_id)
        if seed is None or seed.topic_id != topic_id:
            raise HTTPException(status_code=404, detail="Chunk not found")
        seed_chunk_id = seed.id

        # Build a query seed from the chunk's atoms and text
        atoms = session.exec(
            select(ExtractedAtom).where(
                ExtractedAtom.chunk_id == seed.id  # type: ignore[arg-type]
            )
        ).all()
        atom_terms = " ".join(a.canonical_name for a in atoms if a.canonical_name)
        text_snippet = (seed.text or "")[:200]
        search_query = f"{atom_terms} {text_snippet}".strip()
        if not search_query:
            search_query = text_snippet[:100]  # fallback to just text
    else:
        search_query = query.strip()  # type: ignore[union-attr]

    if not search_query:
        return SimilarScenesResponse(results=[])

    candidates = hybrid_retrieve(
        topic_id=topic_id,
        query=search_query,
        session=session,
        top_k=limit + 1,  # fetch extra to account for self-exclusion
        methods=["fts", "keyword_fallback"],
    )

    results: list[SimilarSceneItem] = []
    for c in candidates:
        cid = c.get("chunk_id")
        if cid is None:
            continue
        if seed_chunk_id and cid == seed_chunk_id:
            continue
        results.append(
            SimilarSceneItem(
                chunk_id=cid,
                chapter_index=c.get("chapter_index"),
                chunk_index=c.get("chunk_index", 0),
                title=c.get("title", ""),
                snippet=c.get("snippet", "")[:EXCERPT_MAX_CHARS],
                score=c["score"],
                locator=c.get("source_locator"),
            )
        )
        if len(results) >= limit:
            break

    return SimilarScenesResponse(results=results)

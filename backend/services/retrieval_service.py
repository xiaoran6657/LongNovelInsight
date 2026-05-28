import json
import logging
import re

from sqlmodel import Session, select

from models.analysis_output import AnalysisOutput, resolve_content_json
from models.chunk import Chunk
from models.extracted_atom import ExtractedAtom
from models.retrieval_trace import RetrievalTrace
from services.fts_service import search_chunks_fts, search_chunks_keyword_fallback

logger = logging.getLogger(__name__)

CHINESE_STOPWORDS = set(
    "的了是在与和及或但而就都很也还这那他她"
    "它我你们我们一个没有不是之为以其于"
    "可所向被把又从对等些能自至由着中后将已"
    "只其既如使便各全小大此彼则因更"
)

DEFAULT_TOP_K = 8
VALID_RETRIEVE_METHODS = {"fts", "keyword_fallback", "structured", "analysis_output"}


# ── Helpers ──


def _has_content(query: str) -> bool:
    return bool(query.strip())


def _make_excerpt(text: str, query: str, max_chars: int = 500) -> str:
    """Return an excerpt centered around the first match of query in text."""
    if len(text) <= max_chars:
        return text

    query_stripped = query.strip()
    lower_text = text.lower()
    lower_query = query_stripped.lower()

    pos = lower_text.find(lower_query)
    if pos == -1:
        for ch in query_stripped:
            if ch in CHINESE_STOPWORDS:
                continue
            cpos = lower_text.find(ch.lower())
            if cpos != -1:
                pos = cpos
                break
    if pos == -1:
        eng_tokens = re.findall(r"\w{2,}", lower_query)
        for tok in eng_tokens:
            tpos = lower_text.find(tok)
            if tpos != -1:
                pos = tpos
                break

    if pos == -1:
        pos = 0

    half = max_chars // 2
    start = max(0, pos - half)
    end = min(len(text), start + max_chars)
    if end < len(text):
        start = max(0, end - max_chars)

    excerpt = text[start:end]
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt = excerpt + "..."
    return excerpt


def _score_chunk(chunk: Chunk, query: str) -> int:
    text = chunk.text
    score = 0
    lower_text = text.lower()
    lower_query = query.lower()

    if lower_query in lower_text:
        score += 10

    query_chars = set(re.findall(r"[一-鿿]", query)) - CHINESE_STOPWORDS
    text_chars = set(re.findall(r"[一-鿿]", text)) - CHINESE_STOPWORDS
    score += len(query_chars & text_chars)

    query_words = {w for w in re.findall(r"\w+", lower_query) if len(w) >= 2}
    text_words = set(re.findall(r"\w+", lower_text))
    if query_words:
        score += len(query_words & text_words) * 2

    return score


# ── Token extraction ──


def _extract_query_tokens(query: str) -> list[str]:
    """Extract searchable tokens from query for matched_terms tracking."""
    tokens: list[str] = []
    cjk = re.findall(r"[一-鿿]", query)
    tokens.extend(ch for ch in cjk if ch not in CHINESE_STOPWORDS)
    alpha = re.findall(r"[a-zA-Z0-9]{2,}", query)
    tokens.extend(t.lower() for t in alpha)
    return tokens


def _extract_matched_terms(text: str, query: str) -> list[str]:
    """Return query tokens that appear in text."""
    tokens = _extract_query_tokens(query)
    lower_text = text.lower()
    return [t for t in tokens if t.lower() in lower_text]


# ── Chunk locator ──


def _get_chunk_locator(chunk_id: str | None, session: Session) -> dict | None:
    """Load source_locator_json for a chunk."""
    if not chunk_id:
        return None
    chunk = session.get(Chunk, chunk_id)
    if chunk is None or not chunk.source_locator_json:
        return None
    try:
        return json.loads(chunk.source_locator_json)
    except (json.JSONDecodeError, TypeError):
        return None


# ── Candidate generators (unified dict shape) ──


def _search_chunks_fts_candidates(
    topic_id: str, query: str, session: Session, limit: int
) -> list[dict]:
    """FTS search returning unified candidate dicts."""
    results = search_chunks_fts(topic_id, query, session, limit)
    return [
        {
            "source_type": "chunk",
            "source_id": r["chunk_id"],
            "chunk_id": r["chunk_id"],
            "chapter_index": r.get("chapter_index"),
            "chunk_index": r.get("chunk_index"),
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "score": r["score"],
            "method": "fts",
            "matched_terms": _extract_matched_terms(r.get("snippet", ""), query),
            "source_locator": _get_chunk_locator(r["chunk_id"], session),
        }
        for r in results
    ]


def _search_chunks_keyword_candidates(
    topic_id: str, query: str, session: Session, limit: int
) -> list[dict]:
    """Keyword fallback search returning unified candidate dicts."""
    results = search_chunks_keyword_fallback(topic_id, query, session, limit)
    return [
        {
            "source_type": "chunk",
            "source_id": r["chunk_id"],
            "chunk_id": r["chunk_id"],
            "chapter_index": r.get("chapter_index"),
            "chunk_index": r.get("chunk_index"),
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "score": r["score"],
            "method": "keyword_fallback",
            "matched_terms": _extract_matched_terms(r.get("snippet", ""), query),
            "source_locator": _get_chunk_locator(r["chunk_id"], session),
        }
        for r in results
    ]


def _search_analysis_output_candidates(
    topic_id: str, query: str, session: Session, limit: int
) -> list[dict]:
    """Search AnalysisOutput title/content/evidence, returning unified candidates."""
    if not _has_content(query):
        return []

    outputs = session.exec(
        select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)
    ).all()

    candidates = []
    for o in outputs:
        resolved = resolve_content_json(session, o.content_json)
        score = 0.0
        lower_query = query.lower()
        lower_content = resolved.lower()
        lower_title = o.title.lower()
        lower_type = o.output_type.lower()
        lower_evidence = o.evidence_quotes.lower()

        if lower_query in lower_content:
            score += 5
        if lower_query in lower_title:
            score += 3
        if lower_query in lower_type:
            score += 2
        if lower_query in lower_evidence:
            score += 4

        if score > 0:
            excerpt = _make_excerpt(resolved, query)
            combined_text = resolved + " " + o.title
            candidates.append(
                {
                    "source_type": "analysis_output",
                    "source_id": o.id,
                    "chunk_id": None,
                    "chapter_index": None,
                    "chunk_index": None,
                    "title": o.title,
                    "snippet": excerpt,
                    "score": score,
                    "method": "analysis_output",
                    "matched_terms": _extract_matched_terms(combined_text, query),
                    "source_locator": None,
                }
            )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:limit]


def _search_atoms_structured(
    topic_id: str, query: str, session: Session, limit: int
) -> list[dict]:
    """Search ExtractedAtom by canonical_name, aliases, evidence_quotes."""
    if not _has_content(query):
        return []

    atoms = session.exec(
        select(ExtractedAtom).where(ExtractedAtom.topic_id == topic_id)
    ).all()

    candidates = []
    for atom in atoms:
        score = 0.0
        lower_query = query.lower()

        # Parse content_json for aliases and structured data
        try:
            content = json.loads(atom.content_json)
        except (json.JSONDecodeError, TypeError):
            content = {}

        # Search canonical_name (strongest signal)
        if atom.canonical_name:
            if lower_query in atom.canonical_name.lower():
                score += 10

        # Search title
        if atom.title and lower_query in atom.title.lower():
            score += 5

        # Search in content_json values (covers aliases, descriptions, etc.)
        if isinstance(content, dict):
            for v in content.values():
                if isinstance(v, str) and lower_query in v.lower():
                    score += 3
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, str) and lower_query in item.lower():
                            score += 3

        # Search evidence_quotes
        try:
            evidence = json.loads(atom.evidence_quotes)
        except (json.JSONDecodeError, TypeError):
            evidence = []
        if isinstance(evidence, list):
            for eq in evidence:
                if isinstance(eq, str) and lower_query in eq.lower():
                    score += 4

        if score > 0:
            snippet_parts = []
            if atom.canonical_name:
                snippet_parts.append(atom.canonical_name)
            if atom.title:
                snippet_parts.append(atom.title)
            if atom.summary:
                snippet_parts.append(atom.summary)
            snippet = " | ".join(snippet_parts) if snippet_parts else ""

            chunk_id = atom.chunk_id
            if not chunk_id:
                try:
                    source_ids = json.loads(atom.source_chunk_ids)
                    if isinstance(source_ids, list) and source_ids:
                        chunk_id = source_ids[0]
                except (json.JSONDecodeError, TypeError):
                    pass

            searchable = " ".join(
                p for p in [atom.canonical_name, atom.title, atom.evidence_quotes] if p
            )

            candidates.append(
                {
                    "source_type": "atom",
                    "source_id": atom.id,
                    "chunk_id": chunk_id,
                    "chapter_index": atom.chapter_index,
                    "chunk_index": atom.chunk_index,
                    "title": atom.canonical_name or atom.title or "",
                    "snippet": snippet,
                    "score": score,
                    "method": "structured",
                    "matched_terms": _extract_matched_terms(searchable, query),
                    "source_locator": _get_chunk_locator(chunk_id, session),
                }
            )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:limit]


# ── Dedup & normalization ──


def _dedup_by_chunk_id(candidates: list[dict]) -> list[dict]:
    """Merge candidates sharing a chunk_id, keeping best score per chunk.

    Candidates without a chunk_id (analysis outputs, atoms with no chunk
    reference) pass through untouched.
    """
    by_chunk: dict[str, dict] = {}
    no_chunk: list[dict] = []

    for c in candidates:
        cid = c.get("chunk_id")
        if cid is None:
            no_chunk.append(c)
        elif cid not in by_chunk:
            by_chunk[cid] = dict(c)
        else:
            existing = by_chunk[cid]
            if c["method"] != existing["method"] and c["method"] not in existing["method"]:
                existing["method"] = existing["method"] + "+" + c["method"]
            if c["score"] > existing["score"]:
                # Merge preserving the combined method string
                combined_method = existing["method"]
                by_chunk[cid] = dict(c)
                if c["method"] not in combined_method:
                    combined_method = combined_method + "+" + c["method"]
                by_chunk[cid]["method"] = combined_method

    return list(by_chunk.values()) + no_chunk


def _normalize_scores(candidates: list[dict]) -> list[dict]:
    """Min-max normalize scores to [0, 1]. Returns unchanged if ≤1 candidate or zero range."""
    if not candidates:
        return candidates
    scores = [c["score"] for c in candidates]
    min_s = min(scores)
    max_s = max(scores)
    if max_s == min_s:
        norm = 1.0 if max_s > 0 else 0.0
        for c in candidates:
            c["score"] = norm
    else:
        for c in candidates:
            c["score"] = round((c["score"] - min_s) / (max_s - min_s), 4)
    return candidates


# ── Main hybrid retrieval ──


def hybrid_retrieve(
    topic_id: str,
    query: str,
    session: Session,
    top_k: int = DEFAULT_TOP_K,
    methods: list[str] | None = None,
) -> list[dict]:
    """Unified hybrid retrieval across chunks (FTS + keyword), outputs, and atoms.

    Returns deduplicated, score-normalized candidates sorted by relevance.
    Each candidate has: source_type, source_id, chunk_id, chapter_index,
    chunk_index, title, snippet, score, method, matched_terms, source_locator.
    """
    if not _has_content(query):
        return []

    if methods is None:
        methods = ["fts", "keyword_fallback", "structured", "analysis_output"]

    all_candidates: list[dict] = []

    if "fts" in methods:
        all_candidates.extend(
            _search_chunks_fts_candidates(topic_id, query, session, top_k * 2)
        )

    if "keyword_fallback" in methods:
        all_candidates.extend(
            _search_chunks_keyword_candidates(topic_id, query, session, top_k * 2)
        )

    if "analysis_output" in methods:
        all_candidates.extend(
            _search_analysis_output_candidates(topic_id, query, session, top_k)
        )

    if "structured" in methods:
        all_candidates.extend(
            _search_atoms_structured(topic_id, query, session, top_k)
        )

    all_candidates = _dedup_by_chunk_id(all_candidates)
    all_candidates = _normalize_scores(all_candidates)
    all_candidates.sort(key=lambda x: x["score"], reverse=True)

    return all_candidates[:top_k]


# ── RetrievalTrace persistence ──


def save_retrieval_trace(
    topic_id: str,
    query: str,
    results: list[dict],
    session: Session,
    session_id: str | None = None,
    message_id: str | None = None,
    method: str = "hybrid",
) -> str:
    """Persist a RetrievalTrace and return its ID.

    Only stores snippet prefix (200 chars) to avoid unbounded storage.
    """
    trace_results = []
    for r in results:
        trace_results.append(
            {
                "source_type": r["source_type"],
                "source_id": r["source_id"],
                "chunk_id": r.get("chunk_id"),
                "title": r.get("title", ""),
                "snippet": (r.get("snippet", "") or "")[:200],
                "score": r["score"],
                "method": r["method"],
                "matched_terms": r.get("matched_terms", []),
            }
        )

    trace = RetrievalTrace(
        topic_id=topic_id,
        session_id=session_id,
        message_id=message_id,
        query=query,
        method=method,
        results_json=json.dumps(trace_results, ensure_ascii=False),
    )
    session.add(trace)
    session.commit()
    session.refresh(trace)
    return trace.id


# ── Legacy API — kept for v0.2 compatibility (tests, chat_service) ──


def retrieve_chunks(
    topic_id: str, query: str, session: Session, top_k: int = DEFAULT_TOP_K
) -> list[dict]:
    if not _has_content(query):
        return []

    chunks = session.exec(select(Chunk).where(Chunk.topic_id == topic_id)).all()

    scored = [(c, _score_chunk(c, query)) for c in chunks]
    scored.sort(key=lambda x: x[1], reverse=True)

    results = []
    for chunk, score in scored[:top_k]:
        if score > 0:
            excerpt = _make_excerpt(chunk.text, query)
            results.append(
                {
                    "chunk_id": chunk.id,
                    "chapter_index": chunk.chapter_index,
                    "chunk_index": chunk.chunk_index,
                    "text_excerpt": excerpt,
                    "score": score,
                }
            )
    return results


def retrieve_analysis(
    topic_id: str, query: str, session: Session, top_k: int = DEFAULT_TOP_K
) -> list[dict]:
    if not _has_content(query):
        return []

    outputs = session.exec(select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)).all()

    results = []
    for o in outputs:
        resolved_content = resolve_content_json(session, o.content_json)
        score = 0
        lower_query = query.lower()
        lower_content = resolved_content.lower()
        lower_title = o.title.lower()
        lower_type = o.output_type.lower()

        if lower_query in lower_content:
            score += 5
        if lower_query in lower_title:
            score += 3
        if lower_query in lower_type:
            score += 2
        lower_evidence = o.evidence_quotes.lower()
        if lower_query in lower_evidence:
            score += 4

        if score > 0:
            excerpt = _make_excerpt(resolved_content, query)
            results.append(
                {
                    "output_id": o.id,
                    "output_type": o.output_type,
                    "title": o.title,
                    "content_excerpt": excerpt,
                    "score": score,
                }
            )
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def build_evidence_context(
    topic_id: str, query: str, session: Session, top_k: int = DEFAULT_TOP_K
) -> dict:
    chunks = retrieve_chunks(topic_id, query, session, top_k)
    analyses = retrieve_analysis(topic_id, query, session, top_k)
    return {"chunks": chunks, "analysis_outputs": analyses}

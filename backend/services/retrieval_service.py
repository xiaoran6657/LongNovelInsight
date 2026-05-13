import re

from sqlmodel import Session, select

from models.analysis_output import AnalysisOutput
from models.chunk import Chunk

CHINESE_STOPWORDS = set(
    "的了是在与和及或但而就都很也还这那他她"
    "它我你们我们他们一个没有不是之为以其于"
    "可所向被把又从对等些能自至由着中后将已"
    "只其既如使便各全小大此彼则因更"
)

DEFAULT_TOP_K = 8


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
        # Try matching individual non-stopword Chinese chars
        for ch in query_stripped:
            if ch in CHINESE_STOPWORDS:
                continue
            cpos = lower_text.find(ch.lower())
            if cpos != -1:
                pos = cpos
                break
    if pos == -1:
        # Try English tokens
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
    # Adjust start if end truncated before text end
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

    # Exact substring match
    if lower_query in lower_text:
        score += 10

    # Chinese character overlap (filter stopwords)
    query_chars = set(re.findall(r"[一-鿿]", query)) - CHINESE_STOPWORDS
    text_chars = set(re.findall(r"[一-鿿]", text)) - CHINESE_STOPWORDS
    score += len(query_chars & text_chars)

    # Word-level overlap (min token length 2)
    query_words = {w for w in re.findall(r"\w+", lower_query) if len(w) >= 2}
    text_words = set(re.findall(r"\w+", lower_text))
    if query_words:
        score += len(query_words & text_words) * 2

    return score


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
        score = 0
        lower_query = query.lower()
        lower_content = o.content_json.lower()
        lower_title = o.title.lower()
        lower_type = o.output_type.lower()

        if lower_query in lower_content:
            score += 5
        if lower_query in lower_title:
            score += 3
        if lower_query in lower_type:
            score += 2
        # Check evidence_quotes
        lower_evidence = o.evidence_quotes.lower()
        if lower_query in lower_evidence:
            score += 4

        if score > 0:
            excerpt = _make_excerpt(o.content_json, query)
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

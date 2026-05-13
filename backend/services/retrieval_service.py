import re

from sqlmodel import Session, select

from models.analysis_output import AnalysisOutput
from models.chunk import Chunk


def _score_chunk(chunk: Chunk, query: str) -> int:
    text = chunk.text
    score = 0
    lower_text = text.lower()
    lower_query = query.lower()

    # Exact substring match
    if lower_query in lower_text:
        score += 10

    # Chinese character overlap
    query_chars = set(re.findall(r"[一-鿿]", query))
    text_chars = set(re.findall(r"[一-鿿]", text))
    score += len(query_chars & text_chars)

    # Word-level overlap (split on whitespace/punctuation)
    query_words = set(re.findall(r"\w+", lower_query))
    text_words = set(re.findall(r"\w+", lower_text))
    score += len(query_words & text_words)

    return score


def retrieve_chunks(topic_id: str, query: str, session: Session, top_k: int = 5) -> list[dict]:
    chunks = session.exec(select(Chunk).where(Chunk.topic_id == topic_id)).all()

    scored = [(c, _score_chunk(c, query)) for c in chunks]
    scored.sort(key=lambda x: x[1], reverse=True)

    results = []
    for chunk, score in scored[:top_k]:
        if score > 0:
            excerpt = chunk.text[:500] if len(chunk.text) > 500 else chunk.text
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


def retrieve_analysis(topic_id: str, query: str, session: Session, top_k: int = 5) -> list[dict]:
    outputs = session.exec(select(AnalysisOutput).where(AnalysisOutput.topic_id == topic_id)).all()

    results = []
    for o in outputs:
        score = 0
        lower_content = o.content_json.lower()
        lower_query = query.lower()
        if lower_query in lower_content:
            score += 5
        if lower_query in o.title.lower():
            score += 3
        if score > 0:
            excerpt = o.content_json[:500] if len(o.content_json) > 500 else o.content_json
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


def build_evidence_context(topic_id: str, query: str, session: Session, top_k: int = 5) -> dict:
    chunks = retrieve_chunks(topic_id, query, session, top_k)
    analyses = retrieve_analysis(topic_id, query, session, top_k)
    return {"chunks": chunks, "analysis_outputs": analyses}

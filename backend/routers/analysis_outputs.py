from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from db import get_session
from models.analysis_output import AnalysisOutputRead
from services import analysis_service

router = APIRouter(prefix="/topics/{topic_id}/analysis", tags=["analysis_outputs"])


@router.post("/run")
def run_analysis(
    topic_id: str,
    limit_chunks: int = 5,
    session: Session = Depends(get_session),
) -> dict:
    try:
        analysis_service.delete_analysis_outputs(topic_id, session)
        outputs = analysis_service.run_structured_analysis(
            topic_id, session, limit_chunks=limit_chunks
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            status = 404
        elif any(kw in msg.lower() for kw in ("no document", "not parsed", "no provider")):
            status = 409
        else:
            status = 400
        raise HTTPException(status_code=status, detail=msg)

    return {
        "outputs": [AnalysisOutputRead.from_orm_with_json(o).model_dump() for o in outputs],
        "count": len(outputs),
    }


@router.get("/outputs")
def get_analysis_outputs(
    topic_id: str,
    output_type: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    outputs = analysis_service.get_analysis_outputs(topic_id, session, output_type)
    return {
        "outputs": [AnalysisOutputRead.from_orm_with_json(o).model_dump() for o in outputs],
        "count": len(outputs),
    }


@router.delete("/outputs")
def delete_analysis_outputs(
    topic_id: str,
    session: Session = Depends(get_session),
) -> dict:
    count = analysis_service.delete_analysis_outputs(topic_id, session)
    return {"deleted": True, "count": count}

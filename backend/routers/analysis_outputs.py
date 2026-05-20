import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from db import get_session
from models.analysis_output import AnalysisOutputRead
from models.job import Job, JobRead
from models.job_item import JobItem, JobItemRead
from models.topic import Topic
from services import analysis_service

router = APIRouter(prefix="/topics/{topic_id}/analysis", tags=["analysis_outputs"])


def _check_topic(topic_id: str, session: Session) -> Topic:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.post("/run")
def run_analysis(
    topic_id: str,
    limit_chunks: int = 5,
    pipeline: str = "v1",
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)

    if pipeline == "v2":
        from services import analysis_run_service as v2_service

        try:
            run = v2_service.create_analysis_run(
                session,
                topic_id,
                mode="preview",
                limit_chunks=limit_chunks,
            )
        except ValueError as e:
            msg = str(e)
            conflict_keywords = (
                "no provider",
                "no chunks",
                "not parsed",
                "parse document",
                "already running",
            )
            status = 409 if any(kw in msg.lower() for kw in conflict_keywords) else 422
            raise HTTPException(status_code=status, detail=msg)

        v2_service.start_analysis_run(run.id)

        return {
            "pipeline": "v2",
            "run": {
                "id": run.id,
                "topic_id": run.topic_id,
                "mode": run.mode,
                "status": run.status,
                "progress_total": run.progress_total,
            },
            "status_url": f"/api/analysis/runs/{run.id}",
        }

    if pipeline not in ("v1",):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid pipeline: {pipeline}. Must be v1 or v2",
        )

    if not analysis_service.acquire_topic_analysis_lock(topic_id):
        raise HTTPException(
            status_code=409,
            detail="Analysis is already running for this topic",
        )

    try:
        analysis_service.delete_analysis_outputs(topic_id, session)
        outputs = analysis_service.run_structured_analysis(
            topic_id, session, limit_chunks=limit_chunks
        )
    except ValueError as e:
        msg = str(e)
        if any(kw in msg.lower() for kw in ("no document", "not parsed", "no provider")):
            status = 409
        else:
            status = 400
        raise HTTPException(status_code=status, detail=msg)
    finally:
        analysis_service.release_topic_analysis_lock(topic_id)

    return {
        "pipeline": "v1",
        "outputs": [
            AnalysisOutputRead.from_orm_with_json(o, session).model_dump() for o in outputs
        ],
        "count": len(outputs),
    }


@router.post("/run-async", status_code=201)
def run_analysis_async(
    topic_id: str,
    limit_chunks: int = 5,
    session: Session = Depends(get_session),
) -> dict:
    """Start an async analysis job. Returns job immediately; poll /status for completion."""
    _check_topic(topic_id, session)

    if not analysis_service.acquire_topic_analysis_lock(topic_id):
        raise HTTPException(
            status_code=409,
            detail="Analysis is already running for this topic",
        )

    # Delete old outputs synchronously
    analysis_service.delete_analysis_outputs(topic_id, session)

    # Create job record
    job = Job(
        topic_id=topic_id,
        job_type="analysis",
        status="pending",
        progress_total=6,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # Create items for each type
    types = ["overview", "characters", "relations", "events", "causality", "themes"]
    items = []
    for t in types:
        item = JobItem(job_id=job.id, item_type=t, status="pending")
        session.add(item)
        items.append(item)
    session.commit()
    for item in items:
        session.refresh(item)

    # Release the lock — background thread will re-acquire
    analysis_service.release_topic_analysis_lock(topic_id)

    # Start background processing
    thread = threading.Thread(
        target=analysis_service.run_analysis_async,
        args=(topic_id, job.id, limit_chunks),
        daemon=True,
    )
    thread.start()

    return {
        "job": JobRead.from_db(job).model_dump(),
        "items": [JobItemRead.model_validate(i).model_dump() for i in items],
    }


@router.post("/run/{output_type}")
def run_single_type_analysis(
    topic_id: str,
    output_type: str,
    limit_chunks: int = 5,
    deepen: bool = False,
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)

    valid_types = {"overview", "characters", "relations", "events", "causality", "themes"}
    if output_type not in valid_types:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid output_type: {output_type}. Must be one of {sorted(valid_types)}",
        )

    if not analysis_service.acquire_topic_analysis_lock(topic_id):
        raise HTTPException(
            status_code=409,
            detail="Analysis is already running for this topic",
        )

    try:
        output = analysis_service.run_single_output_type(
            topic_id,
            output_type,
            session,
            limit_chunks=limit_chunks,
            deepen=deepen,
        )
    except ValueError as e:
        msg = str(e)
        if any(kw in msg.lower() for kw in ("no document", "not parsed", "no provider")):
            status = 409
        else:
            status = 400
        raise HTTPException(status_code=status, detail=msg)
    finally:
        analysis_service.release_topic_analysis_lock(topic_id)

    return {"output": AnalysisOutputRead.from_orm_with_json(output, session).model_dump()}


@router.get("/outputs")
def get_analysis_outputs(
    topic_id: str,
    output_type: str | None = None,
    run_id: str | None = None,
    latest_only: bool = False,
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)
    outputs = analysis_service.get_analysis_outputs(
        topic_id, session, output_type, run_id=run_id, latest_only=latest_only
    )
    return {
        "outputs": [
            AnalysisOutputRead.from_orm_with_json(o, session).model_dump() for o in outputs
        ],
        "count": len(outputs),
    }


@router.delete("/outputs")
def delete_analysis_outputs(
    topic_id: str,
    run_id: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    _check_topic(topic_id, session)
    count = analysis_service.delete_analysis_outputs(topic_id, session, run_id=run_id)
    return {"deleted": True, "count": count}

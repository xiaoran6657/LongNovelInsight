import asyncio
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy.engine import Engine
from sqlmodel import Session

from models.analysis_run import AnalysisRun
from models.enums import JobStatus
from models.topic import Topic
from services import analysis_run_service


class ParkedThread:
    created: list["ParkedThread"] = []

    def __init__(
        self,
        *,
        target: Callable[..., None],
        args: tuple[Any, ...],
        name: str,
        daemon: bool,
    ) -> None:
        self.target = target
        self.args = args
        self.name = name
        self.daemon = daemon
        self.started = False
        self.created.append(self)

    def start(self) -> None:
        self.started = True

    def run(self) -> None:
        self.target(*self.args)


class FailingThread(ParkedThread):
    def start(self) -> None:
        raise RuntimeError("thread unavailable")


@pytest.fixture(autouse=True)
def clear_executor_registry() -> None:
    ParkedThread.created.clear()
    with analysis_run_service._EXECUTOR_STATE_LOCK:
        analysis_run_service._ACTIVE_EXECUTORS_BY_TOPIC.clear()
        analysis_run_service._ACTIVE_EXECUTOR_RUNS.clear()
    yield
    with analysis_run_service._EXECUTOR_STATE_LOCK:
        analysis_run_service._ACTIVE_EXECUTORS_BY_TOPIC.clear()
        analysis_run_service._ACTIVE_EXECUTOR_RUNS.clear()


def _seed_runs(engine: Engine, statuses: list[str]) -> tuple[str, list[str]]:
    with Session(engine) as session:
        topic = Topic(name="Recovery test")
        session.add(topic)
        session.flush()
        runs = [AnalysisRun(topic_id=topic.id, status=status) for status in statuses]
        session.add_all(runs)
        session.commit()
        return topic.id, [run.id for run in runs]


def test_startup_recovery_marks_only_running_runs_and_is_idempotent(engine: Engine) -> None:
    _, run_ids = _seed_runs(
        engine,
        [
            JobStatus.PENDING,
            JobStatus.RUNNING,
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.PARTIAL_SUCCESS,
        ],
    )
    running_id = run_ids[1]
    with Session(engine) as session:
        running = session.get(AnalysisRun, running_id)
        assert running is not None
        running.set_metadata({"preserved": "value"})
        session.add(running)
        session.commit()

    assert analysis_run_service.recover_interrupted_analysis_runs(engine) == [running_id]

    with Session(engine) as session:
        runs = [session.get(AnalysisRun, run_id) for run_id in run_ids]
        assert all(run is not None for run in runs)
        assert [run.status for run in runs if run is not None] == [
            JobStatus.PENDING,
            JobStatus.FAILED,
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.PARTIAL_SUCCESS,
        ]
        recovered = runs[1]
        assert recovered is not None
        assert recovered.error_message == analysis_run_service.INTERRUPTED_RUN_MESSAGE
        assert recovered.finished_at is not None
        metadata = recovered.get_metadata()
        assert metadata["preserved"] == "value"
        assert metadata["startup_recovery"]["previous_status"] == JobStatus.RUNNING
        assert metadata["startup_recovery"]["reason"] == "backend_restart"
        assert metadata["startup_recovery"]["action"] == "marked_failed"
        assert metadata["startup_recovery"]["resume_available"] is True
        first_recovery = metadata["startup_recovery"].copy()

    assert analysis_run_service.recover_interrupted_analysis_runs(engine) == []
    with Session(engine) as session:
        recovered = session.get(AnalysisRun, running_id)
        assert recovered is not None
        assert recovered.get_metadata()["startup_recovery"] == first_recovery


def test_lifespan_recovers_after_database_initialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import db
    from main import lifespan

    events: list[str] = []
    monkeypatch.setattr(db, "init_db", lambda: events.append("init"))
    monkeypatch.setattr(
        analysis_run_service,
        "recover_interrupted_analysis_runs",
        lambda: events.append("recover"),
    )

    async def exercise_lifespan() -> None:
        async with lifespan(FastAPI()):
            events.append("ready")

    asyncio.run(exercise_lifespan())
    assert events == ["init", "recover", "ready"]


def test_duplicate_start_is_rejected_until_executor_releases(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, (run_id,) = _seed_runs(engine, [JobStatus.PENDING])
    monkeypatch.setattr(analysis_run_service.threading, "Thread", ParkedThread)
    monkeypatch.setattr(analysis_run_service, "_execute_run", lambda *_args, **_kwargs: None)

    assert analysis_run_service.start_analysis_run(run_id, engine) is True
    assert analysis_run_service.start_analysis_run(run_id, engine) is False
    assert len(ParkedThread.created) == 1

    ParkedThread.created[0].run()

    assert analysis_run_service.start_analysis_run(run_id, engine) is True
    assert len(ParkedThread.created) == 2


def test_one_executor_per_topic_rejects_a_second_run(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run_ids = _seed_runs(engine, [JobStatus.PENDING, JobStatus.PENDING])
    monkeypatch.setattr(analysis_run_service.threading, "Thread", ParkedThread)
    monkeypatch.setattr(analysis_run_service, "_execute_run", lambda *_args, **_kwargs: None)

    assert analysis_run_service.start_analysis_run(run_ids[0], engine) is True
    assert analysis_run_service.start_analysis_run(run_ids[1], engine) is False
    assert len(ParkedThread.created) == 1


def test_create_is_rejected_while_topic_executor_is_registered(engine: Engine) -> None:
    topic_id, (run_id,) = _seed_runs(engine, [JobStatus.SUCCEEDED])
    with analysis_run_service._EXECUTOR_STATE_LOCK:
        analysis_run_service._ACTIVE_EXECUTOR_RUNS.add(run_id)
        analysis_run_service._ACTIVE_EXECUTORS_BY_TOPIC[topic_id] = run_id

    with Session(engine) as session:
        with pytest.raises(ValueError, match="already running"):
            analysis_run_service.create_analysis_run(session, topic_id)


def test_terminal_run_cannot_reenter_initial_executor(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, (run_id,) = _seed_runs(engine, [JobStatus.FAILED])
    monkeypatch.setattr(
        analysis_run_service,
        "_resolve_api_key",
        lambda *_args, **_kwargs: pytest.fail("terminal run attempted execution"),
    )

    analysis_run_service._execute_run_impl(run_id, engine)

    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run is not None
        assert run.status == JobStatus.FAILED


def test_thread_start_failure_releases_registry_and_marks_run_failed(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, (run_id,) = _seed_runs(engine, [JobStatus.PENDING])
    monkeypatch.setattr(analysis_run_service.threading, "Thread", FailingThread)

    with pytest.raises(RuntimeError, match="thread unavailable"):
        analysis_run_service.start_analysis_run(run_id, engine)

    assert not analysis_run_service._ACTIVE_EXECUTOR_RUNS
    assert not analysis_run_service._ACTIVE_EXECUTORS_BY_TOPIC
    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        assert run is not None
        assert run.status == JobStatus.FAILED
        assert "Failed to start analysis executor" in (run.error_message or "")

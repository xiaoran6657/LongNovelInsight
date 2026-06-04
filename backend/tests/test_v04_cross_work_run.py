"""Tests for v0.4 cross-work run orchestration."""

from sqlmodel import Session

from models.cross_work_run import CrossWorkRun
from models.topic import Topic


class TestCrossWorkRun:
    def test_create_run_full(self, engine):
        with Session(engine) as session:
            topic = Topic(name="CWRTopic", status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

        from services.cross_work_run_service import (
            create_cross_work_run,
            execute_cross_work_run,
        )

        with Session(engine) as session:
            run = create_cross_work_run(session, tid, mode="full")
            rid = run.id

        # Execute OUTSIDE the session to avoid SQLite lock contention
        execute_cross_work_run(rid, engine=engine)

        with Session(engine) as session:
            run = session.get(CrossWorkRun, rid)
            assert run.status == "succeeded", f"Run failed: {run.error}"
            assert run.error is None

    def test_create_run_entities_only(self, engine):
        with Session(engine) as session:
            topic = Topic(name="CWREntities", status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

        from services.cross_work_run_service import (
            create_cross_work_run,
            execute_cross_work_run,
        )

        with Session(engine) as session:
            run = create_cross_work_run(session, tid, mode="entities_only")
            rid = run.id
        execute_cross_work_run(rid, engine=engine)

        with Session(engine) as session:
            run = session.get(CrossWorkRun, rid)
            assert run.status == "succeeded"

    def test_list_runs(self, engine):
        with Session(engine) as session:
            topic = Topic(name="CWRList", status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

        from services.cross_work_run_service import (
            create_cross_work_run,
            execute_cross_work_run,
            list_cross_work_runs,
        )

        with Session(engine) as session:
            run = create_cross_work_run(session, tid, mode="full")
            rid = run.id
        execute_cross_work_run(rid, engine=engine)

        with Session(engine) as session:
            runs, total = list_cross_work_runs(session, tid)
            assert total >= 1
            assert runs[0].id == rid

    def test_get_run_status(self, engine):
        with Session(engine) as session:
            topic = Topic(name="CWRStatus", status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

        from services.cross_work_run_service import (
            create_cross_work_run,
            execute_cross_work_run,
            get_cross_work_run_status,
        )

        with Session(engine) as session:
            run = create_cross_work_run(session, tid, mode="full")
            rid = run.id
        execute_cross_work_run(rid, engine=engine)

        with Session(engine) as session:
            status = get_cross_work_run_status(session, rid)
            assert status is not None
            assert status["status"] == "succeeded"
            assert "stats" in status

    def test_create_run_api(self, engine, client):
        with Session(engine) as session:
            topic = Topic(name="CWRAPI", status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

        r = client.post(
            f"/api/topics/{tid}/cross-work/runs",
            json={"mode": "full", "rebuild": True},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["id"] is not None
        assert data["status"] == "pending"

    def test_list_runs_api(self, engine, client):
        with Session(engine) as session:
            topic = Topic(name="CWRListAPI", status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

        client.post(
            f"/api/topics/{tid}/cross-work/runs",
            json={"mode": "full"},
        )
        r = client.get(f"/api/topics/{tid}/cross-work/runs")
        assert r.status_code == 200
        assert len(r.json()["runs"]) >= 1

    def test_get_run_api(self, engine, client):
        with Session(engine) as session:
            topic = Topic(name="CWRGetAPI", status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

        r_create = client.post(
            f"/api/topics/{tid}/cross-work/runs",
            json={"mode": "entities_only"},
        )
        rid = r_create.json()["id"]
        # Run is executed in background; status may be pending/running
        r = client.get(f"/api/topics/{tid}/cross-work/runs/{rid}")
        assert r.status_code == 200
        assert r.json()["status"] in ("pending", "running", "succeeded")

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


class TestCrossWorkRunScope:
    def test_scope_is_canonical_and_survives_execution(self, engine):
        from models.work import Work
        from services.cross_work_run_service import (
            create_cross_work_run,
            execute_cross_work_run,
            get_cross_work_run_status,
            get_cross_work_run_work_ids,
        )

        with Session(engine) as session:
            topic = Topic(name="Scoped run topic", status="created")
            session.add(topic)
            session.flush()
            work_one = Work(topic_id=topic.id, title="Work One", series_index=1)
            work_two = Work(topic_id=topic.id, title="Work Two", series_index=2)
            session.add(work_one)
            session.add(work_two)
            session.commit()
            tid = topic.id
            expected_scope = sorted([work_one.id, work_two.id])

            run = create_cross_work_run(
                session,
                tid,
                mode="entities_only",
                work_ids=[work_two.id, work_one.id, work_one.id],
            )
            run_id = run.id
            assert get_cross_work_run_work_ids(run) == expected_scope

        execute_cross_work_run(run_id, engine=engine)

        with Session(engine) as session:
            status = get_cross_work_run_status(session, run_id)
            assert status is not None
            assert status["status"] == "succeeded"
            assert status["work_ids"] == expected_scope
            assert status["stats"]["scope"] == {"work_ids": expected_scope}

    def test_scope_rejects_foreign_or_unknown_work_ids(self, engine, client):
        from models.work import Work

        with Session(engine) as session:
            topic = Topic(name="Run scope topic", status="created")
            other_topic = Topic(name="Foreign run scope topic", status="created")
            session.add(topic)
            session.add(other_topic)
            session.flush()
            foreign_work = Work(topic_id=other_topic.id, title="Foreign Work")
            session.add(foreign_work)
            session.commit()
            topic_id = topic.id
            foreign_work_id = foreign_work.id

        response = client.post(
            f"/api/topics/{topic_id}/cross-work/runs",
            json={"mode": "graph_only", "work_ids": [foreign_work_id]},
        )
        assert response.status_code == 422
        assert "work_ids must belong to the Topic" in response.json()["detail"]

    def test_create_and_list_gets_expose_canonical_scope(self, engine, client):
        from unittest.mock import patch

        from models.work import Work

        with Session(engine) as session:
            topic = Topic(name="Run scope API topic", status="created")
            session.add(topic)
            session.flush()
            work_one = Work(topic_id=topic.id, title="API Work One")
            work_two = Work(topic_id=topic.id, title="API Work Two")
            session.add(work_one)
            session.add(work_two)
            session.commit()
            topic_id = topic.id
            expected_scope = sorted([work_one.id, work_two.id])

        with patch("services.cross_work_run_service.start_cross_work_run"):
            created = client.post(
                f"/api/topics/{topic_id}/cross-work/runs",
                json={
                    "mode": "graph_only",
                    "work_ids": [work_two.id, work_one.id, work_two.id],
                },
            )
        assert created.status_code == 201
        assert created.json()["work_ids"] == expected_scope
        run_id = created.json()["id"]

        listed = client.get(f"/api/topics/{topic_id}/cross-work/runs")
        assert listed.status_code == 200
        matching = next(run for run in listed.json()["runs"] if run["id"] == run_id)
        assert matching["work_ids"] == expected_scope

        detail = client.get(f"/api/topics/{topic_id}/cross-work/runs/{run_id}")
        assert detail.status_code == 200
        assert detail.json()["work_ids"] == expected_scope
        assert detail.json()["stats"]["scope"] == {"work_ids": expected_scope}

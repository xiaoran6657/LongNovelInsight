"""Tests for v0.4 Work-scoped search and retrieve filters."""

import io

from sqlmodel import Session

from models.model_provider import ModelProvider
from models.topic import Topic
from models.work import Work


def _setup_topic_with_two_works(engine, client):
    """Create topic + 2 Works with parsed documents. Returns (topic_id, w1_id, w2_id)."""
    with Session(engine) as session:
        prov = ModelProvider(
            name="SearchFlP",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="SearchFlTopic", provider_id=prov.id, status="created")
        session.add(topic)
        session.flush()
        w1 = Work(topic_id=topic.id, title="Red Book", series_index=1)
        w2 = Work(topic_id=topic.id, title="Blue Book", series_index=2)
        session.add(w1)
        session.add(w2)
        session.commit()
        tid = topic.id
        w1_id = w1.id
        w2_id = w2.id
        pid = prov.id

    client.put(f"/api/topics/{tid}/provider-config", json={"provider_id": pid})

    # Upload + parse Work 1
    client.post(
        f"/api/works/{w1_id}/documents/upload",
        files={
            "file": (
                "w1.txt",
                io.BytesIO("第一章 红色书籍\n这是关于红色的故事。\n".encode()),
                "text/plain",
            )
        },
    )
    client.post(f"/api/works/{w1_id}/parse")

    # Upload + parse Work 2
    client.post(
        f"/api/works/{w2_id}/documents/upload",
        files={
            "file": (
                "w2.txt",
                io.BytesIO("第一章 蓝色书籍\n这是关于蓝色的故事。\n".encode()),
                "text/plain",
            )
        },
    )
    client.post(f"/api/works/{w2_id}/parse")

    return tid, w1_id, w2_id


class TestWorkSearchFilter:
    def test_search_no_filter_returns_all(self, engine, client):
        tid, w1_id, w2_id = _setup_topic_with_two_works(engine, client)

        r = client.post(
            f"/api/topics/{tid}/search",
            json={"query": "第一章", "methods": ["fts"]},
        )
        assert r.status_code == 200
        # Both works have "第一章" — should get results from both
        assert len(r.json()["results"]) >= 2

    def test_search_filter_by_work_id(self, engine, client):
        tid, w1_id, w2_id = _setup_topic_with_two_works(engine, client)

        r = client.post(
            f"/api/topics/{tid}/search",
            json={
                "query": "第一章",
                "methods": ["fts"],
                "work_ids": [w1_id],
            },
        )
        assert r.status_code == 200
        results = r.json()["results"]
        # Should only get Work 1's results
        for res in results:
            assert res.get("work_id") == w1_id, (
                f"Result should be from Work 1 only, got work_id={res.get('work_id')}"
            )

    def test_search_results_have_work_metadata(self, engine, client):
        tid, w1_id, w2_id = _setup_topic_with_two_works(engine, client)

        r = client.post(
            f"/api/topics/{tid}/search",
            json={"query": "第一章", "methods": ["fts"]},
        )
        assert r.status_code == 200
        results = r.json()["results"]
        for res in results:
            assert "work_id" in res
            assert "work_title" in res

    def test_search_empty_work_ids_returns_all(self, engine, client):
        tid, w1_id, w2_id = _setup_topic_with_two_works(engine, client)

        r1 = client.post(
            f"/api/topics/{tid}/search",
            json={"query": "第一章", "methods": ["fts"], "work_ids": None},
        )
        r2 = client.post(
            f"/api/topics/{tid}/search",
            json={"query": "第一章", "methods": ["fts"]},
        )
        # Both should return same count (default = no filter)
        assert len(r1.json()["results"]) == len(r2.json()["results"])


class TestWorkRetrieveFilter:
    def test_retrieve_filter_by_work_id(self, engine, client):
        tid, w1_id, w2_id = _setup_topic_with_two_works(engine, client)

        r = client.post(
            f"/api/topics/{tid}/retrieve",
            json={
                "query": "红色",
                "top_k": 10,
                "work_ids": [w1_id],
            },
        )
        assert r.status_code == 200
        results = r.json()["results"]
        for res in results:
            if "work_id" in res:
                assert res["work_id"] == w1_id, (
                    f"Result should be from Work 1, got {res.get('work_id')}"
                )

    def test_retrieve_no_filter_legacy(self, engine, client):
        tid, w1_id, w2_id = _setup_topic_with_two_works(engine, client)

        r = client.post(
            f"/api/topics/{tid}/retrieve",
            json={"query": "第一章", "top_k": 10},
        )
        assert r.status_code == 200
        # Should return results (existing behavior preserved)
        assert "results" in r.json()

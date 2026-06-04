"""Tests for v0.4 cross-work timeline builder."""

import json

from sqlmodel import Session, select

from models.chapter import Chapter
from models.chunk import Chunk
from models.document import Document
from models.enums import AtomType
from models.extracted_atom import ExtractedAtom
from models.model_provider import ModelProvider
from models.timeline_item import TimelineItem
from models.topic import Topic
from models.work import Work


def _setup_timeline_data(engine):
    """Create topic + 1 Work with parsed document and event atoms."""
    from models.analysis_run import AnalysisRun

    with Session(engine) as session:
        prov = ModelProvider(
            name="TimelineP",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="TimelineTopic", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        run = AnalysisRun(topic_id=topic.id, mode="full")
        session.add(run)
        session.flush()
        w = Work(topic_id=topic.id, title="W1", series_index=1)
        session.add(w)
        session.flush()
        d = Document(
            topic_id=topic.id,
            work_id=w.id,
            original_filename="w.txt",
            file_size_bytes=100,
            char_count=100,
            status="parsed",
        )
        session.add(d)
        session.flush()

        # Two chapters for ordering test
        ch0 = Chapter(
            topic_id=topic.id,
            document_id=d.id,
            chapter_index=0,
            title="Ch0",
            start_char=0,
            end_char=50,
            char_count=50,
        )
        ch1 = Chapter(
            topic_id=topic.id,
            document_id=d.id,
            chapter_index=1,
            title="Ch1",
            start_char=50,
            end_char=100,
            char_count=50,
        )
        session.add(ch0)
        session.add(ch1)
        session.flush()
        ck0 = Chunk(
            topic_id=topic.id,
            document_id=d.id,
            chapter_id=ch0.id,
            chapter_index=0,
            chunk_index=0,
            text="Ch0 text",
            start_char=0,
            end_char=50,
            char_count=50,
            estimated_tokens=34,
        )
        ck1 = Chunk(
            topic_id=topic.id,
            document_id=d.id,
            chapter_id=ch1.id,
            chapter_index=1,
            chunk_index=0,
            text="Ch1 text",
            start_char=50,
            end_char=100,
            char_count=50,
            estimated_tokens=34,
        )
        session.add(ck0)
        session.add(ck1)
        session.flush()

        # Event atoms
        session.add(
            ExtractedAtom(
                run_id=run.id,
                topic_id=topic.id,
                chunk_id=ck0.id,
                atom_type=AtomType.EVENT,
                stable_id="evt_later",
                title="Later Event",
                content_json=json.dumps(
                    {
                        "title": "Later Event",
                        "participants": ["Alice"],
                    }
                ),
                source_chunk_ids=json.dumps([ck0.id]),
                evidence_quotes=json.dumps(["later"]),
                confidence=0.9,
            )
        )
        session.add(
            ExtractedAtom(
                run_id=run.id,
                topic_id=topic.id,
                chunk_id=ck1.id,
                atom_type=AtomType.EVENT,
                stable_id="evt_earlier",
                title="Earlier Event",
                content_json=json.dumps(
                    {
                        "title": "Earlier Event",
                        "participants": ["Bob"],
                    }
                ),
                source_chunk_ids=json.dumps([ck1.id]),
                evidence_quotes=json.dumps(["earlier"]),
                confidence=0.9,
            )
        )
        session.commit()
        return topic.id, w.id


class TestTimelineBuild:
    def test_build_timeline_creates_items(self, engine):
        tid, wid = _setup_timeline_data(engine)

        with Session(engine) as session:
            from services.cross_work_timeline_service import build_timeline

            result = build_timeline(tid, session)
            assert result["item_count"] == 2

    def test_timeline_items_persisted(self, engine):
        tid, wid = _setup_timeline_data(engine)

        with Session(engine) as session:
            from services.cross_work_timeline_service import build_timeline

            build_timeline(tid, session)

            items = session.exec(select(TimelineItem).where(TimelineItem.topic_id == tid)).all()
            assert len(items) == 2

    def test_timeline_ordering(self, engine):
        """Items ordered by sequence_index (chapter/chunk order)."""
        tid, wid = _setup_timeline_data(engine)

        with Session(engine) as session:
            from services.cross_work_timeline_service import build_timeline

            build_timeline(tid, session)

            items = session.exec(
                select(TimelineItem)
                .where(TimelineItem.topic_id == tid)
                .order_by(TimelineItem.sequence_index)
            ).all()
            assert len(items) == 2
            # Earlier event is in ch1, later event in ch0
            # ch0 (sequence=1000000) < ch1 (sequence=1001000)
            assert items[0].title == "Later Event"
            assert items[1].title == "Earlier Event"

    def test_empty_timeline(self, engine):
        with Session(engine) as session:
            topic = Topic(name="EmptyTL", status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

            from services.cross_work_timeline_service import build_timeline

            result = build_timeline(tid, session)
            assert result["item_count"] == 0

    def test_timeline_api_endpoint(self, engine, client):
        tid, wid = _setup_timeline_data(engine)

        client.post(f"/api/topics/{tid}/timeline/build")

        r = client.get(f"/api/topics/{tid}/timeline")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) >= 2
        assert "sequence_index" in data["items"][0]

    def test_timeline_work_filter(self, engine, client):
        tid, wid = _setup_timeline_data(engine)

        client.post(f"/api/topics/{tid}/timeline/build")

        r = client.get(f"/api/topics/{tid}/timeline?work_id={wid}")
        assert r.status_code == 200
        assert len(r.json()["items"]) >= 2

    def test_timeline_confidence_filter(self, engine, client):
        tid, wid = _setup_timeline_data(engine)

        client.post(f"/api/topics/{tid}/timeline/build")

        r = client.get(f"/api/topics/{tid}/timeline?min_confidence=0.95")
        assert r.status_code == 200
        # Confidence is 0.9, all filtered out
        assert len(r.json()["items"]) == 0

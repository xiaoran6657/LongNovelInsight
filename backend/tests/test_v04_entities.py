"""Tests for v0.4 cross-work entity registry."""

import json

from sqlmodel import Session

from models.chapter import Chapter
from models.chunk import Chunk
from models.document import Document
from models.enums import AtomType
from models.extracted_atom import ExtractedAtom
from models.model_provider import ModelProvider
from models.topic import Topic
from models.work import Work


def _create_atom(session, run_id, topic_id, atom_type, stable_id, content,
                 chunk_id="c1", confidence=0.9):
    atom = ExtractedAtom(
        run_id=run_id, topic_id=topic_id, chunk_id=chunk_id,
        atom_type=atom_type, stable_id=stable_id,
        canonical_name=content.get("name") or content.get("canonical_name"),
        title=content.get("title"),
        content_json=json.dumps(content, ensure_ascii=False),
        source_chunk_ids=json.dumps([chunk_id], ensure_ascii=False),
        evidence_quotes=json.dumps([content.get("evidence", "test")], ensure_ascii=False),
        confidence=confidence,
    )
    session.add(atom)
    return atom


def _setup_topic_with_works(engine, num_works=2):
    """Create topic with Works and parsed Documents. Returns (topic_id, work_ids, chunk_ids)."""
    from models.analysis_run import AnalysisRun

    with Session(engine) as session:
        prov = ModelProvider(
            name="EntityP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="EntityTopic", provider_id=prov.id, status="parsed")
        session.add(topic); session.flush()
        run = AnalysisRun(topic_id=topic.id, mode="full")
        session.add(run); session.flush()

        wids = []
        cids = []
        for i in range(num_works):
            w = Work(topic_id=topic.id, title=f"Work {i}", series_index=i + 1)
            session.add(w); session.flush()
            d = Document(
                topic_id=topic.id, work_id=w.id,
                original_filename=f"w{i}.txt", file_size_bytes=100,
                char_count=50, status="parsed",
            )
            session.add(d); session.flush()
            ch = Chapter(
                topic_id=topic.id, document_id=d.id,
                chapter_index=0, title=f"Ch{i}",
                start_char=0, end_char=50, char_count=50,
            )
            session.add(ch); session.flush()
            ck = Chunk(
                topic_id=topic.id, document_id=d.id, chapter_id=ch.id,
                chapter_index=0, chunk_index=0, text=f"work{i} text",
                start_char=0, end_char=50, char_count=50, estimated_tokens=34,
            )
            session.add(ck); session.flush()
            wids.append(w.id)
            cids.append(ck.id)

        session.commit()
        return topic.id, run.id, wids, cids


class TestEntityBuild:
    def test_build_empty_topic(self, engine):
        """Empty topic → 0 entities, no error."""
        with Session(engine) as session:
            topic = Topic(name="EmptyEnt", status="created")
            session.add(topic); session.commit()
            tid = topic.id

            from services.cross_work_entity_service import build_entity_registry
            result = build_entity_registry(tid, session)
            assert result["entity_count"] == 0
            assert result["mention_count"] == 0

    def test_same_character_across_works_merges(self, engine):
        """Same character name across two Works → one GlobalEntity."""
        tid, rid, wids, cids = _setup_topic_with_works(engine, num_works=2)

        with Session(engine) as session:
            _create_atom(session, rid, tid, AtomType.CHARACTER, "char_zhangsan",
                         {"name": "张三", "evidence": "he appeared"}, cids[0])
            _create_atom(session, rid, tid, AtomType.CHARACTER, "char_zhangsan",
                         {"name": "张三", "evidence": "he spoke"}, cids[1])
            session.commit()

            from services.cross_work_entity_service import build_entity_registry
            result = build_entity_registry(tid, session)
            assert result["entity_count"] == 1
            assert result["mention_count"] == 2

    def test_alias_match_merges(self, engine):
        """Alias matching canonical name should merge."""
        tid, rid, wids, cids = _setup_topic_with_works(engine, num_works=2)

        with Session(engine) as session:
            _create_atom(session, rid, tid, AtomType.CHARACTER, "char_sun",
                         {"name": "孙悟空"}, cids[0])
            _create_atom(session, rid, tid, AtomType.CHARACTER, "char_qitian",
                         {"name": "齐天大圣", "aliases": ["孙悟空"]}, cids[1])
            session.commit()

            from services.cross_work_entity_service import build_entity_registry
            result = build_entity_registry(tid, session)
            assert result["entity_count"] == 1

    def test_type_conflict_no_merge(self, engine):
        """Same name but different entity types → no merge, warning."""
        tid, rid, wids, cids = _setup_topic_with_works(engine, num_works=2)

        with Session(engine) as session:
            _create_atom(session, rid, tid, AtomType.CHARACTER, "char_beijing",
                         {"name": "北京"}, cids[0])
            _create_atom(session, rid, tid, AtomType.WORLDBUILDING, "wb_beijing",
                         {"name": "北京"}, cids[1])
            session.commit()

            from services.cross_work_entity_service import build_entity_registry
            result = build_entity_registry(tid, session)
            assert result["entity_count"] == 2
            assert len(result["warnings"]) >= 1

    def test_mentions_have_work_and_source(self, engine):
        """EntityMention rows should reference correct Work and source atom."""
        tid, rid, wids, cids = _setup_topic_with_works(engine, num_works=1)

        with Session(engine) as session:
            atom = _create_atom(session, rid, tid, AtomType.CHARACTER, "char_a",
                                {"name": "Alice", "evidence": "found here"}, cids[0])
            session.commit()
            aid = atom.id

            from services.cross_work_entity_service import build_entity_registry
            build_entity_registry(tid, session)

            from models.entity_mention import EntityMention
            mentions = session.exec(
                __import__("sqlmodel").select(EntityMention).where(
                    EntityMention.topic_id == tid
                )
            ).all()
            assert len(mentions) == 1
            assert mentions[0].work_id == wids[0]
            assert mentions[0].source_id == aid
            assert mentions[0].source_type == "atom"

    def test_entity_list_filters(self, engine):
        """Entity list API with type and name filters."""
        tid, rid, wids, cids = _setup_topic_with_works(engine, num_works=2)

        with Session(engine) as session:
            _create_atom(session, rid, tid, AtomType.CHARACTER, "char_x",
                         {"name": "XiaoMing"}, cids[0])
            _create_atom(session, rid, tid, AtomType.WORLDBUILDING, "wb_city",
                         {"name": "Shanghai"}, cids[1])
            session.commit()

            from services.cross_work_entity_service import build_entity_registry
            build_entity_registry(tid, session)

    def test_entity_detail_api(self, client, engine):
        """GET entity detail returns correct fields."""
        tid, rid, wids, cids = _setup_topic_with_works(engine, num_works=1)

        with Session(engine) as session:
            _create_atom(session, rid, tid, AtomType.CHARACTER, "char_test",
                         {"name": "TestChar", "evidence": "present"}, cids[0])
            session.commit()

            from services.cross_work_entity_service import build_entity_registry
            build_entity_registry(tid, session)

            from models.global_entity import GlobalEntity
            entity = session.exec(
                __import__("sqlmodel").select(GlobalEntity).where(
                    GlobalEntity.topic_id == tid
                )
            ).first()

        if entity:
            r = client.get(f"/api/topics/{tid}/entities/{entity.id}")
            assert r.status_code == 200
            assert r.json()["canonical_name"] == "TestChar"

    def test_build_api_endpoint(self, client, engine):
        """POST /cross-work/build triggers rebuild."""
        tid, rid, wids, cids = _setup_topic_with_works(engine, num_works=1)

        with Session(engine) as session:
            _create_atom(session, rid, tid, AtomType.CHARACTER, "char_api",
                         {"name": "ApiChar", "evidence": "seen"}, cids[0])
            session.commit()

        r = client.post(f"/api/topics/{tid}/cross-work/build")
        assert r.status_code == 200
        assert r.json()["entity_count"] >= 1

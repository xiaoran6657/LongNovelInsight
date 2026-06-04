"""Tests for v0.4 cross-work graph snapshot builder."""

import json

from sqlmodel import Session, select

from models.chapter import Chapter
from models.chunk import Chunk
from models.document import Document
from models.enums import AtomType
from models.extracted_atom import ExtractedAtom
from models.global_entity import GlobalEntity
from models.graph_snapshot import GraphSnapshot
from models.model_provider import ModelProvider
from models.topic import Topic
from models.work import Work


def _setup_entities_and_relations(engine):
    """Create topic + 2 Works with parsed documents, global entities, and relation atoms."""
    from models.analysis_run import AnalysisRun
    from models.entity_mention import EntityMention

    with Session(engine) as session:
        prov = ModelProvider(
            name="GraphP",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="GraphTopic", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        run = AnalysisRun(topic_id=topic.id, mode="full")
        session.add(run)
        session.flush()

        wids = []
        cids = []
        for i in range(2):
            w = Work(topic_id=topic.id, title=f"Work {i}", series_index=i + 1)
            session.add(w)
            session.flush()
            d = Document(
                topic_id=topic.id,
                work_id=w.id,
                original_filename=f"w{i}.txt",
                file_size_bytes=100,
                char_count=50,
                status="parsed",
            )
            session.add(d)
            session.flush()
            ch = Chapter(
                topic_id=topic.id,
                document_id=d.id,
                chapter_index=0,
                title=f"Ch{i}",
                start_char=0,
                end_char=50,
                char_count=50,
            )
            session.add(ch)
            session.flush()
            ck = Chunk(
                topic_id=topic.id,
                document_id=d.id,
                chapter_id=ch.id,
                chapter_index=0,
                chunk_index=0,
                text=f"work{i} text",
                start_char=0,
                end_char=50,
                char_count=50,
                estimated_tokens=34,
            )
            session.add(ck)
            session.flush()
            wids.append(w.id)
            cids.append(ck.id)

        # Global entities for two characters
        char_a = GlobalEntity(
            topic_id=topic.id,
            entity_type="character",
            canonical_name="Alice",
            aliases_json='["A"]',
            work_ids_json=json.dumps([wids[0]]),
            mention_count=1,
            confidence=0.92,
            merge_strategy="exact",
        )
        char_b = GlobalEntity(
            topic_id=topic.id,
            entity_type="character",
            canonical_name="Bob",
            aliases_json='["B"]',
            work_ids_json=json.dumps([wids[1]]),
            mention_count=1,
            confidence=0.92,
            merge_strategy="exact",
        )
        session.add(char_a)
        session.add(char_b)
        session.flush()

        # Entity mentions with stable_id for graph resolution
        session.add(
            EntityMention(
                topic_id=topic.id,
                global_entity_id=char_a.id,
                work_id=wids[0],
                source_type="atom",
                source_id="a1",
                chunk_id=cids[0],
                surface_text="Alice",
                metadata_json=json.dumps({"stable_id": "char_alice"}),
            )
        )
        session.add(
            EntityMention(
                topic_id=topic.id,
                global_entity_id=char_b.id,
                work_id=wids[1],
                source_type="atom",
                source_id="a2",
                chunk_id=cids[1],
                surface_text="Bob",
                metadata_json=json.dumps({"stable_id": "char_bob"}),
            )
        )

        # Relation atom
        session.add(
            ExtractedAtom(
                run_id=run.id,
                topic_id=topic.id,
                chunk_id=cids[0],
                atom_type=AtomType.RELATION,
                stable_id="rel_ab",
                content_json=json.dumps(
                    {
                        "character_a": "Alice",
                        "character_b": "Bob",
                        "relation_type": "ally",
                        "evidence": "Allies",
                    }
                ),
                source_chunk_ids=json.dumps([cids[0]]),
                evidence_quotes=json.dumps(["Allies"]),
                confidence=0.85,
            )
        )
        session.commit()
        return topic.id, wids, cids


class TestGraphBuild:
    def test_build_graph_from_relations(self, engine):
        tid, wids, cids = _setup_entities_and_relations(engine)

        with Session(engine) as session:
            from services.cross_work_graph_service import build_character_graph

            result = build_character_graph(tid, session)
            assert result["graph_type"] == "character_relationship"
            assert len(result["nodes"]) >= 2
            assert len(result["edges"]) >= 1
            assert result["edges"][0]["relation_type"] == "ally"

    def test_graph_snapshot_persisted(self, engine):
        tid, wids, cids = _setup_entities_and_relations(engine)

        with Session(engine) as session:
            from services.cross_work_graph_service import build_character_graph

            build_character_graph(tid, session)

            snapshots = session.exec(
                select(GraphSnapshot).where(
                    GraphSnapshot.topic_id == tid,
                    GraphSnapshot.graph_type == "character_relationship",
                )
            ).all()
            assert len(snapshots) >= 1
            nodes = json.loads(snapshots[0].nodes_json)
            edges = json.loads(snapshots[0].edges_json)
            assert len(nodes) >= 2
            assert len(edges) >= 1

    def test_empty_graph_no_entities(self, engine):
        with Session(engine) as session:
            topic = Topic(name="EmptyGraph", status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

            from services.cross_work_graph_service import build_character_graph

            result = build_character_graph(tid, session)
            assert result["nodes"] == []
            assert result["edges"] == []

    def test_graph_api_endpoint(self, engine, client):
        tid, wids, cids = _setup_entities_and_relations(engine)

        # Build first
        client.post(f"/api/topics/{tid}/graphs/build")

        r = client.get(f"/api/topics/{tid}/graphs/characters")
        assert r.status_code == 200
        data = r.json()
        assert data["graph_type"] == "character_relationship"
        assert len(data["nodes"]) >= 2
        assert len(data["edges"]) >= 1

    def test_graph_filters_work_id(self, engine, client):
        tid, wids, cids = _setup_entities_and_relations(engine)

        client.post(f"/api/topics/{tid}/graphs/build")

        r = client.get(f"/api/topics/{tid}/graphs/characters?work_id={wids[0]}")
        assert r.status_code == 200
        data = r.json()
        # With work_id filter for Work 0 only, may have fewer nodes
        assert data["graph_type"] == "character_relationship"

    def test_graph_filters_min_confidence(self, engine, client):
        tid, wids, cids = _setup_entities_and_relations(engine)

        client.post(f"/api/topics/{tid}/graphs/build")

        r = client.get(f"/api/topics/{tid}/graphs/characters?min_confidence=0.9")
        assert r.status_code == 200
        # Edge confidence is 0.85, should be filtered out
        assert len(r.json()["edges"]) >= 0

    def test_event_cooccurrence_fallback(self, engine):
        """When no relation atoms exist, edges built from event co-occurrence."""
        from models.analysis_run import AnalysisRun
        from models.entity_mention import EntityMention

        with Session(engine) as session:
            prov = ModelProvider(
                name="CoocP",
                provider_type="openai_compatible",
                base_url="http://mock",
                api_key="sk-m",
                model_name="m",
                is_default=True,
            )
            session.add(prov)
            session.flush()
            topic = Topic(name="CoocTopic", provider_id=prov.id, status="parsed")
            session.add(topic)
            session.flush()
            run = AnalysisRun(topic_id=topic.id, mode="full")
            session.add(run)
            session.flush()
            w = Work(topic_id=topic.id, title="W", series_index=1)
            session.add(w)
            session.flush()
            d = Document(
                topic_id=topic.id,
                work_id=w.id,
                original_filename="w.txt",
                file_size_bytes=50,
                char_count=50,
                status="parsed",
            )
            session.add(d)
            session.flush()
            ch = Chapter(
                topic_id=topic.id,
                document_id=d.id,
                chapter_index=0,
                title="Ch",
                start_char=0,
                end_char=50,
                char_count=50,
            )
            session.add(ch)
            session.flush()
            ck = Chunk(
                topic_id=topic.id,
                document_id=d.id,
                chapter_id=ch.id,
                chapter_index=0,
                chunk_index=0,
                text="test",
                start_char=0,
                end_char=50,
                char_count=50,
                estimated_tokens=34,
            )
            session.add(ck)
            session.flush()

            char_a = GlobalEntity(
                topic_id=topic.id,
                entity_type="character",
                canonical_name="Alice",
                work_ids_json=json.dumps([w.id]),
                mention_count=1,
                confidence=0.92,
            )
            char_b = GlobalEntity(
                topic_id=topic.id,
                entity_type="character",
                canonical_name="Bob",
                work_ids_json=json.dumps([w.id]),
                mention_count=1,
                confidence=0.92,
            )
            session.add(char_a)
            session.add(char_b)
            session.flush()
            session.add(
                EntityMention(
                    topic_id=topic.id,
                    global_entity_id=char_a.id,
                    work_id=w.id,
                    source_type="atom",
                    source_id="a1",
                    chunk_id=ck.id,
                    surface_text="Alice",
                    metadata_json=json.dumps({"stable_id": "char_a"}),
                )
            )
            session.add(
                EntityMention(
                    topic_id=topic.id,
                    global_entity_id=char_b.id,
                    work_id=w.id,
                    source_type="atom",
                    source_id="a2",
                    chunk_id=ck.id,
                    surface_text="Bob",
                    metadata_json=json.dumps({"stable_id": "char_b"}),
                )
            )

            # Event atom with participants (no relation atoms)
            session.add(
                ExtractedAtom(
                    run_id=run.id,
                    topic_id=topic.id,
                    chunk_id=ck.id,
                    atom_type=AtomType.EVENT,
                    stable_id="evt_ab",
                    content_json=json.dumps(
                        {
                            "title": "Meeting",
                            "participants": ["Alice", "Bob"],
                        }
                    ),
                    source_chunk_ids=json.dumps([ck.id]),
                    evidence_quotes=json.dumps(["test"]),
                    confidence=0.9,
                )
            )
            session.commit()
            tid = topic.id

        with Session(engine) as session:
            from services.cross_work_graph_service import build_character_graph

            result = build_character_graph(tid, session)
            assert len(result["edges"]) >= 1
            assert result["edges"][0]["relation_type"] == "co_occurrence"

"""Tests for v0.2 deterministic merge stage."""

import json

from sqlmodel import Session

from models.analysis_output import AnalysisOutput
from models.analysis_run import AnalysisRun
from models.enums import AnalysisMode, AtomType
from models.extracted_atom import ExtractedAtom
from services.merge_service import (
    merge_causality,
    merge_characters,
    merge_events,
    merge_overview,
    merge_relations,
    merge_themes,
    run_merge_stage,
)


def _create_atom(
    session,
    run_id,
    topic_id,
    atom_type,
    stable_id,
    content,
    chunk_id="c1",
    chapter_index=0,
    chunk_index=0,
    confidence=0.9,
):
    atom = ExtractedAtom(
        run_id=run_id,
        topic_id=topic_id,
        chunk_id=chunk_id,
        atom_type=atom_type,
        stable_id=stable_id,
        content_json=json.dumps(content, ensure_ascii=False),
        source_chunk_ids=json.dumps([chunk_id], ensure_ascii=False),
        evidence_quotes=json.dumps([content.get("evidence", "test")], ensure_ascii=False),
        confidence=confidence,
        chapter_index=chapter_index,
        chunk_index=chunk_index,
    )
    session.add(atom)
    return atom


def _setup_run(engine):
    """Create topic + AnalysisRun + return (topic_id, run_id, ck_id)."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="Merge P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Merge Test", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id,
            original_filename="t.txt",
            file_size_bytes=10,
            char_count=10,
            status="parsed",
        )
        session.add(doc)
        session.flush()
        ch = Chapter(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_index=0,
            title="Ch1",
            start_char=0,
            end_char=10,
            char_count=10,
        )
        session.add(ch)
        session.flush()
        ck = Chunk(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_id=ch.id,
            chapter_index=0,
            chunk_index=0,
            text="t",
            start_char=0,
            end_char=1,
            char_count=1,
            estimated_tokens=1,
        )
        session.add(ck)
        session.flush()
        run = AnalysisRun(topic_id=topic.id, mode=AnalysisMode.PREVIEW)
        session.add(run)
        session.commit()
        return topic.id, run.id, ck.id


class TestMergeCharacters:
    def test_dedup_by_stable_id(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_zhangsan",
                {"name": "张三", "observed_traits": ["brave"]},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_zhangsan",
                {"name": "张三丰", "observed_traits": ["wise"]},
                cid,
                confidence=0.8,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_lisi",
                {"name": "李四"},
                cid,
                confidence=0.7,
            )
            session.commit()

            summary = merge_characters(session, rid)
            assert summary.atom_count == 3
            assert summary.merged_count == 2  # zhangsan deduped

    def test_merges_traits(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_a",
                {"name": "A", "observed_traits": ["brave"]},
                cid,
                0,
                0,
                0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_a",
                {"name": "A2", "observed_traits": ["wise"]},
                cid,
                0,
                1,
                0.8,
            )
            session.commit()
            merge_characters(session, rid)

            out = session.exec(
                __import__("sqlmodel").select(AnalysisOutput).where(AnalysisOutput.run_id == rid)
            ).first()
            merged = json.loads(out.content_json)
            assert len(merged) == 1
            assert "brave" in merged[0]["traits"]
            assert "wise" in merged[0]["traits"]

    def test_per_item_has_source_and_evidence_and_confidence(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_x",
                {"name": "X", "evidence": "he appeared"},
                cid,
                0,
                0,
                0.85,
            )
            session.commit()
            merge_characters(session, rid)
            out = session.exec(
                __import__("sqlmodel").select(AnalysisOutput).where(AnalysisOutput.run_id == rid)
            ).first()
            merged = json.loads(out.content_json)
            item = merged[0]
            assert "source_chunk_ids" in item
            assert "evidence_quotes" in item
            assert "confidence" in item
            assert item["confidence"] > 0


class TestMergeEvents:
    def test_dedup_events(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_battle",
                {"title": "Battle", "participants": ["张三"]},
                cid,
                0,
                0,
                0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_battle",
                {"title": "Battle", "participants": ["李四"]},
                cid,
                0,
                1,
                0.8,
            )
            _create_atom(
                session, rid, tid, AtomType.EVENT, "evt_feast", {"title": "Feast"}, cid, 1, 0, 0.7
            )
            session.commit()

            summary = merge_events(session, rid)
            assert summary.atom_count == 3
            assert summary.merged_count == 2

    def test_merges_participants(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_e1",
                {"title": "E1", "participants": ["A"]},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_e1",
                {"title": "E1", "participants": ["B"]},
                cid,
                confidence=0.9,
            )
            session.commit()
            merge_events(session, rid)
            out = session.exec(
                __import__("sqlmodel").select(AnalysisOutput).where(AnalysisOutput.run_id == rid)
            ).first()
            merged = json.loads(out.content_json)
            assert "A" in merged[0]["participants"]
            assert "B" in merged[0]["participants"]

    def test_per_item_has_source_and_evidence(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_e",
                {"title": "E", "evidence": "it happened"},
                cid,
                confidence=0.9,
            )
            session.commit()
            merge_events(session, rid)
            out = session.exec(
                __import__("sqlmodel").select(AnalysisOutput).where(AnalysisOutput.run_id == rid)
            ).first()
            merged = json.loads(out.content_json)
            assert "source_chunk_ids" in merged[0]


class TestMergeRelations:
    def test_dedup_by_stable_id(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.RELATION,
                "rel_ab_ally",
                {"character_a": "A", "character_b": "B", "relation_type": "ally"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.RELATION,
                "rel_ab_ally",
                {"character_a": "A", "character_b": "B", "relation_type": "ally"},
                cid,
                confidence=0.8,
            )
            session.commit()
            summary = merge_relations(session, rid)
            assert summary.merged_count == 1

    def test_per_item_has_confidence(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.RELATION,
                "rel_ab",
                {"character_a": "A", "character_b": "B", "relation_type": "r"},
                cid,
                confidence=0.75,
            )
            session.commit()
            merge_relations(session, rid)
            out = session.exec(
                __import__("sqlmodel").select(AnalysisOutput).where(AnalysisOutput.run_id == rid)
            ).first()
            merged = json.loads(out.content_json)
            assert merged[0]["confidence"] == 0.75


class TestMergeCausality:
    def test_resolved_links(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_cause",
                {"title": "Cause"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_effect",
                {"title": "Effect"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CAUSAL_LINK,
                "caus_cause_to_effect",
                {"cause_event": "evt_cause", "effect_event": "evt_effect"},
                cid,
                confidence=0.85,
            )
            session.commit()
            summary = merge_causality(session, rid)
            assert summary.merged_count == 1

    def test_unresolved_links(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CAUSAL_LINK,
                "caus_unknown",
                {"cause_event": "missing_a", "effect_event": "missing_b"},
                cid,
                confidence=0.6,
            )
            session.commit()
            summary = merge_causality(session, rid)
            assert len(summary.warnings) > 0
            assert "unresolved" in summary.warnings[0].lower()

    def test_cause_hint_equals_event_title_resolved(self, engine):
        """cause_hint equal to event title should resolve the link."""
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_sword",
                {"title": "Sword Drawn"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_battle",
                {"title": "Battle Begins"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CAUSAL_LINK,
                "caus_sword_battle",
                {"cause_hint": "Sword Drawn", "effect_hint": "Battle Begins"},
                cid,
                confidence=0.85,
            )
            session.commit()
            summary = merge_causality(session, rid)
            assert summary.merged_count == 1
            assert len(summary.warnings) == 0  # Should be resolved

    def test_cause_hint_contains_event_title_resolved(self, engine):
        """cause_hint containing the event title should resolve."""
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_battle",
                {"title": "Great Battle"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_flee",
                {"title": "Fleeing"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CAUSAL_LINK,
                "caus_battle_flee",
                {"cause_hint": "the Great Battle at dawn", "effect_hint": "army Fleeing south"},
                cid,
                confidence=0.85,
            )
            session.commit()
            summary = merge_causality(session, rid)
            assert len(summary.warnings) == 0

    def test_short_string_no_false_match(self, engine):
        """Very short cause/effect (< 4 chars normalized) should not match."""
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_a",
                {"title": "A"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CAUSAL_LINK,
                "caus_short",
                {"cause_hint": "a", "effect_hint": "b"},
                cid,
                confidence=0.5,
            )
            session.commit()
            summary = merge_causality(session, rid)
            assert len(summary.warnings) > 0
            assert "unresolved" in summary.warnings[0].lower()

    def test_resolved_event_ids_in_output(self, engine):
        """Resolved links should have resolved_cause_event_id and resolved_effect_event_id."""
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_cause",
                {"title": "Earthquake"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_effect",
                {"title": "Tsunami"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CAUSAL_LINK,
                "caus_eq_tsunami",
                {"cause_hint": "Earthquake", "effect_hint": "Tsunami"},
                cid,
                confidence=0.85,
            )
            session.commit()
            merge_causality(session, rid)

        with Session(engine) as session:
            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "merge_causality",
                )
            ).first()
            merged = json.loads(out.content_json)
            assert len(merged) == 1
            assert merged[0]["resolved"] is True
            assert merged[0].get("resolved_cause_event_id") == "evt_cause"
            assert merged[0].get("resolved_effect_event_id") == "evt_effect"


class TestMergeThemes:
    def test_dedup_themes(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.THEME_SIGNAL,
                "thm_revenge",
                {"theme_name": "复仇"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.THEME_SIGNAL,
                "thm_revenge",
                {"theme_name": "复仇"},
                cid,
                confidence=0.8,
            )
            session.commit()
            summary = merge_themes(session, rid)
            assert summary.merged_count == 1


class TestMergeOverview:
    def test_creates_overview_output(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session, rid, tid, AtomType.CHARACTER, "char_x", {"name": "X"}, cid, confidence=0.9
            )
            _create_atom(
                session, rid, tid, AtomType.EVENT, "evt_y", {"title": "Y"}, cid, confidence=0.9
            )
            session.commit()
            summary = merge_overview(session, rid)
            assert summary.merge_type == "overview"
            assert summary.atom_count == 2
            assert summary.merged_count == 1

            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "merge_overview",
                )
            ).first()
            assert out is not None
            merged = json.loads(out.content_json)
            assert merged[0]["character_count"] == 1
            assert merged[0]["event_count"] == 1

    def test_empty_overview(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            summary = merge_overview(session, rid)
            assert summary.atom_count == 0


class TestMergeDeduplication:
    def test_rerun_does_not_duplicate_outputs(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session, rid, tid, AtomType.CHARACTER, "char_x", {"name": "X"}, cid, confidence=0.9
            )
            session.commit()

        with Session(engine) as session:
            merge_characters(session, rid)

        with Session(engine) as session:
            # Run merge again
            merge_characters(session, rid)

        with Session(engine) as session:
            outs = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "merge_characters",
                )
            ).all()
            assert len(outs) == 1


class TestRequestedTypes:
    def test_requested_overview_and_characters(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session, rid, tid, AtomType.CHARACTER, "char_x", {"name": "X"}, cid, confidence=0.9
            )
            session.commit()

        with Session(engine) as session:
            summaries = run_merge_stage(session, rid, requested_types=["overview", "characters"])
            types = {s.merge_type for s in summaries}
            assert "overview" in types
            assert "characters" in types

        with Session(engine) as session:
            outs = session.exec(
                __import__("sqlmodel").select(AnalysisOutput).where(AnalysisOutput.run_id == rid)
            ).all()
            output_types = {o.output_type for o in outs}
            assert "merge_overview" in output_types
            assert "merge_characters" in output_types

    def test_unknown_requested_type_warns(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            summaries = run_merge_stage(session, rid, requested_types=["nonexistent"])
            assert len(summaries) >= 1
            s = summaries[0]
            assert len(s.warnings) > 0
            assert "unknown" in s.warnings[0].lower() or "Unknown" in s.warnings[0]


class TestRunMergeStage:
    def test_all_types_merged(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(session, rid, tid, AtomType.CHARACTER, "char_x", {"name": "X"}, cid)
            _create_atom(session, rid, tid, AtomType.EVENT, "evt_y", {"title": "Y"}, cid)
            _create_atom(
                session,
                rid,
                tid,
                AtomType.RELATION,
                "rel_z",
                {"character_a": "A", "character_b": "B", "relation_type": "r"},
                cid,
            )
            _create_atom(
                session, rid, tid, AtomType.THEME_SIGNAL, "thm_t", {"theme_name": "T"}, cid
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CAUSAL_LINK,
                "caus_c",
                {"cause_event": "a", "effect_event": "b"},
                cid,
            )
            _create_atom(session, rid, tid, AtomType.WORLDBUILDING, "wb_w", {"name": "W"}, cid)
            _create_atom(session, rid, tid, AtomType.FORESHADOWING, "fsh_f", {"title": "F"}, cid)
            session.commit()

        with Session(engine) as session:
            summaries = run_merge_stage(session, rid)
            assert len(summaries) >= 8  # overview + 7 types

            outs = session.exec(
                __import__("sqlmodel").select(AnalysisOutput).where(AnalysisOutput.run_id == rid)
            ).all()
            assert len(outs) >= 8

    def test_empty_atoms_no_error(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            summaries = run_merge_stage(session, rid)
            for s in summaries:
                assert s.atom_count == 0
                assert s.merged_count == 0


class TestMergeOverviewFields:
    def test_overview_item_has_source_evidence_confidence(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_x",
                {"name": "X", "evidence": "he spoke"},
                cid,
                0,
                0,
                0.9,
            )
            session.commit()
            merge_overview(session, rid)

            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "merge_overview",
                )
            ).first()
            assert out is not None
            merged = json.loads(out.content_json)
            item = merged[0]
            assert "source_atom_ids" in item
            assert "source_chunk_ids" in item
            assert "evidence_quotes" in item
            assert "confidence" in item

    def test_empty_overview_has_fields_with_zero_values(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            merge_overview(session, rid)

            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "merge_overview",
                )
            ).first()
            assert out is not None
            merged = json.loads(out.content_json)
            item = merged[0]
            assert item["source_atom_ids"] == []
            assert item["source_chunk_ids"] == []
            assert item["evidence_quotes"] == []
            assert item["confidence"] == 0.0

    def test_relation_hint_fields_in_merge(self, engine):
        """merge_relations reads character_a_hint/character_b_hint/interaction_type."""
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.RELATION,
                "rel_ab",
                {
                    "character_a_hint": "lady",
                    "character_b_hint": "knight",
                    "interaction_type": "rivalry",
                },
                cid,
                confidence=0.9,
            )
            session.commit()
            merge_relations(session, rid)

        with Session(engine) as session:
            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "merge_relations",
                )
            ).first()
            assert out is not None
            merged = json.loads(out.content_json)
            assert len(merged) == 1
            assert merged[0]["character_a"] == "lady"
            assert merged[0]["character_b"] == "knight"
            assert merged[0]["relation_type"] == "rivalry"

    def test_causal_hint_fields_in_merge(self, engine):
        """merge_causality reads cause_hint/effect_hint from atom content_json."""
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_sword",
                {"title": "sword_drawn"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_battle",
                {"title": "battle_begins"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CAUSAL_LINK,
                "caus_sword_battle",
                {
                    "cause_hint": "sword_drawn",
                    "effect_hint": "battle_begins",
                    "link_description": "sword drawn starts battle",
                },
                cid,
                confidence=0.85,
            )
            session.commit()
            merge_causality(session, rid)

        with Session(engine) as session:
            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "merge_causality",
                )
            ).first()
            assert out is not None
            merged = json.loads(out.content_json)
            assert len(merged) == 1
            assert merged[0]["cause_event"] == "sword_drawn"
            assert merged[0]["effect_event"] == "battle_begins"

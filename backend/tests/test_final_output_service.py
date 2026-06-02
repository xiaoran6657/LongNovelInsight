"""Tests for v0.2 Step 8 — Final Output Service."""

import json

from sqlmodel import Session

from models.analysis_output import AnalysisOutput
from models.analysis_run import AnalysisRun
from models.enums import AnalysisMode, AtomType
from models.extracted_atom import ExtractedAtom
from services.final_output_service import (
    build_final_causality,
    build_final_characters,
    build_final_events,
    build_final_overview,
    build_final_relations,
    build_final_themes,
    run_final_output_stage,
)
from services.merge_service import (
    merge_causality,
    merge_characters,
    merge_events,
    merge_overview,
    merge_relations,
    merge_themes,
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
    title=None,
    canonical_name=None,
):
    atom = ExtractedAtom(
        run_id=run_id,
        topic_id=topic_id,
        chunk_id=chunk_id,
        atom_type=atom_type,
        stable_id=stable_id,
        title=title or content.get("title"),
        canonical_name=canonical_name
        or content.get("name")
        or content.get("canonical_name")
        or content.get("theme_name"),
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
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="Final P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Final Test", provider_id=prov.id, status="parsed")
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


class TestBuildFinalCharacters:
    def test_creates_output_with_characters_key(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_zhangsan",
                {"name": "张三", "evidence": "he appeared"},
                cid,
                confidence=0.9,
            )
            session.commit()
            merge_characters(session, rid)
            build_final_characters(session, rid)

        with Session(engine) as session:
            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "characters",
                )
            ).first()
            assert out is not None
            content = json.loads(out.content_json)
            assert content["analysis_type"] == "characters"
            assert "characters" in content
            assert len(content["characters"]) == 1
            assert content["characters"][0]["name"] == "张三"

    def test_has_evidence_and_source_and_confidence(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_x",
                {"name": "X", "evidence": "said hello"},
                cid,
                0,
                0,
                0.85,
            )
            session.commit()
            merge_characters(session, rid)
            build_final_characters(session, rid)

        with Session(engine) as session:
            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "characters",
                )
            ).first()
            assert out is not None
            assert len(json.loads(out.source_chunk_ids)) > 0
            assert len(json.loads(out.evidence_quotes)) > 0
            assert out.confidence > 0

    def test_empty_merge_returns_zero_count(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            summary = build_final_characters(session, rid)
            assert summary.item_count == 0


class TestBuildFinalEvents:
    def test_creates_output_with_events_key(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_battle",
                {"title": "Battle", "participants": ["A"]},
                cid,
                confidence=0.9,
            )
            session.commit()
            merge_events(session, rid)
            build_final_events(session, rid)

        with Session(engine) as session:
            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "events",
                )
            ).first()
            assert out is not None
            content = json.loads(out.content_json)
            assert "events" in content
            assert content["events"][0]["title"] == "Battle"
            assert "event_id" in content["events"][0]


class TestBuildFinalRelations:
    def test_creates_output_with_relationships_key(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.RELATION,
                "rel_ab",
                {"character_a": "A", "character_b": "B", "relation_type": "ally"},
                cid,
                confidence=0.9,
            )
            session.commit()
            merge_relations(session, rid)
            build_final_relations(session, rid)

        with Session(engine) as session:
            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "relations",
                )
            ).first()
            assert out is not None
            content = json.loads(out.content_json)
            assert "relationships" in content
            item = content["relationships"][0]
            assert item["relationship_type"] == "ally"
            assert item["relation_type"] == "ally"


class TestBuildFinalCausality:
    def test_creates_output_with_causal_chains_key(self, engine):
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
                "caus_ce",
                {"cause_event": "evt_cause", "effect_event": "evt_effect"},
                cid,
                confidence=0.85,
            )
            session.commit()
            merge_causality(session, rid)
            build_final_causality(session, rid)

        with Session(engine) as session:
            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "causality",
                )
            ).first()
            assert out is not None
            content = json.loads(out.content_json)
            assert "causal_chains" in content
            assert content["causal_chains"][0]["resolved"] is True


class TestBuildFinalCausalityWarnings:
    def test_warnings_not_linear_with_unresolved_items(self, engine):
        """Many unresolved items should produce at most 1 warning, not N warnings."""
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            # Create 20 events with unique stable_ids
            for i in range(20):
                _create_atom(
                    session, rid, tid, AtomType.EVENT,
                    f"evt_{i}", {"title": f"Event_{i}"}, cid, confidence=0.9,
                )
            # Create 15 causal links, none matching any event (all unresolved)
            for i in range(15):
                _create_atom(
                    session, rid, tid, AtomType.CAUSAL_LINK,
                    f"caus_{i}",
                    {"cause_hint": f"Unknown_X_{i}", "effect_hint": f"Unknown_Y_{i}"},
                    cid, confidence=0.5,
                )
            session.commit()
            merge_causality(session, rid)
            summary = build_final_causality(session, rid)

        # Should have at most 1 consolidated warning, not 15
        assert len(summary.warnings) <= 1
        if summary.warnings:
            assert "unresolved causal links" in summary.warnings[0].lower()

    def test_resolved_event_ids_passed_through(self, engine):
        """resolved_cause_event_id / resolved_effect_event_id from merge should appear in final."""
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session, rid, tid, AtomType.EVENT,
                "evt_sunrise", {"title": "Sunrise"}, cid, confidence=0.9,
            )
            _create_atom(
                session, rid, tid, AtomType.EVENT,
                "evt_departure", {"title": "Departure"}, cid, confidence=0.9,
            )
            _create_atom(
                session, rid, tid, AtomType.CAUSAL_LINK,
                "caus_sun_dep",
                {"cause_hint": "Sunrise", "effect_hint": "Departure"},
                cid, confidence=0.85,
            )
            session.commit()
            merge_causality(session, rid)
            build_final_causality(session, rid)

        with Session(engine) as session:
            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "causality",
                )
            ).first()
            content = json.loads(out.content_json)
            item = content["causal_chains"][0]
            assert item["resolved"] is True
            assert item.get("resolved_cause_event_id") == "evt_sunrise"
            assert item.get("resolved_effect_event_id") == "evt_departure"


class TestBuildFinalThemes:
    def test_creates_output_with_themes_key(self, engine):
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
            session.commit()
            merge_themes(session, rid)
            build_final_themes(session, rid)

        with Session(engine) as session:
            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "themes",
                )
            ).first()
            assert out is not None
            content = json.loads(out.content_json)
            assert "themes" in content
            item = content["themes"][0]
            assert item["theme_name"] == "复仇"
            assert item["theme"] == "复仇"


class TestBuildFinalOverview:
    def test_creates_output_with_summary(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_x",
                {"name": "X"},
                cid,
                confidence=0.9,
            )
            _create_atom(
                session,
                rid,
                tid,
                AtomType.EVENT,
                "evt_y",
                {"title": "Y"},
                cid,
                confidence=0.9,
            )
            session.commit()
            merge_overview(session, rid)
            build_final_overview(session, rid)

        with Session(engine) as session:
            out = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "overview",
                )
            ).first()
            assert out is not None
            content = json.loads(out.content_json)
            assert "summary" in content
            assert content["character_count"] == 1
            assert content["event_count"] == 1


class TestRunFinalOutputStage:
    def test_requested_types_subset(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_x",
                {"name": "X"},
                cid,
                confidence=0.9,
            )
            session.commit()
            merge_characters(session, rid)
            merge_overview(session, rid)
            summaries = run_final_output_stage(
                session, rid, requested_types=["overview", "characters"]
            )
            types_produced = {s.output_type for s in summaries}
            assert "overview" in types_produced
            assert "characters" in types_produced
            assert "events" not in types_produced

    def test_rerun_no_duplicates(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_x",
                {"name": "X"},
                cid,
                confidence=0.9,
            )
            session.commit()
            merge_characters(session, rid)
            build_final_characters(session, rid)

        with Session(engine) as session:
            build_final_characters(session, rid)

        with Session(engine) as session:
            outs = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "characters",
                )
            ).all()
            assert len(outs) == 1

    def test_unknown_type_warns(self, engine):
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            summaries = run_final_output_stage(session, rid, requested_types=["nonexistent"])
            assert len(summaries) == 1
            assert any("unknown" in w.lower() for w in summaries[0].warnings)

    def test_skipped_type_generates_empty_output(self, engine):
        """Zero-item final type: skipped count is set, empty AnalysisOutput written."""
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            # No atoms → merge_characters creates 0-item merge
            merge_characters(session, rid)
            # Run final stage with characters type requested
            summaries = run_final_output_stage(session, rid, requested_types=["characters"])
            assert len(summaries) == 1
            assert summaries[0].item_count == 0
            assert any("insufficient evidence" in w.lower() for w in summaries[0].warnings)

            # Verify run counters
            run = session.get(AnalysisRun, rid)
            assert run.final_succeeded == 0
            assert run.final_failed == 0
            assert run.final_skipped == 1

            # Verify empty AnalysisOutput was written
            outputs = session.exec(
                __import__("sqlmodel")
                .select(AnalysisOutput)
                .where(
                    AnalysisOutput.run_id == rid,
                    AnalysisOutput.output_type == "characters",
                )
            ).all()
            assert len(outputs) == 1
            content = json.loads(outputs[0].content_json)
            assert content.get("insufficient_evidence") is True
            assert outputs[0].confidence == 0.0

    def test_succeeded_type_sets_correct_counters(self, engine):
        """Non-empty final type: succeeded count is set, no skipped."""
        tid, rid, cid = _setup_run(engine)
        with Session(engine) as session:
            _create_atom(
                session,
                rid,
                tid,
                AtomType.CHARACTER,
                "char_x",
                {"name": "X"},
                cid,
                confidence=0.9,
            )
            session.commit()
            merge_characters(session, rid)
            summaries = run_final_output_stage(session, rid, requested_types=["characters"])

            assert len(summaries) == 1
            assert summaries[0].item_count == 1

            run = session.get(AnalysisRun, rid)
            assert run.final_succeeded == 1
            assert run.final_skipped == 0

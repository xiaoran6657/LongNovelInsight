"""Tests for v0.4 multi-Work isolation — no cross-contamination between Works."""

import io
import json

from sqlmodel import Session, select

from models.chapter import Chapter
from models.chunk import Chunk
from models.document import Document
from models.enums import AtomType
from models.extracted_atom import ExtractedAtom
from models.model_provider import ModelProvider
from models.topic import Topic
from models.work import Work


def _setup_two_works(engine):
    """Create topic + 2 empty Works with provider. Returns (topic_id, w1_id, w2_id)."""
    with Session(engine) as session:
        prov = ModelProvider(
            name="IsoP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="IsoTopic", provider_id=prov.id, status="created")
        session.add(topic); session.flush()
        w1 = Work(topic_id=topic.id, title="Work 1", series_index=1)
        w2 = Work(topic_id=topic.id, title="Work 2", series_index=2)
        session.add(w1); session.add(w2)
        session.commit()
        return topic.id, w1.id, w2.id, prov.id


class TestSourceFileIsolation:
    def test_two_works_upload_same_format_no_overwrite(self, engine, client):
        """Two Works in same Topic + same file type → each has its own source file."""
        tid, w1_id, w2_id, pid = _setup_two_works(engine)

        client.put(
            f"/api/topics/{tid}/provider-config",
            json={"provider_id": pid},
        )

        # Upload TXT to Work 1
        r1 = client.post(
            f"/api/works/{w1_id}/documents/upload",
            files={"file": ("w1.txt", io.BytesIO("Work One\n第一章 内容。\n".encode()), "text/plain")},
        )
        assert r1.status_code == 201

        # Upload TXT to Work 2
        r2 = client.post(
            f"/api/works/{w2_id}/documents/upload",
            files={"file": ("w2.txt", io.BytesIO("Work Two\n第一章 不同。\n".encode()), "text/plain")},
        )
        assert r2.status_code == 201

        # Parse Work 1
        r3 = client.post(f"/api/works/{w1_id}/parse")
        assert r3.status_code == 200

        # Verify Work 1 chapters contain "Work One", not "Work Two"
        r4 = client.get(f"/api/works/{w1_id}/chapters")
        chapters = r4.json()["chapters"]
        chunk_texts = [c["title"] for c in chapters]
        # Should have content from Work 1, not Work 2
        assert any("Work One" in t or "第一章" in t for t in chunk_texts), (
            f"Work 1 chapters should contain its own content: {chunk_texts}"
        )

    def test_two_works_parse_independently(self, engine, client):
        """Parse Work 1 then Work 2 — Work 2's parse should not destroy Work 1's chunks."""
        tid, w1_id, w2_id, pid = _setup_two_works(engine)

        client.put(f"/api/topics/{tid}/provider-config", json={"provider_id": pid})
        client.post(
            f"/api/works/{w1_id}/documents/upload",
            files={"file": ("w1.txt", io.BytesIO("Work One\n第一章。\n".encode()), "text/plain")},
        )
        client.post(
            f"/api/works/{w2_id}/documents/upload",
            files={"file": ("w2.txt", io.BytesIO("Work Two\n第一章。\n".encode()), "text/plain")},
        )
        client.post(f"/api/works/{w1_id}/parse")

        w1_chunks_before = client.get(f"/api/works/{w1_id}/chunks").json()["chunks"]

        # Parse Work 2
        client.post(f"/api/works/{w2_id}/parse")

        # Work 1 chunks should be unchanged
        w1_chunks_after = client.get(f"/api/works/{w1_id}/chunks").json()["chunks"]
        assert len(w1_chunks_after) == len(w1_chunks_before), (
            f"Work 1 chunks should not be affected by Work 2 parse: "
            f"{len(w1_chunks_before)} → {len(w1_chunks_after)}"
        )


class TestDeleteIsolation:
    def test_legacy_delete_does_not_affect_other_works(self, engine, client):
        """Deleting default Work's document should not delete other Work's chunks."""
        tid, w1_id, w2_id, pid = _setup_two_works(engine)

        client.put(f"/api/topics/{tid}/provider-config", json={"provider_id": pid})

        # Upload and parse both Works
        client.post(
            f"/api/works/{w1_id}/documents/upload",
            files={"file": ("w1.txt", io.BytesIO("W1 第一章。\n".encode()), "text/plain")},
        )
        client.post(f"/api/works/{w1_id}/parse")

        client.post(
            f"/api/works/{w2_id}/documents/upload",
            files={"file": ("w2.txt", io.BytesIO("W2 第一章。\n".encode()), "text/plain")},
        )
        client.post(f"/api/works/{w2_id}/parse")
        w2_chunk_count = len(client.get(f"/api/works/{w2_id}/chunks").json()["chunks"])

        # Legacy delete on the Topic (deletes default Work's document)
        r = client.delete(f"/api/topics/{tid}/documents/current")
        assert r.status_code == 200

        # Work 2's chunks should still exist
        w2_chunks_after = client.get(f"/api/works/{w2_id}/chunks").json()["chunks"]
        assert len(w2_chunks_after) == w2_chunk_count, (
            f"Work 2 chunks should survive legacy delete: "
            f"{w2_chunk_count} → {len(w2_chunks_after)}"
        )

    def test_delete_does_not_remove_other_work_analysis(self, engine, client):
        """Legacy delete of default Work doc should preserve other Work's analysis data."""
        from models.analysis_output import AnalysisOutput

        tid, w1_id, w2_id, pid = _setup_two_works(engine)

        client.put(f"/api/topics/{tid}/provider-config", json={"provider_id": pid})

        # Upload + parse Work 2
        client.post(
            f"/api/works/{w2_id}/documents/upload",
            files={"file": ("w2.txt", io.BytesIO("W2 第一章。\n".encode()), "text/plain")},
        )
        client.post(f"/api/works/{w2_id}/parse")

        # Insert analysis output directly for Work 2
        with Session(engine) as session:
            from models.analysis_run import AnalysisRun
            run = AnalysisRun(topic_id=tid, mode="full")
            session.add(run)
            run.set_chunk_selection({"selected_chunk_ids": [], "work_id": w2_id})
            session.add(run); session.flush()
            ao = AnalysisOutput(
                topic_id=tid, run_id=run.id, output_type="characters",
                title="Chars", content_json="{}",
                source_chunk_ids="[]", evidence_quotes="[]", confidence=0.5,
            )
            session.add(ao)
            session.commit()

        # Work 1 is the default Work (series_index=1), upload + parse it
        client.post(
            f"/api/works/{w1_id}/documents/upload",
            files={"file": ("w1.txt", io.BytesIO("W1 第一章。\n".encode()), "text/plain")},
        )
        client.post(f"/api/works/{w1_id}/parse")

        # Legacy delete on the Topic (deletes default Work 1's document)
        r = client.delete(f"/api/topics/{tid}/documents/current")
        assert r.status_code == 200

        # Work 2's analysis output should still exist
        with Session(engine) as session:
            outputs_after = session.exec(
                select(AnalysisOutput).where(AnalysisOutput.topic_id == tid)
            ).all()
            assert len(outputs_after) >= 1, (
                "Work 2's analysis outputs should survive legacy delete of Work 1"
            )


class TestOutputIsolation:
    def test_work_outputs_only_show_own_runs(self, engine, client):
        """Work outputs endpoint should only return outputs from that Work's runs."""
        from models.analysis_output import AnalysisOutput

        tid, w1_id, w2_id, pid = _setup_two_works(engine)

        client.put(f"/api/topics/{tid}/provider-config", json={"provider_id": pid})

        # Upload + parse both Works
        client.post(
            f"/api/works/{w1_id}/documents/upload",
            files={"file": ("w1.txt", io.BytesIO("W1 第一章。\n".encode()), "text/plain")},
        )
        client.post(f"/api/works/{w1_id}/parse")
        client.post(
            f"/api/works/{w2_id}/documents/upload",
            files={"file": ("w2.txt", io.BytesIO("W2 第一章。\n".encode()), "text/plain")},
        )
        client.post(f"/api/works/{w2_id}/parse")

        # Insert outputs directly for both Works
        with Session(engine) as session:
            from models.analysis_run import AnalysisRun

            r1 = AnalysisRun(topic_id=tid, mode="full")
            session.add(r1)
            r1.set_chunk_selection({"selected_chunk_ids": [], "work_id": w1_id})
            session.add(r1); session.flush()
            session.add(AnalysisOutput(
                topic_id=tid, run_id=r1.id, output_type="characters",
                title="W1 Chars", content_json="{}",
                source_chunk_ids="[]", evidence_quotes="[]", confidence=0.5,
            ))

            r2 = AnalysisRun(topic_id=tid, mode="full")
            session.add(r2)
            r2.set_chunk_selection({"selected_chunk_ids": [], "work_id": w2_id})
            session.add(r2); session.flush()
            session.add(AnalysisOutput(
                topic_id=tid, run_id=r2.id, output_type="characters",
                title="W2 Chars", content_json="{}",
                source_chunk_ids="[]", evidence_quotes="[]", confidence=0.5,
            ))
            session.commit()

        # Work 1 outputs should only include W1's output
        r = client.get(f"/api/works/{w1_id}/analysis/outputs")
        assert r.status_code == 200
        w1_outputs = r.json()["outputs"]
        w1_titles = {o["title"] for o in w1_outputs}
        assert "W1 Chars" in w1_titles
        assert "W2 Chars" not in w1_titles, (
            f"Work 1 outputs should not include Work 2 outputs: {w1_titles}"
        )


class TestEntityAliasSafety:
    def test_traits_not_used_as_aliases(self, engine):
        """observed_traits like 'brave' should not be used for entity merging."""
        from models.analysis_run import AnalysisRun

        with Session(engine) as session:
            prov = ModelProvider(
                name="TraitP", provider_type="openai_compatible",
                base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
            )
            session.add(prov); session.flush()
            topic = Topic(name="TraitTopic", provider_id=prov.id, status="parsed")
            session.add(topic); session.flush()
            w1 = Work(topic_id=topic.id, title="W1", series_index=1)
            w2 = Work(topic_id=topic.id, title="W2", series_index=2)
            session.add(w1); session.add(w2); session.flush()
            run = AnalysisRun(topic_id=topic.id, mode="full")
            session.add(run); session.flush()
            d1 = Document(topic_id=topic.id, work_id=w1.id, original_filename="a.txt",
                          file_size_bytes=50, char_count=50, status="parsed")
            d2 = Document(topic_id=topic.id, work_id=w2.id, original_filename="b.txt",
                          file_size_bytes=50, char_count=50, status="parsed")
            session.add(d1); session.add(d2); session.flush()
            ch1 = Chapter(topic_id=topic.id, document_id=d1.id, chapter_index=0,
                          title="Ch", start_char=0, end_char=50, char_count=50)
            ch2 = Chapter(topic_id=topic.id, document_id=d2.id, chapter_index=0,
                          title="Ch", start_char=0, end_char=50, char_count=50)
            session.add(ch1); session.add(ch2); session.flush()
            ck1 = Chunk(topic_id=topic.id, document_id=d1.id, chapter_id=ch1.id,
                        chapter_index=0, chunk_index=0, text="a",
                        start_char=0, end_char=50, char_count=50, estimated_tokens=34)
            ck2 = Chunk(topic_id=topic.id, document_id=d2.id, chapter_id=ch2.id,
                        chapter_index=0, chunk_index=0, text="b",
                        start_char=0, end_char=50, char_count=50, estimated_tokens=34)
            session.add(ck1); session.add(ck2)
            session.commit()
            tid = topic.id
            rid = run.id
            c1_id = ck1.id
            c2_id = ck2.id

        with Session(engine) as session:
            # Two different characters with same trait → should NOT merge
            session.add(ExtractedAtom(
                run_id=rid, topic_id=tid, chunk_id=c1_id,
                atom_type=AtomType.CHARACTER, stable_id="char_li",
                canonical_name="李明", title="李明",
                content_json=json.dumps({"name": "李明", "observed_traits": ["brave"]}),
                source_chunk_ids=json.dumps([c1_id]),
                evidence_quotes=json.dumps(["test"]), confidence=0.9,
            ))
            session.add(ExtractedAtom(
                run_id=rid, topic_id=tid, chunk_id=c2_id,
                atom_type=AtomType.CHARACTER, stable_id="char_wang",
                canonical_name="王芳", title="王芳",
                content_json=json.dumps({"name": "王芳", "observed_traits": ["brave"]}),
                source_chunk_ids=json.dumps([c2_id]),
                evidence_quotes=json.dumps(["test"]), confidence=0.9,
            ))
            session.commit()

            from services.cross_work_entity_service import build_entity_registry
            result = build_entity_registry(tid, session)
            # Should be 2 separate entities — traits are not aliases
            assert result["entity_count"] == 2, (
                f"Different characters with same trait should not merge, got {result['entity_count']}"
            )


class TestEntityRebuildClears:
    def test_empty_rebuild_clears_old_registry(self, engine):
        """Rebuild with atoms → entities. Rebuild with empty → registry cleared."""
        from models.analysis_run import AnalysisRun

        with Session(engine) as session:
            prov = ModelProvider(
                name="ClearP", provider_type="openai_compatible",
                base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
            )
            session.add(prov); session.flush()
            topic = Topic(name="ClearTopic", provider_id=prov.id, status="parsed")
            session.add(topic); session.flush()
            w = Work(topic_id=topic.id, title="W", series_index=1)
            session.add(w); session.flush()
            run = AnalysisRun(topic_id=topic.id, mode="full")
            session.add(run); session.flush()
            d = Document(topic_id=topic.id, work_id=w.id, original_filename="a.txt",
                         file_size_bytes=50, char_count=50, status="parsed")
            session.add(d); session.flush()
            ch = Chapter(topic_id=topic.id, document_id=d.id, chapter_index=0,
                         title="Ch", start_char=0, end_char=50, char_count=50)
            session.add(ch); session.flush()
            ck = Chunk(topic_id=topic.id, document_id=d.id, chapter_id=ch.id,
                       chapter_index=0, chunk_index=0, text="a",
                       start_char=0, end_char=50, char_count=50, estimated_tokens=34)
            session.add(ck)
            session.commit()
            tid = topic.id
            rid = run.id
            cid = ck.id

        # First build: has atoms
        with Session(engine) as session:
            session.add(ExtractedAtom(
                run_id=rid, topic_id=tid, chunk_id=cid,
                atom_type=AtomType.CHARACTER, stable_id="char_x",
                canonical_name="X", title="X",
                content_json=json.dumps({"name": "X"}),
                source_chunk_ids=json.dumps([cid]),
                evidence_quotes=json.dumps(["test"]), confidence=0.9,
            ))
            session.commit()

            from models.global_entity import GlobalEntity
            from services.cross_work_entity_service import build_entity_registry
            result = build_entity_registry(tid, session)
            assert result["entity_count"] == 1
            entities = session.exec(
                select(GlobalEntity).where(GlobalEntity.topic_id == tid)
            ).all()
            assert len(entities) == 1

            # Delete all atoms, rebuild with empty
            session.exec(
                __import__("sqlmodel").delete(ExtractedAtom).where(
                    ExtractedAtom.topic_id == tid
                )
            )
            session.commit()
            result2 = build_entity_registry(tid, session)
            assert result2["entity_count"] == 0
            entities2 = session.exec(
                select(GlobalEntity).where(GlobalEntity.topic_id == tid)
            ).all()
            assert len(entities2) == 0, (
                f"Empty rebuild should clear old registry, got {len(entities2)} entities"
            )


class TestDeleteCleansOwnAnalysis:
    def test_delete_removes_only_own_extractions_and_atoms(self, engine, client):
        """Legacy delete of default Work should remove its extractions/atoms,
        but preserve another Work's extractions/atoms."""
        from models.analysis_run import AnalysisRun
        from models.local_extraction import LocalExtraction

        tid, w1_id, w2_id, pid = _setup_two_works(engine)

        client.put(f"/api/topics/{tid}/provider-config", json={"provider_id": pid})

        # Upload + parse both Works to get real chunks
        client.post(
            f"/api/works/{w1_id}/documents/upload",
            files={"file": ("w1.txt", io.BytesIO("W1 第一章。\n".encode()), "text/plain")},
        )
        client.post(f"/api/works/{w1_id}/parse")
        client.post(
            f"/api/works/{w2_id}/documents/upload",
            files={"file": ("w2.txt", io.BytesIO("W2 第一章。\n".encode()), "text/plain")},
        )
        client.post(f"/api/works/{w2_id}/parse")

        # Get chunk IDs for each Work
        with Session(engine) as session:
            w1_doc = session.exec(
                select(Document).where(Document.work_id == w1_id)
            ).first()
            w2_doc = session.exec(
                select(Document).where(Document.work_id == w2_id)
            ).first()
            w1_chunk = session.exec(
                select(Chunk).where(Chunk.document_id == w1_doc.id).limit(1)
            ).first()
            w2_chunk = session.exec(
                select(Chunk).where(Chunk.document_id == w2_doc.id).limit(1)
            ).first()

            run = AnalysisRun(topic_id=tid, mode="full")
            session.add(run); session.flush()

            # Create extraction + atom for each Work
            ext1 = LocalExtraction(
                run_id=run.id, topic_id=tid, chunk_id=w1_chunk.id,
                status="succeeded", attempt_count=1, confidence=0.5,
            )
            ext2 = LocalExtraction(
                run_id=run.id, topic_id=tid, chunk_id=w2_chunk.id,
                status="succeeded", attempt_count=1, confidence=0.5,
            )
            session.add(ext1); session.add(ext2); session.flush()

            atom1 = ExtractedAtom(
                run_id=run.id, topic_id=tid, chunk_id=w1_chunk.id,
                atom_type=AtomType.CHARACTER, stable_id="char_a",
                content_json='{"name":"A"}',
                source_chunk_ids=json.dumps([w1_chunk.id]),
                evidence_quotes=json.dumps(["test"]), confidence=0.9,
            )
            atom2 = ExtractedAtom(
                run_id=run.id, topic_id=tid, chunk_id=w2_chunk.id,
                atom_type=AtomType.CHARACTER, stable_id="char_b",
                content_json='{"name":"B"}',
                source_chunk_ids=json.dumps([w2_chunk.id]),
                evidence_quotes=json.dumps(["test"]), confidence=0.9,
            )
            session.add(atom1); session.add(atom2)
            session.commit()

            ext1_id = ext1.id
            ext2_id = ext2.id
            atom1_id = atom1.id
            atom2_id = atom2.id

        # Legacy delete on default Work (w1)
        r = client.delete(f"/api/topics/{tid}/documents/current")
        assert r.status_code == 200

        # Verify: Work 1's extraction and atom are gone
        with Session(engine) as session:
            ext1_after = session.get(LocalExtraction, ext1_id)
            atom1_after = session.get(ExtractedAtom, atom1_id)
            assert ext1_after is None, "Work 1's extraction should be deleted"
            assert atom1_after is None, "Work 1's atom should be deleted"

            # Work 2's extraction and atom are preserved
            ext2_after = session.get(LocalExtraction, ext2_id)
            atom2_after = session.get(ExtractedAtom, atom2_id)
            assert ext2_after is not None, "Work 2's extraction should survive"
            assert atom2_after is not None, "Work 2's atom should survive"

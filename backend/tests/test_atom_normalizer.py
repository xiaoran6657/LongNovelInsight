"""Tests for atom_normalizer — full pipeline from mock JSON to ExtractedAtom rows."""

import json

from models.analysis_run import AnalysisRun
from models.enums import AnalysisMode, AtomType
from models.local_extraction import LocalExtraction
from services.atom_normalizer import normalize_local_extraction

MOCK_VALID_JSON = json.dumps({
    "local_characters": [
        {
            "character_id_hint": "boy_at_window",
            "name": "张三",
            "entity_type": "person",
            "brief_description": "一个站在窗边的少年",
            "observed_traits": ["好奇", "勇敢"],
            "source_chunk_ids": ["chunk-1"],
            "evidence_quotes": ["张三站在窗前望着远处"],
            "confidence": 0.9,
        },
        {
            "character_id_hint": "old_man",
            "name": "李四",
            "brief_description": "一位老者",
            "source_chunk_ids": ["chunk-1"],
            "evidence_quotes": ["李四拄着拐杖"],
            "confidence": 0.85,
        },
    ],
    "local_events": [
        {
            "event_id_hint": "battle_start",
            "title": "赤壁之战开始",
            "summary": "一场大规模水战",
            "event_type": "conflict",
            "participants": ["张三", "李四"],
            "source_chunk_ids": ["chunk-1"],
            "evidence_quotes": ["战鼓响起"],
            "confidence": 0.95,
        }
    ],
    "local_causal_links": [
        {
            "causal_link_id_hint": "battle_to_defeat",
            "title": "赤壁之战导致曹操败退",
            "cause_event": "赤壁之战开始",
            "effect_event": "曹操败退",
            "strength": "strong",
            "source_chunk_ids": ["chunk-1"],
            "evidence_quotes": ["曹操败退而走"],
            "confidence": 0.85,
        }
    ],
    "local_relations": [
        {
            "relation_id_hint": "mentor_student",
            "character_a": "张三",
            "character_b": "李四",
            "relation_type": "师徒",
            "source_chunk_ids": ["chunk-1"],
            "evidence_quotes": ["李四教导张三"],
            "confidence": 0.8,
        }
    ],
    "local_theme_signals": [
        {
            "theme_id_hint": "revenge_theme",
            "theme_name": "复仇",
            "description": "主角为父报仇",
            "source_chunk_ids": ["chunk-1"],
            "evidence_quotes": ["我一定要为父亲报仇"],
            "confidence": 0.7,
        }
    ],
    "local_worldbuilding": [
        {
            "location_id_hint": "xiangyang_city",
            "name": "襄阳城",
            "location_type": "city",
            "description": "一座边境城市",
            "source_chunk_ids": ["chunk-1"],
            "evidence_quotes": ["襄阳城高墙厚"],
            "confidence": 0.9,
        }
    ],
    "local_foreshadowing": [
        {
            "foreshadowing_id_hint": "tower_hint",
            "title": "塔楼伏笔",
            "signal": "张三注意到塔楼上有人影",
            "possible_payoff": "塔楼上的人可能是刺客",
            "source_chunk_ids": ["chunk-1"],
            "evidence_quotes": ["塔楼上闪过一个人影"],
            "confidence": 0.6,
        }
    ],
    "local_open_questions": [
        {
            "question_id_hint": "who_is_shadow",
            "title": "人影是谁",
            "question": "塔楼上的人影是谁？",
            "source_chunk_ids": ["chunk-1"],
            "evidence_quotes": ["塔楼上闪过一个人影"],
            "confidence": 0.5,
        }
    ],
})


def _setup(client):
    """Create topic + chunk + AnalysisRun for normalizer tests."""
    import io

    r = client.post("/api/topics", json={"name": "Normalizer Test"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    content = io.BytesIO("第一章 测试\n内容。\n第二章 更多\n内容。\n".encode())
    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("novel.txt", content, "text/plain")},
    )
    r = client.post(f"/api/topics/{topic_id}/parse")
    assert r.status_code == 200

    chunks = client.get(f"/api/topics/{topic_id}/chunks?limit=1").json()["chunks"]
    chunk_id = chunks[0]["id"]

    from sqlmodel import Session

    from db import engine

    with Session(engine) as session:
        run = AnalysisRun(topic_id=topic_id, mode=AnalysisMode.PREVIEW)
        run.set_requested_types(["characters", "events"])
        session.add(run)
        session.flush()

        ext = LocalExtraction(
            run_id=run.id,
            topic_id=topic_id,
            chunk_id=chunk_id,
            status="succeeded",
            attempt_count=1,
            content_json=MOCK_VALID_JSON,
            source_chunk_ids=json.dumps([chunk_id]),
        )
        session.add(ext)
        session.commit()
        session.refresh(ext)
        session.refresh(run)
        return topic_id, run.id, ext.id, chunk_id

    return "", "", "", ""


def test_normalize_creates_all_atom_types(client):
    """All 8 atom types are created from valid mock JSON."""
    topic_id, run_id, ext_id, chunk_id = _setup(client)
    assert topic_id

    from sqlmodel import Session, select

    from db import engine
    from models.extracted_atom import ExtractedAtom

    with Session(engine) as session:
        result = normalize_local_extraction(
            extraction_id=ext_id,
            run_id=run_id,
            topic_id=topic_id,
            chunk_id=chunk_id,
            content_json_str=MOCK_VALID_JSON,
            session=session,
        )
        session.commit()

        assert result.created_count == 9
        assert result.skipped_count == 0
        assert len(result.warnings) == 0

        atoms = session.exec(
            select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)
        ).all()
        assert len(atoms) == 9

        types_found = {a.atom_type for a in atoms}
        expected = {
            AtomType.CHARACTER,
            AtomType.EVENT,
            AtomType.RELATION,
            AtomType.CAUSAL_LINK,
            AtomType.THEME_SIGNAL,
            AtomType.WORLDBUILDING,
            AtomType.FORESHADOWING,
            AtomType.OPEN_QUESTION,
        }
        assert types_found == expected

    client.delete(f"/api/topics/{topic_id}")


def test_atoms_have_evidence(client):
    """Each created atom preserves evidence and source_chunk_ids."""
    topic_id, run_id, ext_id, chunk_id = _setup(client)
    assert topic_id

    from sqlmodel import Session, select

    from db import engine
    from models.extracted_atom import ExtractedAtom

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, MOCK_VALID_JSON, session)
        session.commit()

        atoms = session.exec(
            select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)
        ).all()
        for atom in atoms:
            ev = json.loads(atom.evidence_quotes)
            src = json.loads(atom.source_chunk_ids)
            assert isinstance(ev, list)
            assert isinstance(src, list)
            assert len(ev) > 0, f"No evidence for {atom.atom_type}"
            assert chunk_id in src or any(src), f"Missing source chunks for {atom.atom_type}"

    client.delete(f"/api/topics/{topic_id}")


def test_atoms_have_stable_ids(client):
    """Each atom gets a deterministic, unique stable ID."""
    topic_id, run_id, ext_id, chunk_id = _setup(client)
    assert topic_id

    from sqlmodel import Session, select

    from db import engine
    from models.extracted_atom import ExtractedAtom

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, MOCK_VALID_JSON, session)
        session.commit()

        atoms = session.exec(
            select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)
        ).all()
        ids = [a.stable_id for a in atoms]
        assert len(ids) == len(set(ids))  # all unique
        for sid in ids:
            assert len(sid) > 2
            assert " " not in sid

    client.delete(f"/api/topics/{topic_id}")


def test_bad_json_returns_warnings(client):
    """Malformed JSON does not crash the normalizer."""
    topic_id, run_id, ext_id, chunk_id = _setup(client)
    assert topic_id

    from sqlmodel import Session

    from db import engine

    with Session(engine) as session:
        result = normalize_local_extraction(
            ext_id, run_id, topic_id, chunk_id, "not valid json{{{", session
        )
        session.commit()
        assert result.created_count == 0
        assert len(result.warnings) > 0

    client.delete(f"/api/topics/{topic_id}")


def test_missing_fields_graceful(client):
    """Atoms with missing fields are still created with defaults."""
    topic_id, run_id, ext_id, chunk_id = _setup(client)
    assert topic_id

    minimal_json = json.dumps({
        "local_characters": [
            {"character_id_hint": "bare_minimum"}  # no evidence, no source_chunk_ids
        ]
    })

    from sqlmodel import Session, select

    from db import engine
    from models.extracted_atom import ExtractedAtom

    with Session(engine) as session:
        result = normalize_local_extraction(
            ext_id, run_id, topic_id, chunk_id, minimal_json, session
        )
        session.commit()
        assert result.created_count == 1
        assert result.skipped_count == 0

        atoms = session.exec(
            select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)
        ).all()
        assert len(atoms) == 1
        a = atoms[0]
        assert a.confidence == 0.5  # default
        # chunk_id auto-added
        src = json.loads(a.source_chunk_ids)
        assert chunk_id in src

    client.delete(f"/api/topics/{topic_id}")


def test_nonexistent_atom_type_skipped(client):
    """Unknown keys in the JSON are silently skipped (not errors)."""
    topic_id, run_id, ext_id, chunk_id = _setup(client)
    assert topic_id

    json_with_extra = json.dumps({
        "local_characters": [],
        "local_events": [],
        "weird_new_type": [{"x": 1}],
    })

    from sqlmodel import Session

    from db import engine

    with Session(engine) as session:
        result = normalize_local_extraction(
            ext_id, run_id, topic_id, chunk_id, json_with_extra, session
        )
        session.commit()
        assert result.created_count == 0  # all lists are empty
        assert result.skipped_count == 0  # unknown key is just ignored

    client.delete(f"/api/topics/{topic_id}")


def test_confidence_clamping(client):
    """Confidence values outside 0.0–1.0 are clamped."""
    topic_id, run_id, ext_id, chunk_id = _setup(client)
    assert topic_id

    json_bad_conf = json.dumps({
        "local_characters": [
            {
                "character_id_hint": "high_conf",
                "name": "High",
                "confidence": 999.0,
                "source_chunk_ids": ["chunk-1"],
                "evidence_quotes": ["test"],
            },
            {
                "character_id_hint": "neg_conf",
                "name": "Neg",
                "confidence": -5.0,
                "source_chunk_ids": ["chunk-1"],
                "evidence_quotes": ["test"],
            },
        ]
    })

    from sqlmodel import Session, select

    from db import engine
    from models.extracted_atom import ExtractedAtom

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, json_bad_conf, session)
        session.commit()

        atoms = session.exec(
            select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)
        ).all()
        confs = [a.confidence for a in atoms]
        for c in confs:
            assert 0.0 <= c <= 1.0, f"Confidence out of range: {c}"

    client.delete(f"/api/topics/{topic_id}")

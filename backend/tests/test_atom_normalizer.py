"""Tests for atom_normalizer — full contract-strict pipeline."""

import json

from sqlmodel import Session

from models.analysis_run import AnalysisRun
from models.enums import AnalysisMode
from models.extracted_atom import ExtractedAtom
from models.local_extraction import LocalExtraction
from services.atom_normalizer import normalize_local_extraction

MOCK_VALID_JSON = json.dumps(
    {
        "local_characters": [
            {
                "character_id_hint": "boy_at_window",
                "name": "张三",
                "entity_type": "person",
                "brief_description": "少年",
                "source_chunk_ids": ["chunk-1"],
                "evidence_quotes": ["张三站在窗前"],
                "confidence": 0.9,
            },
        ],
        "local_events": [
            {
                "event_id_hint": "battle_start",
                "title": "赤壁之战开始",
                "summary": "水战",
                "source_chunk_ids": ["chunk-1"],
                "evidence_quotes": ["战鼓响起"],
                "confidence": 0.95,
            },
        ],
        "local_relations": [
            {
                "relation_id_hint": "mentor",
                "character_a": "张三",
                "character_b": "李四",
                "relation_type": "师徒",
                "source_chunk_ids": ["chunk-1"],
                "evidence_quotes": ["李四教导张三"],
                "confidence": 0.8,
            },
        ],
        "local_causal_links": [
            {
                "causal_link_id_hint": "battle_to_defeat",
                "title": "战败",
                "cause_event": "赤壁之战开始",
                "effect_event": "曹操败退",
                "source_chunk_ids": ["chunk-1"],
                "evidence_quotes": ["曹操败退"],
                "confidence": 0.85,
            },
        ],
        "local_open_questions": [
            {
                "question_id_hint": "who",
                "title": "人影是谁",
                "source_chunk_ids": ["chunk-1"],
                "evidence_quotes": ["人影闪过"],
                "confidence": 0.5,
            },
        ],
    }
)


def _setup(client, engine):
    """Create topic + chunk + AnalysisRun + LocalExtraction. Returns IDs."""
    import io

    r = client.post("/api/topics", json={"name": "Norm Test"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("n.txt", io.BytesIO("第一章 测试\n内容。\n".encode()), "text/plain")},
    )
    r = client.post(f"/api/topics/{topic_id}/parse")
    assert r.status_code == 200

    chunks = client.get(f"/api/topics/{topic_id}/chunks?limit=1").json()["chunks"]
    chunk_id = chunks[0]["id"]

    with Session(engine) as session:
        run = AnalysisRun(topic_id=topic_id, mode=AnalysisMode.PREVIEW)
        session.add(run)
        session.flush()
        ext = LocalExtraction(
            run_id=run.id,
            topic_id=topic_id,
            chunk_id=chunk_id,
            status="succeeded",
            attempt_count=1,
            content_json=MOCK_VALID_JSON,
        )
        session.add(ext)
        session.commit()
        return topic_id, run.id, ext.id, chunk_id


def test_normalize_creates_all_types(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    from sqlmodel import select

    with Session(engine) as session:
        result = normalize_local_extraction(
            ext_id, run_id, topic_id, chunk_id, MOCK_VALID_JSON, session
        )
        session.commit()
        assert result.created_count == 5
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        types = {a.atom_type for a in atoms}
        assert types == {"character", "event", "relation", "causal_link", "open_question"}
    client.delete(f"/api/topics/{topic_id}")


def test_atoms_have_evidence(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    from sqlmodel import select

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, MOCK_VALID_JSON, session)
        session.commit()
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        for a in atoms:
            ev = json.loads(a.evidence_quotes)
            src = json.loads(a.source_chunk_ids)
            assert isinstance(ev, list)
            assert len(ev) > 0, f"No evidence for {a.atom_type}"
            assert chunk_id in src, f"chunk_id missing from {a.atom_type} source"
    client.delete(f"/api/topics/{topic_id}")


def test_evidence_non_list_warning(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    bad = json.dumps(
        {
            "local_characters": [
                {
                    "character_id_hint": "x",
                    "name": "X",
                    "evidence_quotes": "not a list",
                    "source_chunk_ids": [chunk_id],
                }
            ]
        }
    )
    with Session(engine) as session:
        result = normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, bad, session)
        session.commit()
        assert result.created_count >= 1
        assert any("evidence_quotes" in w.lower() for w in result.warnings)
    client.delete(f"/api/topics/{topic_id}")


def test_source_non_list_auto_adds_chunk(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    bad = json.dumps(
        {
            "local_characters": [
                {
                    "character_id_hint": "x",
                    "name": "X",
                    "source_chunk_ids": 123,
                    "evidence_quotes": ["ok"],
                }
            ]
        }
    )
    from sqlmodel import select

    with Session(engine) as session:
        result = normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, bad, session)
        session.commit()
        assert result.created_count >= 1
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        assert len(atoms) >= 1
        src = json.loads(atoms[0].source_chunk_ids)
        assert chunk_id in src
    client.delete(f"/api/topics/{topic_id}")


def test_no_evidence_caps_confidence(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    bad = json.dumps(
        {
            "local_characters": [
                {
                    "character_id_hint": "x",
                    "name": "X",
                    "source_chunk_ids": [chunk_id],
                    "confidence": 0.9,
                }
            ]
        }
    )  # missing evidence_quotes
    from sqlmodel import select

    with Session(engine) as session:
        result = normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, bad, session)
        session.commit()
        assert result.created_count >= 1
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        assert atoms[0].confidence <= 0.3
        assert any("evidence" in w.lower() for w in result.warnings)
    client.delete(f"/api/topics/{topic_id}")


def test_dict_wrapped_items(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    wrapped = json.dumps(
        {
            "local_characters": {
                "items": [
                    {
                        "character_id_hint": "x",
                        "name": "X",
                        "source_chunk_ids": [chunk_id],
                        "evidence_quotes": ["ok"],
                        "confidence": 0.8,
                    }
                ]
            }
        }
    )
    with Session(engine) as session:
        result = normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, wrapped, session)
        session.commit()
        assert result.created_count == 1
    client.delete(f"/api/topics/{topic_id}")


def test_relation_stable_id_directional(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    rel = json.dumps(
        {
            "local_relations": [
                {
                    "character_a": "刘备",
                    "character_b": "关羽",
                    "relation_type": "结义",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["兄弟"],
                    "confidence": 0.9,
                }
            ]
        }
    )
    from sqlmodel import select

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, rel, session)
        session.commit()
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        assert len(atoms) == 1
        # ID should start with rel_
        assert atoms[0].stable_id.startswith("rel_")
    client.delete(f"/api/topics/{topic_id}")


def test_relation_bidirectional_same_id(client, engine):
    """A-B and B-A produce same stable ID."""
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    rel1 = json.dumps(
        {
            "local_relations": [
                {
                    "character_a": "刘备",
                    "character_b": "关羽",
                    "relation_type": "结义",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["兄弟"],
                    "confidence": 0.9,
                }
            ]
        }
    )
    with Session(engine) as s1:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, rel1, s1)
        s1.commit()

    # Second extraction with reversed order
    r2 = client.post("/api/topics", json={"name": "Norm Test 2"})
    t2 = r2.json()["id"]
    import io

    client.post(
        f"/api/topics/{t2}/documents/upload",
        files={"file": ("n.txt", io.BytesIO("第一章 测试\n".encode()), "text/plain")},
    )
    client.post(f"/api/topics/{t2}/parse")
    c2 = client.get(f"/api/topics/{t2}/chunks?limit=1").json()["chunks"][0]["id"]
    with Session(engine) as s2:
        run2 = AnalysisRun(topic_id=t2, mode=AnalysisMode.PREVIEW)
        s2.add(run2)
        s2.flush()
        ext2 = LocalExtraction(
            run_id=run2.id, topic_id=t2, chunk_id=c2, status="succeeded", attempt_count=1
        )
        s2.add(ext2)
        s2.flush()
        rel2 = json.dumps(
            {
                "local_relations": [
                    {
                        "character_a": "关羽",
                        "character_b": "刘备",
                        "relation_type": "结义",
                        "source_chunk_ids": [c2],
                        "evidence_quotes": ["兄弟"],
                        "confidence": 0.9,
                    }
                ]
            }
        )
        normalize_local_extraction(ext2.id, run2.id, t2, c2, rel2, s2)
        s2.commit()
        from sqlmodel import select

        a1 = s2.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        a2 = s2.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run2.id)).all()
        assert a1[0].stable_id == a2[0].stable_id
    client.delete(f"/api/topics/{topic_id}")
    client.delete(f"/api/topics/{t2}")


def test_causal_link_stable_id(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    data = json.dumps(
        {
            "local_causal_links": [
                {
                    "cause_event": "赤壁之战",
                    "effect_event": "曹操败退",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["败退"],
                    "confidence": 0.85,
                }
            ]
        }
    )
    from sqlmodel import select

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, data, session)
        session.commit()
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        assert atoms[0].stable_id.startswith("caus_")
    client.delete(f"/api/topics/{topic_id}")


def test_causal_link_asymmetric(client, engine):
    """e1→e2 and e2→e1 produce DIFFERENT IDs."""
    tid = _setup(client, engine)[0]

    def _make_ext(session, run, cause, effect):
        d = json.dumps(
            {
                "local_causal_links": [
                    {
                        "cause_event": cause,
                        "effect_event": effect,
                        "source_chunk_ids": [cid],
                        "evidence_quotes": ["x"],
                        "confidence": 0.8,
                    }
                ]
            }
        )
        return normalize_local_extraction(
            None,
            run.id,
            tid,
            cid,
            d,
            session,  # type: ignore[arg-type]
        )

    with Session(engine) as s:
        r1 = AnalysisRun(topic_id=tid, mode=AnalysisMode.PREVIEW)
        s.add(r1)
        s.flush()
        cid_val = client.get(f"/api/topics/{tid}/chunks?limit=1").json()["chunks"]
        cid = cid_val[0]["id"]
        e1 = LocalExtraction(
            run_id=r1.id,
            topic_id=tid,
            chunk_id=cid,
            status="succeeded",
            attempt_count=1,
        )
        s.add(e1)
        s.flush()
        d1 = json.dumps(
            {
                "local_causal_links": [
                    {
                        "cause_event": "A",
                        "effect_event": "B",
                        "source_chunk_ids": [cid],
                        "evidence_quotes": ["x"],
                        "confidence": 0.8,
                    }
                ]
            }
        )
        normalize_local_extraction(e1.id, r1.id, tid, cid, d1, s)
        s.commit()
        from sqlmodel import select

        a1 = s.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == r1.id)).first()

    with Session(engine) as s:
        r2 = AnalysisRun(topic_id=tid, mode=AnalysisMode.PREVIEW)
        s.add(r2)
        s.flush()
        e2 = LocalExtraction(
            run_id=r2.id,
            topic_id=tid,
            chunk_id=cid,
            status="succeeded",
            attempt_count=1,
        )
        s.add(e2)
        s.flush()
        d2 = json.dumps(
            {
                "local_causal_links": [
                    {
                        "cause_event": "B",
                        "effect_event": "A",
                        "source_chunk_ids": [cid],
                        "evidence_quotes": ["x"],
                        "confidence": 0.8,
                    }
                ]
            }
        )
        normalize_local_extraction(e2.id, r2.id, tid, cid, d2, s)
        s.commit()
        a2 = s.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == r2.id)).first()
        assert a1.stable_id != a2.stable_id
    client.delete(f"/api/topics/{tid}")


def test_top_level_list_merged(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    data = json.dumps(
        [
            {
                "local_characters": [
                    {
                        "character_id_hint": "a",
                        "name": "A",
                        "source_chunk_ids": [chunk_id],
                        "evidence_quotes": ["ok"],
                        "confidence": 0.8,
                    }
                ]
            },
            {
                "local_characters": [
                    {
                        "character_id_hint": "b",
                        "name": "B",
                        "source_chunk_ids": [chunk_id],
                        "evidence_quotes": ["ok"],
                        "confidence": 0.8,
                    }
                ]
            },
        ]
    )
    with Session(engine) as session:
        result = normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, data, session)
        session.commit()
        assert result.created_count == 2
    client.delete(f"/api/topics/{topic_id}")


def test_bad_json_returns_warnings(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    with Session(engine) as session:
        result = normalize_local_extraction(
            ext_id, run_id, topic_id, chunk_id, "not json{{{", session
        )
        assert result.created_count == 0
        assert len(result.warnings) > 0
    client.delete(f"/api/topics/{topic_id}")


def test_confidence_clamping(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    data = json.dumps(
        {
            "local_characters": [
                {
                    "character_id_hint": "high",
                    "name": "H",
                    "confidence": 999.0,
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["test"],
                },
                {
                    "character_id_hint": "neg",
                    "name": "N",
                    "confidence": -5.0,
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["test"],
                },
            ]
        }
    )
    from sqlmodel import select

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, data, session)
        session.commit()
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        for a in atoms:
            assert 0.0 <= a.confidence <= 1.0
    client.delete(f"/api/topics/{topic_id}")


def test_chunk_index_string_coerced(client, engine):
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    data = json.dumps(
        {
            "local_characters": [
                {
                    "character_id_hint": "x",
                    "name": "X",
                    "chunk_index": "5",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["ok"],
                    "confidence": 0.8,
                }
            ]
        }
    )
    from sqlmodel import select

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, data, session)
        session.commit()
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        assert atoms[0].chunk_index == 5
    client.delete(f"/api/topics/{topic_id}")


# ── P1-2: Field name compatibility tests ──


def test_relation_hint_fallback(client, engine):
    """Relation with prompt field names (character_a_hint, character_b_hint, interaction_type)."""
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    data = json.dumps(
        {
            "local_relations": [
                {
                    "character_a_hint": "lady",
                    "character_b_hint": "knight",
                    "interaction_type": "rivalry",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["they fought"],
                    "confidence": 0.9,
                }
            ]
        }
    )
    from sqlmodel import select

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, data, session)
        session.commit()
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        assert len(atoms) == 1
        assert atoms[0].stable_id.startswith("rel_")
        assert "lady" in atoms[0].stable_id or "knight" in atoms[0].stable_id
    client.delete(f"/api/topics/{topic_id}")


def test_causal_link_hint_fallback(client, engine):
    """Causal link with prompt field names (cause_hint, effect_hint)."""
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    data = json.dumps(
        {
            "local_causal_links": [
                {
                    "cause_hint": "sword_drawn",
                    "effect_hint": "battle_begins",
                    "link_description": "sword drawn starts battle",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["drew sword"],
                    "confidence": 0.85,
                }
            ]
        }
    )
    from sqlmodel import select

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, data, session)
        session.commit()
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        assert len(atoms) == 1
        assert atoms[0].stable_id.startswith("caus_")
    client.delete(f"/api/topics/{topic_id}")


def test_theme_signal_label_fallback(client, engine):
    """Theme signal with prompt field name (signal_label)."""
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    data = json.dumps(
        {
            "local_theme_signals": [
                {
                    "signal_label": "loneliness",
                    "signal_description": "character is alone",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["alone in the crowd"],
                    "confidence": 0.85,
                }
            ]
        }
    )
    from sqlmodel import select

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, data, session)
        session.commit()
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        assert len(atoms) == 1
        assert atoms[0].canonical_name == "loneliness"
    client.delete(f"/api/topics/{topic_id}")


def test_open_question_fallback(client, engine):
    """Open question with prompt field name (question)."""
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    data = json.dumps(
        {
            "local_open_questions": [
                {
                    "question": "Who is the shadowy figure?",
                    "question_type": "mystery",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["a figure in the dark"],
                    "confidence": 0.5,
                }
            ]
        }
    )
    from sqlmodel import select

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, data, session)
        session.commit()
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        assert len(atoms) == 1
        # Title should be extracted from "question" field
        assert atoms[0].title is not None
    client.delete(f"/api/topics/{topic_id}")


def test_different_relations_produce_different_stable_ids(client, engine):
    """Two different relations should not degenerate to same stable_id."""
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    data = json.dumps(
        {
            "local_relations": [
                {
                    "character_a": "刘备",
                    "character_b": "关羽",
                    "relation_type": "结义",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["兄弟"],
                    "confidence": 0.9,
                },
                {
                    "character_a": "关羽",
                    "character_b": "张飞",
                    "relation_type": "结义",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["兄弟"],
                    "confidence": 0.9,
                },
            ]
        }
    )
    from sqlmodel import select

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, data, session)
        session.commit()
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        assert len(atoms) == 2
        assert atoms[0].stable_id != atoms[1].stable_id
    client.delete(f"/api/topics/{topic_id}")


def test_different_causal_links_produce_different_stable_ids(client, engine):
    """Two different causal links should not degenerate to same stable_id."""
    topic_id, run_id, ext_id, chunk_id = _setup(client, engine)
    data = json.dumps(
        {
            "local_causal_links": [
                {
                    "cause_event": "赤壁之战",
                    "effect_event": "曹操败退",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["败退"],
                    "confidence": 0.85,
                },
                {
                    "cause_event": "官渡之战",
                    "effect_event": "袁绍败退",
                    "source_chunk_ids": [chunk_id],
                    "evidence_quotes": ["袁绍败退"],
                    "confidence": 0.85,
                },
            ]
        }
    )
    from sqlmodel import select

    with Session(engine) as session:
        normalize_local_extraction(ext_id, run_id, topic_id, chunk_id, data, session)
        session.commit()
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == run_id)).all()
        assert len(atoms) == 2
        assert atoms[0].stable_id != atoms[1].stable_id
    client.delete(f"/api/topics/{topic_id}")

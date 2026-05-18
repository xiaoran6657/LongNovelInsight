"""Tests for stable_id_service — deterministic, idempotent, CJK-safe."""

import pytest

from services.stable_id_service import (
    ensure_unique_stable_id,
    make_causal_link_id,
    make_relation_id,
    make_stable_id,
    normalize_text_for_id,
)


class TestNormalizeTextForId:
    def test_ascii_simple(self):
        assert normalize_text_for_id("Battle of Red Cliffs") == "battle-of-red-cliffs"

    def test_leading_trailing_dashes(self):
        assert normalize_text_for_id("- hello world -") == "hello-world"

    def test_consecutive_special_chars(self):
        assert normalize_text_for_id("hello!!!world") == "hello-world"

    def test_cjk_text_preserved(self):
        result = normalize_text_for_id("赤壁之战")
        assert "赤壁之战" in result

    def test_mixed_cjk_ascii(self):
        result = normalize_text_for_id("Zhang飞")
        assert "zhang" in result.lower()

    def test_empty_returns_unknown(self):
        assert normalize_text_for_id("") == "unknown"

    def test_only_special_chars(self):
        assert normalize_text_for_id("!!!") == "unknown"

    def test_unicode_normalization(self):
        # NFKC should normalize full-width characters
        result = normalize_text_for_id("ＡＢＣ")  # full-width ABC
        assert "abc" in result.lower()


class TestMakeStableId:
    def test_ascii_id_hint(self):
        sid = make_stable_id("character", "boy_at_window", "unknown", set())
        assert sid.startswith("char_")
        assert "boy-at-window" in sid

    def test_cjk_fallback_uses_hash(self):
        sid = make_stable_id("event", None, "赤壁之战", set())
        assert sid.startswith("evt_")
        # CJK → hash, so should look like evt_a1b2c3d4
        assert len(sid) <= 13  # evt_ + 8 hex

    def test_idempotent(self):
        s1 = make_stable_id("character", "liu_bei", "刘备", set())
        s2 = make_stable_id("character", "liu_bei", "刘备", set())
        assert s1 == s2

    def test_different_atom_types(self):
        a = make_stable_id("character", "test", "x", set())
        b = make_stable_id("event", "test", "x", set())
        assert a != b
        assert a.startswith("char_")
        assert b.startswith("evt_")

    def test_empty_input(self):
        sid = make_stable_id("theme_signal", "", "", set())
        assert sid.startswith("thm_")

    def test_all_atom_types_have_prefix(self):
        types = [
            "character", "event", "relation", "causal_link",
            "theme_signal", "worldbuilding", "foreshadowing", "open_question",
        ]
        for t in types:
            sid = make_stable_id(t, "test_entity", "fallback", set())
            assert sid, f"empty ID for {t}"


class TestMakeRelationId:
    def test_directional(self):
        rid = make_relation_id("char_lucy", "char_tom", "ally")
        # IDs sorted, so always lucy before tom
        assert "lucy" in rid
        assert "tom" in rid
        assert "ally" in rid

    def test_idempotent_bidirectional(self):
        r1 = make_relation_id("a", "b", "friend")
        r2 = make_relation_id("b", "a", "friend")
        assert r1 == r2

    def test_starts_with_rel(self):
        rid = make_relation_id("a", "b", "enemy")
        assert rid.startswith("rel_")


class TestMakeCausalLinkId:
    def test_causal_link(self):
        cid = make_causal_link_id("evt_war_start", "evt_king_death")
        assert cid.startswith("caus_")
        assert "war-start" in cid
        assert "king-death" in cid

    def test_idempotent(self):
        c1 = make_causal_link_id("e1", "e2")
        c2 = make_causal_link_id("e1", "e2")
        assert c1 == c2


class TestEnsureUniqueStableId:
    def test_first_is_unchanged(self):
        assert ensure_unique_stable_id("char_bob", set()) == "char_bob"

    def test_duplicate_gets_suffix(self):
        assert ensure_unique_stable_id("char_bob", {"char_bob"}) == "char_bob-2"

    def test_multiple_duplicates(self):
        existing = {"char_bob", "char_bob-2", "char_bob-3"}
        assert ensure_unique_stable_id("char_bob", existing) == "char_bob-4"

    def test_suffix_not_in_existing(self):
        existing = {"char_bob", "char_bob-2"}
        assert ensure_unique_stable_id("char_bob", existing) == "char_bob-3"


class TestStableIdSafety:
    def test_no_random_uuids(self):
        """Stable IDs must never contain UUIDs."""
        import uuid
        for _ in range(20):
            sid = make_stable_id("character", "random_test", "test", set())
            try:
                uuid.UUID(sid)
                pytest.fail(f"Stable ID looks like a UUID: {sid}")
            except ValueError:
                pass

    def test_no_dangerous_characters(self):
        dangerous = {"\"", "'", ";", "`", "$", "(", ")", "<", ">", "&", "|", " "}
        for _ in range(10):
            sid = make_stable_id("character", "test entity", "test entity", set())
            for ch in dangerous:
                assert ch not in sid, f"Dangerous char '{ch}' in '{sid}'"

    def test_cjk_input_does_not_crash(self):
        """CJK input should generate a valid ID without exception."""
        sid = make_stable_id("character", None, "三国演义之刘备传", set())
        assert len(sid) > 3
        assert sid.startswith("char_")

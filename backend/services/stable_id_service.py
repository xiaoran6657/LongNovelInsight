"""Stable ID generation for v0.2 analysis entities.

All IDs are deterministic: same input → same output. No random UUIDs.
CJK input is handled via prefix + hash; no external dependencies required.
"""

import hashlib
import re
import unicodedata


def normalize_text_for_id(text: str) -> str:
    """Normalize arbitrary text into a safe, lowercase slug fragment."""
    # NFKC normalize to collapse compatibility characters
    text = unicodedata.normalize("NFKC", text)
    # Replace non-alphanumeric with hyphens
    slug = re.sub(r"[^a-zA-Z0-9一-鿿]", "-", text)
    # Collapse consecutive hyphens
    slug = re.sub(r"-{2,}", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    if not slug:
        return "unknown"
    return slug.lower()


def _is_cjk(s: str) -> bool:
    """Return True if the string contains any CJK character."""
    return any("一" <= c <= "鿿" or "㐀" <= c <= "䶿" for c in s)


def _type_prefix(atom_type: str) -> str:
    """Short prefix per atom type for readable IDs."""
    prefixes: dict[str, str] = {
        "character": "char",
        "event": "evt",
        "relation": "rel",
        "causal_link": "caus",
        "theme_signal": "thm",
        "worldbuilding": "wb",
        "foreshadowing": "fsh",
        "open_question": "oq",
    }
    return prefixes.get(atom_type, "atom")


def make_stable_id(
    atom_type: str,
    id_hint: str | None,
    fallback_text: str,
    existing_ids: set[str],
) -> str:
    """Generate a deterministic stable ID for an atom.

    Priority: id_hint > fallback_text > hash of fallback.
    CJK input: prefix + short hash.
    ASCII input: slugified.
    Ensures uniqueness against existing_ids.
    """
    raw = (id_hint or "").strip() or fallback_text.strip()
    if not raw:
        raw = fallback_text.strip() or "unknown"

    prefix = _type_prefix(atom_type)

    if _is_cjk(raw):
        # CJK: use prefix + 8-char hash
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
        base = f"{prefix}_{h}"
    else:
        slug = normalize_text_for_id(raw)
        if len(slug) > 40:
            slug = slug[:40].rstrip("-")
        base = f"{prefix}_{slug}" if slug else f"{prefix}_unknown"

    base = base.lower()
    return ensure_unique_stable_id(base, existing_ids)


def make_relation_id(
    character_a_id: str,
    character_b_id: str,
    relation_type: str,
) -> str:
    """Generate a stable relation ID from two character IDs and relation type.

    Character IDs are sorted to normalize direction for bidirectional relations.
    """
    parts = sorted([character_a_id, character_b_id])
    raw = f"{parts[0]}_{parts[1]}_{relation_type}"
    slug = normalize_text_for_id(raw)
    return f"rel_{slug}"


def make_causal_link_id(
    cause_event_id: str,
    effect_event_id: str,
) -> str:
    """Generate a causal link ID from two event IDs."""
    raw = f"{cause_event_id}_to_{effect_event_id}"
    slug = normalize_text_for_id(raw)
    return f"caus_{slug}"


def ensure_unique_stable_id(base_id: str, existing_ids: set[str]) -> str:
    """If base_id is already taken, append a numeric suffix.

    Returns base_id unchanged if unique, or base_id-2, base_id-3, etc.
    """
    if base_id not in existing_ids:
        return base_id
    n = 2
    while f"{base_id}-{n}" in existing_ids:
        n += 1
    return f"{base_id}-{n}"

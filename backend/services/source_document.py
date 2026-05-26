"""Internal types for unified TXT/EPUB source document representation.

These are plain dataclasses, not DB models. v0.3 Step 3 uses them for
the EPUB parser output; Step 4 unifies TXT and EPUB into the same shapes
before Chapter/Chunk DB row creation.
"""

from dataclasses import dataclass, field


@dataclass
class SourceChapter:
    title: str
    text: str
    chapter_index: int
    source_href: str | None = None
    nav_order: int | None = None
    metadata: dict[str, str | None] | None = None


@dataclass
class SourceDocument:
    document_id: str
    topic_id: str
    file_type: str
    original_filename: str
    storage_path: str
    metadata: dict[str, object]
    chapters: list[SourceChapter] = field(default_factory=list)

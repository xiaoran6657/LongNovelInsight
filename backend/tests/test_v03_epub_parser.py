"""v0.3 Step 3 — EPUB Parser Core tests."""

import zipfile
from pathlib import Path

import pytest

OPF_WRAPPER = """<?xml version="1.0"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{creator}</dc:creator>
    <dc:language>{language}</dc:language>
    <dc:publisher>{publisher}</dc:publisher>
    <dc:identifier id="book-id">{identifier}</dc:identifier>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    {manifest_items}
  </manifest>
  <spine>
    {spine_items}
  </spine>
</package>
"""

CONTAINER_XML = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def _make_epub(
    tmp_path: Path,
    chapters: list[tuple[str, str]] | None = None,
    *,
    title: str = "Test Book",
    creator: str = "Test Author",
    language: str = "en",
    publisher: str = "Test Publisher",
    identifier: str = "urn:uuid:test-1234",
    include_opf: bool = True,
    include_container: bool = True,
) -> Path:
    """Build a minimal EPUB file on disk. Returns the path."""
    if chapters is None:
        chapters = [("Chapter 1", "<h1>Chapter 1</h1><p>Hello world.</p>")]

    epub_path = tmp_path / "test.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        if include_container:
            zf.writestr("META-INF/container.xml", CONTAINER_XML)
        if include_opf:
            manifest_items_xml = "\n    ".join(
                f'<item id="ch{i}" href="{href}" media-type="application/xhtml+xml"/>'
                for i, (href, _) in enumerate(chapters)
            )
            spine_items_xml = "\n    ".join(
                f'<itemref idref="ch{i}"/>' for i in range(len(chapters))
            )
            opf = OPF_WRAPPER.format(
                title=title,
                creator=creator,
                language=language,
                publisher=publisher,
                identifier=identifier,
                manifest_items=manifest_items_xml,
                spine_items=spine_items_xml,
            )
            zf.writestr("content.opf", opf)
        for href, body in chapters:
            zf.writestr(href, f"<html><body>{body}</body></html>")
    return epub_path


# ── Tests ──


class TestEPUBParserBasic:
    def test_parse_single_chapter(self, tmp_path):
        epub_path = _make_epub(tmp_path, [("ch01.xhtml", "<h1>Chapter 1</h1><p>Hello world.</p>")])

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "test.epub")

        assert doc.file_type == "epub"
        assert doc.topic_id == "t1"
        assert doc.document_id == "d1"
        assert len(doc.chapters) == 1
        ch = doc.chapters[0]
        assert ch.title == "Chapter 1"
        assert "Hello world" in ch.text
        assert ch.chapter_index == 0
        assert ch.source_href == "ch01.xhtml"
        assert ch.nav_order == 0

    def test_extracts_opf_metadata(self, tmp_path):
        epub_path = _make_epub(
            tmp_path,
            title="My Novel",
            creator="Jane Doe",
            language="zh-CN",
            publisher="Test Press",
            identifier="urn:isbn:1234567890",
        )

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "book.epub")

        assert doc.metadata["title"] == "My Novel"
        assert doc.metadata["creator"] == "Jane Doe"
        assert doc.metadata["language"] == "zh-CN"
        assert doc.metadata["publisher"] == "Test Press"
        assert doc.metadata["identifier"] == "urn:isbn:1234567890"

    def test_parses_multiple_chapters_in_spine_order(self, tmp_path):
        chapters = [
            ("ch01.xhtml", "<h1>First</h1><p>Content one.</p>"),
            ("ch02.xhtml", "<h1>Second</h1><p>Content two.</p>"),
            ("ch03.xhtml", "<h1>Third</h1><p>Content three.</p>"),
        ]
        epub_path = _make_epub(tmp_path, chapters)

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "book.epub")
        assert len(doc.chapters) == 3

        titles = [ch.title for ch in doc.chapters]
        assert titles == ["First", "Second", "Third"]

        for i, ch in enumerate(doc.chapters):
            assert ch.chapter_index == i
            assert ch.nav_order == i


class TestXHTMLCleaning:
    def test_removes_script_tags(self, tmp_path):
        epub_path = _make_epub(
            tmp_path,
            [("ch01.xhtml", "<h1>Title</h1><script>alert('xss')</script><p>Safe text.</p>")],
        )

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "book.epub")
        text = doc.chapters[0].text
        assert "Safe text" in text
        assert "alert" not in text
        assert "script" not in text.lower()

    def test_removes_style_tags(self, tmp_path):
        epub_path = _make_epub(
            tmp_path,
            [("ch01.xhtml", "<h1>Title</h1><style>p { color: red; }</style><p>Visible.</p>")],
        )

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "book.epub")
        text = doc.chapters[0].text
        assert "Visible" in text
        assert "color" not in text

    def test_removes_nav_elements(self, tmp_path):
        epub_path = _make_epub(
            tmp_path,
            [("ch01.xhtml", "<nav><a href='ch02.xhtml'>Next</a></nav><p>Main text.</p>")],
        )

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "book.epub")
        text = doc.chapters[0].text
        assert "Main text" in text
        assert "Next" not in text

    def test_normalizes_whitespace(self, tmp_path):
        epub_path = _make_epub(
            tmp_path,
            [("ch01.xhtml", "<p>Line one.</p>\n\n\n<p>Line two.</p>")],
        )

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "book.epub")
        text = doc.chapters[0].text
        # Should not have 3+ consecutive newlines
        assert "\n\n\n" not in text
        assert "Line one" in text
        assert "Line two" in text


class TestErrorHandling:
    def test_missing_container_raises(self, tmp_path):
        epub_path = _make_epub(tmp_path, include_container=False)

        from services.epub_parser_service import parse_epub

        with pytest.raises(ValueError, match="container"):
            parse_epub(epub_path, "t1", "d1", "book.epub")

    def test_missing_opf_raises(self, tmp_path):
        epub_path = _make_epub(tmp_path, include_opf=False)

        from services.epub_parser_service import parse_epub

        with pytest.raises(ValueError, match="OPF file not found"):
            parse_epub(epub_path, "t1", "d1", "book.epub")

    def test_missing_title_produces_warning(self, tmp_path):
        epub_path = _make_epub(tmp_path, title="")

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "book.epub")
        warnings = doc.metadata["parsing_warnings"]
        assert any("title" in w.lower() for w in warnings)

    def test_empty_chapter_produces_warning(self, tmp_path):
        """A spine item with only whitespace should be skipped with a warning."""
        epub_path = _make_epub(
            tmp_path,
            [
                ("ch01.xhtml", "<p>Real content.</p>"),
                ("ch02.xhtml", "   \n  "),
            ],
        )

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "book.epub")
        assert len(doc.chapters) == 1
        warnings = doc.metadata["parsing_warnings"]
        assert any("Empty chapter" in w for w in warnings)

    def test_spine_item_not_found_produces_warning(self, tmp_path):
        """A spine item referencing a missing file produces a warning."""
        # Create EPUB with a manifest item referencing a non-existent file
        import zipfile as zf_mod

        epub_path2 = tmp_path / "bad_spine.epub"
        with zf_mod.ZipFile(epub_path2, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr("META-INF/container.xml", CONTAINER_XML)
            opf = OPF_WRAPPER.format(
                title="Test",
                creator="A",
                language="en",
                publisher="P",
                identifier="id",
                manifest_items='<item id="ch0" href="ch01.xhtml" media-type="application/xhtml+xml"/>\n    '
                '<item id="ch1" href="missing.xhtml" media-type="application/xhtml+xml"/>',
                spine_items='<itemref idref="ch0"/>\n    <itemref idref="ch1"/>',
            )
            zf.writestr("content.opf", opf)
            zf.writestr("ch01.xhtml", "<html><body><p>Here.</p></body></html>")

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path2, "t1", "d1", "book.epub")
        assert len(doc.chapters) == 1  # only the existing file
        warnings = doc.metadata["parsing_warnings"]
        assert any("missing" in w.lower() for w in warnings)

    def test_file_not_found_raises(self, tmp_path):
        from services.epub_parser_service import parse_epub

        with pytest.raises(ValueError, match="not found"):
            parse_epub(tmp_path / "nonexistent.epub", "t1", "d1", "book.epub")

    def test_not_a_zip_raises(self, tmp_path):
        bad_path = tmp_path / "bad.epub"
        bad_path.write_text("not a zip file")

        from services.epub_parser_service import parse_epub

        with pytest.raises((ValueError, zipfile.BadZipFile)):
            parse_epub(bad_path, "t1", "d1", "book.epub")


class TestDerivedChapterTitles:
    def test_uses_h1_as_title(self, tmp_path):
        epub_path = _make_epub(tmp_path, [("ch01.xhtml", "<h1>My Title</h1><p>Text.</p>")])

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "book.epub")
        assert doc.chapters[0].title == "My Title"

    def test_uses_h2_fallback(self, tmp_path):
        epub_path = _make_epub(tmp_path, [("ch01.xhtml", "<h2>Second Level</h2><p>Text.</p>")])

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "book.epub")
        assert doc.chapters[0].title == "Second Level"

    def test_fallback_to_chapter_n(self, tmp_path):
        epub_path = _make_epub(tmp_path, [("ch01.xhtml", "<p>No heading here.</p>")])

        from services.epub_parser_service import parse_epub

        doc = parse_epub(epub_path, "t1", "d1", "book.epub")
        assert doc.chapters[0].title == "Chapter 1"

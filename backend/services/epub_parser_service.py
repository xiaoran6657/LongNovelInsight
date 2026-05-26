"""v0.3 EPUB parser — extracts plain text and metadata from EPUB files.

Uses Python stdlib (zipfile + xml.etree.ElementTree) for container/OPF
parsing and beautifulsoup4 for XHTML-to-text extraction.

No network access. No JS execution. No CSS rendering. No DB writes.
"""

import logging
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup, NavigableString, Tag

from services.source_document import SourceChapter, SourceDocument

logger = logging.getLogger(__name__)

# XML namespaces commonly found in EPUB OPF files
NSMAP = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "xhtml": "http://www.w3.org/1999/xhtml",
}

# Block-level HTML elements that should produce paragraph breaks
BLOCK_TAGS = {
    "p",
    "div",
    "section",
    "article",
    "aside",
    "blockquote",
    "pre",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "dd",
    "dt",
    "figcaption",
    "figure",
    "hr",
    "br",
    "table",
    "tr",
}


def _ns(tag: str, prefix: str = "opf") -> str:
    """Return a namespace-qualified tag for ElementTree."""
    return f"{{{NSMAP[prefix]}}}{tag}"


def parse_epub(
    source_path: Path, topic_id: str, document_id: str, original_filename: str
) -> SourceDocument:
    """Parse an EPUB file from disk into a SourceDocument.

    Returns:
        SourceDocument with metadata and chapters.

    Raises:
        ValueError: If the EPUB structure is invalid (container, OPF, spine),
                    malformed XML, or not a valid zip.
    """
    warnings: list[str] = []
    chapters: list[SourceChapter] = []

    if not source_path.exists():
        raise ValueError(f"EPUB file not found: {source_path}")

    try:
        zf = zipfile.ZipFile(source_path, "r")
    except zipfile.BadZipFile:
        raise ValueError("Invalid EPUB: file is not a valid zip archive")

    with zf:
        namelist = zf.namelist()

        # 1. Parse container.xml to find OPF path
        if "META-INF/container.xml" not in namelist:
            raise ValueError("Invalid EPUB: missing META-INF/container.xml")

        try:
            container_root = ET.fromstring(zf.read("META-INF/container.xml"))
        except ET.ParseError as e:
            raise ValueError(f"Invalid EPUB: malformed container.xml: {e}")

        opf_path = _find_opf_path(container_root)
        if opf_path is None:
            raise ValueError("Invalid EPUB: no rootfile entry in container.xml")
        if opf_path not in namelist:
            raise ValueError(f"Invalid EPUB: OPF file not found: {opf_path}")

        # 2. Parse OPF for metadata, manifest, spine
        try:
            opf_root = ET.fromstring(zf.read(opf_path))
        except ET.ParseError as e:
            raise ValueError(f"Invalid EPUB: malformed OPF: {e}")

        opf_dir = posixpath.dirname(opf_path)

        metadata = _parse_opf_metadata(opf_root, warnings)
        spine_hrefs, manifest_map = _parse_opf_spine(opf_root)
        if not spine_hrefs:
            raise ValueError("Invalid EPUB: no spine items found")

        # 3. Read spine items in order, extract text from XHTML
        for idx, href in enumerate(spine_hrefs):
            # Resolve OPF-relative URL to archive-internal path.
            # href is a URL path (always /), may contain ../, %xx encoding, or
            # subdirectories. Use posixpath for archive-internal resolution.
            decoded = unquote(href)
            full_path = posixpath.normpath(posixpath.join(opf_dir, decoded))
            if full_path not in namelist:
                warnings.append(f"Spine item not found: {full_path} (href={href})")
                continue

            content_bytes = zf.read(full_path)
            try:
                text = _xhtml_to_text(content_bytes)
            except Exception as e:
                warnings.append(f"Failed to extract text from {full_path}: {e}")
                continue

            if not text.strip():
                warnings.append(f"Empty chapter: {full_path}")
                continue

            title = _derive_chapter_title(zf, opf_dir, href, namelist, idx)
            chapters.append(
                SourceChapter(
                    title=title,
                    text=text,
                    chapter_index=idx,
                    source_href=full_path,
                    nav_order=idx,
                )
            )

    # Build metadata: OPF metadata + source_format + warnings
    metadata["source_format"] = "epub"
    metadata["parsing_warnings"] = warnings

    return SourceDocument(
        document_id=document_id,
        topic_id=topic_id,
        file_type="epub",
        original_filename=original_filename,
        storage_path=str(source_path),
        metadata=metadata,
        chapters=chapters,
    )


# ── container.xml ──


def _find_opf_path(container_root: ET.Element) -> str | None:
    for rootfile in container_root.iter(_ns("rootfile", "container")):
        path = rootfile.get("full-path")
        if path:
            return path
    return None


# ── OPF metadata ──


def _parse_opf_metadata(opf_root: ET.Element, warnings: list[str]) -> dict[str, Any]:
    meta: dict[str, Any] = {}

    def _first(tag: str, prefix: str = "dc") -> str | None:
        el = opf_root.find(f".//{_ns(tag, prefix)}")
        if el is not None and el.text:
            return el.text.strip()
        return None

    title = _first("title")
    if title:
        meta["title"] = title

    creator = _first("creator")
    if creator:
        meta["creator"] = creator

    language = _first("language")
    if language:
        meta["language"] = language

    publisher = _first("publisher")
    if publisher:
        meta["publisher"] = publisher

    identifier = _first("identifier")
    if identifier:
        meta["identifier"] = identifier

    creators = [el.text.strip() for el in opf_root.findall(f".//{_ns('creator')}") if el.text]
    if len(creators) > 1:
        meta["creators"] = creators

    if not title:
        warnings.append("Missing title in OPF metadata")

    return meta


def _parse_opf_spine(opf_root: ET.Element) -> tuple[list[str], dict[str, dict[str, str]]]:
    """Return (list of spine hrefs in order, manifest map of id→attrs)."""
    manifest_map: dict[str, dict[str, str]] = {}
    manifest_el = opf_root.find(_ns("manifest"))
    if manifest_el is not None:
        for item in manifest_el:
            item_id = item.get("id")
            if item_id:
                manifest_map[item_id] = {
                    "href": item.get("href", ""),
                    "media-type": item.get("media-type", ""),
                }

    spine_hrefs: list[str] = []
    spine_el = opf_root.find(_ns("spine"))
    if spine_el is not None:
        for itemref in spine_el:
            idref = itemref.get("idref")
            if idref and idref in manifest_map:
                spine_hrefs.append(manifest_map[idref]["href"])

    return spine_hrefs, manifest_map


# ── XHTML text extraction ──


def _has_block_descendant(tag: Tag) -> bool:
    """Return True if `tag` directly or indirectly contains a block-level element."""
    for child in tag.descendants:
        if isinstance(child, Tag) and child.name in BLOCK_TAGS:
            return True
    return False


def _collect_inline_pieces(element: Tag) -> list[str]:
    """Walk an element tree, collecting text pieces from inline nodes.

    Each piece is a stripped text segment. The caller is responsible for
    joining them with appropriate spacing (word-boundary-aware).
    """
    pieces: list[str] = []
    for child in element.children:
        if isinstance(child, NavigableString):
            text = child.strip()
            if text:
                pieces.append(text)
        elif isinstance(child, Tag):
            if child.name in BLOCK_TAGS:
                # Block inside inline context — treat as paragraph break
                inner = _extract_block_text(child)
                if inner:
                    pieces.append("\n" + inner + "\n")
            else:
                pieces.extend(_collect_inline_pieces(child))
    return pieces


def _join_inline_pieces(pieces: list[str]) -> str:
    """Join inline text pieces with word-boundary-aware spacing.

    Inserts a space between two pieces only when the first ends with a
    word character and the second starts with one. Otherwise joins
    directly (handling punctuation like '.', ',', ')' after inline tags).
    """
    result: list[str] = []
    for piece in pieces:
        if piece.startswith("\n") or piece.endswith("\n"):
            result.append(piece)
        elif result and _needs_space_between(result[-1], piece):
            result.append(" " + piece)
        else:
            result.append(piece)
    return "".join(result)


def _needs_space_between(prev: str, curr: str) -> bool:
    """Return True if a space is needed between two inline text pieces.

    Only inserts a space between Latin-script word characters (ASCII
    alphanumerics). CJK, punctuation, and other scripts are already
    self-delimiting and should not get injected spaces.
    """
    if not prev or not curr:
        return False
    last = prev[-1]
    first = curr[0]
    # Only space-separate ASCII alphanumeric word boundaries
    return last.isascii() and last.isalnum() and first.isascii() and first.isalnum()


def _extract_block_text(element: Tag) -> str:
    """Extract text from a block-level element.

    Inline tags (em, span, a, strong, etc.) are preserved as contiguous text
    with word-boundary-aware spacing. Nested block tags get newline separators.
    """
    pieces = _collect_inline_pieces(element)
    return _join_inline_pieces(pieces).strip()


def _xhtml_to_text(content: bytes) -> str:
    """Extract plain text from XHTML content using beautifulsoup4.

    - Removes script, style, nav, head and other non-content elements.
    - Block elements (p, div, h1-h6, etc.) are separated by newlines.
    - Inline elements (em, span, a, etc.) are kept as contiguous text.
    """
    soup = BeautifulSoup(content, "html.parser")

    # Remove non-content elements
    for tag in soup.find_all(["script", "style", "nav", "head", "meta", "link"]):
        tag.decompose()

    body = soup.find("body")
    if body is None:
        # No body — extract from root, treating top-level block tags as paragraphs
        root = soup.find("html") or soup
        blocks: list[str] = []
        for child in root.children:
            if isinstance(child, Tag) and child.name in BLOCK_TAGS:
                blocks.append(_extract_block_text(child))
            elif isinstance(child, NavigableString):
                text = child.strip()
                if text:
                    blocks.append(text)
        text = "\n\n".join(b for b in blocks if b)
        return text

    # Extract text from body, preserving block structure
    blocks: list[str] = []
    for child in body.children:
        if isinstance(child, Tag) and child.name in BLOCK_TAGS:
            blocks.append(_extract_block_text(child))
        elif isinstance(child, NavigableString):
            text = child.strip()
            if text:
                blocks.append(text)

    text = "\n\n".join(b for b in blocks if b)

    # Normalize whitespace: collapse 3+ newlines → 2
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


# ── Chapter title derivation ──


def _zip_resolve_path(opf_dir: str, href: str) -> str:
    """Resolve an OPF-relative href to an archive-internal path.

    Uses POSIX semantics (always forward-slash) since ZIP internal paths
    always use `/` regardless of host OS.
    """
    decoded = unquote(href)
    return posixpath.normpath(posixpath.join(opf_dir, decoded))


def _derive_chapter_title(
    zf: zipfile.ZipFile,
    opf_dir: str,
    href: str,
    namelist: list[str],
    index: int,
) -> str:
    """Derive a chapter title from the XHTML heading or fall back to index."""
    full = _zip_resolve_path(opf_dir, href)
    if full not in namelist:
        return f"Chapter {index + 1}"

    try:
        content = zf.read(full)
        soup = BeautifulSoup(content, "html.parser")
        for level in ("h1", "h2", "h3"):
            heading = soup.find(level)
            if heading and heading.get_text(strip=True):
                return heading.get_text(strip=True)
    except Exception:
        pass

    return f"Chapter {index + 1}"

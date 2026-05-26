"""v0.3 EPUB parser — extracts plain text and metadata from EPUB files.

Uses Python stdlib (zipfile + xml.etree.ElementTree) for container/OPF
parsing and beautifulsoup4 for XHTML-to-text extraction.

No network access. No JS execution. No CSS rendering. No DB writes.
"""

import logging
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from services.source_document import SourceChapter, SourceDocument

logger = logging.getLogger(__name__)

# XML namespaces commonly found in EPUB OPF files
NSMAP = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "xhtml": "http://www.w3.org/1999/xhtml",
}


def _ns(tag: str, prefix: str = "opf") -> str:
    """Return a namespace-qualified tag for ElementTree."""
    return f"{{{NSMAP[prefix]}}}{tag}"


def parse_epub(
    source_path: Path, topic_id: str, document_id: str, original_filename: str
) -> SourceDocument:
    """Parse an EPUB file from disk into a SourceDocument.

    Args:
        source_path: Path to the .epub file on disk.
        topic_id: Topic UUID.
        document_id: Document UUID.
        original_filename: Original uploaded filename.

    Returns:
        SourceDocument with metadata and chapters.

    Raises:
        ValueError: If the EPUB structure is invalid (missing container, OPF, or spine).
    """
    metadata: dict[str, Any] = {"source_format": "epub"}
    warnings: list[str] = []
    chapters: list[SourceChapter] = []

    if not source_path.exists():
        raise ValueError(f"EPUB file not found: {source_path}")

    with zipfile.ZipFile(source_path, "r") as zf:
        namelist = zf.namelist()

        # 1. Parse container.xml to find OPF path
        if "META-INF/container.xml" not in namelist:
            raise ValueError("Invalid EPUB: missing META-INF/container.xml")

        container_root = ET.fromstring(zf.read("META-INF/container.xml"))
        opf_path = _find_opf_path(container_root)
        if opf_path is None:
            raise ValueError("Invalid EPUB: no rootfile entry in container.xml")
        if opf_path not in namelist:
            raise ValueError(f"Invalid EPUB: OPF file not found: {opf_path}")

        # 2. Parse OPF for metadata, manifest, spine
        opf_root = ET.fromstring(zf.read(opf_path))
        opf_dir = Path(opf_path).parent

        metadata = _parse_opf_metadata(opf_root, warnings)
        spine_hrefs, manifest_map = _parse_opf_spine(opf_root)
        if not spine_hrefs:
            raise ValueError("Invalid EPUB: no spine items found")

        # 3. Read spine items in order, extract text from XHTML
        for idx, href in enumerate(spine_hrefs):
            full_path = str(opf_dir / href) if opf_dir != Path(".") else href
            if full_path not in namelist:
                warnings.append(f"Spine item not found: {full_path}")
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

    # Collect multiple creators
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


def _xhtml_to_text(content: bytes) -> str:
    """Extract plain text from XHTML content using beautifulsoup4.

    Removes script, style, nav, and other non-content elements.
    Preserves paragraph breaks.
    """
    soup = BeautifulSoup(content, "html.parser")

    # Remove non-content elements
    for tag in soup.find_all(["script", "style", "nav", "head", "meta", "link"]):
        tag.decompose()

    # Get text with separator for block elements
    text = soup.get_text(separator="\n", strip=True)

    # Normalize whitespace: collapse 3+ newlines → 2, strip trailing spaces per line
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


def _derive_chapter_title(
    zf: zipfile.ZipFile,
    opf_dir: Path,
    href: str,
    namelist: list[str],
    index: int,
) -> str:
    """Derive a chapter title from the XHTML heading or fall back to index."""
    full = str(opf_dir / href) if opf_dir != Path(".") else href
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

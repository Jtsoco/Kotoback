from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.test import SimpleTestCase

from book.nlp.extract import extract_epub_metadata


def _container_xml(rootfile_path: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<container
    version="1.0"
    xmlns="urn:oasis:names:tc:opendocument:xmlns:container"
>
  <rootfiles>
        <rootfile
            full-path="{rootfile_path}"
            media-type="application/oebps-package+xml"
        />
  </rootfiles>
</container>
'''


def _package_opf(
    manifest_items: list[tuple[str, str]],
    spine_ids: list[str],
    title: str = "Test",
    identifier: str = "urn:uuid:test",
    creators: list[str] | None = None,
) -> str:
    manifest_xml = "\n".join(
        (
            f'    <item id="{item_id}" href="{href}" '
            'media-type="application/xhtml+xml"/>'
        )
        for item_id, href in manifest_items
    )
    spine_xml = "\n".join(
        f'    <itemref idref="{item_id}"/>' for item_id in spine_ids
    )

    creators_xml = ""
    if creators:
        creators_xml = "\n".join(
            f"    <dc:creator>{creator}</dc:creator>" for creator in creators
        )
        creators_xml = "\n" + creators_xml

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<package
    xmlns="http://www.idpf.org/2007/opf"
    version="3.0"
    unique-identifier="bookid"
>
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{identifier}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:language>en</dc:language>{creators_xml}
  </metadata>
  <manifest>
{manifest_xml}
  </manifest>
  <spine>
{spine_xml}
  </spine>
</package>
'''


def _write_test_epub(
    epub_path: Path,
    *,
    rootfile_path: str,
    manifest_items: list[tuple[str, str]],
    spine_ids: list[str],
    title: str = "Test",
    identifier: str = "urn:uuid:test",
    creators: list[str] | None = None,
    extra_files: dict[str, str] | None = None,
) -> None:
    with ZipFile(epub_path, "w") as zf:
        zf.writestr("META-INF/container.xml", _container_xml(rootfile_path))
        zf.writestr(
            rootfile_path,
            _package_opf(
                manifest_items,
                spine_ids,
                title=title,
                identifier=identifier,
                creators=creators,
            ),
        )
        if extra_files:
            for archive_path, content in extra_files.items():
                zf.writestr(archive_path, content)


class ExtractMetadataTests(SimpleTestCase):
    """Test EPUB metadata extraction: title, authors, identifier parsing."""

    def test_extract_epub_metadata_with_single_author(self):
        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "single-author.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="content.opf",
                manifest_items=[("c1", "chapter1.xhtml")],
                spine_ids=["c1"],
                title="The Great Gatsby",
                identifier="isbn:9780743273565",
                creators=["F. Scott Fitzgerald"],
            )

            metadata = extract_epub_metadata(epub_path, "content.opf")

            self.assertEqual(metadata["title"], "The Great Gatsby")
            self.assertEqual(metadata["identifier"], "isbn:9780743273565")
            self.assertEqual(metadata["authors"], ["F. Scott Fitzgerald"])

    def test_extract_epub_metadata_with_multiple_authors(self):
        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "multi-author.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="OEBPS/content.opf",
                manifest_items=[("c1", "Text/ch1.xhtml")],
                spine_ids=["c1"],
                title="Good Omens",
                identifier="urn:uuid:12345",
                creators=["Neil Gaiman", "Terry Pratchett"],
            )

            metadata = extract_epub_metadata(epub_path, "OEBPS/content.opf")

            self.assertEqual(metadata["title"], "Good Omens")
            self.assertEqual(metadata["identifier"], "urn:uuid:12345")
            self.assertEqual(
                metadata["authors"],
                ["Neil Gaiman", "Terry Pratchett"],
            )

    def test_extract_epub_metadata_with_three_authors(self):
        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "three-authors.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="EPUB/package.opf",
                manifest_items=[("c1", "xhtml/ch1.xhtml")],
                spine_ids=["c1"],
                title="Collaborative Work",
                identifier="urn:isbn:9998887776",
                creators=["Author One", "Author Two", "Author Three"],
            )

            metadata = extract_epub_metadata(epub_path, "EPUB/package.opf")

            self.assertEqual(metadata["title"], "Collaborative Work")
            self.assertEqual(metadata["identifier"], "urn:isbn:9998887776")
            self.assertEqual(
                metadata["authors"],
                ["Author One", "Author Two", "Author Three"],
            )

    def test_extract_epub_metadata_no_authors(self):
        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "no-authors.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="content.opf",
                manifest_items=[("c1", "ch1.xhtml")],
                spine_ids=["c1"],
                title="Anonymous Work",
                identifier="unknown-id",
                creators=None,
            )

            metadata = extract_epub_metadata(epub_path, "content.opf")

            self.assertEqual(metadata["title"], "Anonymous Work")
            self.assertEqual(metadata["identifier"], "unknown-id")
            self.assertEqual(metadata["authors"], [])

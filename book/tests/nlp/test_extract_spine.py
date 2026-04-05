from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.test import SimpleTestCase

from book.nlp.extract import (
    _extract_chapter_text_from_zip,
    _get_rootfile_path_from_zip,
    _get_spine_content_paths_from_zip,
    extract_chapter_text,
    get_rootfile_path_from_epub,
    get_spine_content_paths,
)


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


class ExtractSpineTests(SimpleTestCase):
    """Test EPUB spine extraction: rootfile resolution, path ordering, text extraction."""

    def test_get_rootfile_path_from_epub_top_level_opf(self):
        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "top-level.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="content.opf",
                manifest_items=[("c1", "chapter1.xhtml")],
                spine_ids=["c1"],
            )

            rootfile_path = get_rootfile_path_from_epub(epub_path)

            self.assertEqual(rootfile_path, "content.opf")

    def test_get_rootfile_path_from_epub_nested_opf(self):
        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "nested.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="OEBPS/content.opf",
                manifest_items=[("c1", "Text/chapter1.xhtml")],
                spine_ids=["c1"],
            )

            rootfile_path = get_rootfile_path_from_epub(epub_path)

            self.assertEqual(rootfile_path, "OEBPS/content.opf")

    def test__get_spine_content_paths_from_zip_returns_ordered_paths(self):
        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "spine.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="OPS/package.opf",
                manifest_items=[
                    ("c1", "Text/chapter1.xhtml"),
                    ("c2", "Text/chapter2.xhtml"),
                    ("c3", "Text/chapter3.xhtml"),
                ],
                spine_ids=["c2", "c1", "c3"],
            )

            with ZipFile(epub_path) as zf:
                spine_paths = _get_spine_content_paths_from_zip(
                    zf,
                    "OPS/package.opf",
                )

            self.assertEqual(
                spine_paths,
                [
                    "OPS/Text/chapter2.xhtml",
                    "OPS/Text/chapter1.xhtml",
                    "OPS/Text/chapter3.xhtml",
                ],
            )

    def test_combined_public_functions_retrieve_spine_top_level_opf(self):
        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "combined-top.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="content.opf",
                manifest_items=[
                    ("a", "chapter-a.xhtml"),
                    ("b", "chapter-b.xhtml"),
                ],
                spine_ids=["a", "b"],
            )

            rootfile_path = get_rootfile_path_from_epub(epub_path)
            spine_paths = get_spine_content_paths(epub_path, rootfile_path)

            self.assertEqual(rootfile_path, "content.opf")
            self.assertEqual(
                spine_paths,
                ["chapter-a.xhtml", "chapter-b.xhtml"],
            )

    def test_combined_public_functions_retrieve_spine_nested_opf(self):
        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "combined-nested.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="EPUB/Great_Expectations.opf",
                manifest_items=[
                    ("i1", "xhtml/intro.xhtml"),
                    ("i2", "xhtml/ch1.xhtml"),
                ],
                spine_ids=["i2", "i1"],
            )

            rootfile_path = get_rootfile_path_from_epub(epub_path)
            spine_paths = get_spine_content_paths(epub_path, rootfile_path)

            self.assertEqual(rootfile_path, "EPUB/Great_Expectations.opf")
            self.assertEqual(
                spine_paths,
                ["EPUB/xhtml/ch1.xhtml", "EPUB/xhtml/intro.xhtml"],
            )

    def test__get_rootfile_path_from_zip_matches_public_rootfile_result(self):
        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "helpers.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="OPS/content.opf",
                manifest_items=[("c1", "Text/ch1.xhtml")],
                spine_ids=["c1"],
            )

            with ZipFile(epub_path) as zf:
                helper_result = _get_rootfile_path_from_zip(zf)
            public_result = get_rootfile_path_from_epub(epub_path)

            self.assertEqual(helper_result, public_result)

    def test__extract_chapter_text_from_zip_returns_bulk_visible_text(self):
        chapter_html = """
        <html>
          <head>
            <title>Hidden title</title>
            <style>.x { color: red; }</style>
          </head>
          <body>
            <h1>Chapter One</h1>
            <p>Hello <b>world</b>.</p>
            <script>console.log('ignore me')</script>
          </body>
        </html>
        """

        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "chapter-helper.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="OPS/content.opf",
                manifest_items=[("c1", "Text/ch1.xhtml")],
                spine_ids=["c1"],
                extra_files={"OPS/Text/ch1.xhtml": chapter_html},
            )

            with ZipFile(epub_path) as zf:
                text = _extract_chapter_text_from_zip(zf, "OPS/Text/ch1.xhtml")

            self.assertEqual(text, "Chapter One Hello world .")

    def test_extract_chapter_text_reads_by_spine_member_path(self):
        chapter_html = """
        <html>
          <head>
            <style>p { display: block; }</style>
          </head>
          <body>
            <h2>Nested Chapter</h2>
            <p>Alpha.</p>
            <p>Beta.</p>
            <script>ignored()</script>
          </body>
        </html>
        """

        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "chapter-public.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="EPUB/book.opf",
                manifest_items=[("c1", "xhtml/ch1.xhtml")],
                spine_ids=["c1"],
                extra_files={"EPUB/xhtml/ch1.xhtml": chapter_html},
            )

            text = extract_chapter_text(epub_path, "EPUB/xhtml/ch1.xhtml")

            self.assertEqual(text, "Nested Chapter Alpha. Beta.")

    def test_spine_and_extract_used_together_for_chapter_content(self):
        chapter_one = """
        <html><body><h1>One</h1><p>First chapter.</p></body></html>
        """
        chapter_two = """
        <html><body><h1>Two</h1><p>Second chapter.</p></body></html>
        """

        with TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "spine-and-text.epub"
            _write_test_epub(
                epub_path,
                rootfile_path="OEBPS/content.opf",
                manifest_items=[
                    ("c1", "Text/ch1.xhtml"),
                    ("c2", "Text/ch2.xhtml"),
                ],
                spine_ids=["c2", "c1"],
                extra_files={
                    "OEBPS/Text/ch1.xhtml": chapter_one,
                    "OEBPS/Text/ch2.xhtml": chapter_two,
                },
            )

            rootfile_path = get_rootfile_path_from_epub(epub_path)
            spine_paths = get_spine_content_paths(epub_path, rootfile_path)
            extracted = [
                extract_chapter_text(epub_path, path)
                for path in spine_paths
            ]

            self.assertEqual(
                spine_paths,
                ["OEBPS/Text/ch2.xhtml", "OEBPS/Text/ch1.xhtml"],
            )
            self.assertEqual(
                extracted,
                ["Two Second chapter.", "One First chapter."],
            )

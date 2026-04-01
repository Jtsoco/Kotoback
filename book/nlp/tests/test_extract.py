from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.test import SimpleTestCase

from book.nlp.extract import (
    _get_rootfile_path_from_zip,
    _get_spine_content_paths_from_zip,
    get_rootfile_path_from_epub,
    get_spine_content_paths,
)


def _container_xml(rootfile_path: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{rootfile_path}" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
'''


def _package_opf(manifest_items: list[tuple[str, str]], spine_ids: list[str]) -> str:
    manifest_xml = "\n".join(
        f'    <item id="{item_id}" href="{href}" media-type="application/xhtml+xml"/>'
        for item_id, href in manifest_items
    )
    spine_xml = "\n".join(
        f'    <itemref idref="{item_id}"/>' for item_id in spine_ids
    )

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:test</dc:identifier>
    <dc:title>Test</dc:title>
    <dc:language>en</dc:language>
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
) -> None:
    with ZipFile(epub_path, "w") as zf:
        zf.writestr("META-INF/container.xml", _container_xml(rootfile_path))
        zf.writestr(rootfile_path, _package_opf(manifest_items, spine_ids))


class ExtractEpubTests(SimpleTestCase):
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
            self.assertEqual(spine_paths, ["chapter-a.xhtml", "chapter-b.xhtml"])

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

"""EPUB archive and spine extraction helpers."""

from __future__ import annotations

from pathlib import Path
from posixpath import dirname, join, normpath
from zipfile import ZipFile

from lxml import etree


def _read_archive_xml(zf: ZipFile, archive_path: str) -> etree._Element:
    """Read and parse one XML file from the EPUB archive."""

    xml_bytes = zf.read(archive_path)
    return etree.fromstring(xml_bytes)


def _get_rootfile_path_from_zip(zf: ZipFile) -> str:
    """Return the OPF rootfile path from META-INF/container.xml."""

    root = _read_archive_xml(zf, "META-INF/container.xml")
    rootfile_nodes = root.xpath(
        "/*[local-name()='container']"
        "/*[local-name()='rootfiles']"
        "/*[local-name()='rootfile']"
    )
    if not rootfile_nodes:
        raise ValueError(
            "No <rootfile> entry found in META-INF/container.xml."
        )

    full_path = rootfile_nodes[0].get("full-path")
    if not full_path:
        raise ValueError(
            "The first <rootfile> is missing a full-path attribute."
        )

    return full_path


def _get_spine_content_paths_from_zip(
    zf: ZipFile,
    rootfile_path: str,
) -> list[str]:
    """Return ordered spine content paths resolved from an OPF rootfile."""

    package_root = _read_archive_xml(zf, rootfile_path)

    manifest_items = package_root.xpath(
        "/*[local-name()='package']"
        "/*[local-name()='manifest']"
        "/*[local-name()='item']"
    )
    manifest_by_id: dict[str, str] = {}
    for item in manifest_items:
        item_id = item.get("id")
        href = item.get("href")
        if item_id and href:
            manifest_by_id[item_id] = href

    opf_dir = dirname(rootfile_path)
    spine_itemrefs = package_root.xpath(
        "/*[local-name()='package']"
        "/*[local-name()='spine']"
        "/*[local-name()='itemref']"
    )

    spine_paths: list[str] = []
    for itemref in spine_itemrefs:
        idref = itemref.get("idref")
        if not idref:
            continue

        href = manifest_by_id.get(idref)
        if not href:
            continue

        resolved = normpath(join(opf_dir, href)) if opf_dir else normpath(href)
        spine_paths.append(resolved)

    return spine_paths


def get_rootfile_path_from_epub(epub_path: str | Path) -> str:
    """
    Read META-INF/container.xml and return the OPF rootfile full-path.

    Args:
        epub_path: Path to the `.epub` file on disk.
    """

    with ZipFile(epub_path) as zf:
        return _get_rootfile_path_from_zip(zf)


def get_spine_content_paths(
    epub_path: str | Path,
    rootfile_path: str,
) -> list[str]:
    """
    Return ordered spine content paths resolved from an OPF rootfile.

    Args:
        epub_path: Path to the `.epub` file on disk.
        rootfile_path: OPF path returned from `get_rootfile_path_from_epub()`.
    """

    with ZipFile(epub_path) as zf:
        return _get_spine_content_paths_from_zip(zf, rootfile_path)

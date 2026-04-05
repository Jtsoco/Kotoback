"""Factory for generating test EPUB files with configurable content."""

from io import BytesIO
from zipfile import ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile


class EPUBFactory:
    """Generate minimal but valid EPUB files for testing with configurable content."""

    # Test content by language
    CONTENT_EN = {
        "chapter1": "<h1>Chapter 1</h1><p>The quick brown fox jumps over the lazy dog. Serendipity and ephemeral moments create indelible memories.</p>",
        "chapter2": "<h1>Chapter 2</h1><p>Luminous constellations shimmer above the horizon. Quintessential artifacts demonstrate exquisite craftsmanship.</p>",
    }

    CONTENT_JA = {
        "chapter1": "<h1>第1章</h1><p>彼は毎日図書館へ行く。その静かな環境で読書することが好きだった。</p>",
        "chapter2": "<h1>第2章</h1><p>春の京都は特に美しい。古い寺院と新しい町並みが調和していた。</p>",
    }

    @staticmethod
    def create(
        filename="test.epub",
        language="en",
        num_chapters=1,
        content_override=None,
    ) -> SimpleUploadedFile:
        """
        Generate a minimal EPUB file.

        Args:
            filename (str): Filename for the returned file.
            language (str): 'en' or 'ja'; determines test content language.
            num_chapters (int): Number of chapters to include in spine (1 or 2).
            content_override (dict): Custom chapter content; keys are chapter identifiers.

        Returns:
            SimpleUploadedFile: In-memory EPUB file ready for upload.
        """
        content_map = (
            EPUBFactory.CONTENT_JA if language == "ja" else EPUBFactory.CONTENT_EN
        )
        if content_override:
            content_map = {**content_map, **content_override}

        # Clamp num_chapters
        num_chapters = max(1, min(num_chapters, len(content_map)))

        buffer = BytesIO()
        with ZipFile(buffer, "w") as z:
            # mimetype must be first and uncompressed
            z.writestr("mimetype", "application/epub+zip")

            # Container
            z.writestr(
                "META-INF/container.xml",
                "<?xml version=\"1.0\"?>"
                '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
                "<rootfiles>"
                '<rootfile media-type="application/xhtml+xml" full-path="content.opf"/>'
                "</rootfiles>"
                "</container>",
            )

            # Book manifest and spine
            manifest_items = []
            spine_items = []
            for i in range(1, num_chapters + 1):
                chapter_id = f"ch{i}"
                chapter_file = f"chapter{i}.xhtml"
                manifest_items.append(
                    f'<item id="{chapter_id}" href="{chapter_file}" media-type="application/xhtml+xml"/>'
                )
                spine_items.append(f'<itemref idref="{chapter_id}"/>')

            manifest = "\n".join(manifest_items)
            spine = "\n".join(spine_items)

            z.writestr(
                "content.opf",
                f'<?xml version="1.0"?>'
                f'<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
                f"<manifest>{manifest}</manifest>"
                f"<spine>{spine}</spine>"
                f"</package>",
            )

            # Chapters
            chapter_keys = list(content_map.keys())[:num_chapters]
            for i, key in enumerate(chapter_keys, 1):
                z.writestr(
                    f"chapter{i}.xhtml",
                    f'<?xml version="1.0"?>'
                    f'<html xmlns="http://www.w3.org/1999/xhtml">'
                    f"<body>{content_map[key]}</body>"
                    f"</html>",
                )

        buffer.seek(0)
        return SimpleUploadedFile(
            filename, buffer.read(), content_type="application/epub+zip"
        )

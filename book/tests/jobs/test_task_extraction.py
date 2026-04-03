import io
import os
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from .models import IngestionJob, IngestionJobStatus


class IngestionTaskExtractionTests(APITestCase):
    """Test ingestion extraction stage: EPUB parsing, spine retrieval."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="task-test-user",
            email="task@example.com",
            password="pass12345",
        )

    def test_stage_extract_spine_missing_file_raises_error(self):
        """Verify extraction stage handles missing EPUB file."""
        from .tasks import _stage_extract_spine

        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "nonexistent.epub",
                b"",
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.PROCESSING,
        )
        # Delete the file but keep the reference
        if os.path.exists(job.source_file.path):
            os.remove(job.source_file.path)

        with self.assertRaises(FileNotFoundError):
            _stage_extract_spine(job)

    def test_stage_extract_spine_returns_required_keys(self):
        """Verify extraction stage returns expected payload shape."""
        from .tasks import _stage_extract_spine

        # Create minimal valid EPUB structure in memory
        epub_bytes = io.BytesIO()
        with ZipFile(epub_bytes, "w") as zf:
            container_xml = (
                b"<?xml version=\"1.0\"?>\n"
                b'<container version="1.0" xmlns='
                b'"urn:oasis:names:tc:opendocument:xmlns:container">\n'
                b"  <rootfiles>\n"
                b'    <rootfile full-path="content.opf"/>\n'
                b"  </rootfiles>\n"
                b"</container>"
            )
            zf.writestr("META-INF/container.xml", container_xml)

            content_opf = (
                b"<?xml version=\"1.0\"?>\n"
                b'<package xmlns="http://www.idpf.org/2007/opf">\n'
                b"  <manifest>\n"
                b'    <item id="c1" href="ch1.xhtml"/>\n'
                b"  </manifest>\n"
                b"  <spine>\n"
                b'    <itemref idref="c1"/>\n'
                b"  </spine>\n"
                b"</package>"
            )
            zf.writestr("content.opf", content_opf)
            zf.writestr("ch1.xhtml", b"<html><body>Text</body></html>")

        job = IngestionJob.objects.create(
            user=self.user,
            source_file=SimpleUploadedFile(
                "test.epub",
                epub_bytes.getvalue(),
                content_type="application/epub+zip",
            ),
            source_language="en",
            target_language="ja",
            status=IngestionJobStatus.PROCESSING,
        )

        result = _stage_extract_spine(job)

        self.assertIn("epub_path", result)
        self.assertIn("spine_paths", result)
        self.assertIn("chapter_count", result)
        self.assertIn("source_language", result)
        self.assertEqual(result["source_language"], "en")
        self.assertGreater(result["chapter_count"], 0)

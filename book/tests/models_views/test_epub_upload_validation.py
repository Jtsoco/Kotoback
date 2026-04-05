from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import serializers
from rest_framework.test import APITestCase

from book.upload_validators import validate_epub_upload


class EpubUploadValidatorTests(APITestCase):
    """Test EPUB upload validation: extension, size, MIME type."""

    def test_rejects_non_epub_extension(self):
        upload = SimpleUploadedFile(
            "not-epub.txt",
            b"hello",
            content_type="text/plain",
        )

        with self.assertRaises(serializers.ValidationError):
            validate_epub_upload(upload)

    @override_settings(EPUB_MAX_UPLOAD_SIZE=10)
    def test_rejects_when_file_exceeds_limit(self):
        upload = SimpleUploadedFile(
            "book.epub",
            b"01234567890",
            content_type="application/epub+zip",
        )

        with self.assertRaises(serializers.ValidationError):
            validate_epub_upload(upload)

    def test_accepts_valid_epub_upload(self):
        upload = SimpleUploadedFile(
            "book.epub",
            b"PK\x03\x04",
            content_type="application/epub+zip",
        )

        validated = validate_epub_upload(upload)
        self.assertEqual(validated.name, "book.epub")

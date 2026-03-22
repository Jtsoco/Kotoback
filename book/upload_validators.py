from django.conf import settings
from rest_framework import serializers


# Browsers and clients can report EPUB uploads with different content types.
ALLOWED_EPUB_CONTENT_TYPES = {
    "application/epub+zip",
    "application/zip",
    "application/octet-stream",
}


def validate_epub_upload(uploaded_file):
    if uploaded_file is None:
        raise serializers.ValidationError("An EPUB file is required.")

    filename = (getattr(uploaded_file, "name", "") or "").lower()
    if not filename.endswith(".epub"):
        raise serializers.ValidationError("Only .epub files are allowed.")

    max_bytes = int(settings.EPUB_MAX_UPLOAD_SIZE)
    file_size = int(getattr(uploaded_file, "size", 0) or 0)
    if file_size > max_bytes:
        raise serializers.ValidationError(
            f"EPUB file is too large. Max size is {max_bytes} bytes."
        )

    content_type = getattr(uploaded_file, "content_type", "") or ""
    if content_type and content_type not in ALLOWED_EPUB_CONTENT_TYPES:
        raise serializers.ValidationError(
            "Invalid EPUB content type."
        )

    return uploaded_file

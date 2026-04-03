from django.db.models import Count
from rest_framework import serializers

from utils.serializers import CamelCaseInputMixin

from .models import (
    Book,
    BookCard,
    DefaultFlashCard,
    FlashCard,
    IngestionJob,
    IngestionJobStatus,
)
from .upload_validators import validate_epub_upload


class DefaultFlashCardSerializer(
    CamelCaseInputMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = DefaultFlashCard
        fields = [
            "id",
            "front_language",
            "back_language",
            "front_data",
            "back_data",
        ]


class FlashCardSerializer(CamelCaseInputMixin, serializers.ModelSerializer):
    def _require_study_word(self, data: object) -> None:
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                "frontData/backData must be a JSON object."
            )
        if "studyWord" not in data and "StudyWord" not in data:
            raise serializers.ValidationError(
                "frontData/backData must include `studyWord` (or `StudyWord`)."
            )

    def validate(self, attrs):
        front_language = attrs.get("front_language", None)
        back_language = attrs.get("back_language", None)
        if (
            front_language is not None
            and back_language is not None
            and front_language == back_language
        ):
            raise serializers.ValidationError(
                "front_language and back_language cannot be the same"
            )

        # For partial updates we may only receive one side.
        front_data = attrs.get("front_data", None)
        back_data = attrs.get("back_data", None)
        if front_data is not None:
            self._require_study_word(front_data)
        if back_data is not None:
            self._require_study_word(back_data)
        return attrs

    class Meta:
        model = FlashCard
        fields = [
            "id",
            "front_language",
            "back_language",
            "front_data",
            "back_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class BookSerializer(serializers.ModelSerializer):
    default_flashcards = DefaultFlashCardSerializer(many=True, read_only=True)

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "info",
            "default_flashcards",
        ]


class BookSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = [
            "id",
            "title",
        ]


class BookCardSerializer(CamelCaseInputMixin, serializers.ModelSerializer):
    book = BookSummarySerializer(read_only=True)
    book_id = serializers.PrimaryKeyRelatedField(
        queryset=Book.objects.all(),
        source="book",
        write_only=True,
    )
    flashcard_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = BookCard
        fields = [
            "id",
            "book",
            "book_id",
            "last_studied_at",
            "created_at",
            "updated_at",
            "flashcard_count",
        ]
        read_only_fields = ["last_studied_at", "created_at", "updated_at"]


class HomepageBookCardSerializer(
    CamelCaseInputMixin,
    serializers.ModelSerializer,
):
    book = BookSummarySerializer(read_only=True)
    flashcard_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = BookCard
        fields = [
            "id",
            "book",
            "last_studied_at",
            "created_at",
            "updated_at",
            "flashcard_count",
        ]


def annotate_flashcard_count(queryset):
    return queryset.annotate(flashcard_count=Count("flashcards"))


class IngestionJobUploadSerializer(
    CamelCaseInputMixin,
    serializers.ModelSerializer,
):
    file = serializers.FileField(source="source_file", write_only=True)
    status = serializers.ChoiceField(
        choices=IngestionJobStatus.choices,
        read_only=True,
    )
    progress = serializers.IntegerField(read_only=True)
    current_stage = serializers.CharField(read_only=True)

    class Meta:
        model = IngestionJob
        fields = [
            "id",
            "file",
            "source_language",
            "target_language",
            "card_count_target",
            "rarity_profile",
            "bookcard",
            "status",
            "progress",
            "current_stage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "bookcard",
            "status",
            "progress",
            "current_stage",
            "created_at",
            "updated_at",
        ]

    def validate_file(self, value):
        return validate_epub_upload(value)

    def validate_card_count_target(self, value):
        if value < 1 or value > 1000:
            raise serializers.ValidationError(
                "cardCountTarget must be between 1 and 1000."
            )
        return value

    def validate(self, attrs):
        source_language = attrs.get("source_language")
        target_language = attrs.get("target_language")
        if source_language == target_language:
            raise serializers.ValidationError(
                "source_language and target_language cannot be the same"
            )
        return attrs


class IngestionJobStatusSerializer(
    CamelCaseInputMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = IngestionJob
        fields = [
            "id",
            "bookcard",
            "status",
            "progress",
            "current_stage",
            "summary",
            "error_payload",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = fields


class IngestionJobResultSerializer(
    CamelCaseInputMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = IngestionJob
        fields = [
            "id",
            "bookcard",
            "status",
            "result_payload",
            "summary",
            "completed_at",
            "updated_at",
        ]
        read_only_fields = fields

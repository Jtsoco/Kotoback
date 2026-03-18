from django.db.models import Count
from rest_framework import serializers

from .models import Book, BookCard, DefaultFlashCard, FlashCard


class DefaultFlashCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefaultFlashCard
        fields = [
            "id",
            "front_language",
            "back_language",
            "front_data",
            "back_data",
        ]


class FlashCardSerializer(serializers.ModelSerializer):
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
            "info",
        ]


class BookCardSerializer(serializers.ModelSerializer):
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
        read_only_fields = ["created_at", "updated_at"]


class HomepageBookCardSerializer(serializers.ModelSerializer):
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


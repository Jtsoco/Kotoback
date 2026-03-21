import string
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Language(models.TextChoices):
    ENGLISH = "en", "English"
    JAPANESE = "ja", "Japanese"


class Book(models.Model):
    title = models.CharField(max_length=512)
    info = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


class BookCard(models.Model):
    """
    A user's relationship to a book (their imported copy + derived cards).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookcards",
    )
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="bookcards")

    # When the user last studied this bookcard (for homepage ordering).
    last_studied_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "book"], name="uniq_bookcard_user_book"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.book_id}"


class DefaultFlashCard(models.Model):
    """
    Optional: book-scoped default cards (not user-specific).
    """

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="default_flashcards")

    front_language = models.CharField(max_length=8, choices=Language.choices)
    back_language = models.CharField(max_length=8, choices=Language.choices)

    front_data = models.JSONField()
    back_data = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(front_language=models.F("back_language")),
                name="default_flashcard_front_back_language_different",
            ),
        ]

    def clean(self) -> None:
        if self.front_language == self.back_language:
            raise ValidationError("front_language and back_language cannot be the same")

    def save(self, *args, **kwargs):
        # Ensure `clean()` is enforced when not using ModelForm/admin.
        self.full_clean()
        return super().save(*args, **kwargs)


class FlashCard(models.Model):
    bookcard = models.ForeignKey(
        BookCard,
        on_delete=models.CASCADE,
        related_name="flashcards",
    )

    front_language = models.CharField(max_length=8, choices=Language.choices)
    back_language = models.CharField(max_length=8, choices=Language.choices)

    front_data = models.JSONField()
    back_data = models.JSONField()
    """
    front and back data langauge depends on langauge, but both have:

        studyWord: string;
        definition?: string;
        phoneticText?: string; (think furigana for kanji)
        exampleSentence?: string;
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(front_language=models.F("back_language")),
                name="flashcard_front_back_language_different",
            ),
        ]

    def clean(self) -> None:
        if self.front_language == self.back_language:
            raise ValidationError("front_language and back_language cannot be the same")

    def save(self, *args, **kwargs):
        # Ensure `clean()` is enforced when not using ModelForm/admin.
        self.full_clean()
        if "studyWord" not in self.front_data:
            raise ValidationError("front_data must have studyWord")
        if "studyWord" not in self.back_data:
            raise ValidationError("back_data must have studyWord")
        return super().save(*args, **kwargs)
        # make sure front end and back end of flashcards have studyWord

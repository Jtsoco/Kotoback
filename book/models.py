from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.core.validators import MaxValueValidator, MinValueValidator


class Language(models.TextChoices):
    ENGLISH = "en", "English"
    JAPANESE = "ja", "Japanese"


class Book(models.Model):
    identifier = models.CharField(max_length=256, unique=True, db_index=True)
    title = models.CharField(max_length=512, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

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
    book = models.ForeignKey(
        Book,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookcards",
    )

    # EPUB metadata fields (temporary until Book integration)
    title = models.CharField(max_length=512, blank=True)
    author = models.JSONField(default=list, blank=True)  # List of author names
    epub_id = models.CharField(max_length=256, blank=True)

    # When the user last studied this bookcard (for homepage ordering).
    last_studied_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = []

    def __str__(self) -> str:
        return self.title or f"BookCard({self.user_id})"


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


class IngestionJobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    PROCESSING = "processing", "Processing"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class IngestionJob(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ingestion_jobs",
    )
    bookcard = models.ForeignKey(
        BookCard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingestion_jobs",
    )

    source_file = models.FileField(upload_to="ingestion-jobs/%Y/%m/%d/")

    source_language = models.CharField(max_length=8, choices=Language.choices)
    target_language = models.CharField(max_length=8, choices=Language.choices)
    card_count_target = models.PositiveIntegerField(default=150)
    rarity_profile = models.CharField(max_length=64, default="standard")

    status = models.CharField(
        max_length=16,
        choices=IngestionJobStatus.choices,
        default=IngestionJobStatus.QUEUED,
    )
    progress = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    current_stage = models.CharField(max_length=64, blank=True, default="")

    result_payload = models.JSONField(default=dict, blank=True)
    error_payload = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)

    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(source_language=models.F("target_language")),
                name="ingestion_job_source_target_language_different",
            ),
            models.CheckConstraint(
                condition=Q(progress__gte=0) & Q(progress__lte=100),
                name="ingestion_job_progress_between_0_and_100",
            ),
        ]

    def clean(self) -> None:
        if self.source_language == self.target_language:
            raise ValidationError(
                "source_language and target_language cannot be the same"
            )
        if self.bookcard_id and self.bookcard.user_id != self.user_id:
            raise ValidationError("bookcard must belong to the same user")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

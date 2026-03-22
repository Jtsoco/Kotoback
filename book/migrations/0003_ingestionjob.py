from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("book", "0002_bookcard_last_studied_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IngestionJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "source_file",
                    models.FileField(upload_to="ingestion-jobs/%Y/%m/%d/"),
                ),
                (
                    "source_language",
                    models.CharField(
                        choices=[("en", "English"), ("ja", "Japanese")],
                        max_length=8,
                    ),
                ),
                (
                    "target_language",
                    models.CharField(
                        choices=[("en", "English"), ("ja", "Japanese")],
                        max_length=8,
                    ),
                ),
                (
                    "card_count_target",
                    models.PositiveIntegerField(default=250),
                ),
                (
                    "rarity_profile",
                    models.CharField(default="standard", max_length=64),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("processing", "Processing"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="queued",
                        max_length=16,
                    ),
                ),
                (
                    "progress",
                    models.PositiveSmallIntegerField(
                        default=0,
                        validators=[
                            MinValueValidator(0),
                            MaxValueValidator(100),
                        ],
                    ),
                ),
                (
                    "current_stage",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("result_payload", models.JSONField(blank=True, default=dict)),
                ("error_payload", models.JSONField(blank=True, default=dict)),
                ("summary", models.JSONField(blank=True, default=dict)),
                (
                    "celery_task_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "bookcard",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ingestion_jobs",
                        to="book.bookcard",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ingestion_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=~models.Q(
                            source_language=models.F("target_language"),
                        ),
                        name="ingestion_job_source_target_language_different",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            progress__gte=0,
                            progress__lte=100,
                        ),
                        name="ingestion_job_progress_between_0_and_100",
                    ),
                ],
            },
        ),
    ]

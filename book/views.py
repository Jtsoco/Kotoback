from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Book, BookCard, FlashCard, IngestionJob, IngestionJobStatus
from .serializers import (
    BookCardSerializer,
    BookSerializer,
    FlashCardSerializer,
    HomepageBookCardSerializer,
    IngestionJobResultSerializer,
    IngestionJobStatusSerializer,
    IngestionJobUploadSerializer,
    annotate_flashcard_count,
)
from .tasks import process_ingestion_job


class HomepageView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {
                    "authenticated": False,
                    "bookcards": [],
                }
            )

        qs = (
            BookCard.objects.filter(user=request.user)
            .select_related("book")
            .order_by("-last_studied_at", "-updated_at")
        )
        qs = annotate_flashcard_count(qs)

        serializer = HomepageBookCardSerializer(qs, many=True)
        return Response(
            {
                "authenticated": True,
                "bookcards": serializer.data,
            }
        )


class BookListView(generics.ListAPIView):
    queryset = Book.objects.all().order_by("title")
    serializer_class = BookSerializer
    permission_classes = [permissions.AllowAny]


class BookDetailView(generics.RetrieveAPIView):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [permissions.AllowAny]


class BookCardListCreateView(generics.ListCreateAPIView):
    serializer_class = BookCardSerializer

    def get_queryset(self):
        qs = BookCard.objects.filter(
            user=self.request.user,
        ).select_related("book")
        return annotate_flashcard_count(qs).order_by(
            "-last_studied_at",
            "-updated_at",
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BookCardDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BookCardSerializer

    def get_queryset(self):
        qs = BookCard.objects.filter(
            user=self.request.user,
        ).select_related("book")
        return annotate_flashcard_count(qs)


class FlashCardListCreateView(generics.ListCreateAPIView):
    serializer_class = FlashCardSerializer

    def get_queryset(self):
        bookcard_id = self.kwargs["bookcard_pk"]
        return FlashCard.objects.filter(
            bookcard__user=self.request.user,
            bookcard_id=bookcard_id,
        )

    def _get_bookcard_or_404(self) -> BookCard:
        bookcard_id = self.kwargs["bookcard_pk"]
        return get_object_or_404(
            BookCard,
            id=bookcard_id,
            user=self.request.user,
        )

    def create(self, request, *args, **kwargs):
        """
        Supports both:
        - single POST with an object payload
                - bulk POST with a list payload
                    (multiple flashcards to the same bookcard)
        """

        bookcard = self._get_bookcard_or_404()
        many = isinstance(request.data, list)
        serializer = self.get_serializer(data=request.data, many=many)
        serializer.is_valid(raise_exception=True)

        if many:
            with transaction.atomic():
                created = [
                    FlashCard.objects.create(bookcard=bookcard, **item)
                    for item in serializer.validated_data
                ]
                bookcard.last_studied_at = timezone.now()
                bookcard.save(update_fields=["last_studied_at"])
            out_serializer = FlashCardSerializer(created, many=True)
            return Response(
                out_serializer.data,
                status=status.HTTP_201_CREATED,
            )

        created = FlashCard.objects.create(
            bookcard=bookcard, **serializer.validated_data
        )
        bookcard.last_studied_at = timezone.now()
        bookcard.save(update_fields=["last_studied_at"])
        out_serializer = FlashCardSerializer(created)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class FlashCardDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FlashCardSerializer

    def get_queryset(self):
        bookcard_id = self.kwargs["bookcard_pk"]
        return FlashCard.objects.filter(
            bookcard__user=self.request.user,
            bookcard_id=bookcard_id,
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        bookcard = instance.bookcard
        bookcard.last_studied_at = timezone.now()
        bookcard.save(update_fields=["last_studied_at"])


class IngestionJobUploadView(generics.CreateAPIView):
    serializer_class = IngestionJobUploadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.save(user=request.user)

        def enqueue_ingestion_job() -> None:
            async_result = process_ingestion_job.delay(job.id)
            IngestionJob.objects.filter(id=job.id).update(
                celery_task_id=async_result.id,
            )

        transaction.on_commit(enqueue_ingestion_job)

        out = IngestionJobStatusSerializer(job)
        return Response(out.data, status=status.HTTP_201_CREATED)


class IngestionJobStatusView(generics.RetrieveAPIView):
    serializer_class = IngestionJobStatusSerializer

    def get_queryset(self):
        return IngestionJob.objects.filter(user=self.request.user)

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            id=self.kwargs["job_id"],
        )


class IngestionJobResultView(APIView):
    def get(self, request, *args, **kwargs):
        job = get_object_or_404(
            IngestionJob,
            id=kwargs["job_id"],
            user=request.user,
        )
        if job.status != IngestionJobStatus.SUCCEEDED:
            return Response(
                {
                    "detail": "Result is not ready yet.",
                    "status": job.status,
                    "progress": job.progress,
                },
                status=status.HTTP_409_CONFLICT,
            )
        serializer = IngestionJobResultSerializer(job)
        return Response(serializer.data)


class IngestionJobCancelView(APIView):
    def post(self, request, *args, **kwargs):
        job = get_object_or_404(
            IngestionJob,
            id=kwargs["job_id"],
            user=request.user,
        )
        if job.status in (
            IngestionJobStatus.SUCCEEDED,
            IngestionJobStatus.FAILED,
            IngestionJobStatus.CANCELLED,
        ):
            return Response(
                {
                    "id": job.id,
                    "status": job.status,
                    "detail": "Job is not cancellable in its current state.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        job.status = IngestionJobStatus.CANCELLED
        job.current_stage = "cancelled"
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "current_stage", "completed_at"])
        serializer = IngestionJobStatusSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)

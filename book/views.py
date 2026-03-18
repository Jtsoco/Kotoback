from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Book, BookCard, FlashCard
from .serializers import (
    BookCardSerializer,
    BookSerializer,
    FlashCardSerializer,
    HomepageBookCardSerializer,
    annotate_flashcard_count,
)


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

    def perform_create(self, serializer):
        bookcard_id = self.kwargs["bookcard_pk"]
        bookcard = BookCard.objects.get(
            id=bookcard_id,
            user=self.request.user,
        )
        serializer.save(bookcard=bookcard)
        # Update last_studied_at as a simple heuristic.
        bookcard.last_studied_at = timezone.now()
        bookcard.save(update_fields=["last_studied_at"])


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

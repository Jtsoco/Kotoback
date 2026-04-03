from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Book, BookCard, FlashCard


def study_payload(word: str) -> dict:
    return {"studyWord": word, "furigana": "ふりがな"}


class BookCardApiTests(APITestCase):
    """Test BookCard API endpoints: homepage listing and card retrieval."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="u1",
            email="u1@example.com",
            password="pass12345",
        )
        self.user2 = User.objects.create_user(
            username="u2",
            email="u2@example.com",
            password="pass12345",
        )

        self.token = Token.objects.create(user=self.user)
        Token.objects.create(user=self.user2)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.book1 = Book.objects.create(title="B1", identifier="book-1")
        self.book2 = Book.objects.create(title="B2", identifier="book-2")

        self.bookcard1 = BookCard.objects.create(
            user=self.user,
            book=self.book1,
        )
        self.bookcard1.last_studied_at = timezone.now() - timedelta(days=2)
        self.bookcard1.save(update_fields=["last_studied_at"])

        self.bookcard2 = BookCard.objects.create(
            user=self.user,
            book=self.book2,
        )
        self.bookcard2.last_studied_at = timezone.now() - timedelta(days=1)
        self.bookcard2.save(update_fields=["last_studied_at"])

        self.other_bookcard = BookCard.objects.create(
            user=self.user2,
            book=self.book1,
        )

        self.flash1 = FlashCard.objects.create(
            bookcard=self.bookcard1,
            front_language="en",
            back_language="ja",
            front_data=study_payload("apple"),
            back_data=study_payload("りんご"),
        )
        self.flash2 = FlashCard.objects.create(
            bookcard=self.bookcard2,
            front_language="en",
            back_language="ja",
            front_data=study_payload("banana"),
            back_data=study_payload("バナナ"),
        )

    def test_homepage_anonymous_empty(self):
        self.client.credentials()  # remove auth
        resp = self.client.get(reverse("book:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["authenticated"], False)
        self.assertEqual(resp.data["bookcards"], [])

    def test_homepage_authenticated_orders_by_last_studied(self):
        resp = self.client.get(reverse("book:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["authenticated"], True)

        bookcards = resp.data["bookcards"]
        self.assertEqual(len(bookcards), 2)
        # bookcard2 is newer (lastStudiedAt -1 day vs -2 days)
        self.assertEqual(bookcards[0]["id"], self.bookcard2.id)
        self.assertEqual(bookcards[1]["id"], self.bookcard1.id)

        # flashcardCount should reflect each bookcard
        self.assertEqual(bookcards[0]["flashcardCount"], 1)
        self.assertEqual(bookcards[1]["flashcardCount"], 1)

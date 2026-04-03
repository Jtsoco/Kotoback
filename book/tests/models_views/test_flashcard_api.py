from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from book.models import Book, BookCard, FlashCard


def study_payload(word: str) -> dict:
    return {"studyWord": word, "furigana": "ふりがな"}


class FlashCardApiTests(APITestCase):
    """Test FlashCard API endpoints: CRUD, bulk create, user scoping."""

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

    def test_flashcard_cannot_have_same_languages(self):
        url = reverse(
            "book:flashcard-list", kwargs={"bookcard_pk": self.bookcard1.id}
        )
        payload = {
            "frontLanguage": "en",
            "backLanguage": "en",
            "frontData": study_payload("apple"),
            "backData": study_payload("りんご"),
        }
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_flashcard_requires_study_word_in_both_json_blobs(self):
        url = reverse(
            "book:flashcard-list", kwargs={"bookcard_pk": self.bookcard1.id}
        )
        payload = {
            "frontLanguage": "en",
            "backLanguage": "ja",
            "frontData": {},  # missing studyWord
            "backData": study_payload("りんご"),
        }
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_flashcard_connections_enforced_user_scoping(self):
        # user1 tries to create under user2's bookcard -> should 404
        url = reverse(
            "book:flashcard-list",
            kwargs={"bookcard_pk": self.other_bookcard.id},
        )
        payload = {
            "frontLanguage": "en",
            "backLanguage": "ja",
            "frontData": study_payload("x"),
            "backData": study_payload("y"),
        }
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_bulk_flashcard_create(self):
        url = reverse(
            "book:flashcard-list", kwargs={"bookcard_pk": self.bookcard1.id}
        )
        payload = [
            {
                "frontLanguage": "en",
                "backLanguage": "ja",
                "frontData": study_payload("c"),
                "backData": study_payload("シー"),
            },
            {
                "frontLanguage": "en",
                "backLanguage": "ja",
                "frontData": study_payload("d"),
                "backData": study_payload("ディー"),
            },
        ]
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 201)

        self.assertEqual(
            FlashCard.objects.filter(bookcard=self.bookcard1).count(),
            3,  # existing flash1 + 2 created
        )
        self.assertIn("frontLanguage", resp.data[0])
        self.assertIn("backLanguage", resp.data[0])

    def test_flashcard_crud(self):
        url = reverse(
            "book:flashcard-list", kwargs={"bookcard_pk": self.bookcard1.id}
        )
        create_payload = {
            "frontLanguage": "en",
            "backLanguage": "ja",
            "frontData": study_payload("e"),
            "backData": study_payload("イー"),
        }
        resp = self.client.post(url, create_payload, format="json")
        self.assertEqual(resp.status_code, 201)

        created_id = resp.data["id"]
        detail_url = reverse(
            "book:flashcard-detail",
            kwargs={"bookcard_pk": self.bookcard1.id, "pk": created_id},
        )

        # GET
        resp = self.client.get(detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], created_id)

        # PATCH
        patch_payload = {
            "frontLanguage": "en",
            "backLanguage": "ja",
            "frontData": study_payload("e2"),
            "backData": study_payload("イー"),
        }
        resp = self.client.patch(detail_url, patch_payload, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["frontData"]["studyWord"], "e2")

        # DELETE
        resp = self.client.delete(detail_url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(FlashCard.objects.filter(id=created_id).exists())

    def test_bulk_flashcard_create_response_fields(self):
        url = reverse(
            "book:flashcard-list", kwargs={"bookcard_pk": self.bookcard1.id}
        )
        payload = [
            {
                "frontLanguage": "en",
                "backLanguage": "ja",
                "frontData": study_payload("c"),
                "backData": study_payload("シー"),
            },
            {
                "frontLanguage": "en",
                "backLanguage": "ja",
                "frontData": study_payload("d"),
                "backData": study_payload("ディー"),
            },
        ]
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            FlashCard.objects.filter(bookcard=self.bookcard1).count(),
            3,
        )
        self.assertIn("frontLanguage", resp.data[0])
        self.assertIn("backLanguage", resp.data[0])
        self.assertIn("frontData", resp.data[0])
        self.assertIn("backData", resp.data[0])
        self.assertIn("createdAt", resp.data[0])
        self.assertIn("updatedAt", resp.data[0])
        self.assertIn("id", resp.data[0])

from django.urls import path

from . import views

app_name = "book"

urlpatterns = [
    path("home/", views.HomepageView.as_view(), name="home"),
    path("books/", views.BookListView.as_view(), name="book-list"),
    path(
        "books/<int:pk>/",
        views.BookDetailView.as_view(),
        name="book-detail",
    ),
    path(
        "bookcards/",
        views.BookCardListCreateView.as_view(),
        name="bookcard-list",
    ),
    path(
        "bookcards/<int:pk>/",
        views.BookCardDetailView.as_view(),
        name="bookcard-detail",
    ),
    path(
        "bookcards/<int:bookcard_pk>/flashcards/",
        views.FlashCardListCreateView.as_view(),
        name="flashcard-list",
    ),
    path(
        "bookcards/<int:bookcard_pk>/flashcards/<int:pk>/",
        views.FlashCardDetailView.as_view(),
        name="flashcard-detail",
    ),
]

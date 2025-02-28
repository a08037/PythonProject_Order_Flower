from django.test import TestCase
from django.contrib.auth.models import User
from .models import Flower, Review, Rating
from django.urls import reverse


class ReviewModelTest(TestCase):

    def setUp(self):
        # Создаем тестового пользователя и цветок
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.flower = Flower.objects.create(name="Роза", price=100.0, description="Красная роза", image="path/to/image")

    def test_create_review(self):
        # Создаем отзыв
        review = Review.objects.create(
            flower=self.flower,
            user=self.user,
            content="Отличный цветок!"
        )
        self.assertEqual(review.flower.name, "Роза")
        self.assertEqual(review.user.username, "testuser")
        self.assertEqual(review.content, "Отличный цветок!")
        self.assertIsNotNone(review.created_at)  # Убедимся, что время создания не пустое

class RatingModelTest(TestCase):

    def setUp(self):
        # Создаем тестового пользователя и цветок
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.flower = Flower.objects.create(name="Роза", price=100.0, description="Красная роза", image="path/to/image")

    def test_create_rating(self):
        # Создаем рейтинг
        rating = Rating.objects.create(
            flower=self.flower,
            user=self.user,
            rating=5
        )
        self.assertEqual(rating.flower.name, "Роза")
        self.assertEqual(rating.user.username, "testuser")
        self.assertEqual(rating.rating, 5)
        self.assertIsNotNone(rating.created_at)

class ReviewAndRatingViewsTest(TestCase):

    def setUp(self):
        # Создаем тестового пользователя и цветок
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.flower = Flower.objects.create(name="Роза", price=100.0, description="Красная роза", image="path/to/image")

    def test_add_review_view(self):
        # Тестируем создание отзыва через представление
        self.client.login(username='testuser', password='password123')
        url = reverse('add_review', args=[self.flower.id])
        response = self.client.post(url, {'content': 'Очень красивый цветок!'})

        self.assertEqual(response.status_code, 302)  # Перенаправление после успешной отправки
        self.assertTrue(Review.objects.filter(content='Очень красивый цветок!').exists())

    def test_add_rating_view(self):
        # Тестируем создание рейтинга через представление
        self.client.login(username='testuser', password='password123')
        url = reverse('add_rating', args=[self.flower.id])
        response = self.client.post(url, {'rating': 5})

        self.assertEqual(response.status_code, 302)  # Перенаправление после успешной отправки
        self.assertTrue(Rating.objects.filter(rating=5).exists())

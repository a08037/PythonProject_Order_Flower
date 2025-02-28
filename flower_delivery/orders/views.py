import logging
import os
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from .models import Flower, Order, Cart, CartItem, Review, Rating, Report, OrderHistory
from .forms import OrderForm, ReviewForm, RatingForm
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth import logout
from django.utils import timezone
from django.db.models import Sum, Avg
from aiogram import Bot
from aiogram.types import Message
from aiogram.filters import Command
from django.utils.timezone import now
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse

# Настройка логирования
logger = logging.getLogger(__name__)

# Инициализация Telegram-бота
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

def index(request):
    """Главная страница с каталогом товаров"""
    flowers = Flower.objects.all()  # Получаем все товары из модели Flower

    # Инициализация переменных корзины
    total_items = 0
    total_price = 0

    # Получаем корзину для авторизованного пользователя или гостя
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(user=None, session_key=session_key)

    # Если корзина существует, получаем данные
    if cart:
        total_items = cart.total_items()
        total_price = cart.total_price()

    logger.info(f"User {request.user} accessed the index page. Cart total items: {total_items}, total price: {total_price}")

    # Передаем данные в шаблон
    return render(request, 'orders/index.html', {
        'flowers': flowers,
        'total_items': total_items,
        'total_price': total_price
    })

def add_to_cart(request, flower_id):
    """Добавление товара в корзину"""
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key

    flower = get_object_or_404(Flower, id=flower_id)

    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        cart, created = Cart.objects.get_or_create(user=None, session_key=session_key)

    cart_item, created = CartItem.objects.get_or_create(cart=cart, flower=flower)
    if not created:
        cart_item.quantity += 1
    cart_item.save()

    logger.info(f"Added {flower.name} (ID: {flower.id}) to cart with quantity {cart_item.quantity}")

    return redirect('cart')

@login_required(login_url='/accounts/login/')
def order(request, flower_id):
    """Оформление заказа для конкретного товара"""
    flower = get_object_or_404(Flower, id=flower_id)  # Получаем информацию о цветке
    if request.method == 'POST':
        delivery_date = request.POST.get('delivery_date')
        delivery_time = request.POST.get('delivery_time')
        address = request.POST.get('address')

        # Проверка на заполнение всех полей
        if not delivery_date or not delivery_time or not address:
            return render(request, 'orders/order.html', {'flower': flower, 'error': 'Все поля должны быть заполнены.'})

        # Создаем заказ на основе выбранного товара
        Order.objects.create(
            user=request.user,
            cart=None,  # Заказ без корзины, только для одного товара
            delivery_date=delivery_date,
            delivery_time=delivery_time,
            address=address
        )
        return redirect('index')  # Перенаправляем на главную страницу
    return render(request, 'orders/order.html', {'flower': flower})

def view_cart(request):
    """Просмотр корзины"""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(user=None, session_key=session_key)

    cart_items = CartItem.objects.filter(cart=cart)
    total_price = cart.total_price()
    total_items = cart.total_items()

    return render(request, 'orders/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'total_items': total_items,
    })

@login_required(login_url='/accounts/login/')
def remove_from_cart(request, cart_item_id):
    """Удаление элемента из корзины"""
    cart_item = get_object_or_404(CartItem, id=cart_item_id)
    cart_item.delete()

    logger.info(f"User {request.user} removed item with ID {cart_item.id} from their cart.")

    return redirect('cart')

def confirm_order(request):
    """Подтверждение заказа для авторизованных пользователей и гостей"""
    if request.user.is_authenticated:
        cart = get_object_or_404(Cart, user=request.user)
        user = request.user
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart = get_object_or_404(Cart, session_key=session_key)
        user = None

    logger.info("Received POST request on /cart/confirm/")

    # Создаем форму
    form = OrderForm(request.POST or None)

    if request.method == 'POST':
        logger.info(f"Processing order confirmation for user: {request.user if request.user.is_authenticated else 'Guest'}")

        # Логирование данных формы для диагностики
        logger.info(f"Form data: {request.POST}")

        # Если форма не прошла валидацию
        if not form.is_valid():
            logger.warning(f"Validation failed: invalid form data {form.errors}")
            messages.error(request, "Форма заполнена неверно.")
            return redirect('cart')

        # Проверка обязательных полей
        if not cart.items.exists():
            messages.error(request, "Ваша корзина пуста.")
            return redirect('cart')

        if Order.objects.filter(cart=cart).exists():
            messages.error(request, "Для этой корзины уже был оформлен заказ.")
            return redirect('cart')

        flower = cart.items.first().flower  # Предполагается, что корзина не пуста

        # Создание нового заказа
        order = Order.objects.create(
            user=user,
            cart=cart,
            flower=flower,
            delivery_date=form.cleaned_data['delivery_date'],
            delivery_time=form.cleaned_data['delivery_time'],
            address=form.cleaned_data['address'],
            guest_email=form.cleaned_data.get('guest_email'),
            guest_phone=form.cleaned_data.get('guest_phone')
        )

        # Обновление общей стоимости
        order.total_price = cart.total_price()
        order.save()

        logger.info(f"Redirecting to payment_window for order ID: {order.id}")

        # Добавление записи в историю заказов
        guest_user, _ = User.objects.get_or_create(username="guest")
        order_user = order.user if order.user else guest_user

        for item in cart.items.all():
            OrderHistory.objects.create(
                user=order_user,
                flower=item.flower,
                delivery_date=order.delivery_date,
                delivery_time=order.delivery_time,
                delivery_address=order.address,
                comment=order.comment,
                cost=item.total_price()
            )

        # Отправка заказа в Telegram
        try:
            logger.info(f"Sending order {order.id} to Telegram")
            order.send_to_telegram()
        except Exception as e:
            logger.error(f"Ошибка при отправке заказа в Telegram: {e}")
            messages.error(request, "Ошибка при отправке заказа, попробуйте позже.")
            return redirect('cart')

        # Очистка корзины
        logger.info(f"Cart {cart.id} items before clearing: {cart.items.count()}")

        # Перенаправление на страницу оплаты
        return redirect('payment_window', order_id=order.id)

    return render(request, 'orders/confirm_order.html', {'cart': cart, 'form': form})



def payment_window(request, order_id):
    """Окно оплаты"""
    # Получаем заказ по ID
    order = get_object_or_404(Order, id=order_id)

    # Если форма отправлена (например, при успешной оплате)
    if request.method == 'POST':
        payment_successful = True  # Пример: если оплата прошла успешно

        if payment_successful:
            # Очистка корзины после успешной оплаты
            order.cart.items.all().delete()  # Удаляем все элементы из корзины
            order.cart.is_completed = True  # Помечаем корзину как завершенную
            order.cart.save()

            # Логирование успешной оплаты
            logger.info(f"Payment for order {order.id} was successful.")

            # Перенаправление на главную страницу
            return redirect('index')
        else:
            # Логирование ошибки при оплате
            logger.warning(f"Payment for order {order.id} failed.")
            return render(request, 'orders/payment_window.html', {'order': order, 'error': 'Оплата не прошла.'})

    # Если не отправлен POST-запрос (например, когда просто загружается страница)
    return render(request, 'orders/payment_window.html', {'order': order, 'total_price': order.total_price})

def send_to_telegram(self):
    # Проверка обязательных данных
    if not self.delivery_date or not self.delivery_time or not self.address:
        logger.error(f"Order {self.id} is missing required data: delivery date, time, or address")
        return False

    # Проверка, есть ли товары в заказе
    if not self.cart.items.exists():
        logger.error(f"Order {self.id} has no items in the cart")
        return False

    # Теперь отправляем данные в Telegram
    try:
        # Логика отправки
        response = requests.post(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage", data={
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": "order details",
            "parse_mode": "Markdown"
        })
        response.raise_for_status()
        logger.info(f"Order {self.id} successfully sent to Telegram.")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending order {self.id} to Telegram: {e}")
        return False

def telegram_webhook(request):
    if request.method == "POST":
        # Обрабатывайте данные из Telegram
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "invalid request"}, status=400)

@login_required
def repeat_order(request, order_id):
    """Повторное оформление заказа"""
    # Получаем заказ из истории
    order_history = get_object_or_404(OrderHistory, id=order_id, user=request.user)

    # Создаем новую корзину для повторного заказа
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart.items.all().delete()  # Очищаем корзину, чтобы добавить элементы текущего заказа

    # Добавляем элемент из истории заказа в корзину
    CartItem.objects.create(
        cart=cart,
        flower=order_history.flower,
        quantity=order_history.quantity  # Используем количество из истории заказа
    )

    # Создаем новый заказ
    new_order = Order.objects.create(
        user=request.user,
        cart=cart,
        flower=order_history.flower,
        quantity=order_history.quantity,
        delivery_date=order_history.delivery_date,
        delivery_time=order_history.delivery_time,
        address=order_history.delivery_address,
        comment=order_history.comment
    )

    # Перенаправляем на страницу оплаты
    return redirect('payment_window', order_id=new_order.id)


@login_required
def order_history(request):
    """Отображение истории заказов пользователя"""
    orders = OrderHistory.objects.filter(user=request.user).order_by('-completed_at')  # Получаем заказы пользователя
    return render(request, 'orders/order_history.html', {'orders': orders})

def signup(request):
    """Регистрация нового пользователя"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

def flower_detail(request, flower_id):
    """Детальная страница для каждого цветка с отзывами и рейтингами"""
    flower = get_object_or_404(Flower, id=flower_id)
    reviews = flower.reviews.all()  # Все отзывы для текущего цветка
    average_rating = flower.reviews.aggregate(Avg('rating'))['rating__avg'] or 0

    if request.method == 'POST':
        rating = int(request.POST.get('rating'))
        comment = request.POST.get('comment')

        if 1 <= rating <= 5:  # Проверка валидности рейтинга
            review = Review.objects.create(
                flower=flower,
                user=request.user,
                rating=rating,
                comment=comment
            )
            return redirect('flower_detail', flower_id=flower.id)

    return render(request, 'orders/flower_detail.html', {
        'flower': flower,
        'reviews': reviews,
        'average_rating': average_rating,
    })

# Страница с отзывами
def view_reviews(request, flower_id):
    flower = get_object_or_404(Flower, id=flower_id)
    reviews = Review.objects.filter(flower=flower)  # Предположим, у вас есть модель Review
    return render(request, 'flower_reviews.html', {'flower': flower, 'reviews': reviews})

def flower_rating(request):
    return render(request, 'flower_rating.html')

# Страница для добавления рейтинга
def add_rating(request, flower_id):
    flower = get_object_or_404(Flower, id=flower_id)
    if request.method == 'POST':
        form = RatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.flower = flower
            rating.user = request.user
            rating.save()
            return redirect('view_reviews', flower_id=flower.id)
    else:
        form = RatingForm()

    return render(request, 'add_rating.html', {'flower': flower, 'form': form})
@login_required(login_url='/accounts/login/')
def generate_report(request):
    """Генерация отчета по заказам за текущий день"""
    today = timezone.now().date()

    total_orders = Order.objects.filter(created_at__date=today).count()
    total_sales = Order.objects.filter(created_at__date=today).aggregate(models.Sum('total_price'))[
                      'total_price__sum'] or 0
    total_revenue = total_sales
    total_expenses = 1000  # Примерные расходы на доставку или другие расходы
    profit = total_revenue - total_expenses

    report = Report.objects.create(
        total_orders=total_orders,
        total_sales=total_sales,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        profit=profit
    )

    return render(request, 'orders/report.html', {
        'report': report
    })



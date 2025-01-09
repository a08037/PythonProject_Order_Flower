import logging
import os
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from .models import Flower, Order, Cart, CartItem, Review, Report, OrderHistory
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.utils import timezone
from django.db.models import Sum
from aiogram import Bot
from aiogram.types import Message
from aiogram.filters import Command

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

def confirm_order(request):
    """Подтверждение заказа для авторизованных пользователей и гостей"""
    if request.user.is_authenticated:
        cart = get_object_or_404(Cart, user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart = get_object_or_404(Cart, session_key=session_key)

    if request.method == 'POST':
        delivery_date = request.POST.get('delivery_date')
        delivery_time = request.POST.get('delivery_time')
        address = request.POST.get('address')

        if not delivery_date or not delivery_time or not address:
            return render(request, 'orders/confirm_order.html', {'cart': cart, 'error': 'Все поля должны быть заполнены.'})

        # Создаём заказ
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            cart=cart,
            delivery_date=delivery_date,
            delivery_time=delivery_time,
            address=address,
            guest_email=guest_email if not request.user.is_authenticated else None,
            guest_phone=guest_phone if not request.user.is_authenticated else None
        )

        logger.info(f"Вызов метода send_to_telegram для заказа {order.id}")

        order.send_to_telegram()  # убедитесь, что эта строка вызывается

        return redirect('payment_window', order_id=order.id)  # Перенаправление на страницу оплаты

    return render(request, 'orders/confirm_order.html', {'cart': cart})

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

    return redirect('cart')

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

def payment_window(request, order_id):
    """Окно оплаты"""
    order = get_object_or_404(Order, id=order_id)

    logger.info(f"User {request.user} is viewing payment window for order {order.id}.")

    if request.method == 'POST':
        payment_successful = True  # Пример: если оплата прошла успешно

        if payment_successful:
            order.cart.delete()  # Очищаем корзину после успешной оплаты
            logger.info(f"Payment for order {order.id} was successful.")
            return redirect('index')
        else:
            logger.warning(f"Payment for order {order.id} failed.")
            return render(request, 'orders/payment_window.html', {'order': order, 'error': 'Оплата не прошла.'})

    return render(request, 'orders/payment_window.html', {'order': order})

@login_required(login_url='/accounts/login/')
def remove_from_cart(request, cart_item_id):
    """Удаление элемента из корзины"""
    cart_item = get_object_or_404(CartItem, id=cart_item_id)
    cart_item.delete()

    logger.info(f"User {request.user} removed item with ID {cart_item.id} from their cart.")

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
    average_rating = flower.reviews.aggregate(models.Avg('rating'))['rating__avg'] or 0

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


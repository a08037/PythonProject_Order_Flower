import logging
import asyncio
import os
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flower_delivery.settings')
import django

django.setup()

from aiogram import Bot, Dispatcher, types
from django.utils import timezone
from aiogram.filters import Command
from aiogram.types import Message
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from orders.models import Flower, OrderHistory, Report, Order
from asgiref.sync import sync_to_async
from datetime import datetime
import aiofiles
from asgiref.sync import sync_to_async

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
# Применение sync_to_async для работы с Django ORM
@sync_to_async
def get_flower_by_id(id):
    try:
        return Flower.objects.get(id=id)
    except Flower.DoesNotExist:
        return None
@sync_to_async
def get_orders_by_status(status):
    return Order.objects.filter(status=status)

# Стартовый обработчик
@dp.message(Command('start'))
async def send_welcome(message: Message):
    logger.info(f"User {message.from_user.id} sent the /start command")
    await message.answer("Здравствуйте! Я ваш помощник для получения заказов!")

# Обработчик команды /help с инструкциями
@dp.message(Command("help"))
async def send_help(message: Message):
    help_text = (
        "Доступные команды:\n\n"
        "/start - Начать взаимодействие с ботом\n"
        "/repeat_order <order_id> - Повторить заказ по ID\n"
        "/status_order <order_id> - Получить статус заказа\n"
        "/report - Генерация отчета по заказам\n"
        "/help - Показать доступные команды\n\n"
        "Инструкции:\n"
        "- Для команды /report используйте даты в формате: YYYY-MM-DD, например: /report 2024-01-01 2024-01-31\n"
        "- Если не знаете ID заказа, попробуйте найти его в истории заказов на сайте.\n"
        "- Для получения статуса всех заказов, находящихся на исполнении, используйте команду /status."
    )
    await message.answer(help_text, parse_mode='Markdown')

# Обработчик для вывода статусов всех заказов "на исполнении"
@dp.message(Command('status'))
async def status_execution(message: Message):
    orders = Order.objects.filter(status='pending')  # Статус "на исполнении"
    if not orders:
        await message.answer("На данный момент нет заказов в статусе 'на исполнении'.")
        return

    statuses = "\n".join([f"Заказ ID: {order.id}, Статус: {order.status}" for order in orders])
    await message.answer(f"Заказы на исполнении:\n{statuses}")

# Обработчик команды /status_order для получения статуса заказа по ID
@dp.message(Command('status_order'))
async def status_order(message: Message):
    try:
        order_id = int(message.text.split()[1])
        order = await get_order_by_id(order_id)

        if not order:
            await message.answer("Заказ с таким ID не найден.")
            return

        await message.answer(f"Статус заказа {order.id}: {order.status}")

    except IndexError:
        await message.answer("Пожалуйста, укажите ID заказа для получения статуса, например: /status_order 3")
    except ValueError:
        await message.answer("ID заказа должно быть числом.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await message.answer("Произошла ошибка, пожалуйста, попробуйте позже.")

# Обработчик команды /repeat_order для повторного оформления заказа
@dp.message(Command('repeat_order'))
async def repeat_order(message: Message):
    try:
        # Получаем заказ из истории по ID
        order_id = int(message.text.split()[1])
        order_history = await get_order_history_by_id(order_id)

        if not order_history:
            await message.answer("Заказ с таким ID не найден.")
            return

        # Создаем новый заказ на основе истории
        cart, created = Cart.objects.get_or_create(user=message.from_user)
        CartItem.objects.create(
            cart=cart,
            flower=order_history.flower,
            quantity=order_history.quantity
        )

        new_order = Order.objects.create(
            user=message.from_user,
            cart=cart,
            flower=order_history.flower,
            quantity=order_history.quantity,
            delivery_date=order_history.delivery_date,
            delivery_time=order_history.delivery_time,
            address=order_history.delivery_address,
            comment=order_history.comment
        )

        await message.answer(f"Ваш заказ {new_order.id} был успешно повторен!")

    except IndexError:
        await message.answer("Пожалуйста, укажите ID заказа для повторения, например: /repeat_order 3")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await message.answer("Произошла ошибка, пожалуйста, попробуйте позже.")

# Обработчик команды /report для генерации отчета
@dp.message(Command('report'))
async def generate_report(message: types.Message):
    try:
        # Разбиваем сообщение на два параметра: start_date и end_date
        date_range = message.text.split()[1:]  # Получаем все слова после команды
        if len(date_range) != 2:
            await message.answer("Пожалуйста, укажите диапазон дат в формате: /report <start_date> <end_date>")
            return

        start_date_str, end_date_str = date_range
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Создаем отчет и выполняем расчеты
        report = Report.objects.create(
            start_date=start_date,
            end_date=end_date
        )
        report.calculate_report()

        # Отправка отчета пользователю
        report_text = (
            f"Отчет за период с {start_date} по {end_date}:\n"
            f"Общее количество заказов: {report.total_orders}\n"
            f"Общий объем продаж: {report.total_sales} ₽\n"
            f"Общий доход: {report.total_revenue} ₽\n"
            f"Общие расходы: {report.total_expenses} ₽\n"
            f"Прибыль: {report.profit} ₽"
        )

        await message.answer(report_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при генерации отчета: {e}")
        await message.answer("Произошла ошибка при генерации отчета, попробуйте позже.")


# Основная функция запуска
async def main():
    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Бот остановлен")

# Запуск бота
if __name__ == '__main__':
    import asyncio
    asyncio.run(main())

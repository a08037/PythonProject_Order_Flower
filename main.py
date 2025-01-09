import os
import sys
# Добавляем путь к Django проекту
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'flower_delivery')))

# Настроим Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "flower_delivery.settings")

# Инициализируем Django
import django
django.setup()

from orders.models import Flower, Order
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.utils import executor
from django.conf import settings

# Настройка логирования
import logging
logging.basicConfig(level=logging.INFO)

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Здравствуйте! Я бот для оформления заказов.")

@dp.message_handler(commands=['order'])
async def order(message: types.Message):
    # Пример обработки заказа
    await message.reply("Ваш заказ принят!")

def start_bot():
    """Запуск Telegram бота"""
    executor.start_polling(dp, skip_updates=True)

def main():
    """Основная функция для запуска всех процессов"""
    print("Запуск проекта...")

    # Можно добавить сюда вызов логики для бота или других задач
    start_bot()

if __name__ == '__main__':
    main()

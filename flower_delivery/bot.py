import logging
import asyncio
import os
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flower_delivery.settings')  # Указание настроек Django
import django

django.setup()
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from config import TOKEN, TELEGRAM_CHAT_ID
from orders.models import Flower, OrderHistory, Report  # Добавил необходимые модели
from asgiref.sync import sync_to_async  # Для асинхронных запросов к базе данных

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()  # Инициализация диспетчера без аргументов
dp["bot"] = bot  # Внедрение объекта `bot` для совместимости с aiogram v3

# Применение sync_to_async для работы с Django ORM в асинхронных функциях
@sync_to_async
def get_flower_by_id(id):
    try:
        return Flower.objects.get(id=id)
    except Flower.DoesNotExist:
        return None

# Стартовый обработчик
@dp.message(Command('start'))
@dp.message(Command('help'))
async def send_welcome(message: Message):
    logger.info(f"User {message.from_user.id} sent the /start command")
    await message.answer("Здравствуйте! Я ваш помощник для получения заказов!")


# Функция отправки информации о заказе в Telegram
async def send_order_to_telegram(order_data):
    logger.info(f"Отправка сообщения с ID {order_data['flower_name']} в Telegram.")
    text = (
        f"Получен новый заказ!\n\n"
        f"🌸 Букет: {order_data['flower_name']}\n"
        f"💰 Стоимость: {order_data['cost']} ₽\n"
        f"📅 Дата доставки: {order_data['delivery_date']}\n"
        f"🕑 Время доставки: {order_data['delivery_time']}\n"
        f"📍 Адрес доставки: {order_data['delivery_address']}\n"
        f"💬 Комментарий: {order_data.get('comment', 'Без комментариев')}"
    )

    try:
        # Если работаем локально
        if settings.SITE_URL.startswith("http://127.0.0.1"):
            flower_image_path = os.path.join(settings.MEDIA_ROOT, order_data['flower_image'].lstrip('/media/'))
            logger.info(f"Local image path: {flower_image_path}")
            if os.path.exists(flower_image_path):
                with open(flower_image_path, 'rb') as photo:
                    await bot.send_photo(TELEGRAM_CHAT_ID, photo, caption=text, parse_mode='Markdown')
                    logger.info("Сообщение успешно отправлено в Telegram.")
            else:
                logger.error(f"Файл не найден: {flower_image_path}")
                await bot.send_message(TELEGRAM_CHAT_ID, f"Не удалось отправить картинку: {order_data['flower_name']}")

        # Если используем ngrok или удаленный URL
        else:
            flower_image_url = f"{settings.SITE_URL}{order_data['flower_image'].lstrip('/')}"
            await bot.send_photo(TELEGRAM_CHAT_ID, flower_image_url, caption=text, parse_mode='Markdown')

        logger.info("Order data sent successfully to Telegram.")
    except Exception as e:
        logger.error(f"Ошибка отправки заказа в Telegram: {e}")
# Обработчик получения информации о заказе
@dp.message(Command('order'))
async def order(message: Message):
    try:
        flower_id = int(message.text.split()[1])
        flower = await get_flower_by_id(flower_id)

        if not flower:
            await message.answer("Букет с таким ID не найден.")
            return

        order_data = {
            "flower_image": flower.image.url,
            "flower_name": flower.name,
            "cost": flower.price,
            "delivery_date": "2024-12-25",
            "delivery_time": "14:00",
            "delivery_address": "Москва, ул. Примерная, 10",
            "comment": "Поздравляю с праздником!"
        }

        text = (
            f"Ваш заказ:\n\n"
            f"🌸 Букет: {order_data['flower_name']}\n"
            f"💰 Стоимость: {order_data['cost']} ₽\n"
            f"📅 Дата доставки: {order_data['delivery_date']}\n"
            f"🕑 Время доставки: {order_data['delivery_time']}\n"
            f"📍 Адрес доставки: {order_data['delivery_address']}\n"
            f"💬 Комментарий: {order_data['comment']}"
        )

        await message.answer_photo(order_data["flower_image"], caption=text, parse_mode=ParseMode.MARKDOWN)
        await send_order_to_telegram(order_data)

    except IndexError:
        await message.answer("Пожалуйста, укажите ID букета, например: /order 3")
    except ValueError:
        await message.answer("ID букета должно быть числом.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await message.answer("Произошла ошибка, пожалуйста, попробуйте позже.")


# Команда /repeat_order для повторного оформления заказа
@dp.message(Command('repeat_order'))
async def repeat_order(message: Message):
    try:
        last_order = await sync_to_async(lambda: OrderHistory.objects.filter(user__id=message.from_user.id).order_by('-completed_at').first())()

        if last_order:
            order_data = {
                "flower_image": last_order.flower.image.url,
                "flower_name": last_order.flower.name,
                "cost": last_order.cost,
                "delivery_date": last_order.delivery_date,
                "delivery_time": last_order.delivery_time,
                "delivery_address": last_order.delivery_address,
                "comment": last_order.comment or "Без комментариев"
            }

            await message.answer_photo(order_data["flower_image"],
                                       caption=f"Повторный заказ: {order_data['flower_name']}\nСтоимость: {order_data['cost']} руб",
                                       parse_mode=ParseMode.MARKDOWN)
            await send_order_to_telegram(order_data)
        else:
            await message.answer("Вы еще не делали заказ.")
    except Exception as e:
        logger.error(f"Error while repeating order: {e}")
        await message.answer("Произошла ошибка, попробуйте позже.")


# Команда /report для получения отчета о заказах
@dp.message(Command('report'))
async def send_report(message: Message):
    try:
        report = await sync_to_async(lambda: Report.objects.filter(date=django.utils.timezone.now().date()).first())()

        if report:
            text = (
                f"Отчет за {report.date}:\n"
                f"Общее количество заказов: {report.total_orders}\n"
                f"Общий объем продаж: {report.total_sales} руб\n"
                f"Общий доход: {report.total_revenue} руб\n"
                f"Общие расходы: {report.total_expenses} руб\n"
                f"Прибыль: {report.profit} руб"
            )
        else:
            text = "Отчетов за сегодня нет."

        await message.answer(text)

    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await message.answer("Произошла ошибка при получении отчета.")


# Основная функция для запуска бота
async def main():
    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Бот остановлен")


if __name__ == '__main__':
    asyncio.run(main())

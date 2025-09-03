from faststream import FastStream, Context
from faststream.redis import RedisBroker
from os import getenv
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from src.infrastructure.logging.logger_setup import *
from aiogram.exceptions import TelegramNotFound, TelegramBadRequest
load_dotenv()

redis_broker = RedisBroker(getenv('REDIS_URL'))
faststream = FastStream(redis_broker)

telegram_service = None

class AlertMessage(BaseModel):
    user_id: int = Field(..., description="ID пользователя")
    text: str = Field(..., description="Текст сообщения для отправки")


from aiogram.exceptions import TelegramBadRequest, TelegramNotFound


@redis_broker.subscriber(stream='alerts')
async def alerts_subscriber(message: AlertMessage):
    info(f"Сообщение для пользователя {message.user_id} пришло из FastStream")

    if telegram_service is None:
        error("TelegramService не инициализирован!")
        return

    try:
        success = await telegram_service.send_message(user_id=message.user_id, text=message.text)
        if success:
            info(f"Сообщение для пользователя {message.user_id} успешно отправлено")
        else:
            error(f"Сообщение для пользователя {message.user_id} не удалось отправить")

    except TelegramBadRequest as e:
        if "chat not found" in str(e).lower():
            error(f"Пользователь {message.user_id} не найден заблокировал бота")
            #   добавить логику очистки пользователя из БД
        else:
            error(f"Ошибка Telegram API для пользователя {message.user_id}: {e}")

    except TelegramNotFound as e:
        error(f"Пользователь {message.user_id} не найден: {e}")
        # пользователь не начинал диалог с ботом

    except Exception as e:
        error(f"Неожиданная ошибка при отправке пользователю {message.user_id}: {e}")


@faststream.on_startup
async def on_startup():
    info("FastStream запущен")

@faststream.on_shutdown
async def on_shutdown():
    info("FastStream остановлен")


async def run_faststream(service):
    global telegram_service
    telegram_service = service

    try:
        await faststream.run()
    except Exception as e:
        error(f"Ошибка при запуске FastStream: {e}")
        raise
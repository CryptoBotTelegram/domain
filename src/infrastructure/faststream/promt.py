from src.infrastructure.faststream.alerts import redis_broker
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import json
from src.infrastructure.logging.logger_setup import *
from aiogram.exceptions import TelegramNotFound, TelegramBadRequest
load_dotenv()


telegram_service = None
class PromtMessage(BaseModel):
    user_id: int = Field(..., description="ID пользователя")
    text: str = Field(..., description="Текст сообщения для отправки")


async def send_promt_message(message: PromtMessage):
    message = message.model_dump_json()
    await redis_broker.publish('promt', message)
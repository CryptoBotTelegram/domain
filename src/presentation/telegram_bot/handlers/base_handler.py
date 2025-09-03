# src/presentation/telegram_bot/handlers/base_handler.py
from aiogram import types, Router, Bot
from src.infrastructure.logging.logger_setup import *
from redis import asyncio as aioredis
import os
from dotenv import load_dotenv
import json
import asyncio
from src.infrastructure.repository.mariadb.user_repo import MariaUserRepository
from src.presentation.telegram_bot.handlers.lang_config import subscription_required_message
from shared import UserSettingsDTO
from src.presentation.telegram_bot.handlers.lang_config import subscription_required_message


load_dotenv()

ADMINS = [int(admin_id) for admin_id in os.getenv('ADMINS', '').split(',') if admin_id]

rt = Router()

bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
repository = MariaUserRepository()


class RedisClient:
    def __init__(self):
        self.redis = None
        self.redis_password = os.getenv('REDIS_PASSWORD')
        self.redis_host = os.getenv('REDIS_HOST', 'redis')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.is_connected = False

    async def connect(self):
        try:
            if self.is_connected and self.redis:
                return

            self.redis = await aioredis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                decode_responses=True
            )
            # Проверяем подключение
            await self.redis.ping()
            self.is_connected = True
            info("Connected to Redis successfully")
        except Exception as e:
            error(f"Failed to connect to Redis: {e}")
            self.is_connected = False
            raise

    async def send_prompt_message(self, user_id: int, text: str):
        """Отправка сообщения в Redis Stream"""
        try:
            if not self.is_connected:
                await self.connect()

            message_data = {
                'user_id': str(user_id),
                'text': text
            }
            await self.redis.xadd('prompt', message_data)
            info(f"Message sent to Redis stream 'prompt' for user {user_id}")

        except Exception as e:
            error(f"Error sending message to Redis: {e}")
            self.is_connected = False
            raise


redis_client = RedisClient()


def is_tag_configuration_response(text: str) -> bool:
    """Проверяет, является ли ответ AI конфигурацией тегов"""
    try:
        # Сначала проверяем, не пустая ли строка
        if not text or not text.strip():
            return False

        # Пытаемся распарсить JSON
        data = json.loads(text)
        return ('specifical_tags' in data and 'general_tags' in data and
                isinstance(data['specifical_tags'], list) and
                isinstance(data['general_tags'], list))
    except (json.JSONDecodeError, TypeError, ValueError):
        return False


async def update_user_tags(user_id: int, ai_response: str) -> bool:
    """Обновляет теги пользователя на основе AI ответа"""
    try:
        data = json.loads(ai_response)
        specifical_tags = data.get('specifical_tags', [])
        general_tags = data.get('general_tags', [])

        # Получаем текущие настройки пользователя
        user = await repository.get_user(user_id)
        if not user:
            error(f"User {user_id} not found for tag update")
            return False

        # Обновляем только теги, сохраняя остальные настройки
        new_settings = UserSettingsDTO(
            LLM_model=user.LLM_model,
            alert_config_general=general_tags,
            alert_config_specific=specifical_tags,
            language=user.language
        )

        success = await repository.set_settings(user_id, new_settings)
        if success:
            info(f"Updated tags for user {user_id}: specific={specifical_tags}, general={general_tags}")
        else:
            error(f"Failed to update tags for user {user_id}")

        return success

    except Exception as e:
        error(f"Error updating user tags: {e}")
        return False


@rt.message()
async def handle_text_message(message: types.Message):
    try:
        if message.text.startswith('/'):
            return

        # Получаем информацию о пользователе
        user = await repository.get_user(message.from_user.id)
        if not user:
            await message.answer("Пожалуйста, сначала зарегистрируйтесь с помощью /start")
            return

        # Проверяем актуальность статуса подписки
        subscription_active = await repository.check_subscription_status(user.telegram_id)
        if not subscription_active:
            await message.answer(subscription_required_message[user.language])
            return

        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

        # Отправляем сообщение в Redis Stream
        await redis_client.send_prompt_message(message.from_user.id, message.text)

        info(f"Сообщение от пользователя {message.from_user.id} отправлено в Redis Stream 'prompt'")

    except Exception as e:
        TGLog(f'Ошибка при обработке текстового сообщения: {e}')
        error(f'Ошибка при обработке текстового сообщения: {e}')


# Обработчик ответов от AI
async def listen_for_ai_responses():
    try:
        await redis_client.connect()
        info("Started listening for AI responses")

        # Используем '$' для чтения только новых сообщений
        last_id = '$'
        retry_count = 0
        max_retries = 3

        while True:
            try:
                # Слушаем ответы из stream 'prompt_response'
                messages = await redis_client.redis.xread(
                    {'prompt_response': last_id}, count=10, block=5000
                )

                if messages:
                    retry_count = 0  # Сброс счетчика повторных попыток при успешном чтении
                    for stream, message_list in messages:
                        for message_id, message_data in message_list:
                            try:
                                user_id_str = message_data.get('user_id')
                                text = message_data.get('text')

                                if not user_id_str or not text:
                                    continue

                                user_id = int(user_id_str)

                                info(f"Received AI response for user {user_id}: {text[:100]}...")

                                if is_tag_configuration_response(text):
                                    # Это конфигурация тегов - обновляем настройки
                                    success = await update_user_tags(user_id, text)

                                    if success:
                                        # Отправляем сообщение об успешном обновлении
                                        user = await repository.get_user(user_id)
                                        language = user.language if user else 'ru'

                                        if language == 'ru':
                                            response_text = "✅ Ваши настройки уведомлений успешно обновлены!"
                                        else:
                                            response_text = "✅ Your notification settings have been successfully updated!"

                                        await bot.send_message(chat_id=user_id, text=response_text)
                                        info(f"Tag configuration applied for user {user_id}")
                                    else:
                                        error_message = "❌ Не удалось обновить настройки. Попробуйте позже." if (
                                                    user and user.language == 'ru') else "❌ Failed to update settings. Please try again later."
                                        await bot.send_message(chat_id=user_id, text=error_message)
                                else:
                                    # Это обычный ответ AI - отправляем как есть
                                    await bot.send_message(chat_id=user_id, text=text)
                                    info(f"Regular AI response sent to user {user_id}")

                                # Обновляем last_id для следующего чтения
                                last_id = message_id

                            except Exception as e:
                                error(f"Error processing AI response for message {message_id}: {e}")
                                continue
                else:
                    # Если сообщений нет, ждем
                    await asyncio.sleep(1)

            except Exception as e:
                error(f"Error reading from Redis stream: {e}")
                retry_count += 1

                if retry_count >= max_retries:
                    error("Max retries reached, reconnecting to Redis...")
                    await redis_client.connect()
                    retry_count = 0
                    last_id = '$'  # Сбрасываем на чтение новых сообщений

                await asyncio.sleep(5)

    except Exception as e:
        error(f"Fatal error in listen_for_ai_responses: {e}")
        # Перезапускаем задачу через некоторое время
        await asyncio.sleep(10)
        await asyncio.create_task(listen_for_ai_responses())


# Глобальная переменная для хранения задачи
ai_listener_task = None


# Функция для запуска слушателя
def start_ai_listener():
    global ai_listener_task
    if ai_listener_task is None or ai_listener_task.done():
        ai_listener_task = asyncio.create_task(listen_for_ai_responses())
        info("AI listener task started")


# Запускаем слушатель при импорте модуля
start_ai_listener()
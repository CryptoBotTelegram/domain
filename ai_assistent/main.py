# ai_alerts/main.py
import json
import asyncio
from redis import asyncio as aioredis
from ai_assistent import request_ai
import os
from dotenv import load_dotenv
import logging
import sys

load_dotenv()


# Настройка логирования
def setup_logging():
    logger = logging.getLogger('ai_processor')
    logger.setLevel(logging.INFO)

    # Форматтер
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Консольный handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # File handler
    file_handler = logging.FileHandler('ai_processor.log')
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# Создаем логгер
logger = setup_logging()


def info(msg):
    logger.info(msg)


def error(msg):
    logger.error(msg)


def warn(msg):
    logger.warning(msg)


def debug(msg):
    logger.debug(msg)


class AIProcessor:
    def __init__(self):
        self.redis = None
        self.redis_password = os.getenv('REDIS_PASSWORD')
        self.redis_host = os.getenv('REDIS_HOST', 'redis')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))

    async def connect_redis(self):
        """Подключение к Redis"""
        try:
            self.redis = await aioredis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                decode_responses=True
            )
            # Проверяем подключение
            await self.redis.ping()
            info("Connected to Redis successfully")
        except Exception as e:
            error(f"Failed to connect to Redis: {e}")
            raise

    async def process_prompt_messages(self):
        """Обработка сообщений из Redis Stream"""
        try:
            info("Starting to process prompt messages from Redis stream")

            while True:
                try:
                    # Читаем сообщения из stream 'prompt'
                    messages = await self.redis.xread(
                        {'prompt': '0'}, count=10, block=5000
                    )

                    if messages:
                        info(f"Received {len(messages[0][1])} messages from prompt stream")

                        for stream, message_list in messages:
                            for message_id, message_data in message_list:
                                try:
                                    # Обрабатываем сообщение
                                    user_id = message_data.get('user_id')
                                    text = message_data.get('text')

                                    if user_id and text:
                                        info(f"Processing AI request from user {user_id}: {text[:50]}...")

                                        # Отправляем запрос к AI
                                        ai_response = request_ai(text)
                                        info(f"AI response generated for user {user_id}")

                                        # Отправляем ответ обратно в stream 'prompt_response'
                                        response_data = {
                                            'user_id': user_id,
                                            'text': ai_response
                                        }

                                        await self.redis.xadd(
                                            'prompt_response',
                                            response_data
                                        )

                                        info(f"AI response sent to prompt_response stream for user {user_id}")

                                    # Удаляем обработанное сообщение
                                    await self.redis.xdel('prompt', message_id)
                                    debug(f"Message {message_id} deleted from prompt stream")

                                except Exception as e:
                                    error(f"Error processing message {message_id}: {e}")
                                    continue
                    else:
                        debug("No messages in prompt stream, waiting...")

                    await asyncio.sleep(1)

                except Exception as e:
                    error(f"Error in message processing loop: {e}")
                    # Переподключаемся при ошибке
                    await asyncio.sleep(5)
                    await self.connect_redis()

        except Exception as e:
            error(f"Fatal error in process_prompt_messages: {e}")
            raise

    async def run(self):
        """Запуск микросервиса"""
        try:
            await self.connect_redis()
            info("AI Processor started successfully")

            # Запускаем обработку сообщений
            await self.process_prompt_messages()

        except KeyboardInterrupt:
            info("AI Processor stopped by user")
        except Exception as e:
            error(f"AI Processor failed: {e}")
            raise
        finally:
            await self.close()

    async def close(self):
        """Корректное закрытие подключений"""
        if self.redis:
            await self.redis.close()
            info("Redis connection closed")


async def main():
    processor = AIProcessor()
    try:
        await processor.run()
    except KeyboardInterrupt:
        info("Application stopped by user")
    except Exception as e:
        error(f"Application failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    info("Starting AI Processor application")
    asyncio.run(main())
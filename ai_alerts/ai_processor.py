# ai_alerts/ai_processor.py
import asyncio
import json
import logging
import re
import time
from redis import asyncio as aioredis
from os import getenv
from dotenv import load_dotenv
from request_ai import request

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Конфигурация ограничения частоты
RATE_LIMIT = {
    'max_news_per_minute': 3,  # Максимум 3 новости в минуту
    'last_news_time': 0,
    'news_count': 0
}


def fix_json_response(response):
    """Исправляет JSON ответ от ИИ, заменяя одинарные кавычки на двойные и экранируя внутренние кавычки"""
    # Убираем возможные markdown обрамления
    response = response.strip()
    if response.startswith('```json'):
        response = response[7:]
    if response.endswith('```'):
        response = response[:-3]

    # Заменяем одинарные кавычки на двойные
    response = response.replace("'", '"')

    # Экранируем внутренние двойные кавычки в текстовых полях
    response = re.sub(r'("text":\s*")([^"]*)(")',
                      lambda m: m.group(1) + m.group(2).replace('"', '\\"') + m.group(3),
                      response)

    # Исправляем возможные проблемы с запятыми
    response = re.sub(r',\s*}', '}', response)
    response = re.sub(r',\s*]', ']', response)

    return response


async def should_process_message():
    """Проверяет, можно ли обрабатывать следующее сообщение с учетом ограничения частоты"""
    current_time = time.time()
    elapsed_time = current_time - RATE_LIMIT['last_news_time']

    # Если прошла минута, сбрасываем счетчик
    if elapsed_time >= 60:
        RATE_LIMIT['news_count'] = 0
        RATE_LIMIT['last_news_time'] = current_time

    # Проверяем, не превышен ли лимит
    if RATE_LIMIT['news_count'] >= RATE_LIMIT['max_news_per_minute']:
        wait_time = 60 - elapsed_time
        logger.info(f"Rate limit exceeded. Waiting {wait_time:.1f} seconds...")
        await asyncio.sleep(wait_time)
        RATE_LIMIT['news_count'] = 0
        RATE_LIMIT['last_news_time'] = time.time()

    return True


async def process_stream():
    # Подключаемся к Redis
    redis_password = getenv('REDIS_PASSWORD')
    redis_host = getenv('REDIS_HOST', 'redis')
    redis_port = int(getenv('REDIS_PORT', 6379))

    redis = await aioredis.from_url(
        f"redis://:{redis_password}@{redis_host}:{redis_port}",
        decode_responses=True
    )

    try:
        logger.info("AI Processor started. Listening for messages...")

        # Создаем потребительскую группу если её нет
        try:
            await redis.xgroup_create("api_alerts", "ai_processor_group", id="0", mkstream=True)
        except Exception as e:
            logger.info(f"Consumer group already exists: {e}")

        while True:
            try:
                # Проверяем ограничение частоты перед обработкой
                await should_process_message()

                # Читаем данные из стрима api_alerts с помощью потребительской группы
                messages = await redis.xreadgroup(
                    groupname="ai_processor_group",
                    consumername="ai_consumer",
                    streams={"api_alerts": ">"},
                    count=1,
                    block=5000
                )

                if not messages:
                    continue

                stream, message_list = messages[0]
                message_id, message_data = message_list[0]

                # Извлекаем и парсим данные
                data_str = message_data["data"]
                data = json.loads(data_str)

                logger.info(f"Received data for processing: {message_id}")

                # Формируем запрос к ИИ
                ai_prompt = f"""
                Проанализируй эти данные криптовалютного рынка и создай краткую новость или аналитическую заметку.
                Данные: {json.dumps(data, ensure_ascii=False, indent=2)}

                Верни ответ в формате JSON массива:
                [
                  {{
                    "text": "Текст новости/анализа",
                    "tags": ["tag1", "tag2", "tag3"],
                    "priority": "high/medium/low"
                  }},
                  {{
                    "text": "Другая новость...",
                    "tags": ["tag4", "tag5"],
                    "priority": "medium"
                  }}
                ]
                """

                # Получаем ответ от ИИ
                ai_response = request(ai_prompt)

                # Исправляем JSON ответ
                fixed_response = fix_json_response(ai_response)

                # Парсим ответ ИИ
                try:
                    news_list = json.loads(fixed_response)

                    # Обрабатываем каждую новость в массиве
                    for news_data in news_list:
                        # Проверяем наличие обязательных полей
                        if not isinstance(news_data, dict) or "text" not in news_data or "tags" not in news_data:
                            logger.error(f"Invalid AI response format: {news_data}")
                            continue

                        # Подготавливаем данные для Redis
                        redis_data = {
                            "text": str(news_data["text"]),
                            "tags": json.dumps(news_data.get("tags", [])),
                            "priority": news_data.get("priority", "medium"),
                            "source_message_id": message_id
                        }

                        # Публикуем в стрим news для Go-обработчика
                        await redis.xadd("news", redis_data)
                        logger.info(f"Processed news: {news_data['text'][:50]}...")

                        # Увеличиваем счетчик обработанных новостей
                        RATE_LIMIT['news_count'] += 1

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}. Response: {fixed_response}")
                except Exception as e:
                    logger.error(f"Error processing AI response: {e}")

                # Подтверждаем обработку сообщения
                await redis.xack("api_alerts", "ai_processor_group", message_id)

            except Exception as e:
                logger.error(f"Processing error: {str(e)}")
                await asyncio.sleep(5)

    except asyncio.CancelledError:
        logger.info("Processor stopped")
    finally:
        await redis.close()
        logger.info("Redis connection closed")


if __name__ == "__main__":
    asyncio.run(process_stream())
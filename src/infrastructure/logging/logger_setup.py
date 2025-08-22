import logging
import asyncio
from aiogram import Bot
from dotenv import load_dotenv
from os import getenv

load_dotenv()

__all__ = [
    'info',
    'warn',
    'debug',
    'error',
    'critical',
    'TG'
]

# Настройки
ADMIN_ID = getenv('ADMIN_ID')
BOT_TOKEN = getenv('TELEGRAM_BOT_TOKEN')

TG = 5
logging.addLevelName(TG, 'TG')

bot = Bot(token=BOT_TOKEN)
message_queue = asyncio.Queue()


async def telegram_worker():
    while True:
        try:
            message = await message_queue.get()
            await bot.send_message(chat_id=ADMIN_ID, text=message)
            await asyncio.sleep(0.1)
        except Exception as e:
            logging.error(f"Ошибка отправки в Telegram: {e}")


class TelegramHandler(logging.Handler):
    def emit(self, record):
        if record.levelno == TG:
            message = self.format(record)
            asyncio.create_task(message_queue.put(message))


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

tg_handler = TelegramHandler()
tg_handler.setLevel(TG)
tg_handler.setFormatter(formatter)
logger.addHandler(tg_handler)

asyncio.create_task(telegram_worker())

info = logging.info
warn = logging.warning
debug = logging.debug
error = logging.error
critical = logging.critical


def TG(message: str):
    logging.log(TG, message)

from aiogram import Bot, Router
from shared import TelegramBotMode
from aiogram.client.default import DefaultBotProperties
from os import getenv
from dotenv import load_dotenv
from typing import Optional
from src.infrastructure.logging.logger_setup import *

load_dotenv()


class TelegramBot:
    def __init__(self, token, mode: TelegramBotMode):
        self.token = token
        self.mode = mode
        self.router = Router()
        self.bot: Optional[Bot] = None
        self.telegram_bot_api_adress = getenv('TELEGRAM_BOT_LOCAL_API_ADRESS')
        self.webhook_url = getenv('WEBHOOK_URL')

    async def init_bot(self):
        match self.mode:
            case TelegramBotMode.POLLING:
                self.bot = Bot(token=self.token, default=DefaultBotProperties(parse_mode='HTML'))
                await self.__delete_webhook()
                info('Bot initialized in polling mode')
            case TelegramBotMode.WEBHOOK:
                self.bot = Bot(token=self.token, default=DefaultBotProperties(parse_mode='HTML'))
                await self.__delete_webhook()
                await self.__set_webhook(self.webhook_url)
                info('Bot initialized in webhook mode')
            case TelegramBotMode.WEBHOOK_LOCAL:
                self.bot = Bot(token=self.token, default=DefaultBotProperties(parse_mode='HTML'), session=await self._get_local_webhook_session())
                await self.__delete_webhook()
                await self.__set_webhook(self.webhook_url)
                info('Bot initialized in webhook local mode')
            case TelegramBotMode.TEST:
                self.bot = Bot(token=self.token, default=DefaultBotProperties(parse_mode='HTML'))
                await self.__delete_webhook()
                info('Bot initialized in test mode')
            case _:
                raise ValueError(f'Unknown mode: {self.mode}')

    async def _get_local_webhook_session(self):
        from aiogram.client.session.aiohttp import AiohttpSession
        from aiogram.client.telegram import TelegramAPIServer
        local_server = TelegramAPIServer.from_base(self.telegram_bot_api_adress)
        session = AiohttpSession(api=local_server)
        return session

    async def __delete_webhook(self):
        await self.bot.delete_webhook()

    async def __set_webhook(self, url):
        await self.bot.set_webhook(url=url, secret_token=self.token, drop_pending_updates=True, allowed_updates=['message', 'callback_query'], max_connections=100)

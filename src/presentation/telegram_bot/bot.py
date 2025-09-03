from aiogram import Bot, Router, Dispatcher
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
        self._webhook_secret = getenv('WEBHOOK_SECRET')
        self.mode = mode
        self.router = Router()
        self.bot: Optional[Bot] = None
        self.telegram_bot_api_adress = getenv('TELEGRAM_BOT_LOCAL_API_ADRESS')
        self.webhook_url = getenv('WEBHOOK_URL')
        self.dp: Optional[Dispatcher] = None

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

        self.router = Router()
        self.dp = Dispatcher()
        self.dp.include_router(self.router)
        info('Bot initialized!')

        from src.presentation.telegram_bot.handlers.starts_handler import rt as starts_router
        from src.presentation.telegram_bot.handlers.base_handler import rt as base_router
        from src.presentation.telegram_bot.handlers.premium_handler import router as premium_router
        from src.presentation.telegram_bot.handlers.admin_handler import router as admin_router
        self.dp.include_router(admin_router)
        self.dp.include_router(starts_router)
        self.dp.include_router(base_router)
        self.dp.include_router(premium_router)
        return self.bot, self.dp

    async def _get_local_webhook_session(self):
        from aiogram.client.session.aiohttp import AiohttpSession
        from aiogram.client.telegram import TelegramAPIServer
        local_server = TelegramAPIServer.from_base(self.telegram_bot_api_adress)
        session = AiohttpSession(api=local_server)
        return session

    async def __delete_webhook(self):
        await self.bot.delete_webhook()

    async def __set_webhook(self, url):
        await self.bot.set_webhook(url=url, secret_token=self._webhook_secret, drop_pending_updates=True, allowed_updates=['message', 'callback_query'], max_connections=100)
        info(f'Webhook set to {url}')

    async def _run_poling(self):
        if self.mode in (TelegramBotMode.POLLING, TelegramBotMode.TEST):
            await self.dp.start_polling(self.bot)

    async def get_includes_dispatcher(self):
        return self.dp

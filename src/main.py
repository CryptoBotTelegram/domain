from src.presentation.telegram_bot.bot import TelegramBot, TelegramBotMode
from fastapi import FastAPI
import uvicorn
from os import getenv
from dotenv import load_dotenv
from src.infrastructure.logging.logger_setup import *
from src.infrastructure.logging.logger_setup import telegram_worker
from src.infrastructure.faststream.alerts import run_faststream
import asyncio
from contextlib import asynccontextmanager
import sys
import multiprocessing

load_dotenv()


class Application:
    def __init__(self, bot_mode: TelegramBotMode):
        self.server = None
        self.bot = TelegramBot(mode=bot_mode, token=getenv("TELEGRAM_BOT_TOKEN"))
        self.bot_mode = bot_mode
        self.tasks = []
        self.faststream = None
        self.bot_exempl = None
        self.fastapi_app = None
        self.telegram_service = None

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        app.state.application = self
        await self._on_startup(app)
        yield
        await self._on_shutdown()

    async def _on_startup(self, app: FastAPI):
        try:
            info('Start application')
            bot, dp = await self.bot.init_bot()
            app.state.bot = bot
            app.state.dp = dp

            from src.services.telegram.telegram_bot_service import TelegramBotService
            self.telegram_service = TelegramBotService(bot)
            app.state.telegram_service = self.telegram_service

            self.tasks.append(asyncio.create_task(run_faststream(self.telegram_service)))
            if self.bot_mode in (TelegramBotMode.POLLING, TelegramBotMode.TEST):
                self.tasks.append(asyncio.create_task(self.bot._run_poling()))
            self.tasks.append(asyncio.create_task(telegram_worker()))
            info('Application startup complete')

        except Exception as e:
            error(f"Application error: {e}")
            TGLog(f"Application error: {e}")
            raise

    async def _on_shutdown(self):
        info('Application shutting down...')
        for task in self.tasks:
            if not task.done():
                task.cancel()
        try:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        except:
            pass
        info('Application shutdown complete')

    def create_server(self):
        self.fastapi_app = FastAPI(lifespan=self.lifespan)

        from src.presentation.server.routers.webhook import router as webhook_router
        self.fastapi_app.include_router(webhook_router)

        return self.fastapi_app

    async def run(self):
        app = self.create_server()
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8841,
            log_level="info",
            workers=min(multiprocessing.cpu_count() + 2, multiprocessing.cpu_count() - 2)
        )
        self.server = uvicorn.Server(config)
        await self.server.serve()


async def main():
    required_vars = ['TELEGRAM_BOT_TOKEN', 'ADMIN_ID']
    missing_vars = [var for var in required_vars if not getenv(var)]

    if missing_vars:
        error(f"Missing required environment variables: {missing_vars}")
        return

    BOT_MODE = TelegramBotMode.WEBHOOK_LOCAL
    app = Application(BOT_MODE)
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        info("Application stopped by user")
    except Exception as e:
        error(f"Application failed: {e}")
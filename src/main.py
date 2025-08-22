from src.presentation.telegram_bot.bot import TelegramBot, TelegramBotMode
from fastapi import FastAPI
import uvicorn
from os import getenv
from dotenv import load_dotenv
from src.infrastructure.logging.logger_setup import *
from src.infrastructure.logging.logger_setup import telegram_worker
import asyncio
from contextlib import asynccontextmanager
import sys
load_dotenv()


class Application:
    def __init__(self, bot_mode: TelegramBotMode):
        self.server = None
        self.bot = TelegramBot(mode=bot_mode, token=getenv("TELEGRAM_BOT_TOKEN"))
        self.bot_mode = bot_mode
        self.tasks = []

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        await self._on_startup()
        yield
        await self._on_shutdown()

    async def _on_startup(self):
        try:
            info('Start application')
            self.tasks.append(asyncio.create_task(self.bot.init_bot()))
            self.tasks.append(asyncio.create_task(telegram_worker()))
            info('Application startup complete')
        except KeyboardInterrupt as e:
            asyncio.gather().cancel()
            info('Stop application')
        except Exception as e:
            error(f"Application error: {e}")
            TGLog(f"Application error: {e}")

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
        return FastAPI(lifespan=self.lifespan)

    async def run(self):
        import signal
        app = self.create_server()

        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8841,
            log_level="info"
        )
        self.server = uvicorn.Server(config)

        stop_event = asyncio.Event()

        if sys.platform == "win32":
            def signal_handler():
                stop_event.set()

            try:
                loop = asyncio.get_event_loop()
                for sig in [signal.SIGTERM, signal.SIGINT]:
                    try:
                        loop.add_signal_handler(sig, signal_handler)
                    except NotImplementedError:
                        info(f"Signal {sig} not supported on Windows")
            except:
                pass
        else:
            loop = asyncio.get_event_loop()
            for sig in [signal.SIGTERM, signal.SIGINT]:
                loop.add_signal_handler(sig, stop_event.set)

        server_task = asyncio.create_task(self.server.serve())
        stop_task = asyncio.create_task(stop_event.wait())

        done, pending = await asyncio.wait(
            [server_task, stop_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        if stop_task.done():
            info("Received shutdown signal, stopping server...")
            self.server.should_exit = True
            await server_task



BOT_MODE = TelegramBotMode.POLLING
app = Application(BOT_MODE)


async def main():
    required_vars = ['TELEGRAM_BOT_TOKEN', 'ADMIN_ID']
    missing_vars = [var for var in required_vars if not getenv(var)]

    if missing_vars:
        error(f"Missing required environment variables: {missing_vars}")
        return

    app = Application(BOT_MODE)
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        info("Application stopped by user")
    except Exception as e:
        error(f"Application failed: {e}")
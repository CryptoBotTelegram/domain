from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException
from aiogram import types
from src.main import app
from src.infrastructure.logging.logger_setup import *
from os import getenv
from dotenv import load_dotenv
load_dotenv()

WEBHOOK_SECRET = getenv("WEBHOOK_SECRET")

router = APIRouter(prefix="/webhook")

bot = app.bot
dp = app.dp

@router.post('/')
async def bot_webhook(request: Request):
    try:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret and secret != WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid secret")
        data = await request.json()

        update = types.Update(**data)

        await dp.feed_webhook_update(bot, update)
        return {"status": "ok"}

    except Exception as e:
        error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
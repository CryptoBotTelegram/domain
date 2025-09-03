from fastapi import APIRouter, Request, Depends
from fastapi.exceptions import HTTPException
from aiogram import types
from src.infrastructure.logging.logger_setup import *
from os import getenv
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_SECRET = getenv("WEBHOOK_SECRET")

router = APIRouter(prefix="/webhook")


async def get_bot_and_dp(request: Request):
    return request.app.state.bot, request.app.state.dp


@router.post('')
async def bot_webhook(
        request: Request,
        bot_dp: tuple = Depends(get_bot_and_dp)
):
    try:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret and secret != WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid secret")

        data = await request.json()
        update = types.Update(**data)
        bot, dp = bot_dp

        info(f"Processing update: {update.update_id}")

        if dp and bot:
            await dp.feed_webhook_update(bot, update)
            info(f"Update {update.update_id} processed successfully")
            return {"status": "ok"}
        else:
            error("DP or Bot is not initialized!")
            raise HTTPException(status_code=500, detail="Bot not initialized")

    except Exception as e:
        error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
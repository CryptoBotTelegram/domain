# src/presentation/telegram_bot/handlers/payment_handlers.py
from aiogram import Router, Bot
from aiogram.types import PreCheckoutQuery, Message, LabeledPrice
from aiogram.filters import Command
from src.infrastructure.repository.mariadb.user_repo import MariaUserRepository
from src.infrastructure.logging.logger_setup import *
from datetime import datetime, timedelta
from shared import UserFull, User

router = Router()
repository = MariaUserRepository()


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    try:
        # Всегда подтверждаем pre-checkout запрос :cite[6]
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception as e:
        error(f"Ошибка при pre-checkout: {e}")
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False,
                                            error_message="Произошла ошибка при обработке платежа")


@router.message(lambda message: message.successful_payment is not None)
async def successful_payment_handler(message: Message):
    try:
        payment_info = message.successful_payment
        user_id = message.from_user.id

        # Активируем премиум подписку на 30 дней
        user = await repository.get_user(user_id)
        if user:
            # Обновляем пользователя с установкой флага премиум
            updated_user = UserFull(
                user=User(
                    telegram_id=user_id,
                    first_name=user.first_name,
                    username=user.username,
                    is_premium=True,
                    is_admin=user.is_admin
                ),
                settings=user.settings
            )

            success = await repository.update_user(updated_user)
            if success:
                await message.answer("✅ Подписка активирована! Теперь у вас есть полный доступ к AI ассистенту.")
            else:
                await message.answer("❌ Ошибка при активации подписки. Попробуйте позже.")
        else:
            await message.answer("❌ Пользователь не найден. Пожалуйста, начните с /start")
    except Exception as e:
        error(f"Ошибка при обработке успешного платежа: {e}")
        await message.answer("❌ Произошла ошибка при обработке платежа. Свяжитесь с поддержкой.")


@router.message(Command(commands=['paysupport']))
async def pay_support_handler(message: Message):
    support_text = (
        "Если у вас возникли проблемы с оплатой или вам нужен возврат средств, "
        "пожалуйста, свяжитесь с поддержкой через @username_support. "
        "Возврат средств возможен в течение 14 дней с момента оплаты."
    )
    await message.answer(support_text)
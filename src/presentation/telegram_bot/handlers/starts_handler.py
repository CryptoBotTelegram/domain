# starts_handler.py
from aiogram import types, Router, Bot
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from src.presentation.telegram_bot.handlers.lang_config import (start_message, first_message, premium_message,
                                                                subscription_active_message, settings_message)
from src.infrastructure.repository.mariadb.user_repo import MariaUserRepository
from shared import UserFull, LLMModel, UserSettingsDTO, User
from src.infrastructure.logging.logger_setup import *
from datetime import datetime, timedelta


from aiogram.utils.keyboard import InlineKeyboardBuilder

def payment_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить 100 Stars", pay=True)
    return builder.as_markup()

repository = MariaUserRepository()

rt = Router()

language_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="English", callback_data="lang_en"),
     InlineKeyboardButton(text="Русский", callback_data="lang_ru")]
])


@rt.message(Command(commands=['start']))
async def start_handler(message: types.Message, bot: Bot):
    try:
        user = await repository.get_user(telegram_id=message.from_user.id)
        if user is None:
            await message.answer(first_message['ru'], reply_markup=language_keyboard)

            new_user = UserFull(
                user=User(
                    telegram_id=message.from_user.id,
                    first_name=message.from_user.first_name,
                    username=message.from_user.username,
                    is_premium=message.from_user.is_premium or False,
                    is_admin=False
                ),
                settings=UserSettingsDTO(
                    LLM_model=LLMModel.GPT,
                    alert_config_general=[],
                    alert_config_specific=[],
                    language='ru'
                )
            )
            await repository.new_user(new_user)
        else:
            # Получаем информацию о боте для использования в сообщении
            bot_info = await bot.get_me()
            bot_username = bot_info.username

            # Заменяем ____ в сообщении на @username бота
            personalized_message = start_message[user.language].replace('____', f'@{bot_username}')
            await message.answer(personalized_message)
    except Exception as e:
        TGLog(f'Ошибка при /start: {e}')
        error(f'Ошибка при /start: {e}')


@rt.message(Command(commands=['premium']))
async def premium_handler(message: types.Message, bot: Bot):
    try:
        user = await repository.get_user(telegram_id=message.from_user.id)
        if user:
            # Проверяем, есть ли уже подписка
            if user.is_premium:
                await message.answer(subscription_active_message[user.language])
            else:
                # Получаем информацию о боте
                bot_info = await bot.get_me()
                bot_username = bot_info.username

                # Персонализируем сообщение
                personalized_message = premium_message[user.language].replace('____', f'@{bot_username}')

                # Выставляем счет для оплаты :cite[6]
                prices = [LabeledPrice(label="Премиум подписка на 30 дней", amount=100)]

                await message.answer_invoice(
                    title="Премиум подписка",
                    description=personalized_message,
                    provider_token="",  # Для Telegram Stars оставляем пустым
                    currency="XTR",  # Валюта Telegram Stars
                    prices=prices,
                    payload=f"premium_subscription:{message.from_user.id}",
                    reply_markup=payment_keyboard()
                )
        else:
            await message.answer("Пожалуйста, сначала зарегистрируйтесь с помощью /start")
    except Exception as e:
        TGLog(f'Ошибка при обработке /premium: {e}')
        error(f'Ошибка при обработке /premium: {e}')

@rt.message(Command(commands=['settings']))
async def settings_handler(message: types.Message):
    try:
        user = await repository.get_user(telegram_id=message.from_user.id)
        if user:
            await message.answer(settings_message[user.language], parse_mode='Markdown')
        else:
            await message.answer("Пожалуйста, сначала зарегистрируйтесь с помощью /start")
    except Exception as e:
        TGLog(f'Ошибка при обработке /settings: {e}')
        error(f'Ошибка при обработке /settings: {e}')



@rt.callback_query(lambda c: c.data == 'pay_premium')
async def process_pay_premium(callback_query: types.CallbackQuery):
    try:
        user_id = callback_query.from_user.id
        user = await repository.get_user(user_id)

        if user:
            # Здесь должна быть реализация оплаты через Telegram Stars
            # Временно просто активируем премиум доступ
            updated_user = UserFull(
                user=User(
                    telegram_id=user_id,
                    first_name=user.first_name,
                    username=user.username,
                    is_premium=True,  # Активируем премиум
                    is_admin=user.is_admin
                ),
                settings=user.settings
            )

            # Обновляем пользователя в базе
            success = await repository.update_user(updated_user)

            if success:
                await callback_query.message.edit_text(
                    "✅ Подписка активирована! Теперь у вас есть доступ к AI ассистенту.",
                    reply_markup=None
                )
            else:
                await callback_query.message.edit_text(
                    "❌ Ошибка при активации подписки. Попробуйте позже."
                )
        else:
            await callback_query.message.edit_text("Ошибка: пользователь не найден")
    except Exception as e:
        TGLog(f'Ошибка при оплате подписки: {e}')
        error(f'Ошибка при оплате подписки: {e}')
    finally:
        await callback_query.answer()


@rt.callback_query(lambda c: c.data.startswith('lang_'))
async def process_language_callback(callback_query: types.CallbackQuery):
    try:
        language = callback_query.data.split('_')[1]
        user_id = callback_query.from_user.id

        user = await repository.get_user(telegram_id=user_id)
        if user:
            settings = UserSettingsDTO(
                LLM_model=user.LLM_model,
                alert_config_general=user.alert_config_general,
                alert_config_specific=user.alert_config_specific,
                language=language
            )
            await repository.set_settings(user_id, settings)

            confirmation_text = "Язык изменен на русский" if language == 'ru' else "Language changed to English"
            await callback_query.message.edit_text(confirmation_text)
        else:
            await callback_query.message.edit_text("Пользователь не найден")
    except Exception as e:
        TGLog(f'Ошибка при смене языка: {e}')
        error(f'Ошибка при смене языка: {e}')
    finally:
        await callback_query.answer()
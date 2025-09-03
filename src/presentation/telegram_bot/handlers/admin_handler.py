from aiogram import Router, types
from aiogram.filters import Command
from src.infrastructure.repository.mariadb.user_repo import MariaUserRepository
from src.infrastructure.logging.logger_setup import *
from src.presentation.telegram_bot.handlers.base_handler import ADMINS
from datetime import datetime, timedelta
from shared import UserFull, User

router = Router()
repository = MariaUserRepository()

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMINS

@router.message(Command(commands=['add_subscription']))
async def add_subscription_handler(message: types.Message):
    try:
        # Проверяем права администратора
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав для выполнения этой команды")
            return

        # Парсим аргументы команды
        args = message.text.split()
        if len(args) != 3:
            await message.answer("❌ Неправильный формат команды. Используйте: /add_subscription <user_id> <days>")
            return

        user_id = int(args[1])
        days = int(args[2])

        # Получаем пользователя
        user = await repository.get_user(user_id)
        if not user:
            await message.answer(f"❌ Пользователь с ID {user_id} не найден")
            return

        # Обновляем подписку
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
            # Добавляем дни подписки
            await repository.add_subscription_days(user_id, days)
            await message.answer(f"✅ Подписка для пользователя {user_id} успешно добавлена на {days} дней")
        else:
            await message.answer(f"❌ Ошибка при добавлении подписки для пользователя {user_id}")

    except ValueError:
        await message.answer("❌ Неверный формат аргументов. user_id и days должны быть числами")
    except Exception as e:
        error(f"Ошибка в add_subscription_handler: {e}")
        await message.answer("❌ Произошла ошибка при выполнении команды")

@router.message(Command(commands=['admin_help']))
async def admin_help_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return

    help_text = """
🛠️ Команды администратора:

/add_subscription <user_id> <days> - Добавить подписку пользователю
/admin_help - Показать эту справку
    """
    await message.answer(help_text)
# infrastructure/database/repositories/maria_user_repository.py
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from shared import UserFull, UserSettingsDTO
from src.infrastructure.database.models import UserORM, Base
from os import getenv
from dotenv import load_dotenv
from src.infrastructure.logging.logger_setup import *
import datetime
from datetime import timedelta

load_dotenv()


class MariaUserRepository():
    def __init__(self):
        # Получаем параметры подключения из переменных окружения
        db_host = getenv('DB_HOST')
        db_port = getenv('DB_PORT')
        db_name = getenv('DB_NAME')
        db_user = getenv('DB_USER')
        db_password = getenv('DB_ROOT_PASSWORD')

        # Создаем подключение к базе данных
        connection_string = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        self.engine = create_engine(connection_string, echo=True)

        # Создаем таблицы, если они не существуют
        Base.metadata.create_all(self.engine)

        # Создаем сессию
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    async def new_user(self, user: UserFull) -> bool:
        try:
            # Проверяем, существует ли пользователь
            existing_user = self.session.get(UserORM, user.telegram_id)
            if existing_user:
                warn(f"Пользователь с ID {user.telegram_id} уже существует")
                return False

            # Создаем новую ORM-запись
            new_user = UserORM(
                telegram_id=user.telegram_id,
                first_name=user.first_name,
                username=user.username,
                is_premium=user.is_premium,
                is_admin=user.is_admin,
                LLM_model=user.LLM_model.value if hasattr(user.LLM_model, 'value') else user.LLM_model,
                alert_config_general=user.alert_config_general,
                alert_config_specific=user.alert_config_specific,
                language=user.language
            )

            # Добавляем и сохраняем
            self.session.add(new_user)
            self.session.commit()
            info(f"Создан новый пользователь: {user.telegram_id}")
            return True

        except Exception as e:
            error(f"Ошибка при создании пользователя: {e}")
            self.session.rollback()
            return False

    async def get_user(self, telegram_id: int) -> UserFull | None:
        try:
            # Ищем пользователя по ID
            user_orm = self.session.get(UserORM, telegram_id)
            if user_orm:
                return user_orm.to_user_full()
            return None
        except Exception as e:
            error(f"Ошибка при получении пользователя {telegram_id}: {e}")
            return None

    async def set_settings(self, telegram_id: int, settings: UserSettingsDTO) -> bool:
        try:
            # Ищем пользователя
            user_orm = self.session.get(UserORM, telegram_id)
            if not user_orm:
                warn(f"Пользователь {telegram_id} не найден при обновлении настроек")
                return False

            # Обновляем настройки
            user_orm.LLM_model = settings.LLM_model.value if hasattr(settings.LLM_model,
                                                                     'value') else settings.LLM_model
            user_orm.alert_config_general = settings.alert_config_general
            user_orm.alert_config_specific = settings.alert_config_specific
            user_orm.language = settings.language

            # Сохраняем изменения
            self.session.commit()
            info(f"Настройки пользователя {telegram_id} обновлены")
            return True

        except Exception as e:
            error(f"Ошибка при обновлении настроек пользователя {telegram_id}: {e}")
            self.session.rollback()
            return False

    async def add_subscription_days(self, telegram_id: int, days: int) -> bool:
        try:
            from datetime import datetime
            user_orm = self.session.get(UserORM, telegram_id)
            if not user_orm:
                warn(f"Пользователь {telegram_id} не найден при добавлении подписки")
                return False

            # Устанавливаем или обновляем дату окончания подписки
            if user_orm.premium_until and user_orm.premium_until > datetime.now():
                # Если подписка уже активна, добавляем дни к текущей дате
                user_orm.premium_until += timedelta(days=days)
            else:
                # Если подписки нет или она истекла, устанавливаем новую дату
                user_orm.premium_until = datetime.now() + timedelta(days=days)

            user_orm.is_premium = True
            self.session.commit()
            info(f"Добавлено {days} дней подписки пользователю {telegram_id}")
            return True
        except Exception as e:
            error(f"Ошибка при добавлении подписки пользователю {telegram_id}: {e}")
            self.session.rollback()
            return False

    async def delete_subscription(self, telegram_id: int) -> bool:
        # В этой реализации просто возвращаем True, так как в текущей модели нет поля для подписки
        info(f"Подписка пользователя {telegram_id} удалена")
        return True


    async def update_user(self, user: UserFull) -> bool:
        try:
            user_orm = self.session.get(UserORM, user.telegram_id)
            from datetime import datetime, timedelta
            if not user_orm:
                warn(f"Пользователь {user.telegram_id} не найден при обновлении")
                return False

            # Обновляем поля
            user_orm.first_name = user.first_name
            user_orm.username = user.username
            user_orm.is_premium = user.is_premium
            user_orm.is_admin = user.is_admin
            user_orm.LLM_model = user.LLM_model.value if hasattr(user.LLM_model, 'value') else user.LLM_model
            user_orm.alert_config_general = user.alert_config_general
            user_orm.alert_config_specific = user.alert_config_specific
            user_orm.language = user.language

            # Устанавливаем дату окончания подписки (30 дней с момента оплаты)
            if user.is_premium and not user_orm.premium_until:
                user_orm.premium_until = datetime.now() + timedelta(days=30)

            self.session.commit()
            info(f"Данные пользователя {user.telegram_id} обновлены")
            return True

        except Exception as e:
            error(f"Ошибка при обновлении пользователя {user.telegram_id}: {e}")
            self.session.rollback()
            return False

    async def check_subscription_status(self, telegram_id: int) -> bool:
        """Проверяет статус подписки пользователя"""
        try:
            from datetime import datetime
            user_orm = self.session.get(UserORM, telegram_id)
            if user_orm and user_orm.is_premium and user_orm.premium_until:
                # Проверяем, не истекла ли подписка (используем UTC)
                if user_orm.premium_until < datetime.now():
                    user_orm.is_premium = False
                    self.session.commit()
                    return False
                return True
            return False
        except Exception as e:
            error(f"Ошибка при проверке статуса подписки: {e}")
            return False

    def __del__(self):
        # Закрываем сессию при уничтожении объекта
        if hasattr(self, 'session'):
            self.session.close()
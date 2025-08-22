from abc import ABC, abstractmethod
from typing import List
from shared import User, UserSettingsDTO, UserFull


class UserRepository(ABC):
    @abstractmethod
    def new_user(self, user: User) -> bool:
        pass

    @abstractmethod
    def get_user(self, telegram_id: int) -> UserFull:
        pass

    @abstractmethod
    def set_settings(self, telegram_id: int, settings: UserSettingsDTO) -> bool:
        pass

    @abstractmethod
    def add_subscription_days(self, telegram_id: int, days: int) -> bool:
        pass

# infrastructure/database/models.py
from sqlalchemy import Column, Integer, String, Boolean, JSON, BigInteger, Index, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserORM(Base):
    __tablename__ = 'users'

    telegram_id = Column(BigInteger, primary_key=True)
    first_name = Column(String(255), nullable=False)
    username = Column(String(255), nullable=True)
    is_premium = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    LLM_model = Column(String(50), default='gpt')
    alert_config_general = Column(JSON, default=[])
    alert_config_specific = Column(JSON, default=[])
    language = Column(String(10), default='ru')
    premium_until = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('ix_users_telegram_id', 'telegram_id'),
        Index('ix_users_alert_config_general', 'alert_config_general'),
        Index('ix_users_alert_config_specific', 'alert_config_specific'),
        Index('ix_users_language', 'language'),
        Index('ix_users_is_admin', 'is_admin'),
    )

    def to_user_full(self):
        from shared import UserFull, User, UserSettingsDTO, LLMModel
        return UserFull(
            user=User(
                telegram_id=self.telegram_id,
                first_name=self.first_name,
                username=self.username,
                is_premium=self.is_premium,
                is_admin=self.is_admin
            ),
            settings=UserSettingsDTO(
                LLM_model=LLMModel(self.LLM_model),
                alert_config_general=self.alert_config_general,
                alert_config_specific=self.alert_config_specific,
                language=self.language
            )
        )
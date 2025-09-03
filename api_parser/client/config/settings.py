import os
from dataclasses import dataclass

@dataclass
class Settings:
    TON_API_URL: str = os.getenv("TON_API_URL", "https://tonapi.io")
    TON_API_KEY: str = os.getenv("TON_API_KEY", "")
    REQUEST_INTERVAL: float = float(os.getenv("REQUEST_INTERVAL", 1.0))
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

settings = Settings()
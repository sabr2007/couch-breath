"""
Конфигурация бота — загрузка переменных окружения
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env из корня проекта
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Конфигурация приложения"""
    
    # --- Telegram ---
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    CURATOR_ID: int = int(os.getenv("CURATOR_ID", "0"))
    ADMIN_IDS: list[int] = [
        int(id_.strip()) 
        for id_ in os.getenv("ADMIN_IDS", "").split(",") 
        if id_.strip()
    ]
    
    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # --- OpenAI ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # --- Settings ---
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Almaty")
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "15"))
    MIN_ANSWER_LENGTH: int = int(os.getenv("MIN_ANSWER_LENGTH", "20"))
    RATE_LIMIT_PER_HOUR: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "7"))
    
    @classmethod
    def validate(cls) -> list[str]:
        """Проверка обязательных переменных"""
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN не задан")
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL не задан")
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY не задан")
        if not cls.CURATOR_ID:
            errors.append("CURATOR_ID не задан")
            
        return errors


# Синглтон конфигурации
config = Config()

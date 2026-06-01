"""
Конфигурация приложения Access Keeper Bot.
Загружает переменные окружения и предоставляет централизованный доступ к настройкам.
Соответствует требованиям ISO 27001 A.10.1.1 (криптографический контроль).
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from cryptography.fernet import Fernet

# Загрузка переменных окружения
load_dotenv()

# Базовая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Config:
    """Класс конфигурации с валидацией и безопасными значениями по умолчанию."""
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ALLOWED_TELEGRAM_USER_IDS: list[int] = [
        int(uid.strip()) 
        for uid in os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").split(",") 
        if uid.strip()
    ]
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_SECRET_PATH: Path = BASE_DIR / os.getenv(
        "GOOGLE_CLIENT_SECRET_PATH", "client_secret.json"
    )
    GOOGLE_TOKEN_PATH: Path = DATA_DIR / os.getenv(
        "GOOGLE_TOKEN_PATH", "token.json"
    )
    
    # Database Configuration
    DB_PATH: Path = DATA_DIR / os.getenv("DB_PATH", "access_keeper.db")
    
    # Default Settings
    DEFAULT_SPREADSHEET_ID: str | None = os.getenv("DEFAULT_SPREADSHEET_ID") or None
    DEFAULT_SHEET_NAME: str = os.getenv("DEFAULT_SHEET_NAME", "Временные доступы")
    DEFAULT_CALENDAR_ID: str = os.getenv("DEFAULT_CALENDAR_ID", "primary")
    
    # Timezone and Event Settings
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Almaty")
    DEFAULT_EVENT_HOUR: int = int(os.getenv("DEFAULT_EVENT_HOUR", "9"))
    DEFAULT_EVENT_MINUTE: int = int(os.getenv("DEFAULT_EVENT_MINUTE", "0"))
    DEFAULT_REMINDER_DAYS: list[int] = [
        int(d.strip()) 
        for d in os.getenv("DEFAULT_REMINDER_DAYS", "1,0").split(",") 
        if d.strip()
    ]
    DEFAULT_ACCESS_ACTION: str = os.getenv("DEFAULT_ACCESS_ACTION", "Забрать доступ")
    
    # Security Settings
    RATE_LIMIT_SECONDS: int = int(os.getenv("RATE_LIMIT_SECONDS", "3"))
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Path = DATA_DIR / os.getenv("LOG_FILE", "bot.log")
    
    # Google OAuth Scopes
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/calendar.events",
    ]
    
    @classmethod
    def validate(cls) -> list[str]:
        """
        Валидация критических настроек безопасности.
        Возвращает список ошибок конфигурации.
        Соответствует ISO 27001 A.6.1.2 (разделение обязанностей).
        """
        errors = []
        
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN не установлен в .env")
        
        if not cls.ALLOWED_TELEGRAM_USER_IDS:
            errors.append("ALLOWED_TELEGRAM_USER_IDS не установлен в .env")
        
        if not cls.GOOGLE_CLIENT_SECRET_PATH.exists():
            errors.append(
                f"Файл client_secret.json не найден по пути: {cls.GOOGLE_CLIENT_SECRET_PATH}"
            )
        
        if not cls.ENCRYPTION_KEY or len(cls.ENCRYPTION_KEY) < 32:
            errors.append(
                "ENCRYPTION_KEY должен быть установлен и содержать минимум 32 символа"
            )
        
        return errors
    
    @classmethod
    def get_fernet(cls) -> Fernet:
        """
        Получение объекта Fernet для шифрования чувствительных данных.
        Соответствует ISO 27001 A.10.1.1 (криптографический контроль).
        """
        if not cls.ENCRYPTION_KEY or len(cls.ENCRYPTION_KEY) < 32:
            raise ValueError("ENCRYPTION_KEY не настроен или слишком короткий")
        
        # Используем первые 32 символа ключа для Fernet
        key = cls.ENCRYPTION_KEY[:32].encode().ljust(32, b'=')
        # Для совместимости с Fernet используем base64 кодирование
        import base64
        safe_key = base64.urlsafe_b64encode(key[:32])
        return Fernet(safe_key)
    
    @classmethod
    def is_user_allowed(cls, telegram_user_id: int) -> bool:
        """Проверка доступа пользователя по ID."""
        return telegram_user_id in cls.ALLOWED_TELEGRAM_USER_IDS


# Глобальный экземпляр конфигурации
config = Config()

# Alias для совместимости
settings = config

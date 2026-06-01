"""Конфигурация приложения."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_TELEGRAM_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").split(",")
    if uid.strip()
]

# Google OAuth
GOOGLE_CLIENT_SECRET_PATH = os.getenv(
    "GOOGLE_CLIENT_SECRET_PATH", "client_secret.json"
)
GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "token.json")

# База данных
DB_PATH = os.getenv("DB_PATH", "data/access_keeper.db")

# Google Sheets по умолчанию
DEFAULT_SPREADSHEET_ID = os.getenv("DEFAULT_SPREADSHEET_ID", "")
DEFAULT_SHEET_NAME = os.getenv("DEFAULT_SHEET_NAME", "Временные доступы")
DEFAULT_CALENDAR_ID = os.getenv("DEFAULT_CALENDAR_ID", "primary")

# Время и таймзона
TIMEZONE = os.getenv("TIMEZONE", "Asia/Almaty")
DEFAULT_EVENT_HOUR = int(os.getenv("DEFAULT_EVENT_HOUR", "9"))
DEFAULT_EVENT_MINUTE = int(os.getenv("DEFAULT_EVENT_MINUTE", "0"))
DEFAULT_REMINDER_DAYS = [
    int(d.strip())
    for d in os.getenv("DEFAULT_REMINDER_DAYS", "1,0").split(",")
    if d.strip()
]
DEFAULT_ACCESS_ACTION = os.getenv("DEFAULT_ACCESS_ACTION", "Забрать доступ")

# Rate limiting
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "3"))

# Пути
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Создаём директорию data, если её нет
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Проверяем обязательные переменные
REQUIRED_VARS = ["TELEGRAM_BOT_TOKEN", "ALLOWED_TELEGRAM_USER_IDS"]
MISSING_VARS = [var for var in REQUIRED_VARS if not os.getenv(var)]

if MISSING_VARS:
    print(f"⚠️  Предупреждение: Не настроены переменные окружения: {MISSING_VARS}")
    print("   Проверьте файл .env")

# Google OAuth scopes
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar.events",
]

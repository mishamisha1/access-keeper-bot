"""Главный файл запуска бота."""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import TELEGRAM_BOT_TOKEN, DB_PATH
from app.logging_config import setup_logging
from app.db.database import Database
from app.bot.handlers import router
from app.google.auth import get_google_auth

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота."""
    logger.info("Запуск Access Keeper Bot...")
    
    # Инициализация базы данных
    db = Database(DB_PATH)
    logger.info("База данных инициализирована: %s", DB_PATH)
    
    # Проверяем авторизацию Google
    google_auth = get_google_auth()
    if not google_auth.is_authenticated():
        logger.warning("Google не авторизован. Запустите интерактивную авторизацию:")
        logger.warning("python -m app.google_auth_setup")
    else:
        logger.info("Google авторизован успешно")
    
    # Инициализация бота
    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    
    # Инициализация диспетчера
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрируем роутер с хендлерами, передавая db как dependency
    @dp.message()
    @dp.callback_query()
    async def inject_db(handler_data, state, bot):
        # Инъекция db в контекст
        pass
    
    dp.include_router(router)
    
    # Добавляем db в глобальный контекст через middleware
    from aiogram import BaseMiddleware
    from typing import Callable, Dict, Any, Awaitable
    
    class DatabaseMiddleware(BaseMiddleware):
        def __init__(self, db: Database):
            self.db = db
        
        async def __call__(
            self,
            handler: Callable[[Dict[str, Any]], Awaitable[Any]],
            event: types.TelegramObject,
            data: Dict[str, Any]
        ) -> Any:
            data["db"] = self.db
            return await handler(event, data)
    
    from aiogram.types import TelegramObject
    dp.message.middleware(DatabaseMiddleware(db))
    dp.callback_query.middleware(DatabaseMiddleware(db))
    
    try:
        # Запускаем polling
        logger.info("Бот запущен. Ожидание сообщений...")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.exception("Критическая ошибка: %s", e)
    finally:
        await bot.session.close()
        logger.info("Сессия бота закрыта")


if __name__ == "__main__":
    asyncio.run(main())

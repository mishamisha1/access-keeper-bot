#!/usr/bin/env python3
"""
Access Keeper Bot - Telegram бот для управления матрицами доступов.
Соответствует требованиям ISO 27001-27005.

Запуск:
    python -m app.main
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.config import config, settings
from app.logging_config import get_logger, logger
from app.db.database import db
from app.bot.keyboards import get_main_menu_keyboard
from app.bot.states import AccessStates
from app.parsers.text_parser import text_parser
from app.google.auth import google_auth
from app.services.access_service import access_service
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.rate_limit_middleware import RateLimitMiddleware
from app.security.privileged_access import PrivilegedAccessChecker
from app.security.audit_logger import AuditLogger

# Инициализация компонентов безопасности
privileged_checker = PrivilegedAccessChecker()
audit_logger = AuditLogger(log_dir=str(project_root / "data" / "audit_logs"))

# Инициализация бота
bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Регистрация middleware
auth_middleware = AuthMiddleware()
rate_limit_middleware = RateLimitMiddleware()

dp.message.middleware(auth_middleware)
dp.message.middleware(rate_limit_middleware)
dp.callback_query.middleware(auth_middleware)


# ==================== Middleware ====================

@dp.message()
async def check_access(message: Message):
    """Проверка доступа пользователя."""
    user_id = message.from_user.id
    
    if not config.is_user_allowed(user_id):
        await message.answer("❌ Доступ запрещён. Вы не авторизованы для использования этого бота.")
        logger.warning(f"Попытка доступа от неразрешенного пользователя: {user_id}")
        return
    
    # Регистрируем пользователя в БД
    db.upsert_user(user_id, message.from_user.username or "unknown")
    
    await dp.propagate_event(message=message)


# ==================== Commands ====================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start - приветствие."""
    user_id = message.from_user.id
    
    if not config.is_user_allowed(user_id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    welcome_text = """
👋 *Добро пожаловать в Access Keeper Bot!*

Я помогу вам управлять матрицами доступов, выдавать временные доступы и автоматизировать ревью.

*Возможности:*
📊 Создание матриц доступа (6 шаблонов)
➕ Быстрое добавление доступов из текста
📁 Импорт из Excel, CSV, DOCX, PDF
⏰ Автоматические напоминания об отзыве
🔴 Отзыв и продление доступов
📋 История всех изменений

*Пример использования:*
`/access Саксонов Михаил, доступ на 2 недели, основание: совместная работа`

Выберите действие в меню или используйте команды:
"""
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown",
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help - справка."""
    help_text = """
📖 *Справка по командам:*

*Основные команды:*
/start - Запустить бота
/help - Эта справка

*Управление доступами:*
/access <текст> - Быстро добавить доступ
/grant_access - Пошаговое добавление доступа
/revoke_access - Отозвать доступ
/extend_access - Продлить доступ

*Просмотр:*
/access_due - Истекающие доступы
/access_overdue - Просроченные доступы

*Таблицы:*
/new_matrix - Создать новую матрицу
/import_file - Импорт из файла
/bind_sheet - Привязать таблицу
/my_sheets - Мои таблицы

*Настройки:*
/settings - Настройки бота
/templates - Шаблоны матриц

*Примеры /access:*
`/access Саксонов Михаил, доступ на 2 недели, основание: работа с разработчиками`
`/access Иванов Иван, Jira read-only на 3 дня, причина: задача DEV-123`
`/access Петров Петр, Splunk admin на месяц, основание INC-12345`
"""
    
    await message.answer(help_text, parse_mode="Markdown")


@dp.message(Command("access"))
async def cmd_access(message: Message, state: FSMContext):
    """Команда /access - быстрое добавление доступа."""
    if not config.is_user_allowed(message.from_user.id):
        return
    
    text = message.text.replace("/access", "").strip()
    
    if not text:
        await message.answer(
            "⚠️ Укажите данные доступа.\n\n"
            "Пример:\n"
            "`/access Саксонов Михаил, доступ на 2 недели, основание: совместная работа`",
            parse_mode="Markdown",
        )
        return
    
    # Парсим текст
    parsed = text_parser.parse(text)
    
    # Сохраняем в состояние
    await state.update_data(parsed_data=parsed.to_dict())
    
    # Показываем preview
    preview_text = parsed.get_preview_text()
    
    if not parsed.is_valid:
        preview_text += "\n\n⚠️ Не хватает данных. Хотите дополнить?"
    
    from app.bot.keyboards import get_access_confirmation_keyboard
    
    await message.answer(
        preview_text,
        reply_markup=get_access_confirmation_keyboard(),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "access_confirm")
async def on_access_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение создания доступа с проверкой привилегий и аудитом."""
    data = await state.get_data()
    parsed_data = data.get("parsed_data", {})
    
    # Проверка привилегированного доступа
    role = parsed_data.get('role', '')
    is_temporary = parsed_data.get('is_temporary', True)
    justification = parsed_data.get('justification', '')
    
    is_valid, issues = privileged_checker.validate_access_request(
        role=role,
        is_temporary=is_temporary,
        justification=justification
    )
    
    if not is_valid:
        issues_text = "\n".join(f"• {issue}" for issue in issues)
        await callback.message.answer(
            f"⚠️ *Обнаружены проблемы безопасности:*\n\n{issues_text}\n\n"
            f"Исправьте данные и попробуйте снова.",
            parse_mode="Markdown"
        )
        return
    
    try:
        result = await access_service.create_access_from_parsed(
            telegram_user_id=callback.from_user.id,
            username=callback.from_user.username or "unknown",
            parsed_data=parsed_data,
        )
        
        # Аудит успешного создания доступа
        audit_logger.log_access_granted(
            user_id=callback.from_user.id,
            username=callback.from_user.username or "unknown",
            full_name=parsed_data.get('full_name', 'Не указано'),
            system=parsed_data.get('system', 'Не указано'),
            role=parsed_data.get('role', 'Не указано'),
            valid_until=parsed_data.get('valid_until', 'Не указано'),
            spreadsheet_id=result.get('spreadsheet_id', ''),
            row_number=result.get('row_number', 0),
            calendar_event_id=result.get('calendar_event_id')
        )
        
        success_text = f"""
✅ *Доступ успешно создан!*

📊 Таблица: {result.get('spreadsheet_url', 'Не доступно')}
📅 Событие календаря: {result.get('calendar_link', 'Не создано')}
📍 Строка: {result.get('row_number', '?')}
"""
        
        # Предупреждение о привилегированном доступе
        if privileged_checker.is_privileged_role(role):
            success_text += "\n⚠️ *ВНИМАНИЕ:* Привилегированный доступ требует обязательного ревью!"
        
        await callback.message.answer(success_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка создания доступа: {e}")
        await callback.message.answer(f"❌ Ошибка: {e}")
    
    await state.clear()


@dp.callback_query(F.data == "access_cancel")
async def on_access_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена создания доступа."""
    await callback.message.answer("❌ Создание доступа отменено.")
    await state.clear()


@dp.message(Command("new_matrix"))
async def cmd_new_matrix(message: Message):
    """Команда /new_matrix - создание новой матрицы."""
    from app.templates.matrix_templates import matrix_templates
    from app.bot.keyboards import get_matrix_template_keyboard
    
    templates = matrix_templates.list_templates()
    
    await message.answer(
        "📊 Выберите шаблон матрицы:",
        reply_markup=get_matrix_template_keyboard(templates),
    )


@dp.message(Command("my_sheets"))
async def cmd_my_sheets(message: Message):
    """Команда /my_sheets - список сохраненных таблиц."""
    sheets = db.get_saved_sheets(message.from_user.id)
    
    if not sheets:
        await message.answer(
            "📭 У вас пока нет сохраненных таблиц.\n\n"
            "Используйте /bind_sheet чтобы привязать таблицу или /new_matrix чтобы создать новую."
        )
        return
    
    text = "📋 *Ваши таблицы:*\n\n"
    for sheet in sheets:
        text += f"• {sheet.title}\n  Вкладка: {sheet.default_sheet_name}\n  URL: {sheet.spreadsheet_url}\n\n"
    
    from app.bot.keyboards import get_saved_sheets_keyboard
    await message.answer(text, reply_markup=get_saved_sheets_keyboard(sheets), parse_mode="Markdown")


@dp.message(Command("settings"))
async def cmd_settings(message: Message):
    """Команда /settings - настройки."""
    from app.bot.keyboards import get_settings_keyboard
    
    settings = db.get_settings(message.from_user.id)
    
    text = "⚙️ *Настройки:*\n\n"
    if settings:
        text += f"Часовой пояс: {settings.timezone}\n"
        text += f"Время событий: {settings.event_hour}:{settings.event_minute:02d}\n"
        text += f"Напоминания: {settings.reminder_days} дн.\n"
        if settings.default_spreadsheet_id:
            text += f"Таблица по умолчанию: {settings.default_sheet_name}\n"
    else:
        text += "Настройки не заданы. Используются значения по умолчанию."
    
    await message.answer(text, reply_markup=get_settings_keyboard(), parse_mode="Markdown")


# ==================== Обработка текстовых сообщений ====================

@dp.message(F.text)
async def handle_text_message(message: Message, state: FSMContext):
    """Обработка обычных текстовых сообщений."""
    if not config.is_user_allowed(message.from_user.id):
        return
    
    # Если это не команда и не состояние FSM, пробуем распарсить как запрос доступа
    current_state = await state.get_state()
    
    if current_state is None and not message.text.startswith('/'):
        # Пробуем распарсить как запрос доступа
        parsed = text_parser.parse(message.text)
        
        if parsed.confidence_score >= 50 and parsed.full_name:
            await state.update_data(parsed_data=parsed.to_dict())
            
            preview_text = parsed.get_preview_text()
            preview_text += "\n\n🤔 Я распознал это как запрос на доступ. Создать?"
            
            from app.bot.keyboards import get_access_confirmation_keyboard
            
            await message.answer(
                preview_text,
                reply_markup=get_access_confirmation_keyboard(),
                parse_mode="Markdown",
            )
            return
    
    await message.answer(
        "Я не понял команду. Используйте /help для списка команд или напишите запрос на доступ в свободной форме."
    )


# ==================== Запуск ====================

async def main():
    """Основная функция запуска."""
    # Валидация конфигурации
    errors = config.validate()
    if errors:
        logger.error("Ошибки конфигурации:")
        for error in errors:
            logger.error(f"  - {error}")
        print("\n".join(errors))
        sys.exit(1)
    
    # Проверка авторизации Google
    if not google_auth.ensure_authenticated():
        logger.warning("Требуется авторизация в Google. Запустите: python -m app.google_auth_setup")
    
    logger.info("Запуск бота...")
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

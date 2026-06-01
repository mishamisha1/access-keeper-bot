"""Обработчики команд Telegram бота."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Router, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.config import ALLOWED_TELEGRAM_USER_IDS, RATE_LIMIT_SECONDS
from app.db.database import Database
from app.db.models import AccessRecord, ParsedAccessRequest
from app.parsers.text_parser import TextParser
from app.services.access_service import AccessService
from app.services.date_service import DateService
from app.google.auth import get_google_auth, check_google_auth
from app.bot.keyboards import (
    get_main_keyboard,
    get_confirm_keyboard,
    get_cancel_keyboard,
    get_template_keyboard,
)
from app.bot.states import AccessStates

logger = logging.getLogger(__name__)

router = Router()


def is_user_allowed(user_id: int) -> bool:
    """Проверяет, разрешён ли пользователь."""
    return user_id in ALLOWED_TELEGRAM_USER_IDS


@router.message(CommandStart())
async def cmd_start(message: Message, db: Database):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    
    if not is_user_allowed(user_id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    # Добавляем пользователя в БД
    db.add_user(user_id, message.from_user.username)
    
    text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я **Access Keeper Bot** — твой помощник для управления матрицами доступа.\n\n"
        "📋 **Что я умею:**\n"
        "• Создавать Google Sheets таблицы под матрицы доступа\n"
        "• Добавлять временные доступы из текста\n"
        "• Импортировать данные из файлов (Excel, CSV, DOCX, PDF)\n"
        "• Создавать события в Google Calendar с напоминаниями\n"
        "• Отслеживать истекающие и просроченные доступы\n"
        "• Продлевать и отзывать доступы\n\n"
        "🚀 **Начни с команды:**\n"
        "`/access Саксонов Михаил, доступ на 2 недели, основание: совместная работа`\n\n"
        "Или используй кнопки ниже 👇"
    )
    
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    user_id = message.from_user.id
    
    if not is_user_allowed(user_id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    text = (
        "📖 **Список команд:**\n\n"
        "/start - Запустить бота\n"
        "/help - Показать эту справку\n"
        "/access <текст> - Быстро добавить временный доступ\n"
        "/new_matrix - Создать новую матрицу доступа\n"
        "/grant_access - Пошаговое добавление доступа\n"
        "/revoke_access - Отозвать доступ\n"
        "/extend_access - Продлить доступ\n"
        "/access_due - Показать истекающие доступы\n"
        "/access_overdue - Показать просроченные доступы\n"
        "/import_file - Импорт из файла\n"
        "/bind_sheet - Привязать таблицу\n"
        "/my_sheets - Мои таблицы\n"
        "/settings - Настройки\n\n"
        "💡 **Примеры использования /access:**\n"
        "• `/access Саксонов Михаил, доступ на 2 недели, основание: совместная работа`\n"
        "• `/access Иванов Иван, Jira read-only на 3 дня, причина: задача DEV-123`\n"
        "• `/access Петров Петр, Splunk admin на месяц, основание INC-12345`\n"
        "• `/access Сидорова Анна, доступ до пятницы, причина: аудит логов`"
    )
    
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("access"))
async def cmd_access(message: Message, db: Database, state: FSMContext):
    """Обработчик команды /access."""
    user_id = message.from_user.id
    
    if not is_user_allowed(user_id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    # Проверяем авторизацию Google
    if not check_google_auth():
        await message.answer(
            "⚠️ Не выполнена авторизация в Google.\n"
            "Запустите бота локально для авторизации или проверьте token.json"
        )
        return
    
    text = message.text.replace("/access", "").strip()
    
    if not text:
        await message.answer(
            "❌ Укажите текст запроса.\n"
            "Пример: `/access Саксонов Михаил, доступ на 2 недели, основание: совместная работа`"
        )
        return
    
    # Парсим текст
    parser = TextParser()
    parsed = parser.parse(text)
    
    # Проверяем обязательные поля
    missing = []
    if not parsed.full_name:
        missing.append("ФИО")
    if not parsed.valid_until:
        missing.append("срок доступа")
    
    if missing:
        await message.answer(
            f"❌ Не удалось распознать: {', '.join(missing)}\n\n"
            "Пожалуйста, уточните запрос.\n"
            "Пример: `Иванов Иван, доступ на 2 недели, основание: тестирование`"
        )
        return
    
    # Сохраняем данные для подтверждения
    await state.update_data(parsed_request=parsed)
    
    # Формируем preview
    preview_text = (
        "🔍 **Я распознал:**\n\n"
        f"• Пользователь: `{parsed.full_name}`\n"
        f"• Система: `{parsed.system or 'Не указано'}`\n"
        f"• Роль: `{parsed.role or 'Не указано'}`\n"
        f"• Срок доступа: `{parsed.duration_days or 'до ' + parsed.valid_until.strftime('%Y-%m-%d')}`\n"
        f"• Дата выдачи: `{parsed.granted_at.strftime('%Y-%m-%d')}`\n"
        f"• Дата окончания: `{parsed.valid_until.strftime('%Y-%m-%d')}`\n"
        f"• Время события: `09:00`\n"
        f"• Основание: `{parsed.reason or 'Не указано'}`\n"
        f"• Действие: `Забрать доступ`\n\n"
        "Создать запись в Google Sheets и событие в Google Calendar?"
    )
    
    await message.answer(
        preview_text,
        parse_mode="Markdown",
        reply_markup=get_confirm_keyboard("access")
    )
    
    await state.set_state(AccessStates.waiting_for_confirmation)


@router.callback_query(F.data == "confirm_access")
async def confirm_access(callback: CallbackQuery, db: Database, state: FSMContext):
    """Подтверждение создания доступа."""
    user_id = callback.from_user.id
    
    if not is_user_allowed(user_id):
        await callback.answer("❌ Доступ запрещён.", show_alert=True)
        return
    
    data = await state.get_data()
    parsed = data.get("parsed_request")
    
    if not parsed:
        await callback.answer("❌ Данные не найдены.", show_alert=True)
        return
    
    # Создаём объект записи
    record = AccessRecord(
        full_name=parsed.full_name,
        login=parsed.login,
        email=parsed.email,
        system=parsed.system,
        role=parsed.role,
        access_level=parsed.access_level,
        reason=parsed.reason,
        ticket_number=parsed.ticket_number,
        granted_at=parsed.granted_at,
        valid_until=parsed.valid_until,
        status="Временный",
        added_by=f"@{callback.from_user.username}" if callback.from_user.username else str(user_id),
        created_at=datetime.now(),
    )
    
    # Создаём запись через сервис
    access_service = AccessService(db)
    settings = db.get_settings(user_id)
    
    success, msg, row_number, event_id = access_service.create_access_record(
        telegram_user_id=user_id,
        record=record,
        spreadsheet_id=settings.get("default_spreadsheet_id"),
        sheet_name=settings.get("default_sheet_name"),
    )
    
    await callback.message.answer(msg)
    await state.clear()


@router.callback_query(F.data == "cancel_access")
@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена действия."""
    await callback.answer("❌ Отменено", show_alert=True)
    await state.clear()


@router.message(Command("new_matrix"))
async def cmd_new_matrix(message: Message):
    """Обработчик команды /new_matrix."""
    user_id = message.from_user.id
    
    if not is_user_allowed(user_id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    await message.answer(
        "📋 Выберите шаблон матрицы:",
        reply_markup=get_template_keyboard()
    )


@router.message(Command("access_due"))
async def cmd_access_due(message: Message, db: Database):
    """Показать истекающие доступы."""
    user_id = message.from_user.id
    
    if not is_user_allowed(user_id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    settings = db.get_settings(user_id)
    spreadsheet_id = settings.get("default_spreadsheet_id")
    sheet_name = settings.get("default_sheet_name", "Временные доступы")
    
    if not spreadsheet_id:
        await message.answer(
            "❌ Таблица не привязана. Используйте /bind_sheet"
        )
        return
    
    access_service = AccessService(db)
    due_accesses = access_service.get_due_accesses(spreadsheet_id, sheet_name, days_ahead=7)
    
    if not due_accesses:
        await message.answer("✅ Нет истекающих доступов на ближайшие 7 дней.")
        return
    
    text = f"⏰ **Истекают в ближайшие 7 дней:**\n\n"
    for access in due_accesses[:10]:  # Показываем максимум 10
        days_left = (access["valid_until"] - datetime.now()).days
        text += (
            f"• `{access['full_name']}` — {access['system']}\n"
            f"  Осталось дней: `{days_left}`\n"
            f"  До: `{access['valid_until'].strftime('%Y-%m-%d')}`\n\n"
        )
    
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("access_overdue"))
async def cmd_access_overdue(message: Message, db: Database):
    """Показать просроченные доступы."""
    user_id = message.from_user.id
    
    if not is_user_allowed(user_id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    settings = db.get_settings(user_id)
    spreadsheet_id = settings.get("default_spreadsheet_id")
    sheet_name = settings.get("default_sheet_name", "Временные доступы")
    
    if not spreadsheet_id:
        await message.answer(
            "❌ Таблица не привязана. Используйте /bind_sheet"
        )
        return
    
    access_service = AccessService(db)
    overdue_accesses = access_service.get_overdue_accesses(spreadsheet_id, sheet_name)
    
    if not overdue_accesses:
        await message.answer("✅ Нет просроченных доступов.")
        return
    
    text = f"⚠️ **Просроченные доступы:**\n\n"
    for access in overdue_accesses[:10]:  # Показываем максимум 10
        days_overdue = (datetime.now() - access["valid_until"]).days
        text += (
            f"• `{access['full_name']}` — {access['system']}\n"
            f"  Просрочено дней: `{days_overdue}`\n"
            f"  Было до: `{access['valid_until'].strftime('%Y-%m-%d')}`\n\n"
        )
    
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("bind_sheet"))
async def cmd_bind_sheet(message: Message, db: Database):
    """Привязать таблицу."""
    user_id = message.from_user.id
    
    if not is_user_allowed(user_id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    text = (
        "📊 **Привязка таблицы**\n\n"
        "Отправьте ссылку на Google Sheets таблицу.\n"
        "Пример: `https://docs.google.com/spreadsheets/d/1ABC123...`\n\n"
        "Или нажмите /my_sheets чтобы выбрать из сохранённых."
    )
    
    await message.answer(text)


@router.message(Command("my_sheets"))
async def cmd_my_sheets(message: Message, db: Database):
    """Показать сохранённые таблицы."""
    user_id = message.from_user.id
    
    if not is_user_allowed(user_id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    sheets = db.get_saved_sheets(user_id)
    
    if not sheets:
        await message.answer("📭 У вас пока нет сохранённых таблиц.")
        return
    
    text = "📑 **Ваши таблицы:**\n\n"
    for sheet in sheets:
        text += f"• `{sheet['title']}`\n"
        text += f"  ID: `{sheet['spreadsheet_id']}`\n"
        text += f"  Вкладка: `{sheet['default_sheet_name'] or 'Не указана'}`\n\n"
    
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("settings"))
async def cmd_settings(message: Message, db: Database):
    """Настройки бота."""
    user_id = message.from_user.id
    
    if not is_user_allowed(user_id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    settings = db.get_settings(user_id)
    
    text = (
        "⚙️ **Настройки:**\n\n"
        f"• Таблица по умолчанию: `{settings.get('default_spreadsheet_id', 'Не указана')}`\n"
        f"• Вкладка по умолчанию: `{settings.get('default_sheet_name', 'Временные доступы')}`\n"
        f"• Календарь: `{settings.get('default_calendar_id', 'primary')}`\n"
        f"• Таймзона: `{settings.get('timezone', 'Asia/Almaty')}`\n"
        f"• Время события: `{settings.get('event_hour', 9):02d}:{settings.get('event_minute', 0):02d}`\n"
        f"• Напоминания: за {settings.get('reminder_days', '1,0')} дн."
    )
    
    await message.answer(text, parse_mode="Markdown")
